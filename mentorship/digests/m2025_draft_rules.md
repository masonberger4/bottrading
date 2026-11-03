# 2025 Lecture Series: DRAFT rules for Mase's review

**Status: DRAFT. Nothing here is wired into the engine and nothing has been backtested.**
Built 2026-11-03 from the per-lecture notes in `mentorship/notes_2025/` (captions only; frames are on the laptop, so "this level / that candle" is resolved from context and prices from captions can be garbled).

## How to read this
- Source tier: **2023 Mentorship wins on every conflict.** The 2025 series sits below it, with 2024 Mentorship and TE/Charter. ICT frames the series as "if I were a new student of my 2024 Mentorship" (L83, L82): the **experienced-trader version stays the default** and beginner rules become switches only.
- Tags: **[new]** not found in the rulebook (not exhaustively grepped; check before wiring), **[refines]** adds detail to an existing idea, **[conflict: X]** differs from 2023 or an owner directive (2023 stays in force), **[conflict check]** maybe differs. All switches are default OFF.
- Lecture refs = `notes_2025/NN_*.md`. Times New York local.

## Coverage (lower-usage, core-only option chosen by Mase 2026-11-03)
- **Read in full and noted (28 lectures):** 01 (live sample), 83, 82, 80, 78, 77, 76, 75, 74, 73, 72, 70, 66, 65, 64, 62, 58, 57, 51, 34, 32, 31, 29, 27, 26, 23, 22, 21. (58, 62, 64, 70 were re-read in full in part 6; the originals were accurate, addenda added.)
- **Pending (not read, ~38 lectures):** daily/live NQ and forex reviews 02-20, 24, 28, 30, 33, 36-50, 52-56, 60, 61, 63, 68. These are applications of the same rules; 02 and 04 (24-36k-word live streams on market maker models and 20-day lookback grading) are probably worth a later read.
- **Missing captions:** 25, 35, 46, 59, 67, 69, 71, 79, 81.
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

## Part E. Questions for Mase (list only; not asked now, ask in the full review)
1. 2025 FPFVG window 09:31-10:00 vs 09:30 candle itself (ICT's own rule for Caleb vs for experienced): which?
2. Do the Venom / midnight opening range / FPFVG blocks replace or sit under 2023 ranking?
3. ORG size buckets: adopt 20/75/120 as filters?
4. Is the 15-handle net minimum also the owner's 5-handle room rule?
5. Reclaimed vs inversion FVG: separate switches or merged?
6. Priority of 2025 lunch macro (first prominent low after 10:00) vs 2023 lunch/11:30 macros.
7. Pending lectures: read the 24-36k-word live streams (02, 04) and a sample of the daily reviews, or stop here?
