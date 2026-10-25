# Rulebook gaps: levels, liquidity and targets

Topic `levels_liquidity_targets`. Every item below is a verified gap between ICT's captions and `mentorship_rules.md`. When the checker gave a corrected rule, that corrected rule is the one written here; when it gave none, the claim's full rule is used. "[our interpretation]" marks thresholds or readings that ICT does not state.

Conventions:
- Times are New York. Params times are minutes from midnight (480 = 08:00, 570 = 09:30, 600 = 10:00, 630 = 10:30, 720 = 12:00, 810 = 13:30, 900 = 15:00, 960 = 16:00).
- New Params switches default off (rule_coverage.md section 3). Each work package adds its fields in its own commented block at the end of `Params`.
- Work packages are the names in `rule_coverage.md` section 3. Code anchors used below (current line numbers in `mentorship/strategy.py` unless a file is named): `DayCtx.__init__` ~1120 (pools `sess`, `pw`, `pm_`, `am_hl`, `pre_at`, `org`, `or_hl`), `_targets` ~1318, `_extra_levels` ~1516, `_lv_target_pools` ~1612, `_lv_target_arrays` ~1637, `_org_state` ~1747, `_org_break` ~1776, `_nwog_half` ~1789, `_wick_ces` ~1808, `_draw_prefs` ~1820, `day_context` ~1902, `mark_levels` ~2217, `run_day` ~2490 (management loop ~786-860 of the package map, now further down), `_lock_step` ~3028, `_scan_core` ~3308, `_lv_finish_targets` ~3641, `_finish_order` ~3949; `htf.py` `_arrays` ~66, `table` ~95, `opening_gaps` ~366, `gaps_for_day` ~395; `levels.py` detectors; `sb_model.py` `run_sb` ~31, `_arm` ~213; `setups.py` `more_targets` ~1003, `draw_prefs` ~1022.
- `_targets` returns `(level, kind)` with kinds "pool", "pool_eq" and "array". New level kinds named below (e.g. "array_ce", "proj") are carried in `pos["level_kinds"]` (built shared piece) so management_exits can treat them differently.
- New tests go in `tests/test_levels_liquidity.py` unless a package's own test file fits better (`tests/test_levels_detectors.py`, `tests/test_setups_models.py`).
- Items scoped `fx_only`, `bonds_only` or `needs_unavailable_data` get the rulebook fix only, with no build spec. True NDOG (17:00-18:00 reopen), the Friday 16:59 print for the Monday NWOG variant, COT and bond futures count as unavailable here.
- "Already in rule_coverage" means the item's switch is already specified there with the same content. Where only part of an item is covered, the build spec covers only the new part and names the existing switch.

Summary: 180 items, 149 new build specs. Items without a build spec:
- 17 fx_only (incl. LLT3-rounding-step-direction, whose index side is the built L17 `round_step_pts`)
- 2 bonds_only
- 5 that need data we do not have (L5-monday-variant-1659, L6-ndog-lifetime-16h, L6-one-tick-ndog, L6-ndog-ce-premium-filter, LLT3-cot-nodule-levels)
- 5 already listed in rule_coverage with the same content: L12-sd-closes-not-wicks (Ep06.4 `sd_close_hit` / `sd_close_window`), X1-old-daily-close (Ep07.1 `close_draw`), X1-opposing-breaker-target (A22 `matrix_targets`, breakers as targets), X2-body-based-pool-levels (A17 `pool_body_edge`, the body-edge pool), L14-conditional-draw-upper-taken (L14e `cond_draw` with its spent flag; only the rulebook wording is wrong)
- 2 text-only: L3-054-citation (source correction) and new-no-long-term-top-picking (the bot trades intraday swings only; nothing to switch)

---

### 1. A2-which-old-high
- **rule_id / kind:** A2 / L1, missing_rule. Scope: index. judgment = false.
- **Rule:** Let H_today = the highest high since today's open. On the higher-timeframe chart in use (daily/HTF in 002), walk back through earlier swing highs and take the first one above H_today. That is the active buy-side pool: the sweep level for shorts and the target for longs. Mirror for sell-side below today's low.
- **Sources:** 002_GHaD0mebgMU ~00:00:34.
- **Quote:** "this is the first one you go to that would be higher than this one"
- **Conflicts:** none.
- **Rulebook fix:** A2: add "Active buy-side pool = the first earlier HTF swing high above today's high so far (walk back newest to oldest); mirror for sell-side (002 ~0:34)."
- **BUILD SPEC (levels_detectors):**
  - New helper `levels.first_old_beyond(highs: list[Pivot], h_today: float) -> float | None`: walk daily pivots (`htf` daily frame, n=1) newest to oldest, return the first price > h_today.
  - In `DayCtx.__init__`, build `self.old_hi_lo` from the daily history (`hist`, completed days only). Recompute per bar in `_targets` from `sd.h[ctx.start:i+1].max()` (no look-ahead).
  - Add it as a "pool" with `created = ctx.start` in `_targets` and as a sweep pool in `mark_levels` (key `old_hi` / `old_lo`).
  - Params: `active_old_pool: bool = False`.
  - Test: `test_first_old_high_beyond_today`. Daily pivots 4100, 4080, 4060 (newest last); today's high 4070 gives 4080; today's high 4085 gives 4100.

### 2. A2-round-number-pool
- **rule_id / kind:** A2 / L3 / L17, missing_rule. Scope: index. judgment = true.
- **Rule:** Optional confluence tag: a round 00 ES handle (e.g. 3900) above price acts as buy-side and below price as sell-side. A sweep = trading through it. Use it only as confluence for the sweep step alongside an old high/low, never on its own.
- **Sources:** 002_GHaD0mebgMU ~00:02:37.
- **Quote:** "the buy side is nice round number 3 900"
- **Conflicts:** L17 (no rounding in 2023 index work) is a different topic (rounding entries/targets), not pools.
- **[our interpretation]:** "near an old high" = within 1 ES pt.
- **Rulebook fix:** A2: "Round 00 handles count as confluence for a sweep when an old high/low sits at them (002 ~2:37); never a standalone pool."
- **BUILD SPEC (levels_detectors):**
  - Already in code: `round_pools=True` (owner #13) adds untaken 00/50 handles as standalone pools via `_round_levels` in `_targets`. New is the confluence-only mode.
  - Add `round_pool_mode: str = "pool"` ("pool" = current behaviour, "confluence" = a round handle is kept only if an old high/low or rel-eq pool lies within `round_conf_pts` of it, and then tags the sweep `lv_tags["round_conf"]`, "tag_only" = never a pool, tag only).
  - Where: `_targets` round-pool line and the round-pool branch of `mark_levels`.
  - Params: `round_pool_mode: str = "pool"`, `round_conf_pts: float = 1.0`.
  - Test: `test_round_pool_confluence_mode`. Handle 3900 with an old high at 3900.50 is kept and tagged; handle 3950 with nothing within 1 pt is dropped in "confluence" mode.

### 3. A2-quick-run-through
- **rule_id / kind:** A2, missing_condition. Scope: general. judgment = true.
- **Rule:** A level (including a gap remainder) is reached with 1 tick through. For continuation toward the next draw, price should run through it quickly with expansion and speed, not merely tap it. Bot proxy (an assumption, not ICT's): require more than 1 tick beyond within N bars, with N tested at 1-3. A tap-and-stall is a weaker signal, so treat the level as a reaction point.
- **Sources:** 033_KXx07qzW5u0 ~00:51:37 (and ~1:09:02).
- **Quote:** "run through that pretty you know quickly not just tap it"
- **Conflicts:** none.
- **[our interpretation]:** the "beyond by more than 1 tick within N bars" proxy and N.
- **Rulebook fix:** A2: "1 tick through books the level; continuation wants a fast run through it (033 ~51:37). A tap and stall = reaction point."
- **BUILD SPEC (management_exits):**
  - In the `run_day` ladder loop, when a rung is first touched (1 tick through, `_thru`), start a counter. If within `run_through_bars` bars price has not exceeded the rung by `run_through_ticks` ticks, mark the rung "stalled": take the scheduled partial and set `pos["stall_at"] = rung`. A later body close back through the rung against the trade exits the rest.
  - Params: `run_through_bars: int = 0` (0 = off; test 1, 2, 3), `run_through_ticks: float = 2.0`.
  - Test: `test_tap_and_stall_rung`. Long, rung 4100: bars 4100.25 then 4100.00, 4099.75 -> stalled, partial, exit on close 4099.50; bars 4100.25 then 4101.50 -> continuation, no stall.

### 4. A3-reh-under-older-high
- **rule_id / kind:** A3, missing_rule. Scope: general. judgment = true.
- **Rule:** If REH (cluster high R1) sits within ~2 ES pts below an older swing high R2, treat both as one buy-side pool. Target = just beyond R2 (R2 + 0.75 pt per X2), not R1. Mirror for REL above an older lower low.
- **Sources:** 021_DVxC7UAHzwk ~00:40:41 (and ~10:19-10:39).
- **Quote:** "if it's going to go to 4089.75 it's going to rip to 4092"
- **Conflicts:** none.
- **[our interpretation]:** the 2 pt merge distance.
- **Rulebook fix:** A3: "REH within ~2 pts under an older higher high = one pool; target beyond the higher high (021 ~40:41)."
- **BUILD SPEC (targets_partials):**
  - In `_targets`, after building `pools`: for each "pool_eq" level v, if another pool w satisfies 0 < w - v <= `reh_merge_pts * es_pt`, drop v and keep w with kind "pool_eq" (exit offset via `_exit_px` stays X2's pool buffer).
  - Same merge in `_eq_levels` consumers for the sweep side (`mark_levels`): sweeping v alone does not book the merged pool.
  - Params: `reh_merge_pts: float = 0.0` (0 = off; test 2.0, 3.0).
  - Test: `test_reh_merged_with_older_high`. REH 4089.75, old high 4091.25: ladder has 4091.25 (kind pool_eq) and not 4089.75.

### 5. A3-engineered-liquidity
- **rule_id / kind:** A3, missing_rule. Scope: general. judgment = true.
- **Rule:** Engineered buy-side: old swing high H1, then a later lower high H2 that falls short of H1, and price drops away from H2. Buy stops (from the new shorts) rest above H2/H1, so the pool is above H1. Rank it higher with more time between H1 and H2 and when an FVG sits above H1. Mirror for sell-side.
- **Sources:** 035_kFIOp8Tprdc ~00:49:54 (EURUSD example; general concept).
- **Quote:** "falls short of it drops down and Traders do what they go short"
- **Conflicts:** none.
- **[our interpretation]:** "falls short" = H2 within `eng_short_pts` below H1; "drops away" = a later pivot low below H2's leg low; ranking weights.
- **Rulebook fix:** A3: add "Engineered liquidity: a lower high that falls short of an older high builds buy stops above both; rank by time between them and an FVG above (035 ~49:54)."
- **BUILD SPEC (levels_detectors):**
  - New `levels.engineered_pools(highs, lows, i, short_pts) -> list[(price, score)]`: pairs of pivot highs H1 > H2 with H1 - H2 <= short_pts, H2 after H1, and a pivot low after H2 below the low between H1 and H2. Price = H1. Score = bars between H1 and H2 (+1 if an unfilled opposing FVG starts within 1 pt above H1).
  - Run on 15m/1h pivots (`tf_pivots`) and daily pivots. Add as "pool" in `_lv_target_pools` with tag `engineered`; with `eq_pref="rank"`, rank them like rel-eq pools.
  - Params: `engineered_pools: bool = False`, `eng_short_pts: float = 3.0`.
  - Test: `test_engineered_pool_detect`. Highs 4100 (bar 10), 4098 (bar 40), low 4090 (bar 50) -> pool 4100, score 30.

### 6. A5-premium-half-daily-fvg
- **rule_id / kind:** A5, missing_rule. Scope: general. judgment = false.
- **Rule:** When bullish and retracing into a large daily BISI, continuation longs should come from reactions at or above its CE. Intraday imbalances in the lower half should remain open. If price fills them or closes below the CE, downgrade the setup (expect chop or consolidation) and wait for more information rather than take the continuation long. Mirror for a daily SIBI.
- **Sources:** 012_HkiPAi1Mdu8 ~00:18:02.
- **Quote:** "I want to see the majority of the reactions in the upper portion"
- **Conflicts:** none.
- **Rulebook fix:** A5: "Inside a large daily BISI, continuation longs come from the upper half; a close below CE = downgrade/wait (012 ~18:02)."
- **BUILD SPEC (setups_models; bias gate):**
  - Daily FVGs are in `htf.table` arrays ("D"). In `_scan_core` before arming a long: if the sweep low lies inside an unfilled daily BISI whose height >= `dfvg_large_pts`, require sweep low >= CE - 1 tick. If any 15m/1h body has closed below that CE today, tag `dfvg_lower_half` and, with mode "skip", do not arm the long until a later session.
  - Params: `dfvg_half: str = "off"` ("tag" / "skip"), `dfvg_large_pts: float = 15.0` [our interpretation of "large"].
  - Test: `test_daily_bisi_upper_half_gate`. Daily BISI 4000-4040 (CE 4020): sweep low 4025 arms; sweep low 4012 is skipped in "skip" mode.

### 7. A6-measuring-gap-anchor
- **rule_id / kind:** A6, wrong. Scope: general. judgment = true.
- **Rule:** Measuring gap = an FVG that forms near the 50% of the (implied) dealing range and leaves part of itself unfilled (bodies never fully close it). Bearish: fib 1 = the swing high where the energetic leg began, 0 = the SIBI low (candle-3 high). Target -1 SD = gapLow - (swingHigh - gapLow) (062: -1 SD = 4269.25 = day low). Bullish mirror: 1 = root low of the energetic run (ignore earlier lows that are not part of the run), 0 = BISI high (candle-3 low), target = gapHigh + (gapHigh - rootLow). The -1 SD must line up with an old liquidity pool (062). 061 can also be read as duplicating the range from the gap's other edge, so test both anchors.
- **Sources:** 061_wWvXWmC_gqU ~01:22:40; 062_sfRO5LrTgTA ~00:44:32.
- **Quote:** "project it down to the low of the Gap if we're bearish"
- **Conflicts:** A6 (mentorship_rules.md line 91) says near edge; both sources use the far edge (from the swing). 061 alternative reading: duplicate the range from the gap's other edge.
- **[our interpretation]:** "near the 50%" tolerance; the root-of-run choice (the leg's origin pivot since the last opposite displacement).
- **Rulebook fix:** A6: replace "project swing extreme -> near edge of the gap" with "swing extreme (root of the energetic leg) -> the gap's FAR edge from the swing (bearish: SIBI low; bullish: BISI high); -1 SD must meet an old pool (062 ~44:32; 061 ~1:22:40)."
- **BUILD SPEC (targets_partials):**
  - Rule_coverage lists A6 `measuring_gap` (near-edge projection) and Ep03.5 `measuring_anchor` near/ce. Change: add "far" (the default when `measuring_gap` is on) and "dup" (061 alt reading: target = gapLow + (gapHigh - rootLow), mirrored for bearish) to `measuring_anchor`; keep "near" as the old reading.
  - Qualify the gap: its CE within `measuring_mid_frac` of the leg's 50% and unfilled by bodies at bar i.
  - Keep the projected level only if a pool lies within `measuring_pool_pts` (kind "proj"); else drop it.
  - Params: `measuring_anchor: str = "far"` ("far" / "near" / "ce" / "dup"), `measuring_mid_frac: float = 0.15`, `measuring_pool_pts: float = 1.0`.
  - Test: `test_measuring_gap_far_edge`. Swing high 4305.25, SIBI low 4287.00 -> target 4268.75; with an old low at 4269.25 the level is kept.

### 8. A10-vi-target-ladder
- **rule_id / kind:** L9 / A9 / A10 / L3, missing_rule. Scope: general. judgment = false.
- **Rule:** Compute VIs on daily and weekly bars (A9 logic on HTF bars) and keep high, low and CE = (high+low)/2. For an HTF VI on the path to the draw: T1 = near edge (enough for the draw), T2 = CE, final = far edge or the next objective beyond. If the wicks inside the body gap leave an unprinted interval (a liquidity void, A10), that void is the preferred objective inside the VI (061). Use the CE only when the VI is not part of an order block; otherwise use the OB levels (045). Once traded, keep both VI edges as support/resistance levels (076). Optional, test only: after the far edge trades, a move back to the opposite edge (077, one FX example).
- **Sources:** 045_DNi9S3_NA44 ~02:47:00; 061_wWvXWmC_gqU ~01:55:50; 076_cgsltOB736E ~00:03:29; 077_OnFifO44Kzo ~00:04:08.
- **Quote:** "have that in your chart and use them as potential support resistance"
- **Conflicts:** none.
- **Rulebook fix:** L9: add an HTF VI ladder (near edge, CE unless part of an OB, far edge; void portion preferred; edges kept as S/R after trading).
- **BUILD SPEC (targets_partials):**
  - Built: `vi_arrays` puts daily/weekly VIs in `htf._arrays`; Ep04.12 `daily_vi_targets` is listed. New parts:
    - Void portion: in `htf._arrays` with `vi=True`, also store `void = (max(high[i-1], close/open edge), min(low[i], ...))` when the wicks do not overlap (non-empty interval); add its midpoint as kind "array" when present.
    - OB exception: if the VI's c1 or c2 is the last opposite candle before the displacement (`levels.order_block` on that bar), replace the CE level with the OB open and MT.
    - S/R after trade: `vi_keep_traded` keeps edges of a traded VI as "array" levels for `vi_keep_days`.
    - `vi_return_tag`: tag only, far edge traded then opposite edge within the week.
  - Params: `vi_void_level: bool = False`, `vi_ob_levels: bool = False`, `vi_keep_traded: bool = False`, `vi_keep_days: int = 20`.
  - Test: `test_htf_vi_void_and_ob`. Daily VI 4000-4004 with wicks 4001 / 4003 gives void midpoint 4002; with c1 an OB the CE is replaced by the OB open.

### 9. A11-bpr-clear-for-htf-targets
- **rule_id / kind:** A11, missing_condition. Scope: general. judgment = true.
- **Rule:** If a BPR lies between price and an HTF (daily) target, keep that target pending. Activate it only after price trades aggressively through the whole BPR, i.e. a displacement close beyond its far edge (proxy: a candle closing beyond it and leaving an FVG). Until then, treat the session as chop risk and use only targets on the near side of the BPR.
- **Sources:** 012_HkiPAi1Mdu8 ~00:08:35.
- **Quote:** "trade aggressively above that then the levels I mentioned on the daily chart are within reason"
- **Conflicts:** none.
- **[our interpretation]:** the displacement-close-plus-FVG proxy.
- **Rulebook fix:** A11: "A BPR between price and an HTF target gates that target until price clears it aggressively; otherwise expect chop (012 ~8:35)."
- **BUILD SPEC (targets_partials):**
  - In `_targets` (after the merge), find the nearest BPR (`Side.bprs`, 15m/5m) with bottom > `above`. Drop every level of kind array/pool from an HTF source ("D"/"W" arrays, daily wick CEs, PDH/PWH) beyond the BPR's far edge, unless a bar since the BPR formed closed beyond its far edge and left an FVG (`levels.fvgs` c1 = that bar - 1).
  - When gated, tag the order `bpr_chop`.
  - Params: `bpr_gate_htf: bool = False`.
  - Test: `test_bpr_gates_daily_target`. BPR 4100-4104, daily target 4120: ladder stops below 4100; after a displacement close 4106 with an FVG, 4120 appears.

### 10. A11-bpr-mt-overshoot-cap
- **rule_id / kind:** A11, missing_rule. Scope: index. judgment = false.
- **Rule:** When a BPR sits directly beyond the far edge of an FVG being retraced into, the expected maximum overshoot of that FVG = the BPR's MT (midpoint of the BPR range). For a short at a bearish FVG, put the stop/invalidation beyond the BPR MT, not at the FVG far edge. Mirror for longs. Single example (026); test as a stop-placement variant.
- **Sources:** 026_GFdWahZUNOw ~00:59:14.
- **Quote:** "what's the midpoint ... for that balanced price range 4117.50"
- **Conflicts:** none.
- **Rulebook fix:** A11: "FVG overshoot cap = MT of a BPR directly beyond it; stop beyond that MT (026 ~59:14)."
- **BUILD SPEC (entries_stops_sizing):**
  - In the `_scan_core` entry/stop block: if a BPR (`Side.bprs`) has its near edge within `bpr_adj_pts` beyond the entry FVG's far edge, set stop = BPR MT + `stop_pad_ticks` (side terms) instead of the FVG far edge; skip if that widens risk past `max_risk`.
  - Params: `stop_bpr_mt: bool = False`, `bpr_adj_pts: float = 1.0`.
  - Test: `test_stop_at_bpr_mt`. Bearish FVG 4110-4114, BPR 4114.5-4120.5 (MT 4117.50): short stop = 4117.75.

### 11. L10-A17-old-high-target-ladder
- **rule_id / kind:** L10 / L11 / A17, shortened. Scope: general. judgment = false.
- **Rule:** For a draw toward an old swing high (mirror for lows), especially when the leg from price to the high has no FVG/VI: T1 = rejection-block body edge (highest close/max(o,c) of the up-close candles at the high), T2 = upper-wick CE = (high + max(o,c))/2, T3 = beyond the wick high (buy-side), T4 = the next pool beyond. When the bias is bullish, treat T1 as a speed bump: take a small partial there, never fade it and do not exit the bulk. Expect expansion through it. Scale out level by level (L14 sorted list). When the bias is bearish, the same body edge can be a short entry after displacement (035, 2022 model).
- **Sources:** 003_ojy5ApHhEu4 ~01:03:13; 030_ZdnGlropfmU ~01:04:30; 035_kFIOp8Tprdc ~00:24:47.
- **Quote:** "this is like a speed bump level ... don't look at that as resistance"
- **Conflicts:** none.
- **Rulebook fix:** L10/L11: state the order body edge -> wick CE -> wick high -> next pool, and that the body edge is a speed bump with the draw above.
- **BUILD SPEC (targets_partials):**
  - Built pieces: `wick_levels`/`_wick_ces`; listed: L11 `rb_targets`, A17 `rej_targets`. New: the ladder for the specific old-high pool that is the draw.
  - In `_targets`, for each "pool" level that is a swing high (daily pivots, `pdh*`, `old_hi`): when no FVG/VI exists between `above` and it (`ctx` gaps + `Side.vis`), insert body edge (kind "speed") and wick CE (kind "array") of that swing candle.
  - In the ladder loop: a "speed" rung takes `speed_frac` of the position only and never triggers `obj_stop`/done flags or a reversal setup.
  - Params: `old_high_ladder: bool = False`, `speed_frac: float = 0.2`.
  - Test: `test_old_high_body_speed_bump`. Old high candle o 4090 c 4096 h 4100: ladder 4096 (speed), 4098 (array), 4100 (pool).

### 12. L1-rth-session-pools
- **rule_id / kind:** L1, missing_condition. Scope: index. judgment = false.
- **Rule:** Previous PM (13:30-16:00), AM (09:30-12:00) and lunch (12:00-13:30) ranges = max high / min low of RTH bars in the window. London (02:00-05:00) = ETH bars. Overnight (16:00-09:30) prints never redefine an RTH session pool, and an overnight trade beyond it does not retire it. The RTH pool stays the reference for the next RTH session.
- **Sources:** 067_vuBRMFhFZAY ~00:15:00, ~00:32:00-33:00, ~00:55:50 (quote placed at ~14:09 in the claim; actually ~55:50).
- **Quote:** "I would still refer to the PM session range"
- **Conflicts:** none.
- **Rulebook fix:** L1: "RTH session pools come from RTH bars only; overnight prints do not redefine or retire them; London from ETH (067 ~55:50)."
- **BUILD SPEC (levels_detectors):**
  - `DayCtx.sess["prev_pm"]` already uses the prior day's 13:30-16:00 bars. New: the spent test. In `_targets` (and `mark_levels` `intact`) with `rth_pool_spent`, a session pool named prev_pm / prev_am / lunch is spent only by bars with t >= 570 (today) after creation, not by overnight bars. London stays spent by any print.
  - Params: `rth_pool_spent: bool = False`.
  - Test: `test_prev_pm_low_survives_overnight_break`. prev PM low 4000, overnight low 3995, RTH low 4002: prev_pm low still a pool at 10:00.

### 13. L3-midnight-session-opening-ranges
- **rule_id / kind:** L3, missing_rule. Scope: general. judgment = false.
- **Rule:** Optional reference levels (050 ~18:13, a journaling remark): record midnight OR30 = H/L 00:00-00:30 ET and OR60 = H/L 00:00-01:00 ET each day for the traded market. The same opening-range idea can be applied to the first 30/60 min of the Asian (20:00), London (02:00), NY (09:30) and PM (13:30) sessions in indices. ICT gives no rule for how to use them (pool, target or filter), so treat them as low-priority candidate liquidity pools to test, not a core rule. He warns in the same breath against bringing every concept into the trading plan.
- **Sources:** 050_F509lJRrYIM ~00:18:13.
- **Quote:** "the opening range of the first 30 minutes and the first 60 Minutes at midnight"
- **Conflicts:** none.
- **Rulebook fix:** L3: add midnight/session OR30/OR60 as optional journal levels (050 ~18:13), with the "kitchen sink" warning.
- **BUILD SPEC (levels_detectors):**
  - `or_extra` (L3, built) exists. Add `session_ors: tuple = ()` of (start_min, minutes) pairs, e.g. ((0,30),(0,60),(1200,30),(120,30),(810,30)); for each, once complete, add H/L as "pool" with tag `sor_<start>_<min>` in `_lv_target_pools` and as sweep pools in `mark_levels`. Asia 20:00 is from the prior evening (ETH data).
  - Params: `session_ors: tuple = ()`.
  - Test: `test_midnight_or_pools`. Bars 00:00-01:00 with H 4010 / L 4000: pools present only after 01:00 for OR60, after 00:30 for OR30.

### 14. L3-054-citation
- **rule_id / kind:** L3, wrong (source). Scope: index. judgment = false.
- **Rule:** Source correction: 054 (~5:01-5:13) supports previous-week high (bullish draw) / previous-week low (bearish draw) as SB draw candidates; 054 ~4:02 is the previous-day H/L item. Previous-month H/L must be sourced from cc04_003 / cc08_007 (~18:34), not 054.
- **Sources:** 054_tRq1hyGGtl4 ~00:05:01.
- **Quote:** "we would look for a run above the previous week's high"
- **Conflicts:** none.
- **Rulebook fix:** L3: change "054 ~4:02 (previous week/month)" to "054 ~5:01 (previous week); previous month: cc04_003, cc08_007 ~18:34".
- **BUILD SPEC:** none (text only; `pool_prev_week` / `pool_prev_month` already exist).

### 15. L4-target-below-eq-leg
- **rule_id / kind:** L4, shortened. Scope: index. judgment = true.
- **Rule:** Short (2022-model framing): the EQ leg runs from the swing low that began the run up to the high that took buy-side (inferred; the captions only say "the low up to the high"). EQ = 50%. Target = a sell-side pool strictly below EQ, preferring the larger pool (REL over a single low) (042). Variant (049): if the 15m shows no imbalance, look on the 60m for the first imbalance/FVG just below the sell-side pool. Use it only if it lies below EQ, and exit with a limit at its near edge (top). Mirror for longs.
- **Sources:** 042_hQ379EuyNKQ ~01:09:19; 049_St9FJHRVdq8 ~00:03:42.
- **Quote:** "here's the 50 level that's equilibrium so we have to find something as a discount below that level"
- **Conflicts:** 042 targets the pool (REL) itself; 049 targets the first imbalance beyond the pool.
- **[our interpretation]:** the leg = from the origin low of the rally that swept buy-side to that high.
- **Rulebook fix:** L4: name the leg (rally origin low -> buy-side-run high) and add the 049 variant (first 15m, else 60m, imbalance beyond the pool, below EQ, exit at its near edge).
- **BUILD SPEC (targets_partials):**
  - Listed: L4 `draw_below_eq`. New: the leg and the beyond-pool variant.
  - `draw_below_eq` leg: lo = the lowest low between the previous opposite MSS (or session start) and `sw["ext_i"]`, hi = sweep extreme. Keep only targets beyond EQ; among pools prefer "pool_eq".
  - `eq_beyond_imb: bool`: after picking the pool P, search 15m FVGs (`zones_tf(…,15)`) with near edge beyond P; if none, 60m. If its near edge is beyond EQ, it becomes the final target (kind "array", exit at the near edge per X2).
  - Params: `eq_leg: str = "sweep"` ("sweep" / "rally"), `eq_beyond_imb: bool = False`.
  - Test: `test_target_imbalance_beyond_pool_below_eq`. Rally 4000->4040 (EQ 4020), REL 4012, 60m FVG top 4008: final target 4008.

### 16. L4-resistance-runs
- **rule_id / kind:** L4, shortened. Scope: general. judgment = true.
- **Rule:** Students/bot: do not take trades whose target sits behind a high-resistance run, meaning several overlapping old highs/lows (LH/LL for a bullish target) formed between price and the old level (cc01_007; 025 ~16:13). The more time price spends in that overlap, the less likely the old level is reached without a news driver (FOMC/NFP) (cc01_007 ~10:00). Prefer low-resistance runs: no opposing argument or reason to pause between entry and target, and price leaves the entry fast (095 ~31:03). Filter (cc08_007 ~6:58): require an easily seen, unobstructed path to an opposing HTF PD array. Proxy: opposing swings/FVGs between entry and target = 0 (or <= k, our parameter). Lingering around the entry = warning (bar/handle thresholds ours; 025 ~17:40 gives ~10 min on 1m). Lunch: 025 labels one day's noon-13:00 chop as high-resistance (example, not a default rule). Mirror for shorts.
- **Sources:** 025_7RiUUCqQ3SY ~00:16:13; 095_LPmMtq9jLm8 ~00:31:03; cc01_007_22XkhpJR5eA ~00:07:34, ~00:10:00; cc08_007_5Z_3NbclMSY ~00:06:58.
- **Quote:** "don't try to trade in high resistance liquidity runs"
- **Conflicts:** none.
- **[our interpretation]:** k, the time-in-overlap ratio K, the linger thresholds.
- **Rulebook fix:** L4: student prohibition, clear-path filter, time factor, news exception (cc01_007, cc08_007, 025, 095).
- **BUILD SPEC (targets_partials):**
  - Listed: L4 `lrlr_max` (opposing swings count). New parts:
    - Time factor: count bars since the first intermediate swing that sit inside the band [first intermediate swing, target]. If > `hrlr_time_k` x the bars of the leg away from the target, drop that target unless the day is FOMC/NFP (`calendar`).
    - Clear path to an HTF array: require at least one opposing 4h/D array (`htf.table` arrays) beyond the target with `lrlr_max` satisfied up to it; else skip (`clear_path=True`).
    - Linger warning: handled by management_exits X9 (existing); add tag `lingered` when price stays within `linger_pts` of entry for `linger_bars`.
  - Params: `hrlr_time_k: float = 0.0` (0 = off; test 1.0), `clear_path: bool = False`, `linger_bars: int = 10`, `linger_pts: float = 1.0`.
  - Test: `test_hrlr_time_factor_drops_target`. Target 4100, intermediate highs 4090/4088, 60 bars inside 4088-4100 vs a 20-bar leg: target dropped.

### 17. L4-session-pool-before-rel
- **rule_id / kind:** L4, unlisted_contradiction. Scope: index. judgment = true.
- **Rule:** Short off the lunch high (M7, 067): T1 = low of the lunch/90-min window (12:00-13:30); a farther REL is T2 only. Precedence: the nearest untaken session-range pool (L1) comes before a farther REL/larger pool; L4's "prefer the larger pool" applies when choosing between pools at a comparable position (e.g. both below EQ), not to skipping a nearer session pool. Record as a conflict between L4 (042/049/103) and 067.
- **Sources:** 067_vuBRMFhFZAY ~00:50:27.
- **Quote:** "before you get there where's the next logical range"
- **Conflicts:** L4 (042, 049, 103): prefer the larger pool; 067: the nearer session-range low first.
- **[our interpretation]:** "comparable position" = both on the same side of EQ.
- **Rulebook fix:** L4: add the precedence note; conflicts list: L4 vs 067.
- **BUILD SPEC (targets_partials):**
  - With `eq_pref="rank"` the rel-eq pool can outrank a nearer pool. Add `session_pool_first`: in `_draw_prefs` / `setups.draw_prefs`, a session pool (`ctx.sess` lunch / prev_pm / london, AM range) nearer than the chosen rel-eq pool becomes the first rung and the draw; the rel-eq pool stays as T2.
  - Params: `session_pool_first: bool = False`.
  - Test: `test_lunch_low_before_rel`. Short at 14:00, lunch low 4050, REL 4040, eq_pref rank: rungs 4050 then 4040, draw 4050.

### 18. L5-partial-redelivery
- **rule_id / kind:** L5, missing_rule. Scope: index. judgment = false.
- **Rule:** (019, single example) If after the Sunday open price (a) trades to the NWOG far edge (Friday close), (b) trades back through the gap to the open side, (c) returns only to the CE and fails, and (d) leaves the gap with a lone FVG at its edge, the gap is treated as rebalanced and the Friday close is no longer required. On a later return, target the exit FVG / the NWOG near-edge area (exit just before it), not the Friday close.
- **Sources:** 019_ZrZJmwrMxFY ~00:16:36.
- **Quote:** "it does not need to come back to Friday's closer"
- **Conflicts:** L9 "unvisited remainder is the next draw" points the other way.
- **Rulebook fix:** L5: add the both-way redelivery state (019 ~16:36, single example).
- **BUILD SPEC (levels_detectors):**
  - In `htf.gaps_for_day` keep, per NWOG, a state machine over all bars since its Sunday open: `far_hit`, `back_through`, `ce_fail` (later return reaches CE ± 1 tick, then closes back out), `exit_fvg` (an FVG whose near edge is within 1 pt of the gap edge on the exit leg). When all four: mark `rebalanced`.
  - In `_targets` with `nwog_rebalanced`, a rebalanced NWOG contributes only its near edge and the exit FVG's near edge; CE and far edge are dropped.
  - Params: `nwog_rebalanced: bool = False`.
  - Test: `test_nwog_rebalanced_drops_far_edge`. Synthetic week following the four steps: CE and Friday close missing from the ladder.

### 19. L5-rth-and-eth-gap-views
- **rule_id / kind:** L5 / L7, missing_condition. Scope: index. judgment = false.
- **Rule:** Find opening gaps on both chart sessions: ETH bars (NWOG Fri 16:59 close to Sun 18:00 open; NDOG 17:00-18:00) and RTH-only bars (prior 16:00/16:15 close to 09:30 open: ORG, and the Fri-close-to-Mon-09:30 NWOG variant), since an ETH-only view hides the RTH gaps (019 ~4:31). Keep both level sets; ICT notes they are not always relevant (selection is discretionary). Keeping both sets without deduping is our implementation choice.
- **Sources:** 019_ZrZJmwrMxFY ~00:04:31.
- **Quote:** "you use regular trading hours and electronic trading hours"
- **Conflicts:** none.
- **[our interpretation]:** keep both without deduping.
- **Rulebook fix:** L5/L7: "Scan both ETH and RTH bar series for opening gaps (019 ~4:31)."
- **BUILD SPEC (levels_detectors):**
  - `htf.opening_gaps` uses ETH when `has_overnight(df)`; `org` uses RTH closes. Add `gap_views: str = "auto"` ("auto" = current; "both" = also compute the RTH Friday-close -> Monday 09:30 gap as kind "nwog_rth" alongside the ETH NWOG, with no dedupe; levels high/CE/low).
  - Params: `gap_views: str = "auto"`.
  - Test: `test_gap_views_both`. Fri RTH close 4000, Fri 16:59 4002, Sun open 4006, Mon 09:30 4010: two gaps (4002-4006 nwog, 4000-4010 nwog_rth).

### 20. L5-nwog-target-ladder
- **rule_id / kind:** L5 / X1 / L9, missing_rule. Scope: index. judgment = false.
- **Rule:** When the draw is an NWOG: first objective = its near edge (NWOG low if price is below, high if above; 020, 025). Once it trades, next objective = CE, where the bulk comes off (80% in 020). Remaining runners aim for the far edge, scaled out one contract at a time (020 ~10:04). CE and far edge become targets only after the near edge trades. Note the conflict with L9 (far edge of a weekly gap = "ringer"). Mirror for shorts.
- **Sources:** 020_MqOVbd1oqZk ~00:03:50; 025_7RiUUCqQ3SY ~00:43:43.
- **Quote:** "that's the low end of the new week opening gap"
- **Conflicts:** L9 (049, 061, 065B) far edge of a weekly gap is a "ringer"; 020 aims runners at the far edge.
- **Rulebook fix:** L5: add the NWOG ladder near edge -> CE (bulk) -> far edge (runners); list the conflict with L9.
- **BUILD SPEC (targets_partials):**
  - `_targets` already adds NWOG high/CE/low as "array". New: when the locked draw (`_lock_step`) is an NWOG level, gate CE and far edge behind the near edge having traded (track in `pos`), and set rung fractions: near edge `nwog_near_frac`, CE `nwog_ce_frac` (bulk), far edge one unit at a time.
  - Params: `nwog_ladder: bool = False`, `nwog_near_frac: float = 0.0`, `nwog_ce_frac: float = 0.8`.
  - Test: `test_nwog_ladder_bulk_at_ce`. Long below NWOG 4076.75-4100: rung 4076.75 (no partial), 4088.4 (80% off), 4100 (rest).

### 21. L5-nwog-sr-levels
- **rule_id / kind:** L5, unlisted_contradiction. Scope: index. judgment = true.
- **Rule:** For each stored NWOG (high, CE, low), treat all three as PD-array levels: support/target when approached from above, resistance/target from below. The CE carries similar weight to the edges, and price tends to move from one NWOG level to the next (039 ~10:52-12:06). The nearest unreached NWOG level in the bias direction is a valid draw. In a consolidating, non-trending week (B14), expect reactions at the exact levels, not a zone (024 ~18:37); use them for partials/targets and scalp turns. In a trending week, price leaves the gap and these reactions are not expected (039 ~12:13-12:30). Bot note: D21 already recommends adding the CE; the current edges-only implementation remains a deviation until done.
- **Sources:** 039_WKKnlIIkBTk ~00:10:52, ~00:11:56; 024_gH1e-TVrK6k ~00:18:37.
- **Quote:** "they many times are treated as support and resistance"
- **Conflicts:** bot Monday-variant mode was edges only (D21; `monday_ce` now built, off).
- **[our interpretation]:** reaction = bar low within 1 tick of the level and a close back above (bodies stop there).
- **Rulebook fix:** L5: "Stored NWOG high/CE/low are S/R and draw levels; exact reactions in consolidation weeks (B14), not in trending weeks (039, 024)."
- **BUILD SPEC (setups_models):**
  - Targets already include high/CE/low for ETH gaps. New: entry use in consolidation weeks. With `nwog_sr_entries` and `htf` regime `nwog_regime == "consolidation"` (B14.1, listed), arm a limit at the nearest NWOG level in the bias direction (long at a level below price, short above), stop 1 pt beyond, first target the next NWOG level. Tag `nwog_sr`.
  - Params: `nwog_sr_entries: bool = False`, `nwog_sr_stop_pts: float = 1.0`.
  - Test: `test_nwog_sr_entry_consolidation_only`. Regime consolidation: a limit at the CE; regime trending: no order.

### 22. L5-friday-close-location-fill
- **rule_id / kind:** L5, missing_condition. Scope: index. judgment = true.
- **Rule:** At the Sunday open, locate Friday's close in the parent dealing range (the dominant recent swing) and note which side of EQ price spent more time in that week. If Friday closed near EQ after chop: a gap toward the less-explored side (especially in the bias direction) need not fill to Friday's close, and a partial fill / stall at intermediate hourly levels is normal. A gap toward the side already heavily explored is expected to fill fully to Friday's close (028 ~1:09:54-1:12:31). If the close was not choppy-at-EQ and the gap leaves price "really extended", expect a full return to Friday's close. Thresholds (e.g. near EQ = within ±10%) are ours to test.
- **Sources:** 028_wWvFUW-jY4w ~01:10:01.
- **Quote:** "I would expect a full return back to Friday's close why because it's really extended"
- **Conflicts:** none.
- **[our interpretation]:** near EQ = ±10%; time spent = count of 1h bars closing above vs below EQ.
- **Rulebook fix:** L5: add the Friday-close-location condition for a full NWOG fill (028 ~1:10).
- **BUILD SPEC (bias_htf):**
  - New `htf.table` weekly column `nwog_fill` (+1 = full fill expected, 0 = partial ok), computed from data up to Friday close plus the Sunday open: parent range = the 20-day range (A21.2 body range); pos = (Fri close - lo)/(hi - lo); time side = share of the week's 1h closes above EQ.
  - In `_targets`, when `nwog_fill_rule` and `nwog_fill == 0`, the NWOG far edge (Friday close) is dropped for that week's targets; when +1 it is kept and ranked as draw.
  - Params: `nwog_fill_rule: bool = False`, `nwog_eq_band: float = 0.10`.
  - Test: `test_nwog_fill_by_friday_location`. Friday close at 51% after a premium-heavy week, gap down: far edge dropped; gap up: kept.

### 23. L5-below-nwog-low
- **rule_id / kind:** L5, missing_rule. Scope: index. judgment = true.
- **Rule:** When price trades below the current NWOG low without large-range displacement candles down, expect accumulation there, then a run back up to work inside the NWOG (033 ~08:19). Further downside to the next level below is expected only if price takes out the NWOG low and the recent low with acceleration (large bearish range candles) (033 ~07:32, ~32:30). ICT prefers buy-side to be taken first before such a leg (033 ~32:46). Which levels to target inside the gap (CE, then high) is our interpretation, not ICT's statement.
- **Sources:** 033_KXx07qzW5u0 ~00:08:19.
- **Quote:** "it'll accumulate here run back up and start to work inside this Gap"
- **Conflicts:** none.
- **[our interpretation]:** displacement = 2+ bars with range >= `disp_mult` x the 20-bar mean range; targets CE then high.
- **Rulebook fix:** L5: add "below the NWOG low without displacement -> expect a return inside; continuation only on acceleration (033)."
- **BUILD SPEC (bias_htf):**
  - In `run_day`, a per-day state `nwog_below`: set when price first trades below the current NWOG low. If the break leg has no displacement bars (A20 test), set `want` = +1 for the session (gap return) with the NWOG CE then high as draw (via `_lock_step`). If it did displace, keep `want` per the existing bias.
  - Params: `nwog_below_return: bool = False`.
  - Test: `test_below_nwog_low_return_draw`. Slow drift below NWOG low: want +1, draw = CE; a 3-bar displacement break: unchanged.

### 24. L5-event-horizon-objective
- **rule_id / kind:** L5, shortened. Scope: index. judgment = false.
- **Rule:** With NWOGs sorted by price, after price reaches or leaves NWOG_k in the expected direction, the minimum objective is the midpoint between NWOG_k's near edge and NWOG_k+1's near edge (the event horizon) (037 ~22:46). If price trades through that midpoint, expect it to reach and trade through NWOG_k+1 (051 ~16:51). If the midpoint does not trade, NWOG_k+1 is not a target.
- **Sources:** 037_wu0sQarBRrI ~00:22:37; 051 ~16:51.
- **Quote:** "between both of them midpoint that's my event horizon"
- **Conflicts:** none.
- **Rulebook fix:** L5: the event horizon is itself the minimum objective; NWOG_k+1 targets only after it trades.
- **BUILD SPEC (targets_partials):**
  - Built: `nwog_halfway` (`_nwog_half`) makes the next NWOG the draw once 50% is reached. New: `event_horizon_target`: add the midpoint as a rung (kind "array") and drop NWOG_k+1's levels from the ladder until that midpoint has traded (1 tick through, bars since the session start).
  - Params: `event_horizon_target: bool = False`.
  - Test: `test_event_horizon_gates_next_nwog`. NWOGs 4000-4010 and 4060-4070, price leaving 4010 up: ladder ends at 4035 until 4035.25 trades, then 4060 appears.

### 25. new-stop-run-overshoot-next-array
- **rule_id / kind:** new / L4 / L5 / M12, missing_rule. Scope: general. judgment = true.
- **Rule:** Mirror of the existing L5/M12 sell-side rule. When a stop run above an old high is expected, its likely extreme is the next opening gap (NWOG/NDOG/ORG) or PD array (e.g. a volume imbalance) above the high (038 ~46:12; 025 ~1:05:16). A level sitting only just above the high, such as a wick CE immediately overhead, is not a reasonable stopping point, so look to the next array beyond it (025). Use that level for the turtle-soup short entry, and place the stop beyond it. The minimum distance threshold and the exact stop and invalidation mechanics are our interpretation, not ICT's statement.
- **Sources:** 025_7RiUUCqQ3SY ~01:05:16; 038_4H74nXabvL0 ~00:46:12.
- **Quote:** "how far can you trust the move above an old high for a turtle soup"
- **Conflicts:** none.
- **[our interpretation]:** skip levels within 1 ES pt of the high; stop 1 tick beyond the array's far edge.
- **Rulebook fix:** M12/L5: add the buy-side mirror: the run extends to the next gap/PD array above, skipping levels hugging the high.
- **BUILD SPEC (setups_models):**
  - Shared turtle-soup core (`levels.turtle_soup`, `_turtle`, `_ts_arrays`) is built for the sell-side mirror. New: `ts_next_array: bool`: the turtle-soup limit is placed at the first level from `_ts_arrays` + gap edges/CE (`ctx.gaps`, `ctx.org`) + VI edges more than `ts_min_beyond_pts` beyond the pool; the stop = that array's far edge + 1 tick. Both sides use the same code (sd.x mirroring).
  - Params: `ts_next_array: bool = False`, `ts_min_beyond_pts: float = 1.0`.
  - Test: `test_ts_skips_wick_ce_hugging_high`. Old high 4100, wick CE 4100.5, VI 4103-4105: short limit 4103, stop 4105.25.

### 26. L5-monday-variant-1659
- **rule_id / kind:** L5, wrong. Scope: needs_unavailable_data. judgment = false.
- **Rule:** NWOG Monday variant (039 ~14:46) = range between the Friday 16:59 ET close (last bar before the 17:00 halt) and the Monday 09:30 ET open, ignoring Sunday and overnight trading. Levels: edges and CE. The bot's RTH-Friday-close-to-Monday-09:30 gap is not this variant. Label it a Monday ORG/proxy (as decision 21 already suggests), and do not cite it as ICT's variant unless 16:59 data exists.
- **Sources:** 039_WKKnlIIkBTk ~00:14:46.
- **Quote:** "use the Friday closing price at 4 59"
- **Conflicts:** Decision 21 equates the bot's gap with the 039 variant.
- **Rulebook fix:** L5 and Decision 21: "039 variant = Fri 16:59 close to Mon 09:30 open; the bot's RTH-close version is a Monday ORG proxy."
- **BUILD SPEC:** none (needs the Friday 16:59 print; rename the bot mode's label in docs only).

### 27. L5-old-nwog-in-consolidation
- **rule_id / kind:** L5, missing_rule. Scope: index. judgment = true.
- **Rule:** (a) For an old swing high or low with a consolidation (old order flow), find the stored NWOG whose range runs through that consolidation. It is the preferred fair-value magnet when price returns toward that swing, together with order blocks and FVGs in the same area (044 ~1:18:34). (b) When current price consolidates or clusters, search the stored NWOGs (up to the 60-day lookback) for one extending through that band and treat it as the anchor/magnet for the range (051 ~17:37). Using its edges and CE as support/resistance is our interpretation.
- **Sources:** 044_LN1nfYp4dBw ~01:18:34; 051_BM1mqQv-ypk ~00:17:37.
- **Quote:** "what new week opening Gap runs through that"
- **Conflicts:** none.
- **[our interpretation]:** consolidation = >= 6 overlapping bars within a band <= 0.3 x ADR5; edges/CE as S/R.
- **Rulebook fix:** L5: add NWOG selection by overlap with old-swing consolidation and with the current cluster (044, 051).
- **BUILD SPEC (targets_partials):**
  - `levels.consolidation_band(h, l, i, n, max_w)` -> (lo, hi) or None.
  - (a) For each daily pivot used as a target, take the price band of its 3-bar consolidation (bodies of pivot bar ±1); a stored NWOG overlapping it gets its levels tagged `nwog_magnet` and ranked first among arrays in `_draw_prefs`.
  - (b) At bar i, if a current band exists, the NWOG intersecting it is tagged `range_anchor`; its high/low become the range targets for that session.
  - Params: `nwog_magnet: bool = False`.
  - Test: `test_nwog_through_old_consolidation_ranked`. Two NWOGs, one overlapping the old high's bodies: that one is the draw.

### 28. L5-holiday-nwog
- **rule_id / kind:** L5, missing_condition. Scope: index. judgment = false.
- **Rule:** If a holiday shortens Friday trading, ignore that week's NWOG. Use the closest normal NWOG to current price formed within the last 60 days; if there is none, use no NWOG (046 ~16:34). If a holiday disrupts the Sunday/Monday session, use Tuesday's opening price as the week's opening reference: 09:30 for indices, midnight for FX (046 ~20:47-21:11).
- **Sources:** 046_VLis0LcbUaQ ~00:16:23.
- **Quote:** "if I don't have it then I don't use it"
- **Conflicts:** none.
- **Rulebook fix:** L5: add the 60-day limit, the none fallback and the Tuesday reference.
- **BUILD SPEC (levels_detectors):**
  - Built: `nwog_skip_holiday` (ignore the holiday week's NWOG). New:
    - `nwog_holiday_pick="closest"`: in `gaps_for_day`, when the current week's NWOG is skipped, keep only the single NWOG (within `nwog_days`=60) closest to the day's open; none if the list is empty.
    - `tue_open_ref`: if Monday is a holiday (`calendar`), the week's opening reference for B13 (`weekly_open` filter) is Tuesday 09:30.
  - Params: `nwog_holiday_pick: str = "all"` ("all" / "closest"), `tue_open_ref: bool = False`.
  - Test: `test_holiday_week_closest_nwog`. Holiday Friday week, NWOGs at 4000 and 4200, open 4150: only 4200's gap kept.

### 29. L5-nwog-not-standalone
- **rule_id / kind:** L5, missing_rule. Scope: index. judgment = false.
- **Rule:** Do not select an NWOG as the draw on liquidity by itself. Combine it with other factors (old highs/lows liquidity, HTF FVG or other PD arrays, B-rule bias) before treating it as the likely draw (051 ~13:55). Use NWOGs as magnets that add weight to the draw assessment, not as a standalone reason.
- **Sources:** 051_BM1mqQv-ypk ~00:13:55.
- **Quote:** "by themselves you don't just simply look at them and say okay price is going to go there"
- **Conflicts:** 050 (~54:42) shorts at the NDOG bottom / NWOG (see item 34).
- **Rulebook fix:** L5: add "confluence only for the draw, like L6 for NDOG (051 ~13:55)."
- **BUILD SPEC (bias_htf):**
  - In `_lock_step` / `_draw_prefs` draw selection, with `nwog_draw_confl`, an NWOG level is eligible as the locked draw only if within `confl_pts` of a pool, an HTF array level (`htf.table` arrays), or it lies in the `want` direction from price. Otherwise it stays a ladder rung only.
  - Params: `nwog_draw_confl: bool = False`, `confl_pts: float = 2.0`.
  - Test: `test_nwog_not_standalone_draw`. NWOG CE alone above: not the draw; with PDH 1 pt away: draw.

### 30. B13-weekly-open-line-lifetime
- **rule_id / kind:** B13 / L5, missing_condition. Scope: index. judgment = false.
- **Rule:** weekly_open_line = the Sunday 18:00 ET first print, drawn from Sunday 18:00 through the end of that trading week (Friday close) (051 ~03:27). The NWOG range (edges, CE) carries forward for many weeks per the L5 lookback (up to 60 days).
- **Sources:** 051_BM1mqQv-ypk ~00:03:27.
- **Quote:** "that price I will extend throughout the entirety of this trading week"
- **Conflicts:** none.
- **Rulebook fix:** B13/L5: state the two lifetimes.
- **BUILD SPEC (bias_htf):**
  - In the B13 `weekly_open` filter (listed) and wherever the Sunday open is used as a level, expire the line at Friday's close; never carry a prior week's opening price as a level. Add an assertion test only (no new switch): `weekly_open_level(day)` returns the current week's Sunday 18:00 open.
  - Params: none.
  - Test: `test_weekly_open_line_one_week`. Monday of week 2 returns week 2's open, never week 1's.

### 31. L5-quarter-level-no-imbalance
- **rule_id / kind:** L5, missing_rule. Scope: index. judgment = true.
- **Rule:** For an NWOG price has broken through (shown for a break below; mirror for above): if the retrace leg has no FVG/VI, the retrace level is the near quarter, (CE + gap low)/2 (030 ~1:23:49). If price reaches that quarter and is repelled, expect continuation toward the sell-side pools and the nearest wick CE below. The bearish read holds until price trades above the next higher reference (in 030, 4146, above the CE), not merely until a body closes above the quarter.
- **Sources:** 030_ZdnGlropfmU ~01:23:49.
- **Quote:** "was there any imbalance in here no so what level are we looking at"
- **Conflicts:** none.
- **[our interpretation]:** "repelled" = a bar trades to the quarter ±1 tick and closes back below it.
- **Rulebook fix:** L5: "Quarters are used when the retrace after a gap break has no imbalance: near quarter = retrace level (030 ~1:23:49)."
- **BUILD SPEC (setups_models):**
  - New setup branch in `setups.extra_setups`: after a close beyond an NWOG edge, if the retrace leg (from the break extreme to bar i) holds no FVG/VI (`Side.vis`, `sd.gaps` in range), arm a limit at the near quarter (short below, long above), stop beyond the CE + 1 tick, targets from `_targets` (sell-side pools, wick CEs). Cancel if price trades beyond the next higher reference (the gap's far edge).
  - Params: `gap_quarter_retrace: bool = False`.
  - Test: `test_quarter_retrace_no_imbalance`. NWOG 4130-4146 (CE 4138), break below, clean retrace: short limit 4134, stop 4138.25.

### 32. L6-ndog-lifetime-16h
- **rule_id / kind:** L6, unlisted_contradiction. Scope: needs_unavailable_data. judgment = true.
- **Rule:** NDOG (Mon-Thu): 17:00 close and 18:00 reopen, CE = midpoint. Param ndog_life = {'16h','friday','5d'}. The 16h version is active from 18:00 to ~10:00 next morning (overnight plus the next NY AM only).
- **Sources:** 025_7RiUUCqQ3SY ~00:24:41.
- **Quote:** "extend that throughout the next 12 to 16 hours"
- **Conflicts:** 052: through Friday; 068: 5 trading days; 025: 12-16 hours.
- **[our interpretation]:** 16h ends ~10:00 next day.
- **Rulebook fix:** L6: cite 025 and list the three lifetimes in the contradictions section.
- **BUILD SPEC:** none (needs the 17:00-18:00 futures reopen; when available, add `ndog_life` to `htf.gaps_for_day`).

### 33. L6-one-tick-ndog
- **rule_id / kind:** L6, unlisted_contradiction. Scope: needs_unavailable_data. judgment = false.
- **Rule:** NDOG = [min, max] of (16:59 bar close, 18:00 bar open), Mon-Thu, kept regardless of size. If it is under 1 pt, use the single price as the level. Test min_ndog_pts = 0 (031) vs 1.0 (052).
- **Sources:** 031_8YSVu51hUWQ ~00:13:32.
- **Quote:** "that's a level that you want to have annotated in your charts all the time"
- **Conflicts:** 052: ignore gaps <= ~1 ES pt; 031: keep even a 1-tick gap.
- **Rulebook fix:** L6: list the conflict 052 vs 031.
- **BUILD SPEC:** none (needs NDOG data; `htf.opening_gaps(ndog_min_pts=1.0)` already exposes the threshold for when it exists).

### 34. L6-ndog-nwog-primary-entry
- **rule_id / kind:** L6, unlisted_contradiction. Scope: index. judgment = true.
- **Rule:** Option (switch): with a bearish daily bias, short when price retraces up to the lower edge of an active NWOG or NDOG (050: the March 5 NWOG in the AM; the NDOG low overlapping that NWOG at 14:00). The entry needs no separate FVG/OB. Stop just above the gap high (above the NWOG). Target the next sell-side pool, exiting 1 tick beyond the low. Mirror for longs. This conflicts with L6/052 ("confluence only") and should be listed as a contradiction. The AM entry time is not stated in 050.
- **Sources:** 050_F509lJRrYIM ~00:54:42 (and ~51:00).
- **Quote:** "we went up to the bottom end of that same new day opening Gap"
- **Conflicts:** L6 / 052 ~6:16: NDOG confluence only; 051 ~13:55: NWOGs never standalone.
- **[our interpretation]:** allowed windows = the bot's AM and PM sessions.
- **Rulebook fix:** L6: add the contradiction 050 vs 052/051.
- **BUILD SPEC (setups_models):**
  - New branch `gap_edge_entry` in `setups.extra_setups`: with daily bias (`want`) -1, when price first trades up to the lower edge of an active NWOG (or NDOG when the data exists) from below in the session, arm a limit at the edge, stop = gap high + `stop_pad_ticks`, targets = `_targets` sell-side pools (1 tick beyond). Mirror for longs. Tag `gap_edge`.
  - Params: `gap_edge_entry: bool = False`.
  - Test: `test_nwog_lower_edge_short`. want -1, NWOG 4080-4095, price rallies to 4080: short limit 4080, stop 4095.25.

### 35. L7-breakaway-test
- **rule_id / kind:** L7, shortened. Scope: index. judgment = true.
- **Rule:** Condition (070): if the ORG is in the direction of the HTF bias and a specific named HTF draw (e.g. an untaken old daily high) lies beyond, do not trade toward the gap fill. Trade only in the gap direction (e.g. buy sell-side runs and FVG retraces for a gap up) toward that draw. Test (033, with B15/030): treat the ORG as breakaway when price extends away from the prior close with no traction back toward it (B15: no attempt within ~30 min), and drop it as a same-day target. Otherwise the revisit remains likely but may come later (033: possibly the PM), not necessarily right away. Also list the conflict with B15's "bullish + gap up = fill then higher".
- **Sources:** 033_KXx07qzW5u0 ~00:15:04; 070_1HtRfFYiwO0 ~00:27:06.
- **Quote:** "it's in a hurry to get somewhere"
- **Conflicts:** B15 "bullish + gap up = fill then higher" vs 070.
- **Rulebook fix:** L7: add the 070 condition and the 033/B15 test; list the B15 conflict.
- **BUILD SPEC (bias_htf):**
  - Built: `org_draw` with `org_break_min` (B15 30-minute test). New: pre-open condition `org_with_bias`: at 09:30, if sign(open - prior close) == `want` and an untaken daily pivot or PDH/PWH (`htf.table` draw columns) lies beyond the open in that direction, set the session side gate to the gap direction only and drop the ORG levels from the AM ladder.
  - Params: `org_with_bias: bool = False`.
  - Test: `test_org_with_bias_blocks_fill_trades`. want +1, gap up 20 pts, untaken daily high above: shorts blocked, ORG levels absent.

### 36. L7-gap-up-premium-template
- **rule_id / kind:** L7 / B15, shortened. Scope: index. judgment = true.
- **Rule:** ORG = [prior RTH close, 09:30 open]. On a significant gap up after an overnight rally into premium: (1) expect an initial rally that draws in buyers; (2) a dip to the ORG high (09:30 open), where early shorts enter with stops above the first high; (3) a second rally that takes those stops; (4) only then look for failure (a bearish FVG / structure break, optionally confirmed by DXY) and short into the ORG. Target about a 5-handle run into the ORG, with the prior close optional. No shorts during steps 1-2. Mirror for a gap down into discount.
- **Sources:** 042_hQ379EuyNKQ ~00:11:31 (and ~01:00:16-01:00:54).
- **Quote:** "a little bit of a move to the upside to draw in the public"
- **Conflicts:** none.
- **[our interpretation]:** "significant" = gap >= 0.25 x ADR5; "premium" = open above the 20-day EQ.
- **Rulebook fix:** L7/B15: add the two-rally template.
- **BUILD SPEC (setups_models):**
  - New branch `org_two_rally`: on such a day, track after 09:30: first high H1, a dip that reaches within 1 pt of the 09:30 open, a second rally above H1. Only then allow the normal sweep/MSS short (the H1 run is the sweep), target = 09:30 open - 5 pts (rung) then the prior close. Shorts before step 3 are blocked.
  - Params: `org_two_rally: bool = False`, `org_sig_adr: float = 0.25`.
  - Test: `test_org_two_rally_short_only_after_second_high`. Gap up 15 pts: short signal before the second high blocked; after it allowed with T1 = open - 5.

### 37. L7-org-overshoot-discount
- **rule_id / kind:** L7, shortened. Scope: index. judgment = true.
- **Rule:** Gap up: target ladder = ORG near edge, CE, ORG low (prior settlement). If a discount PD array or sell-side pool lies below the ORG low, price may continue beyond the ORG low to reach it (043 ~12:22). Mirror for a gap down.
- **Sources:** 043_NkwqJBzgQwo ~00:12:22.
- **Quote:** "or Beyond it if there's something else that you could reach for for a discount"
- **Conflicts:** none.
- **[our interpretation]:** "below the ORG low" = within 0.5 x ADR5.
- **Rulebook fix:** L7: extend the ladder beyond the far edge to the next discount array/pool.
- **BUILD SPEC (targets_partials):**
  - When the trade's draw is the ORG (`org_draw="draw"`), append after the far edge the first pool or HTF array beyond it within `org_beyond_adr` x ADR5 (from `_targets` output). Without the switch the ladder stops at the far edge (current behaviour in `_lv_finish_targets`).
  - Params: `org_beyond: bool = False`, `org_beyond_adr: float = 0.5`.
  - Test: `test_org_ladder_extends_to_discount_array`. Gap 4000->4020, daily FVG top 3992: ladder ..., 4000, 3992.

### 38. L7-org-fill-delayed-pm
- **rule_id / kind:** L7 / M8, unlisted_contradiction. Scope: index. judgment = true.
- **Rule:** Gap down: the first draw is the nearest RTH session sell-side (the previous AM-session low), and the ORG stays a pending upside target. In the PM, if (a) today has traded below the previous AM-session low (deep discount) and (b) price has not traded into today's ORG since 09:30 -> PM bias up. Buy a sweep into a PD array (067: a rejection block) without needing the lunch low taken. Targets: the lunch (12:00-13:30) relative equal highs, then the ORG near edge, CE and far edge. Ignore the REL below. Mirror for a gap up. List the timing conflict with L7/M8.
- **Sources:** 067_vuBRMFhFZAY ~00:31:06, ~01:07:42.
- **Quote:** "It doesn't mean it wants to run up there immediately"
- **Conflicts:** L7 (033, 055) / M8: price reprices into the ORG after the 09:30 Judas; 067: the fill can wait until the PM.
- **Rulebook fix:** L7/M8: add the PM ORG draw and list the conflict.
- **BUILD SPEC (bias_htf):**
  - In `run_day` at 13:30 (PM session start): if `org_pm_draw` and the ORG is a gap down, today's low < `sess["prev_am"]` low (RTH, `prev_am_pool`) and no bar since 09:30 has traded into the ORG, set PM `want` = +1 and lock the draw to the ORG near edge (then CE, far edge), with lunch REH as the first rung. Mirror for gap up.
  - Params: `org_pm_draw: bool = False`.
  - Test: `test_org_pm_draw_after_deep_discount`. Gap down untouched, low below prev AM low: PM want +1, draw = ORG low edge.

### 39. L7-org-partial-close-orderflow
- **rule_id / kind:** L7, missing_condition. Scope: index. judgment = true.
- **Rule:** When price trades back into today's ORG and opposing order flow (order blocks / PD arrays) sits inside the gap, the objective is the ORG CE and the far edge (prior close) is optional. CE was reached twice in 068 and the prior close never. Whether a clean interior implies a full fill is our extrapolation; test it.
- **Sources:** 068_V0uV6lcgobQ ~00:11:50.
- **Quote:** "so it's not necessary to do a complete closure"
- **Conflicts:** none.
- **Rulebook fix:** L7: "Arrays inside the ORG make the CE the objective, far edge optional (068)."
- **BUILD SPEC (targets_partials):**
  - When the ORG is the draw, check for opposing OBs/FVGs (`Side.opposing`, 5m/15m zones) inside the gap range; if any, the CE becomes the final rung (`obj_stop` source) and the far edge is kept as a runner-only rung.
  - Params: `org_ce_if_flow: bool = False`.
  - Test: `test_org_ce_final_when_ob_inside`. ORG 4000-4020 with a bearish OB at 4012: final = 4010, runner rung 4000.

### 40. L7-org-lifetime-sr
- **rule_id / kind:** L7, shortened. Scope: index. judgment = false.
- **Rule:** Keep a list of daily ORGs (prior RTH close to 09:30 open) marked on RTH bars; project low, 25%, CE, 75% and high forward onto ETH charts. While active, an ORG above price is resistance and one below is support. Track per ORG whether price has traded through it upward and whether downward; it stays active after a one-way fill. If delivery in one direction stopped part-way, the pending draw = [partial-delivery extreme, far edge]. Lifetime switch: 5 trading days (068, ICT's personal filter) vs ~60 days (092: "about a month, maybe a month and a half"); 072 gives no number. A revisit of an ORG high/75%/CE in the bias direction counts only with another PD array nearby at a valid time (10-11, 14-15, 15-16) (092). NWOGs are exempt.
- **Sources:** 068_V0uV6lcgobQ ~00:09:51; 072_AKg_r0DIa3k ~00:23:03; 092_9MLRE-n6St8 ~01:59:32.
- **Quote:** "they'll eventually be offered buy side and sell side"
- **Conflicts:** lifetime: 060 3 days, 068/080 5 days, 092 ~60 days, 072 no number.
- **Rulebook fix:** L7: add the S/R use, both-way tracking, the partial-delivery remainder, ETH projection, and the lifetime list.
- **BUILD SPEC (levels_detectors):**
  - `ctx.org` keeps (a, b) pairs; `org_days` sets the count. New:
    - Store per ORG `up_done`, `dn_done` and `part_ext` (furthest point reached inside the gap per direction), updated from all bars (ETH included) since formation in `DayCtx`.
    - With `org_both_ways`, an ORG stays in `ctx.org` until both directions are done or the lifetime ends; its target levels in `_targets` become [part_ext, far edge] for the undone direction.
    - `org_days` accepts up to 60 (history widened via `nwog_days`-style trading-day count).
  - Params: `org_both_ways: bool = False` (and test `org_days` 5 vs 60).
  - Test: `test_org_partial_delivery_remainder`. ORG 4000-4020 filled up to 4012 only: pending upside levels 4012-4020.

### 41. L9-htf-fvg-target-ladder
- **rule_id / kind:** L9, unlisted_contradiction. Scope: general. judgment = true.
- **Rule:** Long into a 15m+ SIBI above (mirror for a short into a BISI below): levels = near edge, 25%, CE, 75%, far edge. Partial at the near edge; CE = session objective (exit all there per X12 in the default mode). Continue only if price closes through CE with expansion: next 75%, then the far edge. Switch htf_gap_final = 'CE' | 'far_edge': in far_edge mode keep the far edge as the next target after a CE reaction while the HTF bias (quarterly shift / weekly draw) is intact and no B8 invalidation fired. Variant (010, last hour, no further targets beyond): T1 near edge, T2 CE, T3 far edge minus 0.5-1.0 pt as the final exit (already in the Ep 08 appendix). A daily BISI formed by an up candle is a sell-side delivery target when bearish. If a REL/old-low pool lies just above an unfilled weekly BISI: targets pool -> BISI CE -> BISI far edge, and [our interpretation] suppress turtle-soup longs at that pool. Turtle soup toward an open daily FVG (cc04_012, FX pattern): T1 = REH below the FVG +1 tick, T2 = near edge, final = far edge. Keep old weekly FVG edges in the level list after they are traded through.
- **Sources:** 010_cWekmMLqiNM ~00:58:40; 029_dwJcsi3ddFg ~00:32:25; 098_PejS-nZTQlE ~01:01:48; 102_uzPM1CuSSx8 ~02:12:22; cc04_012_FgacYSN9QEo ~00:07:20.
- **Quote:** "you'll have a gradient four levels"
- **Conflicts:** L9 (049, 061, 065B): CE of a weekly gap is enough, far edge a ringer. 029: far edge only on a blow-off. 010, 098, 102, cc04_012: far edge / full fill expected and hit.
- **[our interpretation]:** the turtle-soup suppression above a weekly BISI.
- **Rulebook fix:** L9: add the quarter ladder, the `htf_gap_final` choice and the conflict list.
- **BUILD SPEC (targets_partials):**
  - Built/listed: `fvg_quadrants` (A5), L9 `fvg_remainder`, `weekly_gap_ce_only`. New:
    - `htf_gap_final: str = "ce"` ("ce" / "far_edge"). In the ladder, an HTF FVG's 75% and far edge are added only after a bar closes beyond its CE; in "far_edge" mode they stay while `htf.table` `flip` is unchanged.
    - `weekly_bisi_ts_block`: no turtle-soup long (`_turtle`) at a REL within `ts_max_pts` above an unfilled weekly BISI.
    - `keep_traded_wfvg`: weekly FVG edges stay "array" levels after being traded.
  - Params: `htf_gap_final: str = "ce"`, `weekly_bisi_ts_block: bool = False`, `keep_traded_wfvg: bool = False`.
  - Test: `test_htf_gap_ladder_far_edge_mode`. 15m SIBI 4120-4134: rungs 4120, 4123.5, 4127; 4130.5/4134 appear only after a close above 4127.

### 42. L10-older-daily-weekly-wick-ce
- **rule_id / kind:** L10, shortened. Scope: index. judgment = true.
- **Rule:** For each daily candle in the lookback (~5-20 trading days; 010, 015 "20 days"), compute upper (premium) wick CE = (high + max(o,c))/2 and lower (discount) wick CE = (low + min(o,c))/2, on daily candles only. Keep each level while it has not been traded through since it formed; after a touch keep it as a reference. Use as targets, partial levels, support/resistance, and the default draw when bias is neutral. Low/high of day: with bullish bias, the nearest unrevisited lower-wick CE below price that coincides with an intraday discount array is the expected low of day (allow ~2 ticks through); mirror for upper wicks. Weekly: wick CEs "several weeks" old (011); with bullish weekly bias the nearest untouched upper-wick CE above is the weekly objective. Treat 093 as a supporting example of the LOD role.
- **Sources:** 010_cWekmMLqiNM ~00:01:45; 015_QKvjPltjsqU ~00:31:48; 029_dwJcsi3ddFg ~00:06:08; 043_NkwqJBzgQwo ~00:04:29; 045_DNi9S3_NA44 ~00:17:02; 011_w0CYBeFTzcM ~00:05:22; 093_CcNOk_3O5wk ~00:06:48.
- **Quote:** "there's a premium wick it means it's the wick that's above the candle"
- **Conflicts:** none.
- **[our interpretation]:** lookback, the 2-tick tolerance, "coincides" = within 1 pt of a 5m/15m discount array.
- **Rulebook fix:** L10: wick CEs of older daily/weekly candles persist until traded; premium/discount wick naming; LOD/HOD role.
- **BUILD SPEC (levels_detectors):**
  - Built: `wick_days`, `wick_weekly`, `wick_both`. New:
    - `wick_untraded`: in `DayCtx`, for each of the last `wick_days` daily candles keep a wick CE only if no later daily bar traded through it (1 tick); weekly CEs from the last `wick_weeks` weeks the same way.
    - `wick_lod_tag`: in `_scan_core`, a sweep low within 2 ticks of an untraded lower-wick CE that also sits within 1 pt of a 5m/15m discount array gets `lv_tags["wick_lod"]` (and with "require" mode longs need it).
  - Params: `wick_untraded: bool = False`, `wick_weeks: int = 1`, `wick_lod_tag: str = "off"` ("tag" / "require").
  - Test: `test_old_daily_wick_ce_persists_until_traded`. Wick CE from 8 days ago untouched: present with wick_days=10; traded 3 days ago: absent.

### 43. L10-intraday-wick-ce
- **rule_id / kind:** L10 / A23, missing_condition. Scope: general. judgment = true.
- **Rule:** Add to A23/L10: (a) 1h wick CEs below price are discount arrays (above = premium) for retrace entries. If price trades through one, the next wick CE beyond is the next level (062, ES). (b) Fallback minimum objective: if the primary draw may not be reached, the CE of the most recent long 1h/4h wick toward the draw is the minimum target (058, FX, wick timeframe unclear). Partials before any wick CE in the path are already in the rulebook (line ~860).
- **Sources:** 062_sfRO5LrTgTA ~00:25:01; 058_hcSGlyfgKgA ~00:17:40.
- **Quote:** "there is another Wick right there"
- **Conflicts:** none.
- **[our interpretation]:** "long wick" = wick >= body and >= the 20-bar median wick of that TF.
- **Rulebook fix:** A23: 1h wick CEs step to the next one on failure; a wick CE is the fallback minimum objective.
- **BUILD SPEC (targets_partials):**
  - New helper in `levels`: `long_wick_ces(o,h,l,c, upper: bool, min_ratio)` on 1h/4h bars built via `htf_bars`.
  - (a) targets: add the nearest two 1h long-wick CEs beyond `above` as kind "array" (`wick_tfs` listed in A23; implement with "1h","4h").
  - (b) fallback: the nearest long 1h/4h wick CE before the primary draw becomes `pos["min_obj"]`; with X12 `obj_stop`, reaching it counts the idea as right (tag) and takes `min_obj_frac`.
  - Params: `wick_tfs: tuple = ()`, `min_obj_frac: float = 0.0`.
  - Test: `test_1h_wick_ce_ladder_steps`. Two 1h long lower wicks below: both CEs in the short ladder in order.

### 44. A23-1h-wick-ce-sweep-depth
- **rule_id / kind:** A23, missing_rule. Scope: index. judgment = true.
- **Rule:** Bullish bias, price consolidating under buy-side REH. Level = the CE of the longest lower 1h wick at the base of the consolidation, at or below the HTF gap low. If price sweeps the REL and reaches the CE (within 1-2 ticks), arm a long. Wait for an MSS (short-term high taken) and buy the retrace into the BISI it leaves (IOFED allowed). [our interpretation] Stop below the CE/sweep low; target the REH. [our interpretation] A 1h body close below the CE cancels it. Not every wick works.
- **Sources:** 063_qA9SCu4gGaU ~00:24:04.
- **Quote:** "how far can it go down below those relative equal lows to that Wick"
- **Conflicts:** none.
- **[our interpretation]:** stop placement and the 1h-close cancel.
- **Rulebook fix:** A23: "The CE of the longest 1h wick under a consolidation sets how deep a REL sweep goes before the long (063 ~24:04)."
- **BUILD SPEC (setups_models):**
  - In the `_scan_core` sweep block: with `wick_sweep_depth`, a sweep of a REL (`pool_eq` key) is valid for a long only if its extreme reaches within 2 ticks of the CE of the longest lower 1h wick among the last `wick_depth_bars` 1h bars below the REL, and no 1h body has closed below that CE. Stop = min(sweep low, CE) - pad. Target = REH (eq levels above).
  - Params: `wick_sweep_depth: bool = False`, `wick_depth_bars: int = 12`.
  - Test: `test_rel_sweep_needs_1h_wick_ce`. REL 4100, wick CE 4096: sweep to 4098 not armed, to 4096.25 armed.

### 45. L12-sd-activation
- **rule_id / kind:** L12 / D23, missing_condition (checker: not "wrong"). Scope: general. judgment = false.
- **Rule:** Arm an SD projection only when a candle body closes beyond the anchor extreme and price continues away (no immediate return). A wick tap through the extreme does not arm it (029). Up-projection: anchor low L and high H; project H + k(H-L), k = 0.5, 1, 1.5, 2, 2.5, 3; -0.5 = partial, -1 = measured move. Down mirror. Drop the projection if, after the break, price retraces through the invalidation (OB MT/BPR) instead of continuing. Add 026 (high to the fulcrum low, -0.5 partial, -1 measured move) to D23's down-leg sources.
- **Sources:** 008_cxdjcXec3eA ~00:06:39; 029_dwJcsi3ddFg ~00:21:45; 026_GFdWahZUNOw ~00:09:36.
- **Quote:** "it all just tap through it ... if it's a fulcrum point it's going to run right through it"
- **Conflicts:** terminology: 008's fulcrum is an intermediate level; 026/029's is the broken swing extreme.
- **Rulebook fix:** L12: arming = body close through the anchor extreme + continuation; D23: add 026.
- **BUILD SPEC (targets_partials):**
  - Listed: L12 `sd_anchor`. New `sd_arm: str = "trade"` ("trade" = current; "close" = SD levels are added to `_targets` only after a bar closes beyond the anchor extreme and the next `sd_arm_bars` bars do not close back inside).
  - Params: `sd_arm: str = "trade"`, `sd_arm_bars: int = 1`.
  - Test: `test_sd_arm_needs_close_through`. Wick through the anchor high and close back: no SD rungs; close above then a higher close: rungs present.

### 46. L12-sd-closes-not-wicks
- **rule_id / kind:** L12, missing_condition. Scope: general. judgment = true.
- **Rule:** Switch `sd_hit = 'touch' | 'close'`: in close mode an SD level counts as reached when a bar closes within 1-2 ticks of it; wicks may overshoot. Place the exit limit at or slightly before the level. Source: one FX example (008); test before adopting.
- **Sources:** 008_cxdjcXec3eA ~00:06:13.
- **Quote:** "you won't get the Wicks but you'll get the closing prices"
- **Conflicts:** none.
- **Rulebook fix:** L12: move the Ep 06 appendix note into the rule as a test switch.
- **BUILD SPEC:** already in rule_coverage (Ep06.4 `sd_close_hit` / `sd_close_window`, targets_partials). No new spec.

### 47. L12-sd-step-to-time-window
- **rule_id / kind:** L12, missing_condition. Scope: general. judgment = true.
- **Rule:** Once armed, list levels at k = 1, 1.5, 2, 2.5, 3, 3.5 ... When price reaches a level outside the target window, roll the target to the next one. Inside the window, the level reached on a close is the final target: exit there. Test against first-level-past-pool. The source is FX (008, London close 10:00-12:00); for index use the window is our mapping (e.g. AM 10:00-12:00 per T12, or the session's macro/turn window).
- **Sources:** 008_cxdjcXec3eA ~00:06:53.
- **Quote:** "and so on until it would meet a Time window like The Kill Zone"
- **Conflicts:** L12 (014, 030): use only the first SD level beyond the pool.
- **[our interpretation]:** the index window.
- **Rulebook fix:** L12: add the time-stop alternative and list the conflict.
- **BUILD SPEC (management_exits):**
  - With `sd_time_roll`, SD rungs (kind "proj") are not exit rungs before `sd_window[0]`; reaching one rolls the active final target to the next SD level. From `sd_window[0]` to `sd_window[1]`, the first SD level reached on a bar close is the final exit.
  - Params: `sd_time_roll: bool = False`, `sd_window: tuple = (600, 720)`.
  - Test: `test_sd_roll_until_window`. SD1 hit at 09:50 rolls; SD1.5 closed at 10:15 exits all.

### 48. L12-ref-rolls-to-new-high
- **rule_id / kind:** L12, missing_condition. Scope: index. judgment = false.
- **Rule:** ref = the original buy-side pool. Each new confirmed swing high above ref before the projection is evaluated sets ref = that high. For each anchored swing, target = the smallest hi + k*(hi-lo), k in {1, 1.5, 2, 2.5, ...}, strictly > ref; re-evaluate whenever ref changes. Mirror for bearish. (Specific prices in the claim are chart-read, not caption-verified.)
- **Sources:** 014_g8bhZReDK-Q ~00:03:27.
- **Quote:** "we have to refer to this frames the buy side now"
- **Conflicts:** none.
- **Rulebook fix:** L12: "The buy-side reference rolls to each newer higher high before picking the first SD level beyond it (014)."
- **BUILD SPEC (targets_partials):**
  - In `_targets` `sd_first_beyond` branch: compute `pool` as the max of the nearest pool and every confirmed pivot high (`sd.ph`, known <= i) above it formed since the anchor, not just the nearest pool. Re-run each bar (already per-bar).
  - Params: `sd_ref_roll: bool = False`.
  - Test: `test_sd_ref_rolls_to_newer_high`. Pool 4100.75, newer pivot 4101.50, SD levels 4101.00 / 4104.25: target 4104.25.

### 49. L12-cluster-anchors
- **rule_id / kind:** L12 / A1, missing_condition. Scope: index. judgment = true.
- **Rule:** [our interpretation] Bullish: anchor each ITL and LTL (A1 tiers) in the current up-leg, from its low to the high before it. Take each anchor's first SD level past the current buy-side ref (rolled per 014). A cluster = 3 or more such levels within 1-2 ticks; the 1-2 tick tolerance is already in L12. 014: two ITLs plus one LTL agreed at 4104.25, the high of day.
- **Sources:** 014_g8bhZReDK-Q ~00:03:48.
- **Quote:** "two times at intermediate term lows a long-term low"
- **Conflicts:** none.
- **[our interpretation]:** anchor set and the 3-level minimum.
- **Rulebook fix:** L12: name ITL/LTL anchors for clusters.
- **BUILD SPEC (targets_partials):**
  - Listed: `sd_anchor="multi"`, `sd_cluster_ticks`. New: `sd_multi_tiers: tuple = ("itl","ltl")`: the multi anchors come from `levels.swing_tiers` (built) lows in the leg, each paired with the pivot high before it; per anchor take the first level past ref (item 48). Levels within `sd_cluster_ticks` with count >= `sd_cluster_min` become one rung of kind "proj_cluster" (preferred as final target).
  - Params: `sd_multi_tiers: tuple = ()`, `sd_cluster_min: int = 3`.
  - Test: `test_sd_cluster_from_tiers`. Three tier anchors giving 4104.25, 4104.25, 4104.50: one cluster rung 4104.25.

### 50. L12-projection-exit-1tick
- **rule_id / kind:** L12 / X2 / D23, missing_condition. Scope: index. judgment = true.
- **Rule:** Anchor the fib at the trade's low (013: the 4063.25 entry low, which was the day's low) and a swing high after it that ICT points to on the chart (not named in the captions). Project the extension (which SD is not stated). Put the final runner limit 1 tick before the projected level (013: 4076 vs 4076.25). Take partials in the 85-100% zone of that best case (X3). Single example: tag/test only (sd_anchor='entry_low', exit 1 tick before the projection).
- **Sources:** 013_V1thfpo-R9U ~00:29:08.
- **Quote:** "the projection on that level takes you up to 40 76 and a quarter"
- **Conflicts:** X2: exit 0.5-1 pt before PD-array targets; 013: 1 tick before a projection.
- **[our interpretation]:** -1 SD of the leg (2x).
- **Rulebook fix:** D23: add the 013 anchor; X2: projections exit 1 tick before.
- **BUILD SPEC (targets_partials):**
  - Add `sd_anchor` value "entry_low": anchor lo = the fill bar's low (or the sweep low if lower), hi = the first confirmed pivot high after the fill; SD levels added mid-trade to `pos` ladder once that pivot confirms.
  - `_exit_px` for kind "proj": offset `proj_exit_ticks` ticks before the level (default X2 behaviour unchanged unless set).
  - Params: `proj_exit_ticks: int = 0` (0 = X2 default; test 1).
  - Test: `test_projection_exit_one_tick_before`. Projection 4076.25: exit limit 4076.00.

### 51. L12-cap-at-htf-array
- **rule_id / kind:** L12, missing_condition. Scope: index. judgment = true.
- **Rule:** After computing SD levels inside a session whose objective is an HTF FVG, ignore any SD level beyond that FVG's far edge (029: -3 SD at 4134.5 was outside the 15m FVG, so it was ignored). Use the in-range levels (-2 SD, the FVG CE, -2.5) as targets. The FVG's CE is a sufficient AM objective. (The "-1 SD caps the AM on low-expectation days" clause has no source and is dropped.)
- **Sources:** 029_dwJcsi3ddFg ~00:37:20.
- **Quote:** "outside the spectrum of the February 9th fair value Gap"
- **Conflicts:** none.
- **Rulebook fix:** L12: "Drop SD levels beyond the far edge of the session's HTF objective array (029)."
- **BUILD SPEC (targets_partials):**
  - In `_targets`, when `sd_cap_htf` and a 15m+ opposing FVG (htf_targets) lies beyond `above`, discard SD levels beyond the nearest such FVG's far edge.
  - Params: `sd_cap_htf: bool = False`.
  - Test: `test_sd_capped_at_htf_fvg`. 15m FVG 4122-4130.5, SDs 4126.25 / 4130.5 / 4134.5: 4134.5 dropped.

### 52. L12-prior-session-swing-htf-extreme
- **rule_id / kind:** L12 / D23, shortened. Scope: general. judgment = true.
- **Rule:** Anchor a fib on the 15m swing low to high that drove the move (bullish; mirror for bearish). Find the SD level that coincides with an HTF level (035: -1.5 SD = the daily wick CE). When price reaches it, and there is a correlated-asset SMT plus the approach of New York lunch, mark it as the likely intraday high. Take profit there and expect consolidation or a retrace rather than continuation. "Previous session" anchor and the no-new-longs filter are [our interpretation].
- **Sources:** 035_kFIOp8Tprdc ~00:38:13.
- **Quote:** "look for a standard deviation that gets to this level here which is consequent encroachment"
- **Conflicts:** none.
- **[our interpretation]:** anchor choice, "coincides" = within 1 ES pt, the no-new-longs filter.
- **Rulebook fix:** L12: "SD level = HTF level + SMT near lunch -> likely intraday high (035 ~38:13)."
- **BUILD SPEC (targets_partials):**
  - Add `sd_anchor` value "m15_leg": the last confirmed 15m pivot low -> pivot high pair (`tf_pivots` m=15). For each SD level within `sd_htf_tol` of an HTF level (daily wick CEs, `htf.table` arrays, rejection-block bodies), mark kind "proj_htf". In the ladder, a "proj_htf" rung reached with a recorded SMT (`_smt` result for the session) after 11:00 closes the trade and sets the session's long side done.
  - Params: `sd_htf_extreme: bool = False`, `sd_htf_tol: float = 1.0`.
  - Test: `test_sd_at_wick_ce_marks_intraday_high`. 15m leg 4100-4110, daily wick CE 4125: -1.5 SD 4125 is "proj_htf".

### 53. L12-sd-in-premium-consolidation
- **rule_id / kind:** L12, missing_condition. Scope: index. judgment = true.
- **Rule:** On a consolidation day, anchor on the latest up-leg (low, lower low, higher low, then fib low to high). Define the dealing range as the day's old high (043: 4034) down to the low. Choose the SD level (043: -1.5 = 4027.75) that lies in the premium of that range, beyond buy-side, and overlaps an old FVG or swing high, rather than the first level past the pool. Use it as the long target and as the short-reversal area in the last hour. Mirror for shorts.
- **Sources:** 043_NkwqJBzgQwo ~00:14:29.
- **Quote:** "it would be better for us to dig up into a premium because we're in consolidation"
- **Conflicts:** L12 (014, 030): first SD level beyond the pool.
- **[our interpretation]:** consolidation-day classifier (reuse N8.1 `consol_skip` predictor).
- **Rulebook fix:** L12: add the consolidation-day premium selection and list the conflict.
- **BUILD SPEC (targets_partials):**
  - With `sd_premium_consol` and the day tagged consolidation (N8 classifier from day_week_context), replace `sd_first_beyond` with: the first SD level beyond the pool AND above the 50% of [day low, day high so far]; prefer one within 1 pt of an old FVG edge or pivot high. Kind "proj".
  - Params: `sd_premium_consol: bool = False`.
  - Test: `test_sd_pick_premium_on_consolidation_day`. Range 4010-4034, SDs 4021 / 4027.75: picks 4027.75.

### 54. L12-minus3-sd-last-hour
- **rule_id / kind:** L12, unlisted_contradiction. Scope: index. judgment = true.
- **Rule:** Last-hour bearish setup: after the 15:00-hour MSS and breakaway FVG, anchor the fib from the swing high to the swing low of that leg (047 wording "this high to that low"). Project -1, -2, -3 SD. Treat -3 SD as a valid final target when reached in the 15:15-15:45 MOC macro (047: 4113.5 = low of day). Mirror for longs. Single observation: test k in {1, 2, 3} with sd_anchor='mss_leg'. Leg size not stated.
- **Sources:** 047_441vklRYYR4 ~00:10:59.
- **Quote:** "during the last hour of trading we have a negative three standard deviation"
- **Conflicts:** L12 (064, 065B): -2 is very extended; first level beyond the pool.
- **Rulebook fix:** L12: add the last-hour -3 SD observation and list the conflict.
- **BUILD SPEC (targets_partials):**
  - Add `sd_anchor` value "mss_leg" (swing high = sweep extreme, low = the MSS reference low broken). With `sd_last_hour_k` > 0, for entries at or after 15:00 the final target is the SD level k (no first-beyond rule), exit by 15:45.
  - Params: `sd_last_hour_k: float = 0.0` (test 1, 2, 3).
  - Test: `test_last_hour_sd_k3`. Leg 4128.5-4123.5, k=3: target 4108.5.

### 55. L13-old-high-to-daily-ce-projection
- **rule_id / kind:** L13, missing_rule. Scope: index. judgment = true.
- **Rule:** A = old daily high, B = CE of the next higher daily candle (019: 4090.75 and the Dec 13 candle CE, about 4117.5). Levels: the midpoint of A-B (019: 4104.25), then B, then B + k(B-A) for k = 0.25, 0.5, 0.75 and 1.0 (terminus, 019: 4144.25). Upside objectives on the daily chart; mirror for bearish. Tag/research only. The exact base of the 25-100% steps is inferred from the chart arithmetic.
- **Sources:** 019_ZrZJmwrMxFY ~00:02:35.
- **Quote:** "25 percent 50 75 in terminus"
- **Conflicts:** none.
- **Rulebook fix:** L13: add as a research projection.
- **BUILD SPEC (bias_htf, research):**
  - `htf.table` columns `dce_proj` (list of levels) built from daily pivots: A = latest untaken daily pivot high below the daily candle with the nearest higher body CE; levels as above. Report only: `study.py` adds a hit-rate table (`dce_proj` levels touched within 10 days).
  - Params: `dce_proj_study: bool = False`.
  - Test: `test_daily_ce_projection_levels`. A 4090.75, B 4117.5: 4104.125, 4117.5, 4124.19, 4130.875, 4137.56, 4144.25.

### 56. L13-org-sd-projection
- **rule_id / kind:** L13, shortened. Scope: index. judgment = true.
- **Rule:** U = ORG size (prior RTH close/settlement to the 09:30 open). Only after the ORG is completely repriced (traded back to the prior close), project multiples of U in the bias direction from the gap (055: 2 SD was near the day's high). Exit at or just before the projected level that overlaps the day's HTF draw (056: -11 SD = 4214.75, overlapping the buy-side/weekly VI target; exit a hair below). Otherwise use the levels as partials. The exact anchor edge is chart-dependent.
- **Sources:** 055_qiv8pkcNvGk ~00:19:31; 056_NeZlyG8FZLQ ~00:18:20.
- **Quote:** "once it's completely repriced then if we're bullish"
- **Conflicts:** none.
- **[our interpretation]:** anchor = the gap's far edge in the bias direction (gap high + kU for bullish).
- **Rulebook fix:** L13: add the reprice precondition, bias direction and overlap exit.
- **BUILD SPEC (targets_partials):**
  - Listed: L13 `proj_org_k`. Specify: levels added only after a bar since 09:30 trades to the prior close; direction = `want`; levels gap_hi + kU (k = 1..`proj_org_kmax`). A level within `sd_htf_tol` of the locked draw / an HTF array becomes kind "proj_htf" (final exit 1 tick before); others "proj" (partials).
  - Params: `proj_org_kmax: int = 12`.
  - Test: `test_org_projection_after_reprice`. ORG 4200-4205: nothing before 4200 trades; after, levels 4210, 4215, ...

### 57. L14-hold-above-reached-objective
- **rule_id / kind:** L14, missing_rule. Scope: index. judgment = true.
- **Rule:** Once the first objective (015: 4012) is reached and price trades above it, the next level up (015: 4035.25, an old daily high) remains the draw only while price holds above the reached level. Losing it cancels the higher draw. The exact trigger is [our interpretation], e.g. a 1m/5m body close back below it. Mirror for shorts.
- **Sources:** 015_QKvjPltjsqU ~00:28:03.
- **Quote:** "as long as we remained above 40 12 that we would see 4035 and a quarter"
- **Conflicts:** none.
- **[our interpretation]:** the 5m body-close trigger.
- **Rulebook fix:** L14: "The next draw holds only while price holds above the objective just reached (015)."
- **BUILD SPEC (management_exits):**
  - In the ladder loop, after a rung is passed, record it as `pos["held_lvl"]`. With `hold_reached`, a 5m body close back below it (side terms) exits remaining units and sets the session side done.
  - Params: `hold_reached: bool = False`, `hold_tf: int = 5`.
  - Test: `test_lose_reached_objective_exits`. Long, rung 4012 passed, 5m close 4011.5: exit rest.

### 58. L14-consolidation-alternation
- **rule_id / kind:** L14, missing_rule. Scope: general. judgment = true.
- **Rule:** Inside an intraday consolidation (index, 022/031), the next draw is the pool on the side opposite the most recent sweep. When counting runs since 08:30, favour the side that has been run fewer times and still has untaken highs/lows. If that pool is not reached before lunch, it carries to the PM 13:30-16:00 (031 ~1:04:20; T8). The rule to block trades toward the side already probed several times is our extrapolation, not ICT's words.
- **Sources:** 022_ALMsQytQ1fg ~03:04:38; 031_8YSVu51hUWQ ~01:02:53.
- **Quote:** "it's going to run from buy side to sell side, buy side to sell side"
- **Conflicts:** none.
- **[our interpretation]:** consolidation detection; the block.
- **Rulebook fix:** L14: add the alternation and run-count rule.
- **BUILD SPEC (bias_htf):**
  - In `run_day` keep `runs = {+1: n, -1: n}` since 08:30: increment when a session pool (`mark_levels` keys) is swept on that side. When the day is in an intraday range (`Chop.update` active, built), set `want` to the side with fewer runs; ties -> opposite of the last sweep. Carry into the PM when unmet (T8 `pm_carry_draw`, listed).
  - Params: `range_alternate: bool = False`, `range_block_probed: int = 0` (0 = off; else block the side swept >= n times).
  - Test: `test_range_alternation_want`. Two sell-side sweeps, one buy-side: want +1.

### 59. L14-conditional-pm-draw-up
- **rule_id / kind:** L14 / T8, missing_rule. Scope: index. judgment = true.
- **Rule:** If the AM runs its sell-side target (024: 4106.50, hit at 4106.00) but does not displace much further lower, the PM draw becomes a pre-marked opposing array above. In 024 this is a 5m FVG from a candle 3 trading days earlier (Feb 3 2023 12:55), and price is expected to reprice up into it 13:30-16:00. Mirror for bearish. "Much lower" is not quantified (our interpretation). That it is a bearish FVG/SIBI is inferred from context and not stated outright.
- **Sources:** 024_gH1e-TVrK6k ~00:08:36.
- **Quote:** "if we fail to go much lower ... the market would want to go back up into that"
- **Conflicts:** none.
- **[our interpretation]:** "much lower" = less than 0.25 x ADR5 beyond the target by 12:00.
- **Rulebook fix:** L14/T8: add the AM-fails-lower -> PM up conditional draw.
- **BUILD SPEC (bias_htf):**
  - At 13:30 in `run_day`: if the AM locked draw (`_lock_step` record) was hit and the AM extreme beyond it is < `pm_flip_adr` x ADR5, set PM `want` opposite and lock the draw to the nearest unfilled 5m/15m opposing FVG within the last `pm_flip_days` sessions (from `hist`).
  - Params: `pm_flip_draw: bool = False`, `pm_flip_adr: float = 0.25`, `pm_flip_days: int = 5`.
  - Test: `test_pm_flip_to_old_5m_fvg`. AM target 4106.5 hit, low 4106.0, 5m SIBI from 3 days ago at 4120: PM want +1, draw 4120.

### 60. L14-session-pools-only
- **rule_id / kind:** L14 / X1, missing_condition. Scope: index. judgment = true.
- **Rule:** Intraday draw candidates should be (or at least be prioritised to) the 067 session-range pools: previous PM 13:30-16:00 H/L, London 02:00-05:00 H/L, plus the ORG. Minor swing points outside these are "irrelevant". ICT says "predominantly", so this is a priority or filter switch rather than an absolute ban. Including lunch/AM ranges and REH/REL inside those windows is our extension, not stated at 00:27.
- **Sources:** 067_vuBRMFhFZAY ~00:27:37.
- **Quote:** "every little small little liquidity ... is irrelevant"
- **Conflicts:** none.
- **[our interpretation]:** lunch/AM ranges included in "extended" mode.
- **Rulebook fix:** L14/X1: add the 067 priority on session-range pools.
- **BUILD SPEC (targets_partials):**
  - `session_pools_mode: str = "off"` ("rank" = session pools sorted first in `_draw_prefs` and the sweep pick; "only" = `mark_levels` sweep pools and `_targets` pools limited to `sess` (prev_pm, london), ORG edges (`org_pools`) and PDH/PDL; "extended" adds lunch/AM and rel-eq inside those windows).
  - Params: `session_pools_mode: str = "off"`.
  - Test: `test_session_pools_only_filters_minor_swings`. A minor 5m swing high is not a pool in "only" mode; London high is.

### 61. L15-room-measure-anchors
- **rule_id / kind:** L15, shortened. Scope: index. judgment = false.
- **Rule:** Potential room = from the planned entry (the entry FVG's CE; 024: 4175.25) to the far edge (top) of the opposing HTF array (024: 15m SIBI high 4185), which price need not reach. In 024 he wants ~10 handles of potential to aim for a ~5 handle take; the actual run went ~7 to 4182. The 5-vs-10 threshold stays per owner correction #2. The take-profit sits below the far edge.
- **Sources:** 024_gH1e-TVrK6k ~00:25:13.
- **Quote:** "that's essentially what 10 handles and that's like the minimum threshold"
- **Conflicts:** bot `min_draw_pts` measured to the draw's exit price; 024 to the array's far edge.
- **Rulebook fix:** L15: define the endpoints (entry -> far edge of the opposing HTF array).
- **BUILD SPEC (targets_partials):**
  - In `_finish_order` (room check, owner #2): `room_ref: str = "exit"` ("exit" = current; "htf_far" = |far edge of the nearest opposing 15m+ array beyond entry - entry|, falling back to "exit" when none). Threshold stays `min_draw_pts`.
  - Params: `room_ref: str = "exit"`.
  - Test: `test_room_to_htf_far_edge`. Entry 4175.25, 15m SIBI 4180-4185, min 10: passes in "htf_far", fails in "exit" (exit 4179.5).

### 62. L15-first-sth-offering-5
- **rule_id / kind:** L15 / X1, shortened. Scope: index. judgment = false.
- **Rule:** Long T1 = the nearest short-term-high pool at least 5 ES pts above the entry, passing over closer pools that do not offer 5 handles (012: 4139.82). Exit just beyond it (X2). Drop the claim that ICT expects 2+ five-handle runs before noon on most days: it was a homework exercise and can at most be a reporting tag.
- **Sources:** 012_HkiPAi1Mdu8 ~00:32:07.
- **Quote:** "why that one because it's going to offer five handles easy"
- **Conflicts:** none.
- **Rulebook fix:** L15/X1: "T1 = the first pool >= 5 handles away; nearer pools are skipped, not trade-killers (012)."
- **BUILD SPEC (targets_partials):**
  - In `_finish_order`, with `t1_skip_near`, instead of rejecting (`x_room_lt_min`) when the nearest pool is < `min_draw_pts`, drop pools nearer than `min_draw_pts` from the ladder and take the next pool as T1; reject only if none remains.
  - Params: `t1_skip_near: bool = False`.
  - Test: `test_t1_skips_pool_under_5`. Entry 4134, pools 4136, 4139.82: T1 4139.82.

### 63. L15-5-handle-legs
- **rule_id / kind:** L15, missing_rule. Scope: index. judgment = true.
- **Rule:** Count completed 5-ES-pt legs in the trade direction (reporting/partials). ~3 legs (~15 handles) is what one day can accumulate (009, one example). Anchoring the grid to multiples of 5 is our implementation choice; ICT counts 5-handle moves along the run, not on a fixed price grid.
- **Sources:** 009_tnxvmHq8xEg ~00:17:52.
- **Quote:** "each one will potentially accumulate to 15 handles"
- **Conflicts:** none.
- **[our interpretation]:** leg = a run of >= 5 pts from a pivot low to a pivot high (no fixed grid).
- **Rulebook fix:** L15: move the appendix line into the rule as a reporting stat.
- **BUILD SPEC (day_week_context, reporting):**
  - In `backtest` day summary add `legs5_bias`: count of 1m pivot-to-pivot legs >= 5 pts in the session's `want` direction 09:30-16:00; `study.py` prints its distribution. No trading effect.
  - Params: none (always reported).
  - Test: `test_count_5pt_legs`. Swings 4000-4006-4003-4009-4004-4010: 3 legs.

### 64. X1-old-daily-close
- **rule_id / kind:** X1, missing_rule. Scope: index. judgment = true.
- **Rule:** Level type old_daily_close: a past daily close (009: Dec 14 2022 close 4030, about a month old) chosen before the week as the draw/target in the bias direction, used as the main target (009 took 9 of 14 off there). ICT does not say why that close was chosen or that it must be untouched since. "Nearest untraded daily close in the bias direction within 60 days" is our interpretation.
- **Sources:** 009_tnxvmHq8xEg ~00:01:29.
- **Quote:** "open high low and close is all you need"
- **Conflicts:** none.
- **Rulebook fix:** X1: add old_daily_close as a target type.
- **BUILD SPEC:** already in rule_coverage (Ep07.1 `close_draw`: unrealized prior closes, the weekly draw as a pool; targets_partials). No new spec.

### 65. X1-london-0300-fvg-draw
- **rule_id / kind:** X1 / L9, missing_rule. Scope: index. judgment = false.
- **Rule:** Pre-mark unfilled 5m FVGs formed in the overnight/London session (018: the 03:00 ET one) on the bias side of price as the morning draw. Expect the AM to reprice into it: core exit at entry + 5 handles + 0.25 (4059.25, inside the gap), and leave a runner (2 contracts) for a higher level in or at the gap (4061.50). Whether 4061.50 is the FVG's far edge is not stated. Nothing in 018 says the 03:00 origin itself matters beyond it being the gap he flagged.
- **Sources:** 018_eTMS36H7HA0 ~00:03:49.
- **Quote:** "reaching up into that three o'clock in the morning fair value Gap"
- **Conflicts:** none.
- **Rulebook fix:** X1: add unfilled overnight 5m FVGs as AM draws.
- **BUILD SPEC (targets_partials):**
  - `htf_targets` covers 15m+. Add `overnight_5m_fvgs`: 5m FVGs (`zones_tf(…,5)`) formed 18:00-09:30 (ETH data) and unfilled at 09:30, beyond `above`, added as kind "array" (near edge, CE, far edge) and eligible as the AM locked draw.
  - Params: `overnight_5m_fvgs: bool = False`.
  - Test: `test_overnight_5m_fvg_target`. 5m SIBI formed 03:00 at 4057-4062, untouched: long ladder contains 4057, 4059.5, 4062.

### 66. X1-htf-ob-open-target
- **rule_id / kind:** X1 / A12, missing_rule. Scope: general. judgment = false.
- **Rule:** When the draw is an opposing weekly (or daily) OB and no inefficiency lies between price and it (B2 order), aim for its near edge (bullish OB approached from above: its high) and, specifically, the OB candle's open as the main target. Transpose both levels to lower timeframes. Source is FX-only (058 EURUSD/DXY weekly). Applying it to index futures is an extrapolation.
- **Sources:** 058_hcSGlyfgKgA ~00:08:20.
- **Quote:** "touch that candles high and or opening price specifically is what I'm aiming for"
- **Conflicts:** none.
- **Rulebook fix:** X1/A12: opposing HTF OB as draw: near edge, then its open.
- **BUILD SPEC (targets_partials):**
  - `htf._arrays` holds D/W OBs. In `_targets` (HTF arrays branch), for an opposing D/W OB add its near edge and its open (kind "array"); with `htf_ob_open_final`, the open is the final target when no FVG/VI lies between `above` and the OB.
  - Params: `htf_ob_open: bool = False`, `htf_ob_open_final: bool = False`.
  - Test: `test_weekly_ob_open_target`. Weekly bullish OB h 4000 o 3990 below a short: rungs 4000, 3990; final 3990.

### 67. N6-news-pool-mapping
- **rule_id / kind:** N6, missing_rule. Scope: index. judgment = true.
- **Rule:** On high-impact event days he would not trade (NFP, FOMC, Fed chair testimony), as a study exercise only, before the event: annotate the 5m/15m buy-side pools (swing highs not revisited) and the sell-side lows near price (mark a close low cluster as likely to be run). Watch which pool the event move takes first, then whether it goes on to the other. If price approached a pool before the event without taking it, his own speculation (not a rule) is: the opposite pool first, then the approached pool, then the FVG beyond it. Observation tag only, no entries.
- **Sources:** 037_wu0sQarBRrI ~00:11:55.
- **Quote:** "the highs that haven't been returned to"
- **Conflicts:** none.
- **Rulebook fix:** N6: add the pre-event mapping as a study exercise.
- **BUILD SPEC (news_calendar_times, study):**
  - `study.py` adds `news_pool_study`: for FOMC/NFP/testimony days (`calendar`), snapshot 5m/15m untaken pivot highs/lows within 1 x ADR5 of price 1 minute before release; log which side's nearest pool is taken first after release and whether the other is taken later. No trades.
  - Params: none (study flag `--news-pools`).
  - Test: `test_news_pool_first_taken`. Synthetic release bar runs the high first: record side +1, then -1 later.

### 68. new-sibi-protected-lows-fx
- **rule_id / kind:** new, missing_rule. Scope: fx_only. judgment = true.
- **Rule:** [fx-only, single source, Sunday outlook] In a bullish context, if price trades above an opposing SIBI (bearish FVG), do not expect the swing low beneath it to be retested before the buy-side above is taken. Minimum objective = roughly the halfway point of the move he marked toward the buy-side (the anchors are ambiguous; about 1.0900-1.0905 EURUSD in his example). The invalidation clause is our inference, not his.
- **Sources:** 011_w0CYBeFTzcM ~00:03:49.
- **Quote:** "should not come back to be retested until these are taken out"
- **Conflicts:** none.
- **Rulebook fix:** FX-only list: add the protected-low note.
- **BUILD SPEC:** none (fx_only).

### 69. new-range-edge-break-retest
- **rule_id / kind:** new, missing_rule. Scope: index. judgment = true.
- **Rule:** After the AM (044), mark the session range: the NWOG high above, and the low plus the FVG below. A bullish PM draw to the next HTF level (4104) is active only if price trades above the upper edge, then holds it as support on the retrace, then runs higher. A bearish draw (to the farther sell-side) needs price to break significantly below the low and below the FVG; no retest is stated. If neither has happened by 14:30, no PM/last-hour trade (overlaps T9).
- **Sources:** 044_LN1nfYp4dBw ~01:58:07.
- **Quote:** "it needs to trade above it treat it as support and then run higher"
- **Conflicts:** none.
- **[our interpretation]:** "holds" = the retrace low stays >= edge - 1 tick; "significantly below" = beyond the FVG's far edge.
- **Rulebook fix:** new rule under L14: break-hold-run for the upper edge; clean break for the lower; T9 14:30 cut-off.
- **BUILD SPEC (bias_htf):**
  - At 12:00 compute `pm_range = (lo_edge, hi_edge)` from the AM (hi_edge = nearest NWOG/gap edge or AM high above, lo_edge = AM low or the FVG below's far edge). In the PM, set `want` +1 only after: trade above hi_edge, a pivot low >= hi_edge - 1 tick, then a new high; set `want` -1 after a trade below lo_edge. If neither by 870 (14:30), mark the PM done.
  - Params: `pm_range_break: bool = False`.
  - Test: `test_pm_range_break_hold_run`. Break above 4098, retrace to 4097.75, new high: want +1; no break by 14:30: done.

### 70. new-reactionary-high-liquidity
- **rule_id / kind:** new, missing_rule. Scope: general. judgment = true.
- **Rule:** During a down leg, shorts' trailed stops sit above the most recent reactionary high (the swing high that launched an energetic leg lower); update it as newer such highs form. That high is the buy-side liquidity a retracement reaches for. After a deep-discount move, if no FVG/VI lies between price and the recent 15m swing highs, the retracement target is the buy stops above those single highs or REH. With the low intact, expect the run there next session, then look for an MSS + FVG to short back toward the lows. Mirror for up legs.
- **Sources:** 046_VLis0LcbUaQ ~00:56:01; 099_v_iJlBKYmUc ~00:51:16.
- **Quote:** "this is exactly where everybody's trailed stop losses are sitting"
- **Conflicts:** none.
- **[our interpretation]:** reactionary high = a pivot high whose following leg contains a displacement bar (A20 test); "+1 tick" target.
- **Rulebook fix:** new rule under L4: reactionary-high (trailed-stop) liquidity.
- **BUILD SPEC (levels_detectors):**
  - `levels.reactionary_highs(o,h,l,c, pivots, disp_mult)`: pivot highs followed by a displacement leg; keep the latest untaken one per side. Add as "pool" with tag `reactionary` in `_lv_target_pools`, and prefer it over nearer minor highs when picking a counter-trend (retracement) draw in `_draw_prefs`.
  - Params: `reactionary_pools: bool = False`.
  - Test: `test_reactionary_high_pool`. Pivot 4120 then a 3-bar displacement down: pool 4120 present; a later minor pivot 4110 without displacement is not.

### 71. new-friday-asian-range-fx
- **rule_id / kind:** new, missing_rule. Scope: fx_only. judgment = false.
- **Rule:** For Monday FX trading, use the Asian range (20:00-00:00 NY) of the prior Friday session, not Sunday's.
- **Sources:** 046_VLis0LcbUaQ ~00:17:56.
- **Quote:** "I don't look at the Asian range on Sundays for Monday's trading"
- **Conflicts:** none.
- **Rulebook fix:** FX-only list: add the Friday-for-Monday Asian range substitution.
- **BUILD SPEC:** none (fx_only).

### 72. M3-sb-extended-htf-target
- **rule_id / kind:** M3, missing_rule. Scope: index. judgment = true.
- **Rule:** SB T1 = the opposing pool beyond entry (e.g. REL), minimum 5 handles. Optional "over-zealous" T2 = the HTF imbalance (FVG) beyond that pool, flagged in the higher-timeframe analysis. It may be reached after 11:00 within the same session. The timeframe of the HTF FVG and the exact exit offset are our parameters.
- **Sources:** 047_441vklRYYR4 ~00:08:26.
- **Quote:** "if you want to be over zealous with your objectives"
- **Conflicts:** none.
- **[our interpretation]:** 1h FVG, exit at its near edge minus 0.5 pt.
- **Rulebook fix:** M3: add the optional T2 beyond the pool.
- **BUILD SPEC (silver_bullet):**
  - In `sb_model._arm`, with `sb_t2="htf_fvg"`, append the near edge of the nearest unfilled 1h (or `sb_t2_tf`) opposing FVG beyond T1 as the runner target; the runner may be held after the window until the AM session end.
  - Params: `sb_t2: str = "off"`, `sb_t2_tf: int = 60`.
  - Test: `test_sb_t2_htf_fvg_runner`. SB short T1 REL 4100, 1h FVG top 4092: runner target 4092.5.

### 73. M3-fx-sb-15-pips
- **rule_id / kind:** M3 / L15, missing_rule. Scope: fx_only. judgment = false.
- **Rule:** [fx-only, single source] FX Silver Bullet (EURUSD): room from the FVG entry to the target (here the rejection block, the lowest close of the down-close candles) should be more than 15 pips; he treats that as making the setup valid. FX analogue of L15; fix L15's 059 citation.
- **Sources:** 059_ZfnY2SH3G24 ~00:10:36.
- **Quote:** "is it more than 15 pips to to offer a short? Yes."
- **Conflicts:** none.
- **Rulebook fix:** L15: move the 059 citation to an FX note "SB room > 15 pips".
- **BUILD SPEC:** none (fx_only).

### 74. new-parent-pool-bodies-short
- **rule_id / kind:** new, missing_rule. Scope: general. judgment = true.
- **Rule:** Given an earlier swing low L0 and several later lows in the same area whose candle bodies all stop short of (stay above) L0, L0 is the parent swing and the real sell-side pool. Target it, not the intermediate lows, which serve as partial levels at most. Our codification: n >= 2 later lows with min(open, close) > L0's low; target 1 tick below L0. Mirror for highs. Single source, hindsight.
- **Sources:** 050_F509lJRrYIM ~00:56:39.
- **Quote:** "the parent price swing and liquidity pool is this one"
- **Conflicts:** none.
- **[our interpretation]:** n >= 2, "same area" = within 0.25 x ADR5 above L0.
- **Rulebook fix:** new rule under A2/L4: parent pool by bodies stopping short.
- **BUILD SPEC (levels_detectors):**
  - `levels.parent_pools(o,h,l,c, lows, n_min, band)`: for each pivot low L0, count later pivot lows within `band` above it whose body low > L0.low and untaken L0; if >= n_min, emit L0 as kind "pool_parent". In `_draw_prefs`, a "pool_parent" beyond the intermediate lows is the draw; the intermediates become rungs only.
  - Params: `parent_pools: bool = False`, `parent_n: int = 2`.
  - Test: `test_parent_pool_bodies_short`. L0 4000, later lows 4001/4002 with bodies 4003/4004: draw 4000.

### 75. B2-stacked-unrun-highs
- **rule_id / kind:** B2, missing_rule. Scope: general. judgment = true.
- **Rule:** When successive swing highs are left unrun while price retraces lower and keeps holding an HTF (weekly/daily) discount FVG, treat the stacked buy-side above those highs as the primary draw. Expect each dip to be bought (offsetting longs from the lows). Targets are the nearest high, then the higher stacked highs, then any REH sitting inside an HTF premium VI/FVG. Mirror for stacked lows. The minimum count of stacked highs is our parameter (ICT gives none); test 2 vs 3.
- **Sources:** 055_qiv8pkcNvGk ~00:04:19.
- **Quote:** "they're not really seeing any runs on liquidity which means that they're stacking that up"
- **Conflicts:** none.
- **[our interpretation]:** count, "holding" = no daily close below the FVG CE.
- **Rulebook fix:** B2: add stacked unrun highs as the primary draw while an HTF discount array holds.
- **BUILD SPEC (bias_htf):**
  - New `htf.table` column `stack_side`: +1 when >= `stack_n` daily pivot highs since the last daily low are untaken AND the latest close is inside/above an unfilled W/D BISI (from `_arrays`) with no daily close below its CE; mirror -1. With `stack_draw`, `want = stack_side` when nonzero, and the draw = the nearest stacked high.
  - Params: `stack_draw: bool = False`, `stack_n: int = 3`.
  - Test: `test_stacked_highs_bias`. Three lower daily highs untaken, price in a daily BISI: stack_side +1.

### 76. L2-sr-needs-fvg
- **rule_id / kind:** L2 / new, shortened. Scope: general. judgment = false.
- **Rule:** An old swing low that price has broken becomes resistance on a retrace only if an FVG from the breaking leg overlaps it and the HTF bias agrees; expect the rejection at the FVG CE/near edge. Mirror: an old high projected forward is support only with an overlapping bullish FVG (076: the CE of a Reaper/breaker FVG). Without an FVG the old level carries no S/R weight. Switch vs L2's "any PD array".
- **Sources:** 058_hcSGlyfgKgA ~00:13:34 (and ~53:36); 076_cgsltOB736E ~00:21:21.
- **Quote:** "classic support resistance is only confirmed if it has one of my fair value gaps"
- **Conflicts:** L2 (Ep 08; 010): any PD array plus time of day suffices; 058/076: an FVG is required.
- **Rulebook fix:** L2: add the FVG requirement as an alternative and list the conflict.
- **BUILD SPEC (levels_detectors):**
  - Listed: L2 `daily_level_needs_array`. Add value: `daily_level_needs_array: str` "any" (current True) / "fvg". In "fvg" mode an old high/low counts as an S/R entry level (flip retest) only if an FVG from the breaking leg has its range within 1 tick of the level; the entry is the FVG CE.
  - Params: extend `daily_level_needs_array` to accept "fvg" (bool True = "any").
  - Test: `test_flip_level_needs_fvg`. Broken low 4000 with a bearish FVG 3998-4002 from the break: short at 4000; without the FVG: no setup.

### 77. new-shallow-rel-sweep-one-more-drive
- **rule_id / kind:** new / M3, missing_rule. Scope: general. judgment = true.
- **Rule:** If price trades only a few ticks below REL and bounces, treat the sell-side run as incomplete: no long. Expect a retrace into the nearest FVG/mitigation block (a sell), then one more drive lower that clears the stops under the REL and the lows below. Look for longs only after that deeper run plus an MSS (short-term high taken) and an FVG/OB entry. This conflicts with M3/057 ~4:18 (a 1-2 tick dip below the draw before the SB fill is acceptable); make it a switch.
- **Sources:** 060_ZtLMTXv-Dr0 ~00:59:18.
- **Quote:** "that little shallow run tells me that any retracement higher is just going to be one more Drive Lower"
- **Conflicts:** M3 (057 ~4:18).
- **[our interpretation]:** shallow = < `shallow_ticks` ticks (default 4).
- **Rulebook fix:** new rule; list the conflict with M3/057.
- **BUILD SPEC (setups_models):**
  - In the `_scan_core` sweep block: with `shallow_sweep_wait`, a REL sweep whose depth < `shallow_ticks` ticks does not arm; it records `pending_drive`. The next sweep of the same side's lows (deeper than the first) arms normally.
  - Params: `shallow_sweep_wait: bool = False`, `shallow_ticks: int = 4`.
  - Test: `test_shallow_rel_sweep_needs_second_drive`. Sweep 2 ticks: no order; later sweep 2 pts deeper + MSS: order.

### 78. B2-buy-program-eq-draw
- **rule_id / kind:** B2, missing_rule. Scope: general. judgment = false.
- **Rule:** After a bullish MSS (close above the short-term high) inside a prior bearish HTF leg, state = BUY_PROGRAM. Dealing range = the HTF swing high to swing low of that bearish leg (weekly in 061). Target = the first unmitigated PD array (FVG/IFVG/OB/VI) at or above 50% of that range. Until it is reached: no shorts, including runs above internal or short-term highs. Every short-term discount PD array is a long candidate. On the hit -> neutral. Mirror for SELL_PROGRAM.
- **Sources:** 061_wWvXWmC_gqU ~00:45:42 (and ~2:34:41).
- **Quote:** "we're looking for the first first equilibrium or higher PD array"
- **Conflicts:** none.
- **Rulebook fix:** B2: add the buy/sell program state.
- **BUILD SPEC (bias_htf):**
  - New `htf.table` column `program` (+1/-1/0) on daily bars: +1 after a daily close above the last daily short-term high while the weekly leg (last weekly pivot high -> low) is bearish; target `program_tgt` = first unmitigated W/D array (from `_arrays`, vi included) with bottom >= that leg's 50%; resets to 0 when a daily high reaches it. With `program_gate`, `want = program` when nonzero and the locked draw = `program_tgt`.
  - Params: `program_gate: bool = False`.
  - Test: `test_buy_program_state_and_target`. Weekly leg 4200->4000, daily MSS up, daily SIBI 4110-4120: program +1, target 4110.

### 79. new-leg-grading-quadrants
- **rule_id / kind:** new / A21, missing_rule. Scope: general. judgment = true.
- **Rule:** Leg = origin O to predefined draw D. O is the low that started the post-MSS run (061), the broken old high once a candle closes above it (075), or the HTF OB / known extreme (cc03). Grades O + k(D-O) for k = 0.25/0.5/0.75. Expect stop hunts / REL sweeps in the first quadrant, consolidation near 0.5, and expansion from 0.75 toward D. Look for PD-array entries (FVG/OB) that form near 0.25-0.5. The grades locate setups; they are not entries or exits by themselves. Tolerance, partials and invalidation are our parameters to test. Mirror bearish.
- **Sources:** 061_wWvXWmC_gqU ~02:07:40; 075_vN2BkfyRWE4 ~01:35:57; cc03_001_UF5J0nEBc0E ~00:38:09; cc03_003_t2VNzJZ4hK4 ~00:22:14.
- **Quote:** "these horizontal lines they're areas at which the market should see new setups"
- **Conflicts:** none.
- **[our interpretation]:** tolerance (one FVG height or 5% of the leg); invalidation beyond O.
- **Rulebook fix:** A21: add the projected-leg grading.
- **BUILD SPEC (setups_models):**
  - With a locked draw D (`_lock_step`) and origin O (`leg_origin`: "mss_low" = the low of the leg that made the MSS; "session_low"), compute grades. In `setups.finish_gates`, tag `grade_q` for the entry (q1..q4); with `leg_grade_gate="require"`, longs only when the entry lies in [O, O + 0.5(D-O)] + tolerance. Cancel pending longs on a close below O.
  - Params: `leg_grade_gate: str = "off"` ("tag" / "require"), `leg_origin: str = "mss_low"`, `leg_grade_tol: float = 0.05`.
  - Test: `test_leg_grade_entry_zone`. O 4000, D 4100: entry 4040 ok, 4070 rejected in require mode.

### 80. new-gap-theory
- **rule_id / kind:** new / L7, missing_rule. Scope: general. judgment = false.
- **Rule:** For any gap (ORG, NWOG, NDOG, FVG, liquidity void) that price trades into: if it overlaps the gap and closes below the gap low, the low is resistance and price continues lower. If it fills and rallies, holding the gap high, the high is support and price continues higher. While inside the gap, the CE decides: holding above CE favours bullish, below CE bearish. Mirror for a gap above price.
- **Sources:** 065_rx15_eN9sxI ~04:53:00.
- **Quote:** "it fills the Gap rallies up treats the higher the Gap is support"
- **Conflicts:** none.
- **Rulebook fix:** new general rule under L7/A8: gap theory for all gap types.
- **BUILD SPEC (bias_htf):**
  - New intraday state in `run_day`: `gap_state` per active gap (ctx.gaps ETH gaps, ctx.org today, 15m FVGs): +1 when a 5m close is above the gap high after trading into it, -1 when a 5m close is below the gap low, CE side while inside. With `gap_theory_bias`, the nearest active gap's state overrides `want` for the session when it disagrees with neutral (only sets `want` when the daily bias is 0).
  - Params: `gap_theory_bias: bool = False`.
  - Test: `test_gap_theory_state`. ORG 4000-4020: 5m close 4021 after trading inside -> +1; close 3999 -> -1.

### 81. M14-reversal-threshold
- **rule_id / kind:** M14, unlisted_contradiction. Scope: index. judgment = true.
- **Rule:** TGIF zone = 20-30% retrace of the weekly range from the extreme (25% midpoint). A Friday retrace beyond the zone hints at a longer-term reversal (top/bottom). 066 gives the threshold as "beyond 30%" (~25:34) and as "40% or more" (~18:12). Switch reversal_flag_pct = 0.30 | 0.40. Any bot action on the flag is our choice.
- **Sources:** 066_wTR-vhOdMgo ~00:25:34 (and ~18:12).
- **Quote:** "if it goes behind Beyond 30 percent that could indicate an all-out reversal"
- **Conflicts:** 066 ~18:12: 40% or more; 066 ~25:41: beyond 30%.
- **[our interpretation]:** the flag's use (next-week tag only).
- **Rulebook fix:** M14: list both thresholds as a contradiction.
- **BUILD SPEC (day_week_context):**
  - Listed: M14.2 `tgif_zone` (stand down at 40%). New: make that stand-down threshold `tgif_reversal_pct` (0.30 / 0.40) and write a weekly tag `wk_reversal_flag` for the next week (reported, no trading effect).
  - Params: `tgif_reversal_pct: float = 0.40`.
  - Test: `test_tgif_reversal_flag_threshold`. Friday retrace 35%: flag at 0.30, none at 0.40.

### 82. L7-org-later-day-entry-array
- **rule_id / kind:** L7, missing_condition. Scope: index. judgment = true.
- **Rule:** Compute each ORG from RTH bars only (prior RTH close to 09:30 open) and track the part not yet traded through. On later days (lifetime per L7), when price returns to that unfilled part from the bias side, its high, upper quadrant (75%) and CE are possible entry-reaction levels, used only if (a) the bias agrees, (b) another PD array (FVG/OB/breaker) sits within a few ticks, and (c) the time is inside 03-04, 10-11, 14-15 or 15-16, as a Silver Bullet or 2022-model entry. Never trade the ORG level alone. Bearish mirror. Switch: require_confluence on (092) / off (080 shows bodies holding the ORG top with no second array named).
- **Sources:** 080_XODINFwpeaw ~00:13:20; 092_9MLRE-n6St8 ~01:59:32.
- **Quote:** "not by itself with other PD arrays"
- **Conflicts:** 080 uses the ORG top alone; 092 never alone.
- **[our interpretation]:** "a few ticks" = 4 ticks.
- **Rulebook fix:** L7: add later-day entry use with the 092 gate and list the conflict.
- **BUILD SPEC (setups_models):**
  - In `setups.array_cands` (entry arrays), with `org_entry_array`, add prior-day ORG levels (from `ctx.org[:-1]`, unfilled part per item 40) as candidate entry levels when the entry bar time is in `org_entry_windows` and `want` agrees; with `org_entry_confl`, require another candidate array within `org_confl_ticks`.
  - Params: `org_entry_array: bool = False`, `org_entry_confl: bool = True`, `org_confl_ticks: int = 4`, `org_entry_windows: tuple = ((180,240),(600,660),(840,900),(900,960))`.
  - Test: `test_prior_org_entry_needs_confluence`. Friday ORG top 4500, Monday 10:15 retrace with an FVG at 4500.5: long; without FVG: no entry (confl on).

### 83. L7-org-breaker-inside
- **rule_id / kind:** L7, missing_condition. Scope: index. judgment = false.
- **Rule:** For an ORG being filled downward: if a breaker (high, low, higher high) formed inside the gap range, set the fill target or partial at the low of the breaker's down-close candle and expect price to stop there instead of reaching the prior close. Mirror for an upward fill: the high of the breaker's up-close candle. A breaker always gets the chance to be respected before a full gap closure is expected.
- **Sources:** 072_AKg_r0DIa3k ~00:32:02.
- **Quote:** "you want to consider where that down closed candles low is"
- **Conflicts:** none.
- **Rulebook fix:** L7: add the breaker-inside-ORG fill stop.
- **BUILD SPEC (targets_partials):**
  - When building ORG levels in `_targets`, look for breakers (`levels.breakers`, built, 5m) whose zone lies inside [org lo, org hi]; for a downward fill add the breaker candle's low as kind "array" and, with `org_breaker_stop`, make it the final rung (prior close kept only as a runner rung).
  - Params: `org_breaker_stop: bool = False`.
  - Test: `test_org_fill_stops_at_inner_breaker`. ORG 4000-4020, bearish breaker candle low 4008: final 4008.

### 84. L12-bodies-hold-sd-continuation
- **rule_id / kind:** L12, missing_rule. Scope: index. judgment = true.
- **Rule:** After price reaches SD level S in the bias direction: if later candle bodies hold S (no body close back through it; small wicks beyond are allowed) and the next draw is not yet taken, read it as continuation and keep runners on. A body close back through S against the bias = treat S as the turn.
- **Sources:** 070_1HtRfFYiwO0 ~00:52:10.
- **Quote:** "confirmed one more time with the bodies that means it's going to go higher"
- **Conflicts:** none.
- **[our interpretation]:** hold check on 5m bodies over the next 3 bars.
- **Rulebook fix:** L12: add "bodies holding an SD level = continuation".
- **BUILD SPEC (management_exits):**
  - In the ladder loop, for a "proj" rung reached: with `sd_body_hold`, defer its partial (keep units) while 5m bodies stay beyond S; a 5m body close back through S takes the rung's partial and arms the trail (`trail_ref` body). Default behaviour unchanged.
  - Params: `sd_body_hold: bool = False`.
  - Test: `test_sd_bodies_hold_keeps_runner`. Rung 4496.5 reached, 5m bodies 4497-4499: no partial; body close 4495: partial.

### 85. B2-target-beyond-pool-inefficiency
- **rule_id / kind:** B2, shortened. Scope: general. judgment = true.
- **Rule:** To size a run through a pool, consider only FVGs/OBs lying beyond the pool and ignore arrays between price and the pool. If one sits just beyond the pool, the pool and that array form the run's objective (071: take the stops, then reach into the FVG/OB). If none lies beyond, target the rejection block (the lowest down-close body, mirror: the highest up-close body) or the next relative-equal pool beyond.
- **Sources:** 071_3FGFEuaDSOc ~00:22:18; 104_iKsIbUblSWM ~00:22:24.
- **Quote:** "don't look at this one because that's above that low"
- **Conflicts:** none.
- **[our interpretation]:** "just beyond" = within 0.25 x ADR5.
- **Rulebook fix:** B2: arrays between price and the pool are excluded; fallback to the rejection block / next REL.
- **BUILD SPEC (targets_partials):**
  - With `beyond_pool_final`: after `_targets`, find the draw pool P; final target = the nearest FVG/OB near edge beyond P within `beyond_pool_adr` x ADR5; else the rejection-block body edge (`levels.rejection_blocks`, A17 listed) beyond P; else the next "pool_eq" beyond P. Arrays between price and P stay as partial rungs only.
  - Params: `beyond_pool_final: bool = False`, `beyond_pool_adr: float = 0.25`.
  - Test: `test_final_target_array_beyond_pool`. Short, low 4000, FVG top 3996 beyond: final 3996; FVG at 4005 (inside) not final.

### 86. new-pool-break-accel-vs-reject
- **rule_id / kind:** new, missing_rule. Scope: general. judgment = true.
- **Rule:** When price trades below a sell-side pool: if it accelerates through it (displacement: large bodies closing well below, an FVG left), the next draw is the deeper sell-side pool; if it trades below and then rejects (closes back above the low), expect the range to persist and do not target the deeper pool yet. Mirror for buy-side. Source is DXY weekly/daily (072 ~1:21), so tag it as timeframe-general [our interpretation for the acceleration test] and validate on index data before using it.
- **Sources:** 072_AKg_r0DIa3k ~00:01:21.
- **Quote:** "does it accelerate if it does then ... reach below here for the sell side"
- **Conflicts:** none.
- **[our interpretation]:** the displacement test (A20).
- **Rulebook fix:** new rule under L14: branch on acceleration vs rejection after a pool is taken.
- **BUILD SPEC (targets_partials):**
  - In `_targets` for an active trade's ladder refresh: when the next-pool rung beyond a just-taken pool exists, keep it only if the break bar(s) passed the A20 displacement test (`disp_mult`) and left an FVG; if the break closed back inside, remove deeper pools for the session.
  - Params: `break_accel_gate: bool = False`.
  - Test: `test_deeper_pool_only_after_acceleration`. Slow break and close back: deeper pool dropped; 2 large bars + FVG: kept.

### 87. L1-prior-day-london-pm-pools
- **rule_id / kind:** L1, missing_condition. Scope: index. judgment = false.
- **Rule:** Add the prior-day London 02:00-05:00 high and low as pools, alongside today's London high/low and the previous PM range L1 already has. Each stays a pool until traded through by 1 tick.
- **Sources:** 072_AKg_r0DIa3k ~00:27:52.
- **Quote:** "we rip lower to take out the London session"
- **Conflicts:** none.
- **Rulebook fix:** L1: add the prior-day London H/L.
- **BUILD SPEC (levels_detectors):**
  - In `DayCtx.__init__`, from `hist[-1]` ETH bars 120-300 add `self.sess["prev_london"] = (hi, lo, 0)` when `prev_london_pool`; `_targets` and `mark_levels` pick it up through the existing `sess` loops (`extra_pools`).
  - Params: `prev_london_pool: bool = False`.
  - Test: `test_prev_day_london_pool`. Yesterday's London high 4120 untaken today: buy-side pool 4120.

### 88. new-old-pool-redelivery
- **rule_id / kind:** new, missing_rule. Scope: general. judgment = true.
- **Rule:** After a buy-side pool is taken and price reverses, the old pool level is a possible re-delivery target on the way back down (price revisits it like an inefficiency), not a support level to buy. Use it as a target only when there is another reason for the draw (it lines up with the bias or draw). Mirror for sell-side.
- **Sources:** 072_AKg_r0DIa3k ~00:36:04.
- **Quote:** "every old liquidity pool acts like an inefficiency"
- **Conflicts:** none.
- **[our interpretation]:** "another reason" = within 1 pt of another level in the ladder or in the `want` direction.
- **Rulebook fix:** new rule: taken pools are re-delivery targets, not support.
- **BUILD SPEC (targets_partials):**
  - Today's swept pools are known in `mark_levels` (`spent`). With `swept_pool_targets`, add each swept pool level as kind "array" for trades in the opposite direction of its sweep, only when `want` agrees with that trade or another ladder level lies within 1 pt. Never use it as an entry level (exclude from `array_cands`).
  - Params: `swept_pool_targets: bool = False`.
  - Test: `test_swept_high_is_short_target`. BSL 4100 swept then short from 4110, want -1: rung 4100.

### 89. L13-breaker-range-sd-weekly
- **rule_id / kind:** L13, missing_rule. Scope: general. judgment = true.
- **Rule:** Bullish breaker: once the lower low L2 sweeps the swing low L1, the measuring range runs from L1 (fib 1) to the swing high H between them (fib 0). -1 SD = H + (H-L1); -2 SD = H + 2(H-L1) = projected weekly range high. Expect price to trade through H, come back to H with bodies respecting it, then expand toward the SDs. Use only when a strong HTF bias in the breaker direction is set and the breaker is valid. Bearish mirror.
- **Sources:** 074_N4am6Jsp8N8 ~00:30:15, ~00:31:20.
- **Quote:** "it qualifies this as a bullish ICT breaker so this is your measuring range"
- **Conflicts:** none.
- **[our interpretation]:** "strong bias" = weekly and daily bias agree.
- **Rulebook fix:** L13: add -1/-2 SD of the breaker range as weekly extreme, with the strong-bias condition.
- **BUILD SPEC (targets_partials):**
  - Listed: L13 `proj_breaker` (B + 1x). Add `proj_breaker_k: tuple = (1.0,)`; test (1.0, 2.0) on 1h breakers (`levels.breakers` on 60m bars). Gate on `weekly_bias(...) == want == daily bias`. The -2 SD rung is kind "proj_wk" and is used as the final target for trades held to the week (management_exits: no forced EOD only if `hold_overnight`, else just a ladder rung).
  - Params: `proj_breaker_k: tuple = (1.0,)`.
  - Test: `test_breaker_range_minus2_sd`. L1 15700, H 15780: rungs 15860, 15940 with k=(1,2).

### 90. new-fvg-wick-ce
- **rule_id / kind:** new, missing_rule. Scope: general. judgment = true.
- **Rule:** When a bullish FVG's boundary candle has a long lower wick beyond the gap, allow the retrace through the FVG down to that wick's CE. Respect should hold between the wick's upper 75% level and its CE. Ladder or limit down to the wick CE and invalidate only on a body close below the wick CE. Mirror for bearish.
- **Sources:** 075_vN2BkfyRWE4 ~01:04:11.
- **Quote:** "it's likely to go into this consequent encroachment not just filled in that Gap"
- **Conflicts:** none.
- **[our interpretation]:** "long wick" = wick >= body of that candle.
- **Rulebook fix:** new rule under A5/A23: FVG plus adjacent wick.
- **BUILD SPEC (entries_stops_sizing):**
  - In the `_scan_core` entry/stop block: with `fvg_wick_ce`, if the entry FVG's c1 (bullish) has lower wick >= body, set entry = wick CE (or ladder between the FVG CE and the wick CE with `entry="ladder"`), stop = wick CE - 1 tick on a close basis (exit only on a body close below; hard stop at the wick low).
  - Params: `fvg_wick_ce: bool = False`.
  - Test: `test_fvg_entry_extends_to_wick_ce`. BISI 4010-4014, c1 o 4012 c 4011 l 4004: entry 4007.5.

### 91. new-eq-stop-hunt-entry
- **rule_id / kind:** new, missing_rule. Scope: general. judgment = true.
- **Rule:** In a bullish program, when a retrace reaches the dealing-range EQ and a short-term low forms there, expect a run of that low before continuation. Do not stop under it. After the sweep, buy the return into the nearest bullish array that is holding (inversion FVG, reclaimed OB, or FVG CE), with the stop beyond the sweep extreme. Mirror for bearish.
- **Sources:** 075_vN2BkfyRWE4 ~01:31:00.
- **Quote:** "equilibrium is where you're going to anticipate ... a stop hunt"
- **Conflicts:** none.
- **[our interpretation]:** "at EQ" = within 10% of the range around 50%.
- **Rulebook fix:** new rule under A21/E6: expect a stop hunt at EQ; enter after it.
- **BUILD SPEC (setups_models):**
  - In the sweep block: a sweep of a short-term low (pool_swings) whose level lies within `eq_hunt_band` of the dealing-range EQ (`pd_day_range`, A21 listed) gets tag `eq_hunt`; with "prefer", such sweeps rank first in the session's sweep pick. Stops for these trades use stop_mode "sweep".
  - Params: `eq_hunt: str = "off"` ("tag" / "prefer"), `eq_hunt_band: float = 0.10`.
  - Test: `test_eq_stop_hunt_tag`. Range 4000-4100, short-term low 4049 swept: tagged.

### 92. new-prev-day-range-eq-long
- **rule_id / kind:** new, missing_rule. Scope: general. judgment = false.
- **Rule:** After a bullish expansion day that took a key high, let R = [the prior day's 00:00 NY open price, the prior day's high]. Today, expect a drop into the prior day's range and buy at or below EQ(R). Exception: if a Reaper (an FVG in the discount half of the impulsive leg) lies below EQ(R), allow price through EQ and expect support at the Reaper (its CE). Mirror for bearish. The caption reads "equilibrium or higher"; treat it as at or below.
- **Sources:** 076_cgsltOB736E ~00:20:09.
- **Quote:** "the best fills for getting long is going to be at equilibrium"
- **Conflicts:** none.
- **Rulebook fix:** new rule: prior-day midnight-to-high EQ as the long reference after an expansion day.
- **BUILD SPEC (setups_models):**
  - `DayCtx`: `prev_mid_open` = hist[-1] open at 00:00 (ETH), prev high; `prev_took_key` = prev high > max(pdh2, pw high) (key high taken). With `prev_eq_long` and `want` +1 and `prev_took_key`, longs only at entry <= EQ(R); if `levels.reaper` (built) finds a reaper on yesterday's leg below EQ, allow entries down to its CE instead.
  - Params: `prev_eq_long: bool = False`.
  - Test: `test_prev_day_eq_long_gate`. R 4000-4100: entry 4060 blocked, 4045 allowed.

### 93. L14-consolidation-above-ssl
- **rule_id / kind:** L14, missing_rule. Scope: index. judgment = true.
- **Rule:** 15m, index: if price rejects an HTF array (e.g. a BPR) and consolidates directly above a cluster of lows, the early-week draw is that SSL plus the inefficiency just below it. The read holds while price stays below the most recent 15m short-term high. Acceptance above it (or a daily close above Friday's high) cancels it, but a brief run above that high followed by a collapse does not. Observe on Monday and trade from Tuesday. Mirror for bullish.
- **Sources:** 077_OnFifO44Kzo ~00:14:58.
- **Quote:** "unless we get above this High here I think it warrants a a probe of lower sell side"
- **Conflicts:** none.
- **[our interpretation]:** "acceptance" = a 15m close above the high followed by another 15m close above it.
- **Rulebook fix:** L14: add the consolidation-above-lows early-week draw.
- **BUILD SPEC (bias_htf):**
  - Weekly state computed at the Sunday open from 15m bars: if the last 15m 8+ bars overlap within 0.3 x ADR5 above a 15m rel-eq low cluster, after a rejection at a D/4h array (`htf` arrays), set `wk_ssl_draw` = that cluster low (and the FVG below). Monday: tag only; Tue+: `want` -1 until acceptance above the latest 15m pivot high.
  - Params: `wk_ssl_draw: bool = False`.
  - Test: `test_consolidation_above_lows_draw`. Cluster at 15000, consolidation 15010-15030: Tue want -1, draw 15000.

### 94. new-level-confluence-scoring
- **rule_id / kind:** new, missing_rule. Scope: general. judgment = true.
- **Rule:** Rank candidate levels by how many independent arrays or levels converge on them (an FVG edge or CE, OB MT, wick CE, a candle high or low, session H/L), with HTF (monthly or weekly) array CEs counting most. Always plot the CEs of HTF arrays. Weights and tolerances are a bot choice (not from ICT): exact tick match for same-TF levels, a small tolerance across TFs. Prefer the highest-ranked levels for entries and final targets. On intraday arrays, a body close through a confluence level invalidates it. Monthly and weekly levels may be probed into their MT and revisited several times.
- **Sources:** 078_FQqwmDJOtxk ~00:48:23; 094_2AC4IKTj2ug ~00:06:04; cc06_005_soY9zX3gt2U ~00:28:58.
- **Quote:** "the more levels that converge around a specific price level the more likely"
- **Conflicts:** none.
- **[our interpretation]:** weights M=3, W=2, D=1, 4h/intraday=0.5; tolerance 1 tick same TF, 0.1% across.
- **Rulebook fix:** new rule: level confluence ranking.
- **BUILD SPEC (targets_partials):**
  - `confluence.py` already scores zones. Add `level_score(level, sources)` over all ladder levels (`_targets` output before merge, with their TF origin). With `confl_rank`, the final target = the highest-scoring level beyond the first rung (ties: nearest); entries in `setups.array_cands` sort by score.
  - Params: `confl_rank: bool = False`, `confl_tol_frac: float = 0.001`.
  - Test: `test_level_confluence_score`. 15m SIBI high 4100 = monthly FVG CE 4100: score 3.5, final target.

### 95. L14-conditional-draw-upper-taken
- **rule_id / kind:** L14, wrong. Scope: general. judgment = false.
- **Rule:** Pre-session: primary draw U (upper pool) and alternate D (lower pool). If price fails to reach U, switch the draw to D. Once U trades 1 tick through, cancel D for the session and keep drawing in U's direction (the next pool or PD array beyond U). Mirror when the primary is below.
- **Sources:** 080_XODINFwpeaw ~00:17:01.
- **Quote:** "because we got that fifteen thousand zero twenty is not likely"
- **Conflicts:** none.
- **Rulebook fix:** L14: replace "once taken the low draw is spent" with "once the UPPER pool is taken, the lower alternate draw is cancelled".
- **BUILD SPEC:** already in rule_coverage (L14e `cond_draw`: failed upper draw -> lower side, spent flag; bias_htf). Build it with the spent flag set when U trades. No new spec.

### 96. X1-opposing-breaker-target
- **rule_id / kind:** X1, shortened. Scope: index. judgment = false.
- **Rule:** For a short, after the sell-side pool targets, the next target is the nearest opposing bullish breaker below. Exit as price digs into the breaker zone (its high toward MT). Mirror for longs at a bearish breaker.
- **Sources:** 086_bDOyDitJZi4 ~00:15:30.
- **Quote:** "the bullish breaker level down here so it digs into it"
- **Conflicts:** none.
- **Rulebook fix:** X1: add breakers to the opposing PD-array list.
- **BUILD SPEC:** already in rule_coverage (A22 `matrix_targets`: breakers, mitigation and rejection blocks as targets; targets_partials). No new spec.

### 97. M14-tgif-daily-fvg-ce-cap
- **rule_id / kind:** M14, missing_rule. Scope: index. judgment = true.
- **Rule:** TGIF Friday (index): mark the daily FVG nearest above price; its CE is the maximum Friday rally. Short on the LTF at or below it, with the stop just above the longest wick's CE (above the daily FVG CE). Targets: just below the previous day's low, the low end of the daily FVG, and the TGIF 20-30% weekly-range band. (Clause not from ICT: no short if bodies accept above the CE.) 089 was an NFP Friday, an explicit exception to N1.
- **Sources:** 089_h0yOpwSilnE ~00:02:57.
- **Quote:** "the market could trade up to that level on Friday"
- **Conflicts:** none (N1 NFP exception noted).
- **[our interpretation]:** the body-acceptance cancel.
- **Rulebook fix:** M14: add the daily FVG CE ceiling and target list.
- **BUILD SPEC (day_week_context):**
  - Within the listed `tgif_model`: add `tgif_fvg_cap`: on TGIF short Fridays, the short entry must be <= the CE of the nearest daily SIBI above the open (from `htf.table` arrays); stop = max(that CE, the longest-wick CE of the last 5m swing) + 1 tick; ladder = PDL - 1 tick, the daily FVG low (if below), then the `tgif_zone` band. Cancel shorts after two 5m closes above the CE.
  - Params: `tgif_fvg_cap: bool = False`.
  - Test: `test_tgif_fvg_ce_cap`. Daily SIBI 15500-15560 (CE 15530): short at 15525 allowed, 15540 blocked.

### 98. D23-inception-fulcrum-anchor
- **rule_id / kind:** D23, wrong. Scope: general. judgment = false.
- **Rule:** D23: replace the "manipulation leg (092)" label with "inception-to-fulcrum leg (092 ~1:21:26; 090 ~1:34:04)". Bearish: anchor 1 = the high where the down move began (inception); anchor 0 = the fulcrum low of that run. Activate only after the fulcrum low trades through (with speed, per 090). SD_k = fulcrum - k(inception - fulcrum), k = 0.5, 1, 1.5, 2, 2.5. Use the levels that converge with a pool or PD array. 090's best-case swing exit is -1. Mirror for bullish.
- **Sources:** 090_bhYcXBI3z9U ~01:34:04; 092_9MLRE-n6St8 ~01:21:26.
- **Quote:** "this is where the Inception of the move began right here and the fulcrum point is right there"
- **Conflicts:** D23 labels the 092 anchor as the manipulation leg.
- **Rulebook fix:** D23: relabel the 092 anchor; cite 090.
- **BUILD SPEC (targets_partials):**
  - Listed: `sd_anchor` "fulcrum". Specify it as inception -> fulcrum: inception = the highest high since the last opposite MSS (bearish), fulcrum = the first displacement leg's low; levels added only after a bar trades through the fulcrum (with `sd_arm="close"` from item 45 if set). Rename the doc label in `models.md` (D23 note) and Params comment. Keep `sd_levels` (0.5-2.5).
  - Params: none new (value "fulcrum" defined as above).
  - Test: `test_inception_fulcrum_sd`. Inception 15680, fulcrum 15665.75: -1 SD 15651.5 after a trade below 15665.75.

### 99. L12-deep-sd-pd-convergence
- **rule_id / kind:** L12, unlisted_contradiction. Scope: general. judgment = true.
- **Rule:** Compute SD_k for k = 1..3 in steps of 0.5. The first SD past the pool (here -2) is the base target. Deeper SDs (-2.5, -3) count only when they land on a PD-array level beyond the pool, within a few ticks (an FVG edge or CE on 5m/15m). The deepest such SD+array convergence is the best-case runner target, and a 1-2 tick wick past it (mohawk) still counts. Our choice: ranking and tick tolerance. Switch vs L12 first-level-only.
- **Sources:** 092_9MLRE-n6St8 ~01:25:18.
- **Quote:** "I'm looking for a a convergence of stand deviations and reaching into specific PD arrays"
- **Conflicts:** L12 (014; 030): only the first SD past the pool; 092: deeper SDs where they converge.
- **[our interpretation]:** tolerance 2 ticks.
- **Rulebook fix:** L12: add the deep-SD convergence switch and the conflict.
- **BUILD SPEC (targets_partials):**
  - With `sd_deep_conv`, after the `sd_first_beyond` level, also keep deeper SD levels that lie within `sd_conv_ticks` of a 5m/15m FVG edge/CE (`zones_tf`); the deepest kept is kind "proj_runner" (final runner target), others "proj".
  - Params: `sd_deep_conv: bool = False`, `sd_conv_ticks: int = 2`.
  - Test: `test_deep_sd_kept_on_fvg`. SDs -2/-2.5/-3, 15m BISI CE = -3 SD: -3 kept as proj_runner, -2.5 dropped unless at an array.

### 100. L6-ndog-ce-premium-filter
- **rule_id / kind:** L6, missing_rule. Scope: needs_unavailable_data. judgment = true.
- **Rule:** Short: the up-close retrace/entry candle should sit in the premium half of the current NDOG (above its CE). A later down-close candle trading below the CE confirms the delivery. Long mirror. 1m bars, confluence only (L6).
- **Sources:** 092_9MLRE-n6St8 ~00:45:52.
- **Quote:** "this up close candle is in the premium side of that new day opening Gap"
- **Conflicts:** none.
- **Rulebook fix:** L6: add the NDOG CE premium/discount use.
- **BUILD SPEC:** none (needs the futures 17:00-18:00 data).

### 101. new-defended-level
- **rule_id / kind:** new, missing_rule. Scope: general. judgment = true.
- **Rule:** For each candidate level, count bars/swing touches inside a band of X points around it in the lookback. If >= M (X and M are ours, by test), mark it "defended": not a target, and trade away from it (longs off a defended low, shorts off a defended high). Clean, untouched levels (A3) stay the preferred targets.
- **Sources:** cc01_007_22XkhpJR5eA ~00:24:23.
- **Quote:** "that is indicating a levels being defended"
- **Conflicts:** none.
- **[our interpretation]:** X = 0.1 x ADR5, M = 4 touches.
- **Rulebook fix:** A3: add the defended-level inverse.
- **BUILD SPEC (targets_partials):**
  - In `_targets`, with `defended_filter`, count bars in the last `defended_bars` (5m) whose high (for a level above) is within X of the level; drop pools with count >= M. Report dropped levels as `lv_tags["defended"]`.
  - Params: `defended_filter: bool = False`, `defended_band_adr: float = 0.1`, `defended_touches: int = 4`, `defended_bars: int = 200`.
  - Test: `test_defended_high_not_target`. Five 5m highs within 0.5 pt of 4100: 4100 removed.

### 102. L14-weekly-two-sided-map
- **rule_id / kind:** L14, missing_rule. Scope: general. judgment = true.
- **Rule:** At the midweek review mark two HTF draws: a premium draw (the nearest unfilled HTF inefficiency above plus its buy-side) and a discount draw (the nearest undelivered HTF inefficiency below). The extension is the next sell-side pool beyond the discount draw, flagged as overzealous for the week. Default bias is the current theme's draw. Each session, take only setups whose target is one of the two draws, using time-of-day for which one price reaches for. The ordering and retrace permission are ours.
- **Sources:** 099_v_iJlBKYmUc ~00:34:25.
- **Quote:** "premium up here discount down here"
- **Conflicts:** none.
- **[our interpretation]:** "midweek" = Wednesday's prior close; "theme" = `want`.
- **Rulebook fix:** L14: add the two-draw weekly map.
- **BUILD SPEC (bias_htf):**
  - `htf.table` columns `wk_prem_draw` / `wk_disc_draw` from Tuesday's close (daily/4h unfilled arrays nearest above/below). With `wk_two_draw`, from Wednesday `_finish_order` keeps an order only if its locked draw or final target lies within 1 pt of either draw level (or between price and it).
  - Params: `wk_two_draw: bool = False`.
  - Test: `test_weekly_two_draw_filter`. Draws 4150 / 4050: a long targeting 4130 rejected, targeting 4150 kept.

### 103. B7-spike-floor-1h-ob-fvg
- **rule_id / kind:** B7, missing_rule. Scope: general. judgment = true.
- **Rule:** When the daily OB MT is pierced intraday with no daily close below it, the acceptable spike floor is the nearest 1h bullish OB below the MT that has an FVG right after it. The exact level inside the OB (open/MT) is ours. Holding there keeps the bias and makes it a candidate discount long. A trade through it or a daily close below the MT = B7 failure. Bearish mirror. Not for NFP days (101 is study-only).
- **Sources:** 101_VElIka5sk0E ~00:38:37.
- **Quote:** "here's your order block right there and it has a fair value gap"
- **Conflicts:** none.
- **[our interpretation]:** the floor = the 1h OB low; candidate entry at its open.
- **Rulebook fix:** B7: add the intraday spike floor.
- **BUILD SPEC (bias_htf):**
  - In `run_day`, when B7 is active (daily bullish OB MT in force) and price trades below the MT intraday: find the nearest 1h bullish OB below with an FVG on the next two 1h bars (`levels.order_block` + `levels.fvgs` on `htf_bars(…,60)`). While price stays above its low, keep `want` +1 and add its open as an entry candidate (`array_cands`); a trade below its low sets `want` 0 for the day. Skip on NFP days.
  - Params: `b7_spike_floor: bool = False`.
  - Test: `test_b7_spike_floor_keeps_bias`. Daily MT 4000, 1h OB 3985-3992 with FVG: low 3988 keeps want +1; 3984 sets 0.

### 104. new-lookback-per-tf-topdown
- **rule_id / kind:** new, missing_rule. Scope: general. judgment = false.
- **Rule:** Build the level set top-down: daily (9-12 months, not multi-year) -> 4h (3 months) -> 1h (>= 3 weeks) -> 15m (>= 3-4 days). Each lower TF inherits the higher-TF levels and adds its own recent untested highs/lows, clean equal highs/lows and levels price moved quickly away from. Tag each level with its source TF; higher TF ranks higher (ranking is ours).
- **Sources:** cc01_003_B7_cjybYQ0g ~00:13:38, ~00:18:23.
- **Quote:** "your daily chart needs to show 12 months no less than nine months view"
- **Conflicts:** none.
- **Rulebook fix:** new rule: per-TF scan windows and top-down transfer.
- **BUILD SPEC (levels_detectors):**
  - Add `tf_lookback: dict = {}` (e.g. {"D": 252, "4h": 63, "1h": 15, "15m": 4} in trading days). `htf.table` and `DayCtx` HTF array builders (`_arrays`, `zones_tf`, `tf_pivots`) cut their history to these windows when set; each level carries `tf` for ranking (used by `confl_rank`, item 94, and `pool_rank`).
  - Params: `tf_lookback: dict = field(default_factory=dict)`.
  - Test: `test_tf_lookback_cuts_history`. A daily pivot 300 days old is excluded with D=252.

### 105. L4-fx-stop-run-overshoot
- **rule_id / kind:** L4, missing_rule. Scope: fx_only. judgment = false.
- **Rule:** [fx-only] On 15m/intraday, expect a stop run to extend 10 or 20 pips beyond an old high/low, including at 20/40/60-day IPDA extremes, before rejection. On 1h and higher, use the double top/bottom (consolidation) range projection instead of pip grades. No index mapping is given; do not port without a test.
- **Sources:** cc01_004_qC0LogyIk2I ~00:51:04; cc02_003_pctqB3UD6dk ~00:06:42; cc04_014_owq30ATPU5s ~00:13:10; cc05_003_LRKtiysz4nA ~00:31:10.
- **Quote:** "10 and 20 pip ranges above a high that's how far they'll reach for a stop"
- **Conflicts:** none.
- **Rulebook fix:** FX-only list: add the 10/20-pip overshoot.
- **BUILD SPEC:** none (fx_only).

### 106. L15-min-3r-final-draw
- **rule_id / kind:** L15, missing_rule. Scope: general. judgment = false.
- **Rule:** R = |entry - stop|. Take a setup only if the reward it permits (to the final draw) is >= 3R. Partials may come earlier (cc02_001 example: half at 1R, BE after 2R, runner to 5R). Swing: require the distance to the closest opposing array among the 4h/daily/weekly/monthly maps to be >= 3R, preferably more. Param min_rr_final = 3 (test 2, 3, 5).
- **Sources:** cc02_001_mjVHmE1gVMg ~00:05:22; cc05_013_crPpMwgwa7k ~00:08:25; cc06_003_g--tikwaupk ~00:22:38.
- **Quote:** "trade setups that permit three reward multiples to one risk or higher"
- **Conflicts:** bot `min_rr=1` on T1 only.
- **Rulebook fix:** L15: add the CC 3R floor to the final draw.
- **BUILD SPEC (targets_partials):**
  - In `_finish_order`, after the ladder is built: with `min_rr_final > 0`, reject when (final target - entry)/risk < `min_rr_final` (side terms). Final target = the locked draw if present, else the last ladder rung. T1's `min_rr` check unchanged.
  - Params: `min_rr_final: float = 0.0` (test 2, 3, 5).
  - Test: `test_min_rr_final_draw`. Risk 4, final 10 pts away: rejected at 3, accepted at 2.

### 107. new-void-fill-target
- **rule_id / kind:** new (kind corrected to shortened, A10/X1). Scope: general. judgment = true.
- **Rule:** Extend A10 and add void fill to X1's target list. Bearish void = consolidation followed by one or more large down candles with few or no up-close candles inside. Full fill = back to the low of the last up-close candle before the drop (the bearish OB, about the open of the first big down candle). cc01_006 says a partial fill into the void, short of that OB low, is acceptable, so use the void top as the final target and the void's interior/CE as a partial. Exit per X2 (PD-array buffer). False-flag short (cc02_007, a false bull flag in a bearish market): T1 = close the void the false flag left, then the bearish OB/lows. Bullish mirror.
- **Sources:** cc01_006_SiVmoeyOWZE ~00:10:28; cc02_007_cRbPS3uxkj4 ~00:17:38; cc04_010_HTQgH11W37o ~00:06:47.
- **Quote:** "first objective would be to close the quality void"
- **Conflicts:** cc01_006 says the void need not fill completely; cc04_010 expects price to cover the entire range.
- **[our interpretation]:** "large" candle = range >= 1.5 x the 20-bar mean; "few up-close" = at most 1.
- **Rulebook fix:** A10/X1: void top level, partial at the interior, X1 target type.
- **BUILD SPEC (targets_partials):**
  - Listed: A10 `void_targets`, `leg_start_target`. Specify: `levels.voids` (built) currently returns gap-like voids; add `levels.one_sided_legs(o,h,l,c, mult, max_opp)` returning (top = low of the last opposite-close candle before the leg, bottom = leg end). With `void_targets`, add CE (kind "array") and top (final, kind "array") of the nearest such leg beyond `above` on 5m/15m/1h.
  - Params: `void_leg_mult: float = 1.5`, `void_max_opp: int = 1`.
  - Test: `test_one_sided_leg_void_target`. Up candle low 4100 then three big down candles to 4070: long rungs 4085, 4100.

### 108. X2-body-based-pool-levels
- **rule_id / kind:** X2, missing_condition. Scope: general. judgment = false.
- **Rule:** Add param target_ref = 'wick' | 'body' (CC default 'body'; 2023 index sources use the wick). Body mode: an old-high pool = max(open, close) of the candles forming the high/cluster, exit just above that body level. An old-low pool = min(open, close), exit just below it (cc04_006: "just below the lowest open or close"). The wick extreme is an optional runner level. Note the conflict with X2 [2023] (beyond the wick extreme) and that the CC rationale is about the retail FX feed.
- **Sources:** cc02_008_pv2-R-STviA ~00:09:09; cc03_002_PQkcFbr61FI ~00:07:06; cc04_006_oALYX0HCSYw ~00:14:27.
- **Quote:** "don't always demand that price gets below the wicks"
- **Conflicts:** X2 [2023] exits beyond the wick extreme.
- **Rulebook fix:** X2: add the CC body-based pool level as a switch and list the conflict.
- **BUILD SPEC:** already in rule_coverage (A17 `pool_body_edge`, the 2023 body-edge pool; targets_partials). No new spec; when building it, also keep the wick extreme as a runner rung.

### 109. L13-sweep-low-measured-move
- **rule_id / kind:** L13, shortened. Scope: general. judgment = false.
- **Rule:** L1 = the first false-breakout (sweep) low below a consolidation, H1 = the impulse high reached from it. When price retraces and is re-bought at a higher low L2 (a retracement buy or a later false breakout/stop run), project T = L2 + (H1 - L1). Larger swing: T = Lk + (Hm - L0), where L0 is the initial buy low, Hm the intermediate high, and Lk the later stop-run low. Give extra weight when T meets an HTF opposing array (the example was a daily bearish OB). Bearish mirror.
- **Sources:** cc02_008_pv2-R-STviA ~00:17:01.
- **Quote:** "it's a measured move from that same buy"
- **Conflicts:** none.
- **Rulebook fix:** L13: add the re-anchored measured move.
- **BUILD SPEC (targets_partials):**
  - Listed: Ep08.9 `mm_targets` with `mm_anchor` ref/leg. Add `mm_anchor="reanchor"`: when the trade's sweep low L2 > an earlier sweep low L1 of the same session/day with an impulse high H1 between, add T = L2 + (H1 - L1) as kind "proj" (kind "proj_htf" when within 1 pt of an HTF array).
  - Params: extend `mm_anchor` values with "reanchor".
  - Test: `test_measured_move_reanchor`. L1 4000, H1 4030, L2 4010: target 4040.

### 110. X1-bullish-objective-order
- **rule_id / kind:** X1, missing_rule. Scope: general. judgment = false.
- **Rule:** Long from a bullish OB: T1 = the nearest up-close candle above (bearish OB; first contact with it, with exit buffer per X2 as an implementation choice); T2 = just above that candle's high / swing high (buy stops); T3 = the next HTF bearish OB above (ICT: price runs up "into" it; near edge/MT is an implementation choice). Mirror for shorts. Source example is a monthly chart.
- **Sources:** cc03_002_PQkcFbr61FI ~00:20:14.
- **Quote:** "see price straight up to this up candle first that's your first objective"
- **Conflicts:** none.
- **Rulebook fix:** X1: add the OB-entry objective order.
- **BUILD SPEC (targets_partials):**
  - For trades whose entry array is an OB (`entry_arrays` ob, built in setups), with `ob_target_order`: first rung = low of the nearest bearish OB candle (last up-close before a down leg) above entry on the entry TF; second = its high + 1 tick; third = near edge of the nearest 1h/4h/D bearish OB (`htf` arrays). Inserted before other rungs; others kept after.
  - Params: `ob_target_order: bool = False`.
  - Test: `test_ob_entry_objective_order`. Up candle 4110-4116 above, 1h bearish OB 4130: rungs 4110, 4116.25, 4130.

### 111. new-retrace-to-recapitalized-ob
- **rule_id / kind:** new, missing_rule. Scope: general. judgment = false.
- **Rule:** While an HTF old high above remains untaken (an unfulfilled objective), a retracement after an intermediate high/old high is run is not a reversal. Expect it to stop at the earlier bullish OB that was already re-bought (recapitalized) on the prior leg. Buy there and target the untaken old high. Mirror bearish.
- **Sources:** cc03_003_t2VNzJZ4hK4 ~00:38:17.
- **Quote:** "because we have an unfulfilled objective up here"
- **Conflicts:** none.
- **Rulebook fix:** new rule under B9/L14.
- **BUILD SPEC (setups_models):**
  - `levels.reclaimed_obs` (built) gives re-bought OBs. New branch: with `recap_ob_entry` and an untaken HTF (D/W pivot or locked draw) high above, after a pool above is swept and price retraces, arm a limit at the most recent reclaimed bullish OB's open, stop below its low, target = the HTF high. Shorts against it are blocked while the objective stands (tag `unfulfilled`).
  - Params: `recap_ob_entry: bool = False`.
  - Test: `test_retrace_to_recapitalized_ob`. Reclaimed OB 4050-4056, HTF high 4120 untaken: long limit 4056 (open), target 4120.

### 112. L3-monthly-ohlc-3m
- **rule_id / kind:** L3, missing_condition. Scope: general. judgment = false.
- **Rule:** Each month, store O, H, L and C of the last 3 completed monthly candles (12 levels) and draw them on weekly, daily and intraday charts as reference levels (confluence/context, not standalone signals). Also frame the monthly range from the most recent down-close monthly candle and the up-close candle above its high (cc03_004 ~2:30). Drop the "support in bullish / resistance in bearish" clause unless another source supports it.
- **Sources:** cc03_004_9kabTfUEVKg ~00:01:46.
- **Quote:** "the opens the highs the close and the low of every single candle on a monthly chart"
- **Conflicts:** none.
- **Rulebook fix:** L3: add the 3-month OHLC reference levels.
- **BUILD SPEC (levels_detectors):**
  - In `DayCtx`, with `monthly_ohlc`, build monthly candles from `hist` (needs ~70 sessions; `ipda_pools` history already passes 61+) and store `ctx.m_ohlc` (12 levels). Feed them only into confluence scoring (item 94 `confl_rank`) and as tags on entries (`lv_tags["m_ohlc"]` when an entry/target is within 1 pt); not as standalone pools.
  - Params: `monthly_ohlc: bool = False`.
  - Test: `test_monthly_ohlc_levels`. Three synthetic months: 12 levels, the current month excluded.

### 113. L3-htf-pd-arrays-intraday
- **rule_id / kind:** L3, missing_rule. Scope: general. judgment = false.
- **Rule:** Build weekly and monthly PD-array levels (OB open/MT, FVG/gap edges and CE, voids, old highs/lows; other array types optional) and keep the untested ones available while day trading, as support/resistance, targets and partial levels. Extend htf_targets to include "W" and "M". Ladder: if a daily array fails, expect the next weekly array, then monthly (cc05_015 ~18:45, already in B9).
- **Sources:** cc05_015_Y1oxwc354oo ~00:19:55.
- **Quote:** "you should have these monthly weekly levels on regardless even if you're a day trader"
- **Conflicts:** none.
- **Rulebook fix:** L3: add W/M PD arrays as intraday levels.
- **BUILD SPEC (levels_detectors):**
  - `htf.table` builds weekly arrays; add monthly (`months(d)` analogous to `weeks`) -> `_arrays(..., "M")`. Allow "W" and "M" in `htf_targets` (the target merge in `_lv_finish_targets` already reads arrays by TF label).
  - Params: none new (values "W", "M" accepted in `htf_targets`).
  - Test: `test_htf_targets_week_month`. A monthly BISI above price appears in the ladder with htf_targets including "M".

### 114. L3-3-6-12-month-pools
- **rule_id / kind:** L3, missing_rule. Scope: general. judgment = false.
- **Rule:** Buy-side open-float pools: the high a bearish shift came from, the prior week high, the prior month high, the 3-month high (noted each quarter; rolling ~63 days as a proxy), the 6-month high (~126 days) and the 12-month high (~252 days). Sell-side mirror. Tag as HTF draw candidates. The 3-month extreme has priority around the quarterly shift.
- **Sources:** cc05_002_BkmZgjuYREU ~00:02:41.
- **Quote:** "above the current six-month high ... above the current 12-month high"
- **Conflicts:** none.
- **Rulebook fix:** L3: add 3/6/12-month pools.
- **BUILD SPEC (levels_detectors):**
  - Extend `ipda_pools` windows: `ipda_windows: tuple = (20, 40, 60)`; allow (20, 40, 60, 63, 126, 252). History passed to `DayCtx` must cover max(window)+1 sessions (backtest loader `hist` length).
  - Params: `ipda_windows: tuple = (20, 40, 60)`.
  - Test: `test_ipda_windows_long`. 252-day high above price present as a pool with windows including 252.

### 115. new-shift-origin-pool
- **rule_id / kind:** new, missing_rule. Scope: general. judgment = false.
- **Rule:** After a bearish daily MSS (a trade or close below a short-term low), record the swing high the down-leg started from as a buy-side pool (fund protective stops), valid for a long period. It is the draw for the next bullish phase after a bullish daily MSS. Mirror after a bullish MSS.
- **Sources:** cc05_002_BkmZgjuYREU ~00:07:58.
- **Quote:** "your eyes need to go right to the high it just came from"
- **Conflicts:** none.
- **Rulebook fix:** new rule under L3/L4.
- **BUILD SPEC (bias_htf):**
  - `htf.table` column `shift_origin_hi` / `shift_origin_lo`: on each daily bearish MSS (close below the last daily pivot low), store the pivot high that started the leg; keep until traded. With `shift_origin_pool`, add it as a "pool" in `_targets` and as the draw after a bullish daily MSS (`want` +1 and lock to it).
  - Params: `shift_origin_pool: bool = False`.
  - Test: `test_shift_origin_pool`. Daily high 4200, then close below pivot low 4100: pool 4200 kept until traded.

### 116. new-trendline-trap-target
- **rule_id / kind:** new, missing_rule. Scope: general. judgment = false.
- **Rule:** Trendline trap (HTF bullish, a retail down-trendline with touches H1 > H2 > H3): buy at a bullish OB at, or a turtle-soup run of, the low between H2 and H3. T1 = just above H2 (the second-touch high, buy stops). Bearish mirror: sell near the high between L2 and L3 of an up-trendline, T1 = just below L2. Any further target comes from the HTF draw (not specified in the source).
- **Sources:** cc03_007_o8NfSK-pUlE ~00:11:26.
- **Quote:** "that's where a lot of the buy stops are going to be residing"
- **Conflicts:** none.
- **[our interpretation]:** trendline = three descending pivot highs whose touches lie within 0.1 x ADR5 of a straight line.
- **Rulebook fix:** new rule: trendline trap and its target.
- **BUILD SPEC (levels_detectors):**
  - `levels.trendline_highs(highs, tol)` -> (H1, H2, H3) indices for three descending pivots on a line. With `trendline_pools`, H2 becomes a "pool" (tag `tl2`) for longs whose entry low lies between H2 and H3 in time; T1 = H2 + 1 tick.
  - Params: `trendline_pools: bool = False`.
  - Test: `test_trendline_second_touch_pool`. Pivots 4120, 4110, 4100 on a line: pool 4110.

### 117. new-no-long-term-top-picking
- **rule_id / kind:** new, missing_rule. Scope: general. judgment = true.
- **Rule:** Do not take trades premised on a long-term (monthly/weekly) top or bottom forming. Trade short- and intermediate-term swings in the HTF order-flow direction (B3/B5). Classic reversal patterns (H&S, inverse H&S) against HTF flow are retail traps, not entries.
- **Sources:** cc03_008_w8lbrvZXUVY ~00:04:18.
- **Quote:** "picking tops and bottoms is one of the worst games to play"
- **Conflicts:** none.
- **Rulebook fix:** B5: add the no-long-term-top-picking line.
- **BUILD SPEC:** none (text only; the bot has no long-term reversal setup).

### 118. L15-fx-room-objectives
- **rule_id / kind:** L15, missing_rule. Scope: fx_only. judgment = true.
- **Rule:** FX only. Intraday room from the OB entry to the range high: skip at ~20 pips, take at >= 40 pips. For a goal of 50+ pips, use 30m/60m swings of >= 50 pips, ideally 75-80, so the goal fits inside the range. Weekly objective: 30-50 pips to start, then 50-75, then 75-100, no more than 100 (ICT prefers 50-75). Swing trades (2+ weeks): 200-500 pips. No index equivalents given.
- **Sources:** cc04_002_npL3ZXJ5zOU ~00:34:41; cc07_006_O69iFqP1j7o ~00:07:10; cc06_001_0juYnbKays0 ~00:01:21.
- **Quote:** "if you can see anything at 40 Pips or higher"
- **Conflicts:** none.
- **Rulebook fix:** FX-only list: add these sizes.
- **BUILD SPEC:** none (fx_only).

### 119. L3-daily-target-weekly-beyond
- **rule_id / kind:** L3, missing_rule. Scope: general. judgment = false.
- **Rule:** T1 = nearest daily-chart pool in the trade direction (PDH, intra-week high, PWH, PMH). Tag weekly_beyond=True when an unmet weekly pool lies beyond T1; prefer/filter for it (higher still with monthly agreement). Mirror for shorts.
- **Sources:** cc04_003_PIYh0CxoY9c ~00:15:58.
- **Quote:** "preferably look for something in the weekly chart that would support even higher"
- **Conflicts:** none.
- **Rulebook fix:** L3: add the weekly-beyond preference.
- **BUILD SPEC (targets_partials):**
  - In `_finish_order`: tag `weekly_beyond` when, beyond the first daily pool rung, a weekly pool (PWH/PWL, weekly pivot, weekly array from `htf` "W") lies in the trade direction and untaken; `monthly_beyond` likewise for "M". With `weekly_beyond_mode="require"`, reject orders without it.
  - Params: `weekly_beyond_mode: str = "off"` ("tag" / "require").
  - Test: `test_weekly_beyond_tag`. PDH 4100 with untaken PWH 4140: tagged.

### 120. A12-mt-retrace-after-stop-run
- **rule_id / kind:** A12, missing_rule. Scope: general. judgment = true.
- **Rule:** If the bullish OB's down candle was itself a run on sell stops (it swept a prior low), expect a shallower retrace: buy at the body MT (open-to-close 50%) instead of the open, stop below the OB low. Otherwise enter at the open (or ~5 pips above). Mirror for bearish. Single DXY example; treat as a test switch.
- **Sources:** cc04_003_PIYh0CxoY9c ~00:32:47.
- **Quote:** "i didn't think we're going to get down to this down candle"
- **Conflicts:** none.
- **Rulebook fix:** A12: add the stop-run OB MT entry.
- **BUILD SPEC (entries_stops_sizing):**
  - In the OB entry path (`ob_entry`, `_ob_pre`, `setups.array_order`): with `ob_mt_if_swept`, if the OB candle's low < the prior pivot low (it swept it), the entry = (open+close)/2 of that candle; else the open.
  - Params: `ob_mt_if_swept: bool = False`.
  - Test: `test_ob_entry_mt_when_candle_swept`. OB candle o 4010 c 4002 low below the prior low: entry 4006.

### 121. M1-turning-level-types
- **rule_id / kind:** M1, missing_rule. Scope: general. judgment = false.
- **Rule:** MM buy model turning level = any higher-TF or immediate-term support: old high (as support), old low, bullish OB, a liquidity void being filled, or an FVG being closed into. Buy side begins only once price reaches one. Mirror for the sell model.
- **Sources:** cc04_007_X5pQjfkAUCI ~00:01:04.
- **Quote:** "that support level can come in the way of an old high it can come in a way of old low"
- **Conflicts:** none.
- **Rulebook fix:** M1: list the turning-level types.
- **BUILD SPEC (setups_models):**
  - Listed: M1 `am_discount_array` (5m OB / 1m BISI). Add `mm_turn_types: tuple = ("ob","fvg")`; allow "old_high", "old_low", "void". `setups._discount_array` checks the sweep extreme against those types (old highs below price as support from daily/1h pivots; voids from `levels.voids`).
  - Params: `mm_turn_types: tuple = ("ob", "fvg")`.
  - Test: `test_mm_turn_at_old_high_support`. Sweep low at an old 1h high 4050: discount-array check passes with "old_high".

### 122. M1-intraweek-pbr-target
- **rule_id / kind:** M1, shortened. Scope: general. judgment = true.
- **Rule:** Weekly-profile context (M17 keeps it as statistics/research). Mark the pre-move consolidation (PBR). An intraweek reversal's objective is a return into the PBR, possibly beyond it to the buy-side above the week's earlier high. Exceeding it is optional, notably when the pre-drop high was a lower high. Typical sequence: Mon consolidation, Tue sell-off, reversal at the Tue/Wed overlap, buy Thu, delivery into the PBR Fri. Near/far-edge partials are our proxy. Mirror for bearish.
- **Sources:** cc07_007_jvc105qaCJs ~00:18:06.
- **Quote:** "intra-week reversals will many times look to return to the previous balanced price range"
- **Conflicts:** none.
- **[our interpretation]:** PBR = Monday's range when Monday's range < 0.6 x ADR5.
- **Rulebook fix:** M1/M17: add the PBR objective as a weekly statistic.
- **BUILD SPEC (day_week_context, study):**
  - `study_week.py` (T14, listed) adds: weeks with a small Monday range and a Tuesday sell-off > 1 x ADR5 -> record whether Thu/Fri price returns into Monday's range and exceeds its high. Report only.
  - Params: none.
  - Test: `test_pbr_return_stat`. Synthetic week following the sequence: return=1, exceed=0.

### 123. new-vb-target
- **rule_id / kind:** new, missing_rule. Scope: index (checker: general). judgment = false.
- **Rule:** Bullish VB long, after the gap is filled and price trades back up through the first up candle: T1 = buy-side above the high formed at the gap opening, if untaken. After that, hold a runner toward the next buy-side pool. Invalidation: a close back below the first up candle's close before the gap means take profits or exit fully. Mirror for bearish.
- **Sources:** cc04_009_shPGUz9pU-A ~00:12:42.
- **Quote:** "once it takes out that high we would recently expect to see price continue on the upside"
- **Conflicts:** none.
- **Rulebook fix:** L8: add the VB target and invalidation.
- **BUILD SPEC (setups_models):**
  - `levels.vacuum_block` (built). New branch `vb_trade`: after the VB is filled and a bar closes above the first post-gap up candle, arm a long (market on close or limit at that close), stop = below the VB fill low, T1 = the high of the gap-opening session segment + 1 tick, runner to the next pool from `_targets`. Exit all on a close below the first up candle's pre-gap close.
  - Params: `vb_trade: bool = False`.
  - Test: `test_vacuum_block_trade_target`. Gap opening high 4110: T1 4110.25.

### 124. L2-raid-level-rolls
- **rule_id / kind:** L2, missing_condition. Scope: general. judgment = false.
- **Rule:** Bullish: raid level = PDL / daily body-cluster low, mapped to the 15m. If price trades below it, bounces without a real reversal, and prints a new intraday swing low below it, the raid level rolls to that newest low. Place the limit a few ticks/pips below it and take no entries above the current raid level. Mirror for bearish. (FX example.)
- **Sources:** cc04_011_Gnw54f9v6SA ~00:13:57.
- **Quote:** "so we're going to be looking for a run below 130.95"
- **Conflicts:** none.
- **[our interpretation]:** "real reversal" = an MSS (15m close above the last 15m pivot high).
- **Rulebook fix:** L2: add the raid-level roll.
- **BUILD SPEC (setups_models):**
  - For the CC turtle-soup limit (`turtle_soup="cc_limit"`, `_cc_limit`): with `raid_roll`, after the PDL trades without a 15m MSS, replace the raid level by each new confirmed 15m pivot low below it; the limit = raid - `ts_pad_ticks`; no entries above the current raid.
  - Params: `raid_roll: bool = False`.
  - Test: `test_raid_level_rolls_to_new_low`. PDL 4000, bounce, new 15m pivot low 3995: limit moves to 3994.75.

### 125. B1-nearby-unrun-high-trap
- **rule_id / kind:** B1 / A2, missing_rule. Scope: general. judgment = true.
- **Rule:** Do not short a signal forming within X of an untaken old high/REH above; expect the pool to be run first. X not given; our proxy: within 0.25x ADR5 or within the current leg. Mirror for longs.
- **Sources:** cc04_013_Xae0VrbkyFk ~00:06:11.
- **Quote:** "they're not going to keep price this close okay and not run that high"
- **Conflicts:** none.
- **[our interpretation]:** X.
- **Rulebook fix:** A2/B1: add the "nearby untaken pool gets run first" filter.
- **BUILD SPEC (setups_models):**
  - In `setups.finish_gates`: with `near_pool_block`, reject a short whose entry lies within `near_pool_adr` x ADR5 below an untaken pool ("pool"/"pool_eq" from `_targets` run on the opposite side) that the setup's sweep did not take. Mirror.
  - Params: `near_pool_block: bool = False`, `near_pool_adr: float = 0.25`.
  - Test: `test_short_blocked_under_near_reh`. REH 4100 untaken, short entry 4097, ADR5 20: rejected.

### 126. new-double-top-projection
- **rule_id / kind:** new, missing_rule. Scope: general. judgment = true.
- **Rule:** Double top (two highs within eq_tol): R = higher peak minus lowest low between the peaks; objective = higher peak + R (allow ~1 tick/pip). Double bottom mirror: lower trough minus R. Keep clean double tops/bottoms with no time expiry. When the pool is traded 1 tick through, mark the pool booked but keep its projection live until reached, then mark it done. After buy stops above a double top are taken and the projection (or a void fill / bearish OB) is reached, stop new longs and make the draw the nearest sell-side (double bottom / REL below), and the mirror for double bottoms. A reversal entry still needs a model trigger (MSS/FVG). Examples are FX 1h; ICT says it holds on all timeframes.
- **Sources:** cc04_014_owq30ATPU5s ~00:08:40, ~00:11:37, ~00:11:53, ~00:14:35.
- **Quote:** "you're going to measure the high down to the low between the two peaks"
- **Conflicts:** none.
- **[our interpretation]:** keep only within the history window passed.
- **Rulebook fix:** L13 and A3: add the double-top projection and no-expiry rule.
- **BUILD SPEC (targets_partials):**
  - `levels.equal_clusters` (built) gives the pairs. New `levels.double_top_proj(h, l, pair)` -> (pool, proj). With `dt_proj`, for 1h/4h rel-eq pairs: pool as "pool_eq", projection as "proj" rung beyond it. After the projection is reached in the session, set the long side done and lock the draw to the nearest sell-side rel-eq pool (via `_lock_step`).
  - Params: `dt_proj: bool = False`.
  - Test: `test_double_top_projection`. Peaks 4100/4099.75, low between 4080: projection 4120.

### 127. B21-reference-points-in-windows
- **rule_id / kind:** B21, missing_condition. Scope: general. judgment = true.
- **Rule:** For each LB20/40/60 (cc05_001 ~24:28): note the range high/low as stop pools. If the extreme candles have long wicks (threshold ours, e.g. wick > body), use the rejection block at the body edge (A17) instead of the wick extreme. Also list the daily OBs, FVGs and liquidity voids inside the windows as reference points/targets. Frame off the window low when the market has been trading higher and off the window high when it has been trading lower.
- **Sources:** cc05_001_n7SPAK_tpN8 ~00:24:28.
- **Quote:** "if those highs have a lot of Wicks you're going to be looking for rejection blocks"
- **Conflicts:** none.
- **[our interpretation]:** wick > body.
- **Rulebook fix:** B21: add RBs and in-window arrays.
- **BUILD SPEC (levels_detectors):**
  - `ipda_pools` (built) adds the H/L. With `ipda_rb`, when the extreme day's wick > body, add its body edge as kind "pool" instead (A17 body edge) and keep the wick as a runner rung. With `ipda_arrays`, limit `htf.table` daily arrays used as targets to those formed within the 60-day window (default currently `lookback=60` in `htf.table`; this just makes the window the IPDA anchor's).
  - Params: `ipda_rb: bool = False`, `ipda_arrays: bool = False`.
  - Test: `test_ipda_extreme_rejection_block`. 20-day high candle o 4090 c 4095 h 4110: pool 4095, runner 4110.

### 128. B21-progression-20-40-60-beyond
- **rule_id / kind:** B21, shortened. Scope: general. judgment = true.
- **Rule:** Near-term draw = the 20-day high/low in the IOF direction (cc05_004). Roll out to the 40-day window when the 20-day extreme is taken or all PD arrays in the 20-day window have been traded to (cc06_008). Next target = the next unused lower low (higher high) or opposing discount (premium) array. If the 40-day window adds nothing beyond the 20-day one, go straight to the 60-day window (cc07_004). Prefer levels where IPDA range extremes and PD arrays converge (tolerance ours). If the 60-day highs/lows have already been run and an obvious older swing sits just beyond 60 days, target it and tag "expansion expected" (cc05_003 ~28:40).
- **Sources:** cc05_004_vqtA1S9JH34 ~00:26:38; cc06_008_VL4YLTRerHY ~00:12:50; cc07_004_YV4fEF4d2wA ~00:07:43; cc05_003_LRKtiysz4nA ~00:28:40.
- **Quote:** "if all the epad data range PD arrays are exhausted ... move out to the 40-day lookback"
- **Conflicts:** none.
- **[our interpretation]:** convergence tolerance 0.25 x ADR5.
- **Rulebook fix:** B21: add the array-exhaustion roll, skip-empty-window and beyond-60 expansion.
- **BUILD SPEC (levels_detectors):**
  - Built: `ipda_next` (extreme-taken sequencing). New:
    - roll on exhaustion: in the `ipda_next` state, also advance when every daily array formed in the 20-day window has been traded to;
    - skip: when the 40-day extreme equals the 20-day one, jump to 60;
    - beyond 60: when all three extremes are taken, add the nearest older daily pivot (up to `ipda_beyond_days`) as the draw and tag `expansion`.
  - Params: `ipda_roll_arrays: bool = False`, `ipda_beyond_days: int = 0` (0 = off; test 120).
  - Test: `test_ipda_skip_empty_40`. 40-day high == 20-day high: next target is the 60-day high.

### 129. B21-open-float-forward-windows
- **rule_id / kind:** B21, missing_rule. Scope: general. judgment = true.
- **Rule:** Anchor D: back pools = 20/40/60-day highs/lows before D. Forward: track running high/low of D..D+19, D+20..D+39, D+40..D+59; each completed interval's high/low becomes a new pool. Large-fund pool = high/low of D-60..D+59 (realised part only; no look-ahead; a bot adaptation). At each forward marker or new obvious daily turn, recompute 20/40/60 look-backs ending there; levels/dates produced by two or more windows rank higher. ICT also uses the forward D+60 marker to anticipate an intermediate-term high/low forming before that date (cc05_003 ~28:40).
- **Sources:** cc05_004_vqtA1S9JH34 ~00:25:15; cc05_003_LRKtiysz4nA ~02:02:01.
- **Quote:** "you look back 60 and you look forward 60"
- **Conflicts:** none.
- **[our interpretation]:** the overlap ranking.
- **Rulebook fix:** B21: add open float (120-day range, forward intervals, overlap).
- **BUILD SPEC (levels_detectors):**
  - In the IPDA builder used by `ipda_pools`: with `ipda_forward`, take the anchor from `ipda_anchor` (item 130); add completed forward 20-day interval H/L as pools (`ipda_f20h` etc.) and the realised 120-day H/L as `ipda_float`. Rank pools hit by >= 2 windows first (`pool_rank`).
  - Params: `ipda_forward: bool = False`.
  - Test: `test_open_float_forward_intervals`. Anchor day 0, today day 45: pools from days 0-19 and 20-39 present, 40-59 not yet.

### 130. B21-anchor-month-vs-daily
- **rule_id / kind:** B21, unlisted_contradiction. Scope: general. judgment = false.
- **Rule:** Switch ipda_anchor = 'month' (anchor = first trading day of the current month, fixed until the next month; cc05_001 ~24:28, cc05_003 ~28:40, cc05_004 ~16:04) | 'daily' (count yesterday as day 1 and roll every day; cc09_008 ~6:03; default).
- **Sources:** cc05_004_vqtA1S9JH34 ~00:16:04.
- **Quote:** "we keep moving that basis forward each new month"
- **Conflicts:** cc05_004 monthly anchor vs cc09_008 daily roll.
- **Rulebook fix:** B21: list both anchors and the contradiction.
- **BUILD SPEC (levels_detectors):**
  - In the IPDA window builder, `ipda_anchor="month"` computes the windows ending at the first trading day of the current month (fixed all month).
  - Params: `ipda_anchor: str = "daily"`.
  - Test: `test_ipda_anchor_month`. On the 15th, 20-day window ends at the 1st trading day of the month.

### 131. new-60day-range-grades
- **rule_id / kind:** A21 / new, missing_rule. Scope: general. judgment = true.
- **Rule:** In a range-bound daily market, define the 60-day range from the highest and lowest candle body (open/close; cc07_005). Mark grades at 0/12.5/25/37.5/50/62.5/75/87.5/100%. Grade levels act as S/R and mile-marker targets. When price trades through a grade without reacting, the next grade is the target; do not set targets between grades (cc07_006 ~14:08). Each sub-range has its own premium/discount: buy at discount arrays within a sub-range and take first profit at 4h/1h premium arrays. Longs remain valid inside the overall premium while the sub-range is in discount, but the odds fall off near the top. Bearish arrays in the top segment give the strongest reactions (cc07_005 ~18:34); the bands are our quantification. EQ (50%) is a high-probability retrace level (cc07_006). Overbought/oversold = the 60-day high/low (cc05_003; wicks there vs bodies in cc07_005, so make this a switch). Taking no new trades at the extremes is not in the source.
- **Sources:** cc07_006_O69iFqP1j7o ~00:10:09, ~00:09:51, ~00:14:08; cc07_005_y0lVKWLsZeM ~00:18:34; cc05_003_LRKtiysz4nA ~01:55:20.
- **Quote:** "you know that it's going to most likely reach for the next level up"
- **Conflicts:** cc07_006/cc07_005 bodies vs cc05_003 wicks for the range.
- **[our interpretation]:** range-bound test (B17/N8 classifier); scoring bands.
- **Rulebook fix:** A21: add the 60-day grade ladder.
- **BUILD SPEC (targets_partials):**
  - With `grades60`, compute the 60-day range (`grades60_src` "body"/"wick") from `hist`; add the 9 grade levels as kind "grade" in `_targets` (only those beyond `above`); in the ladder, after a grade is traded through, the next grade is the final target unless a nearer pool exists. Tag entries with their grade band.
  - Params: `grades60: bool = False`, `grades60_src: str = "body"`.
  - Test: `test_60day_grades`. Body range 4000-4800: grades every 100; long from 4410 ladder includes 4500, 4600.

### 132. L14-target-past-eq
- **rule_id / kind:** L14, missing_rule. Scope: general. judgment = false.
- **Rule:** Short from a premium array above the overall EQ: target = first untraded bullish M/W/D array at or below EQ (OB MT, FVG, RB). Long mirror. Raise priority when the target overlaps a quadrant/eighth 50% line. The range is the 60-day body consolidation (cc07_005).
- **Sources:** cc07_005_y0lVKWLsZeM ~00:08:07.
- **Quote:** "when price moves that down to either the 50 level of the total consolidation or any level below"
- **Conflicts:** none.
- **Rulebook fix:** L14: tie the opposing target to the range EQ.
- **BUILD SPEC (targets_partials):**
  - With `target_past_eq60`, for shorts entered above the 60-day body EQ (item 131 range), the final target = the first untraded bullish M/W/D array (`htf` arrays) whose top <= EQ; mirror for longs.
  - Params: `target_past_eq60: bool = False`.
  - Test: `test_target_first_array_below_eq60`. EQ 4400, weekly BISI 4380-4390: final 4390.

### 133. L14-target-timeframe
- **rule_id / kind:** L14, unlisted_contradiction. Scope: general. judgment = false.
- **Rule:** Switch target_tf = 'one_lower' | 'same'. one_lower (cc07_003, cc07_004, cc07_001, cc06_003): monthly entry -> weekly/daily (4h allowed); weekly -> daily/4h; daily -> 4h/1h. same (cc06_006, position-trade context): walk the entry timeframe's opposing matrix arrays nearest first. Target = the nearest untraded opposing array on the allowed timeframes.
- **Sources:** cc06_006_JAjL7rUX2Iw ~00:03:24; cc07_003_hbE8S5FSdtQ ~00:02:50; cc07_004_YV4fEF4d2wA ~00:14:37.
- **Quote:** "you're gonna be looking for a weekly or daily premium PD array"
- **Conflicts:** cc06_006 same-timeframe objective vs cc07_003/cc06_003/cc07_001 one timeframe lower (may be scope: position vs weekly templates).
- **Rulebook fix:** L14: list both and the contradiction.
- **BUILD SPEC (bias_htf):**
  - Listed: L14c `matrix_tf_lower`. Extend it to `target_tf: str = "off"` ("one_lower" = the listed behaviour with the mapping above; "same" = the react TF's arrays). The react TF comes from `htf.table`'s reaction column.
  - Params: `target_tf: str = "off"`.
  - Test: `test_target_tf_mapping`. Reaction at a daily array: one_lower allows 4h/1h targets only.

### 134. L13-cc-extension-projections
- **rule_id / kind:** L13, shortened (checker; claim said wrong). Scope: general. judgment = true.
- **Rule:** Anchor (cc06_008 ~28:08): after the EQ breach and the stop run, measure from the short-term high down to the stop-run low and project the 1.27 and 1.62 extensions. Midweek bearish template (cc07_003 ~30:54): H = Wednesday's high, L = the lowest low from Monday's open up to H, R = H - L; targets are H - 1.27R and H - 1.68R (bullish mirror). An alternative is a 100% symmetrical swing (perfect market-structure swing), anchor unstated. Valid only where the projection overlaps an opposing PD array on a timeframe lower than the entry array (cc07_003 ~16:13); tolerance is ours. Swing objective = nearest untraded contrary M/W/D array (cc06_008 ~16:20). Switch ext2 = 1.62 | 1.68.
- **Sources:** cc06_008_VL4YLTRerHY ~00:28:08, ~00:16:20; cc07_003_hbE8S5FSdtQ ~00:16:13, ~00:30:54.
- **Quote:** "use your extensions 127 and 162"
- **Conflicts:** cc06_008 uses 1.62; cc07_003 uses 1.68 and adds the 100% swing.
- **[our interpretation]:** tolerance 1 ES pt.
- **Rulebook fix:** L13: add the anchors, 1.68 variant and the lower-TF overlap condition.
- **BUILD SPEC (targets_partials):**
  - Listed: L13 `proj_ext`. Specify anchors `proj_ext_anchor: str = "stop_run"` ("stop_run" = last pivot high before the sweep -> sweep low; "midweek" = Wed high -> Mon-Wed low, used from Wednesday); levels 1.27 and `proj_ext2` (1.62/1.68); keep a level only within `sd_htf_tol` of an opposing array of a TF lower than the entry array's TF.
  - Params: `proj_ext_anchor: str = "stop_run"`, `proj_ext2: float = 1.62`.
  - Test: `test_cc_extension_levels`. H 4100, L 4060 (midweek): 4049.2 and 4032.8 with 1.68.

### 135. new-weekly-market-price-friday-close
- **rule_id / kind:** new, missing_rule. Scope: general. judgment = false.
- **Rule:** For the weekly map built before Monday, P = last Friday's close; premium arrays above P, discount below; W20 = 20 trading days ending that Friday. (cc07_004 ~8:49.)
- **Sources:** cc07_004_YV4fEF4d2wA ~00:08:49.
- **Quote:** "market price is defined as Friday's close"
- **Conflicts:** none.
- **Rulebook fix:** new definition under B21/A21.
- **BUILD SPEC (bias_htf):**
  - Where weekly premium/discount is computed in `htf.table` (weekly arrays split above/below price), use Friday's close as the reference for the whole next week (not each day's close) when `wk_ref_friday`.
  - Params: `wk_ref_friday: bool = False`.
  - Test: `test_weekly_ref_is_friday_close`. Tuesday's weekly split uses Friday's close.

### 136. B7-fast-week-htf-reversal-level
- **rule_id / kind:** B7 (new rule), missing_rule. Scope: general. judgment = true.
- **Rule:** New rule (not B7). Trigger: on Monday and/or Tuesday, price covers well above the 5-day ADR quickly (often most of the week's range in one day). Treat that as a possible intra-week reversal profile, not a reason to expect an equal second leg. List the monthly, weekly, daily and 4h PD arrays in the move's path. The first one reached is the candidate reversal level (example: daily bullish OB MT, with very little trade below it). Look for the reversal around the Tue-Wed changeover, and for evidence of sponsorship: a short-term high breaks and the bullish OBs that follow are bought. The first target is the nearest opposing 4h+ PD array (example: 4h bearish OB). Intra-week reversals often return to the prior price-balance range, and can go beyond it. Choosing among arrays is discretionary. Mirror for the bearish case. Scope: general, but ICT's example is FX and M17 currently puts weekly profiles out of scope.
- **Sources:** cc07_007_jvc105qaCJs ~00:13:57, ~00:11:43.
- **Quote:** "may cut cause or be a catalyst for intra-week Market reversal"
- **Conflicts:** none.
- **[our interpretation]:** "well above ADR5" = Mon+Tue range >= 1.5 x ADR5.
- **Rulebook fix:** new rule next to M17: fast-week HTF reversal level.
- **BUILD SPEC (bias_htf):**
  - `htf.table` daily state `fast_week` (+1 bearish-fast / -1): on Tue/Wed close if the week's range >= 1.5 x ADR5 and price reached a D/W/4h array in the move's direction (first array touched = `fw_level`). With `fast_week_rev`, from Wednesday `want` = opposite of the move while price holds beyond `fw_level` (no daily close through its MT); draw = nearest opposing 4h+ array.
  - Params: `fast_week_rev: bool = False`, `fast_week_adr: float = 1.5`.
  - Test: `test_fast_week_reversal_bias`. Mon-Tue drop 2x ADR5 into a daily OB MT: Wed want +1.

### 137. L13-weekly-high-london-swing
- **rule_id / kind:** L13, missing_rule. Scope: general. judgment = true.
- **Rule:** Bearish week, Monday rallies after the open: fib 1.0 = the London-session high and 0 = the intraday retracement low before the NY rally. Project above. The extension level is not stated in the transcript; it was hit exactly in the example. Shade the projected level one pip/tick toward price; that is the expected weekly high and the short entry. Use it only when it lines up with a weekly premium array (the example: a weekly bearish OB traded into on Monday). Take only a partial position on Monday, because Tue or Wed may still make the high. Mirror for a bullish week. Judgment; ICT's example is FX.
- **Sources:** cc07_008_LBlK6JB0QS0 ~00:30:29.
- **Quote:** "from the high formed in London down to the retracement low prior to the New York session rally"
- **Conflicts:** none.
- **[our interpretation]:** extension multiples tested 1.27/1.62/2.0.
- **Rulebook fix:** L13: add the Monday London-swing weekly-high projection.
- **BUILD SPEC (setups_models):**
  - Monday only, `weekly_bias` -1: compute L = London high (sess london, 02:00-05:00), R = lowest low between 05:00 and the NY rally start (09:30); levels = L + k(L-R) for k in `wk_proj_k`. A level within 1 pt of a weekly bearish array (`htf` "W") becomes a short limit (shaded 1 tick down), size x `wk_proj_size` (partial).
  - Params: `wk_high_proj: bool = False`, `wk_proj_k: tuple = (1.27, 1.62)`, `wk_proj_size: float = 0.5`.
  - Test: `test_monday_weekly_high_projection`. London high 4100, low 4090, weekly OB at 4112: short limit 4112.

### 138. B1-eq-consolidation-breakout
- **rule_id / kind:** B1, missing_rule. Scope: general. judgment = true.
- **Rule:** Swing context: mark untraded monthly/weekly imbalances (price not traded at in recent weeks or months) as primary draws. While price sits at equilibrium inside a consolidation, take no swing position. Once price breaks out of the consolidation, expect it to travel to the nearest imbalance in that direction: a premium array if up, a deep-discount array if down. How the breakout is confirmed (e.g., a daily close) is not specified by ICT and is our choice. Judgment.
- **Sources:** cc06_002_Xs1i0aIeTME ~00:07:55.
- **Quote:** "if price is at equilibrium we're going to be looking for an opportunity to see that price move to an imbalance"
- **Conflicts:** none.
- **[our interpretation]:** daily close beyond the consolidation range.
- **Rulebook fix:** B1: add the swing corollary.
- **BUILD SPEC (bias_htf):**
  - Reuse the `drange` regime (bias_htf item BH-B17, drange column). With `eq_breakout_draw`, when `drange` turns nonzero, set the draw = nearest untraded W/M array in that direction (from `_arrays` "W"/"M", item 113) and `want` = drange sign; while drange == 0 and price within 10% of the range EQ, `want` = 0.
  - Params: `eq_breakout_draw: bool = False`.
  - Test: `test_breakout_draws_to_weekly_imbalance`. Close above the daily range with a weekly SIBI above: draw = its near edge.

### 139. L17-fx-institutional-levels
- **rule_id / kind:** L17, missing_rule. Scope: fx_only. judgment = true.
- **Rule:** FX only: as a setup quality check, recent swing highs and lows should react at institutional levels (00 and 50 first, then 80/20, then 30/70). If price ignores them, rate the setup as less clean. The tolerance is not given by ICT; choose it by test. There is no index analogue (see L17 rounding).
- **Sources:** cc06_002_Xs1i0aIeTME ~00:09:28.
- **Quote:** "the big figure levels zero zero levels the 50 mid figure levels"
- **Conflicts:** none.
- **Rulebook fix:** FX-only list: add the institutional-level check.
- **BUILD SPEC:** none (fx_only).

### 140. new-swing-target-breaker-cap
- **rule_id / kind:** new, missing_rule. Scope: general. judgment = true.
- **Rule:** Swing long: T1 = fill of the nearest overhead liquidity void/FVG, which completes at the low of the last up-close candle before the down move. T2 cap = the nearest daily bearish breaker overhead; expect no more than that at first (consistent with A22). Extend to the next monthly/weekly premium array only once the daily chart shows a willingness to trade higher through the breaker; treat that as a judgment call, or proxy it by a daily close above the breaker. Mirror for shorts. Swing scope; M17 currently parks this.
- **Sources:** cc06_004_osRUnIpGIJ0 ~00:29:06.
- **Quote:** "we'll wait and see if the daily chart has a willingness to go higher"
- **Conflicts:** none.
- **[our interpretation]:** the daily-close proxy.
- **Rulebook fix:** new swing-target ladder note (parked under M17).
- **BUILD SPEC (targets_partials):**
  - For intraday use, with `daily_breaker_cap`, drop ladder levels beyond the nearest daily bearish breaker (`levels.breakers` on daily bars, `htf` arrays) above `above`, unless a daily close above that breaker exists; the breaker's low becomes the final target.
  - Params: `daily_breaker_cap: bool = False`.
  - Test: `test_daily_breaker_caps_ladder`. Daily breaker 4150-4170: rungs above 4150 removed; after a daily close 4172 restored.

### 141. M4-swept-low-age
- **rule_id / kind:** M4, missing_rule. Scope: general. judgment = false.
- **Rule:** The swing low swept for the breaker/turtle-soup setup may be any age (no limit; months is fine). Prefer a low formed recently, about a few days to a week before the sweep on the daily chart. The new low should hit a key support level (bullish OB, unfilled void, old high/low), and price should leave it quickly rather than linger below. Mirror for highs.
- **Sources:** cc05_005_xRjKtUEKkSE ~00:13:24.
- **Quote:** "there is no limit to time between this low and the new low"
- **Conflicts:** none.
- **Rulebook fix:** M4: add "no age limit, recent preferred, quick departure".
- **BUILD SPEC (setups_models):**
  - Turtle-soup core: `ts_back_bars` limits lookback. Add `ts_age_rank`: no lookback cap (0 = all history passed) and a tag `ts_age_days`; with "prefer", ties in the sweep pick go to the swing whose age <= 5 sessions. Linger check: cancel if more than `ts_linger_bars` closes stay below the level after the sweep.
  - Params: `ts_age_rank: str = "off"` ("tag" / "prefer"), `ts_linger_bars: int = 0`.
  - Test: `test_turtle_soup_any_age_prefer_recent`. Two candidate lows (3 days, 40 days): prefer picks the 3-day one; both eligible.

### 142. B23-seasonal-entry-arrays
- **rule_id / kind:** B23, missing_rule. Scope: general. judgment = true.
- **Rule:** Bullish HTF regime: during a bearish seasonal window, mark higher-timeframe bullish OBs (down-close candles in the uptrend) and broken prior swing highs (old resistance turned support). A long is a candidate when the seasonal decline trades into one of them and the next bullish seasonal window begins. Target the next higher-timeframe premium/BSL (our choice; ICT just measures the rally). Seasonals remain a road map; macro events can override them. Mirror for bearish.
- **Sources:** cc05_011_Vb6ueaPqut0 ~00:24:21.
- **Quote:** "retrace back down into a bearish candle which is a bullish order block"
- **Conflicts:** none.
- **[our interpretation]:** HTF = weekly; target.
- **Rulebook fix:** B23: add the entry arrays for seasonal retracements.
- **BUILD SPEC (bias_htf, report):**
  - B23 `seasonal_tag` (listed) is report-only. Extend the report: on days tagged "bullish window start" record whether price is inside a weekly bullish OB or above a broken weekly pivot high (support), and the next 20-day return. No trading effect.
  - Params: none (report columns).
  - Test: `test_seasonal_entry_array_tag`. Window start day inside a weekly OB: tag true.

### 143. LLT3-weekly-dealing-range
- **rule_id / kind:** new, missing_rule. Scope: general. judgment = false.
- **Rule:** Bearish week: top = the projected weekly high (entry zone, see the Monday London-swing projection). Bottom = the discount PD array below that is the week's objective (example: a 4h liquidity void), which is the final weekly target. EQ = 50% of [bottom, top], which defines the week's premium/discount matrix. Premium arrays inside the range (gaps, old highs, bearish OBs) are places to sell or add as price slides. Arrays nearer the bottom are the path toward the target; using them as partials is our choice, not stated by ICT. Mirror for a bullish week. Judgment; ICT's example is FX.
- **Sources:** cc07_008_LBlK6JB0QS0 ~00:32:10.
- **Quote:** "that's our range and then we can divide that in half"
- **Conflicts:** none.
- **Rulebook fix:** A21: add the weekly anticipated dealing range.
- **BUILD SPEC (bias_htf):**
  - With `wk_range`, from Monday's projected high (item 137 level, or the week's high so far once Wednesday passes) and the weekly draw (nearest 4h+ discount array below, `htf` arrays), compute `wk_eq`. In `setups.finish_gates`, bearish-week shorts allowed only at entries >= `wk_eq` (premium of the weekly range); the weekly draw becomes the final target of those shorts.
  - Params: `wk_range: bool = False`.
  - Test: `test_weekly_range_premium_shorts`. Top 4100, draw 4000: short at 4040 rejected, 4060 allowed.

### 144. LLT3-cbdr-definition-sd
- **rule_id / kind:** L13, shortened. Scope: fx_only. judgment = false.
- **Rule:** [fx-only] CBDR = bars starting at or after 14:00 and before 20:00 NY on the prior day. Body mode (ICT's preference): high = max(open, close), low = min(open, close). Wick mode: max(high) and min(low). Check both. Validity: range under 40 pips, ideally 20-30; above 30 is often poor for projections. R = CBDR_high - CBDR_low. For k = 1..4: SD_up_k = CBDR_high + k*R and SD_dn_k = CBDR_low - k*R. Treat levels as zones and use them only with a directional bias.
- **Sources:** cc08_003_nI1AMOC1pro ~00:04:34, ~00:02:11; cc12_004_Oec_0NM_OeY ~00:09:32.
- **Quote:** "the time period that frames the Central Bank dealers range is 2 P.M to 8 PM"
- **Conflicts:** none.
- **Rulebook fix:** L13 [fx-only]: add the CBDR definition, size filter and SD construction.
- **BUILD SPEC:** none (fx_only).

### 145. LLT3-cbdr-judas-hod-lod-zone
- **rule_id / kind:** L13, missing_rule. Scope: fx_only. judgment = false.
- **Rule:** [fx-only] Bearish day with a valid CBDR (under 40 pips): the expected HOD/Judas high lies in [CBDR_high, SD_up_2], most often SD_up_1, with SD_up_3 the normal limit. SD_up_4 is reached only on high-impact news or in a NY reversal profile. Bullish day mirrors this for the LOD. London protraction profile filters: Asian range 20-30 pips, and price rallying from 00:00 to 02:00 NY on a sell day. Enter only where a 15m/30m/60m premium (discount) PD array (FVG, OB, or an old high/low for turtle soup) overlaps SD 1, 2 or 3. Never enter on a bare SD level. Treat levels as zones.
- **Sources:** cc08_003_nI1AMOC1pro ~00:03:27; cc08_005_eU8WcUftUtY ~00:03:28; cc12_004_Oec_0NM_OeY ~00:09:32.
- **Quote:** "many times just one standard deviation"
- **Conflicts:** none.
- **Rulebook fix:** L13 [fx-only]: add the HOD/LOD zone and the overlap requirement.
- **BUILD SPEC:** none (fx_only).

### 146. LLT3-cbdr-projection-unit
- **rule_id / kind:** L13, missing_rule. Scope: fx_only. judgment = false.
- **Rule:** Only when the CBDR (14:00-20:00 NY) is < 40 pips (ideally 20-30) and the daily bias is set by a PD array. After London prints the Judas extreme, n = the number of CBDR SDs reached. U = R*(n+1), measured CBDR low to London high on sell days (CBDR high to London low on buy days). Sell-day projections = CBDR_low - k*U; buy-day = CBDR_high + k*U, k = 1..3. Use only where they overlap a PD array and the expected time of day. The entry-side extreme is the precise one. The far projection may land exactly, 1-2 pips short or 5-6 pips beyond, so take most profit on approach and leave a small piece.
- **Sources:** cc08_004_JKzEhfwV1dY ~00:15:51, ~00:24:37.
- **Quote:** "the Precision really is on the entry side"
- **Conflicts:** none.
- **Rulebook fix:** L13 [fx-only]: add the projection unit and tolerance.
- **BUILD SPEC:** none (fx_only).

### 147. LLT3-daily-draw-multiday
- **rule_id / kind:** new, missing_rule. Scope: general. judgment = false.
- **Rule:** Daily draw D = the next daily premium array above (bullish, after a reaction at a daily discount array) or discount array below (bearish). Expected move = |D - price|. It may take several days. While D is unreached, the daily chart still respects the PD-array matrix and no bias flip (B8) has occurred, keep the same bias and allow a new same-direction setup the next day (ICT: the next day's London). Mark D done once traded.
- **Sources:** cc08_006_stK2gNqhLaM ~00:22:03.
- **Quote:** "it can take several days and that's going to also facilitate the continuation"
- **Conflicts:** none.
- **Rulebook fix:** new rule under B17/L14: an unmet daily draw carries across days.
- **BUILD SPEC (bias_htf):**
  - `htf.table` column `d_draw` (level) and `d_draw_dir`: set when a daily bar reacts at a daily array (existing reaction logic), cleared when traded or when `flip` changes. With `d_draw_carry`, `want` = `d_draw_dir` on each following day while set (overrides a neutral daily bias only), and the draw lock prefers `d_draw`.
  - Params: `d_draw_carry: bool = False`.
  - Test: `test_daily_draw_carries_until_hit`. Draw 4200 set Monday, unmet Tue/Wed: want +1 both days; hit Wed: cleared Thu.

### 148. LLT3-london-extreme-preny-range
- **rule_id / kind:** L1, missing_rule. Scope: general. judgment = true.
- **Rule:** At the NY open, LR = [London session extreme E (high when bearish, low when bullish), the opposite extreme printed between E and the NY open]. Bearish: expect the next trading day's retracement up to trade into LR and sell its premium with an entry PD array. Bullish: mirror. Also mark the prior NY session high/low: a retracement inside it often frames the next day's higher low (bullish) or lower high (bearish). The 09:30 index mapping is our interpretation.
- **Sources:** cc08_007_5Z_3NbclMSY ~00:02:37.
- **Quote:** "the total range from the London session extreme ... to the lower high prior to the New York session beginning"
- **Conflicts:** none.
- **[our interpretation]:** NY open = 09:30 for indices.
- **Rulebook fix:** L1: add the London-extreme-to-pre-NY range.
- **BUILD SPEC (levels_detectors):**
  - In `DayCtx` for the next day: from yesterday's bars, E = London (02:00-05:00) high (bearish `want`) and O = lowest low between E's bar and 09:30; store `ctx.lr_prev = (O, E)`. With `london_lr_zone`, a short entry in today's session is tagged `in_lr` when within LR's premium half (>= (O+E)/2); "require" mode rejects others for bearish days. Mirror.
  - Params: `london_lr_zone: str = "off"` ("tag" / "require").
  - Test: `test_prev_london_range_zone`. Yesterday E 4120, O 4100: today short at 4115 tagged, 4105 not.

### 149. LLT3-pdh-raid-after-multiday-run
- **rule_id / kind:** L2, missing_condition. Scope: general. judgment = true.
- **Rule:** After several (our test: >=3) consecutive up days into a daily premium PD array, a trade above the previous day's high (buy-stop raid) marks a likely end of the move: look to sell for a day trade after the raid. Mirror: several down days into a daily discount array, a run below PDL -> buy the sell stops for a day-trade long. Still needs an HTF array at the level (L2).
- **Sources:** cc08_007_5Z_3NbclMSY ~00:05:05.
- **Quote:** "I'll look for a buy stock run there and then go short the next day"
- **Conflicts:** none.
- **[our interpretation]:** n = 3 up closes.
- **Rulebook fix:** L2: add the multi-day-run context for PDH/PDL raids.
- **BUILD SPEC (bias_htf):**
  - `htf.table` column `run_into_array` (+1 after >= `raid_run_days` up closes with the last high inside a daily premium array; -1 mirror). With `pdh_raid_rev`, on such a day a sweep of PDH arms shorts only (side gate -1 after the raid), mirror for PDL.
  - Params: `pdh_raid_rev: bool = False`, `raid_run_days: int = 3`.
  - Test: `test_pdh_raid_after_three_up_days`. Three up closes into a daily SIBI, today's sweep of PDH: shorts allowed, longs blocked.

### 150. LLT3-room-dayscalp-threshold
- **rule_id / kind:** L15, missing_condition. Scope: fx_only. judgment = true.
- **Rule:** room = distance from current price at entry to the opposing daily/4h PD array (premium for longs, discount for shorts), after price has reacted at a daily/4h array in the bias direction. FX: >= 50-60 pips = day trade; < 40 pips = scalp (allowed, small target); 40-50 undefined (judgment). The index thresholds and the "no runner on scalps" rule are our interpretation, to be tested.
- **Sources:** cc09_001__TNhWRPa6GA ~00:04:43.
- **Quote:** "anything less than 40 pips it's a scalp"
- **Conflicts:** none.
- **Rulebook fix:** FX-only list: add the day-trade vs scalp room tiers.
- **BUILD SPEC:** none (fx_only; an index analogue would reuse `room_ref="htf_far"`, item 61).

### 151. LLT3-asian-range-pool-entry
- **rule_id / kind:** new, missing_rule. Scope: fx_only. judgment = true.
- **Rule:** Asian range = 20:00-00:00 NY high/low. Bullish daily/4h IOF: enter longs below the Asian high, preferably after a run below the Asian low (or PDL) and below the midnight/opening price into a 15m discount array, with a sharp response. A later retracement to the Asian high that holds as support = an entry or add (often into the NY open or London close). Bearish: mirror. HOD/LOD estimate: where Asian-range SD projections lie close to CBDR SD projections and a PD array. The number of SDs is not specified. Index use of an Asia pool is our interpretation.
- **Sources:** cc09_001__TNhWRPa6GA ~00:02:07; cc09_004_g7jchu4g31c ~00:19:20; cc12_004_Oec_0NM_OeY ~00:11:14.
- **Quote:** "smart money sells above the Asian range high"
- **Conflicts:** cc09_001 "and/or" vs checklist "and"; T3/L1 Asia FX-only vs cc09_004 generic pool.
- **Rulebook fix:** FX-only list: add the Asian-range entry rules.
- **BUILD SPEC:** none (fx_only; an index test would add `asia_pool` to `DayCtx.sess` with 20:00-00:00 ETH bars).

### 152. LLT3-filling-numbers-count
- **rule_id / kind:** L13, missing_rule. Scope: fx_only. judgment = false.
- **Rule:** Build a sorted level list from the chosen tool (pivots with midpoints M0-M5, CBDR, Asian or Flout ladder). Long: the first 4 levels above the entry, in order; short: the first 4 below. A level fills when price trades through it. Four is a rule-of-thumb minimum, not a cap. After 4 fill, take about 75-80% off and leave about 20-30% for a possible large-range day if time permits. Log fills per tool.
- **Sources:** cc09_002_zanmou0ic5U ~00:05:47, ~00:06:23.
- **Quote:** "you look above your entry point for the sequential four levels above"
- **Conflicts:** none.
- **Rulebook fix:** L13 [fx-only]: define filling the numbers.
- **BUILD SPEC:** none (fx_only).

### 153. LLT3-filling-numbers-cbdr-asian-ladders
- **rule_id / kind:** L13, missing_rule. Scope: fx_only. judgment = false.
- **Rule:** CBDR ladder (14:00-20:00 NY, H = height, wicks or bodies). Short with the entry above the CBDR low: level k = CBDR_low - (k-1)*H. Long with the entry below the CBDR high (ICT says "low", likely a slip): level k = CBDR_high + (k-1)*H. Asian ladder (20:00-00:00, H = height). Long with the entry below the Asian range (ICT's wording; cc12_004 allows below the Asian high): level k = Asian_high + (k-1)*H. Short: mirror from the Asian low. A level counts when price crosses it. Expect about 4.
- **Sources:** cc09_002_zanmou0ic5U ~00:07:40, ~00:10:50.
- **Quote:** "you count the high of the Asian Range as level one of four to fill"
- **Conflicts:** ~9:58 "below the CBDR low" (likely a slip); level-1-at-edge (cc09_002) vs cc08_003 SD_k counting (offset by one).
- **Rulebook fix:** L13 [fx-only]: add both ladders.
- **BUILD SPEC:** none (fx_only).

### 154. LLT3-pivots-staged-orders
- **rule_id / kind:** new, missing_rule. Scope: fx_only. judgment = true.
- **Rule:** Use 0 GMT floor pivots (PP, R1-R3, S1-S3 and midpoints M0-M5) as staged-order magnets that price trades to and through, mainly for counting filled levels. On a bearish day after the range has expanded below S1/S2, a retrace up to S1/S2 is a continuation-sell location (still needs a premium PD array). Do not buy just because price is below PP. Mirror for R1/R2 on bullish days. Never use a pivot alone as an entry.
- **Sources:** cc09_002_zanmou0ic5U ~00:03:23.
- **Quote:** "that actually might be a really good area to sell short"
- **Conflicts:** none.
- **Rulebook fix:** FX-only list: pivots are staged orders.
- **BUILD SPEC:** none (fx_only).

### 155. LLT3-projection-tool-selection
- **rule_id / kind:** new, missing_rule. Scope: fx_only. judgment = true.
- **Rule:** Each day compute the pivot, CBDR, Asian and Flout ladders. No tool is known in advance. From London into the NY session, note which ladder(s) price is respecting (our test: count levels touched and turned or paused at). Then target levels where one or more ladders agree with a PD array, time of day and the bias. A projection alone means nothing.
- **Sources:** cc09_002_zanmou0ic5U ~00:16:14.
- **Quote:** "The New York session will generally provide the measurements"
- **Conflicts:** none.
- **Rulebook fix:** FX-only list: tool selection by observation.
- **BUILD SPEC:** none (fx_only).

### 156. LLT3-target-confluence-projection-adr-array
- **rule_id / kind:** X1, missing_rule. Scope: general. judgment = true.
- **Rule:** Long: projected ADR high = LOD (or the midnight open) + ADR5. Candidate targets = opposing premium arrays on 15m/60m/4h/daily. Prefer the candidate whose zone holds the ADR high plus >= 1 projection level. For index that means L12 SD levels or L13 projections; CBDR/Asian/flout SDs and pivots are fx-only. Factor in time of day: the kill zone and whether the session still has room to run there is our interpretation. Shorts mirror. FX example: 1.0930 called, off by ~5 pips.
- **Sources:** cc09_002_zanmou0ic5U ~00:17:01; cc09_008_cqf8nH54bb8 ~00:47:17.
- **Quote:** "looking for average daily Range High to converge as well again with an opposing premium array"
- **Conflicts:** none.
- **[our interpretation]:** "zone holds" = within the array or 1 pt of it; time check = before 11:30 for AM trades.
- **Rulebook fix:** X1/L16: add the ADR + projection + opposing-array convergence target.
- **BUILD SPEC (targets_partials):**
  - With `adr_conv_target`: adr_hi = min(day low so far, midnight open) + ADR5 (`strategy.adr5`, built). Among ladder levels of kind "array" from 15m/1h/4h/D, the first whose zone contains adr_hi (± `adr_conv_pts`) and has a "proj" level within the same tolerance becomes the final target (kind "proj_htf"); skip if after `adr_conv_last`.
  - Params: `adr_conv_target: bool = False`, `adr_conv_pts: float = 1.0`, `adr_conv_last: int = 690`.
  - Test: `test_adr_projection_array_convergence`. Low 4000, ADR5 40, 1h SIBI 4038-4044, SD 4040: final 4040.

### 157. LLT3-pdh-pdl-daily-expectation
- **rule_id / kind:** L2, missing_condition. Scope: general. judgment = false.
- **Rule:** Each day expect price to retest or trade through at least one of PDH/PDL (cc09_002 ~1:23). Exception per ICT: the day's range may be too small to reach either. Our proxy for that is ADR5 < the distance from the open to the nearer level. Keep the last 3 days' high/low as reference levels. Log the % of days that touch PDH or PDL.
- **Sources:** cc09_002_zanmou0ic5U ~00:01:23.
- **Quote:** "we always look for one of those levels to be traded to"
- **Conflicts:** none.
- **Rulebook fix:** L2: add the daily expectation and the small-range exception.
- **BUILD SPEC (day_week_context, report):**
  - Add day summary fields `pdh_hit`, `pdl_hit`, `pd_reach_ok` (ADR5 >= distance from the 09:30/midnight open to the nearer level); `study.py` prints the touch rate overall and when `pd_reach_ok`. No trading effect (the `pdh*`/`pdl*` pools already exist).
  - Params: none.
  - Test: `test_pdh_pdl_touch_stat`. A day trading above PDH: pdh_hit 1.

### 158. LLT3-equal-highs-fade-condition
- **rule_id / kind:** A3, missing_condition. Scope: general. judgment = true.
- **Rule:** After price runs an REH, short the raid if either (1) HTF order flow (weekly/daily/4h) is bearish and the rally is a retracement into a premium array, or (2) the market is neutral/consolidating or at a turning point and an HTF premium array sits just above the REH, with confluent PD arrays. If neither holds, treat the REH as a continuation target. Mirror for REL. Raid depth 10-20 pips in FX. Index depth is our interpretation (L4: up to ~10 handles).
- **Sources:** cc09_005_KrGTimL3YRQ ~00:20:04.
- **Quote:** "sometimes old equal highs can be just targets for a longer term price move higher"
- **Conflicts:** none.
- **[our interpretation]:** "just above" = within `ts_max_pts`; neutral = daily bias 0 or `drange` 0.
- **Rulebook fix:** A3: add the fade-vs-continuation condition.
- **BUILD SPEC (setups_models):**
  - In the sweep block, with `reh_fade_gate`, a short after a "pool_eq" sweep is armed only if (`want` == -1 and the sweep is into a premium array per `htf` arrays) or (`want` == 0 and an opposing 1h+ array lies within `ts_max_pts` above the REH). Otherwise the REH stays a long target only.
  - Params: `reh_fade_gate: bool = False`.
  - Test: `test_reh_fade_needs_context`. want +1, REH swept, no array above: no short.

### 159. LLT3-adr5-target-ladder
- **rule_id / kind:** L16, missing_condition. Scope: general. judgment = true.
- **Rule:** ADR5 = mean(high-low) over the last 5 days. Long: ADR_high = day low or London low + ADR5. T1 = ADR_high, T2 = the next 4h or 60m premium PD array above (cc09_006). If reached before 10:00, take 80% and keep a runner (L16). If price trades beyond ADR_high, fib the ADR range and use the 1.27 and 1.62 extensions only where a 15m/60m premium array overlaps (cc12_004; this extends L13). Shorts mirror. Treating the first-reached as the main exit is our interpretation.
- **Sources:** cc09_006_OVfn-gDk2dE ~00:19:23; cc09_007_-oMtfDvc18Y ~00:08:32; cc12_004_Oec_0NM_OeY ~00:17:45.
- **Quote:** "targets will be the five-day average daily Range High and the next higher time frame premium array"
- **Conflicts:** none.
- **[our interpretation]:** anchor (day low vs London low switch).
- **Rulebook fix:** L16: add T2 = next 4h/60m array and the ADR-range extensions.
- **BUILD SPEC (targets_partials):**
  - Listed: L16 `adr_target`/`adr_frac`, `adr_early`. New: `adr_t2_htf` (append the nearest 1h/4h opposing array beyond the ADR level as the next rung) and `adr_ext` (once a bar trades beyond the ADR level, add ADR_lo + 1.27/1.62 x ADR5 rungs, kept only within 1 pt of a 15m/1h array). `adr_anchor: str = "day_low"` / "london_low".
  - Params: `adr_t2_htf: bool = False`, `adr_ext: bool = False`, `adr_anchor: str = "day_low"`.
  - Test: `test_adr_ladder_ext`. Low 4000, ADR5 40, 1h SIBI at 4051: rungs 4040, 4050.8 (kept, near 4051).

### 160. LLT3-adr-fib-close-zone
- **rule_id / kind:** new, missing_rule. Scope: general. judgment = false.
- **Rule:** Bullish day: L = day low or London low, H = L + ADR5, anchored ahead of time. Expected close = on H, or after trading off H, in [H - 0.30*(H-L), H - 0.20*(H-L)]. London close counter-trade (10:30-13:00, after ADR is met) targets a 20-30% retracement of the day's range (cc09_007). Bearish mirror. Source is FX; index use is untested.
- **Sources:** cc09_006_OVfn-gDk2dE ~00:26:59.
- **Quote:** "close in between the 20 and 30 levels on your FIB"
- **Conflicts:** none.
- **Rulebook fix:** new rule under L16: the ADR fib close zone.
- **BUILD SPEC (day_week_context, study first):**
  - Report: day summary field `close_in_adr_zone` (close inside [H-0.30R, H-0.20R] or at H) on days ADR was met. Trading switch only after the stat: `adr_close_runner` exits runners at H - 0.20R if price has traded H and turned (a 5m close back below H).
  - Params: `adr_close_runner: bool = False`.
  - Test: `test_adr_close_zone_stat`. L 4000, ADR5 40, close 4031: in zone.

### 161. LLT3-adr-can-double
- **rule_id / kind:** L16, shortened. Scope: fx_only. judgment = true.
- **Rule:** Expect day range ~= 2x ADR5 when (a) a long-term trend is underway, an intermediate-term swing has just begun, and ADR5 < 60 pips, or (b) an intermediate swing is completing into a daily/weekly PD array on high-impact news (capitulation). Otherwise ADR5 is a soft objective that may not be reached.
- **Sources:** cc09_007_-oMtfDvc18Y ~00:14:20.
- **Quote:** "a large impulse swing can surge the daily range twice the average daily range"
- **Conflicts:** none.
- **Rulebook fix:** L16 [fx-only]: ADR is soft; doubling conditions.
- **BUILD SPEC:** none (fx_only; N8.5 `expansion_due` covers the index analogue).

### 162. LLT3-judas-depth-third-adr
- **rule_id / kind:** L16, missing_rule. Scope: general (checker: fx; index analogue is ours). judgment = true.
- **Rule:** FX classic day (the index analog is our interpretation): the move from the midnight NY open against the bias is expected to reach roughly 1/3 of ADR (33 pips on a 100-pip day). LOD candidate zone = [open - ~0.33*ADR5, open], ideally at a 15m discount array converging with a daily/4h/60m one. A much deeper dip weakening the template is our interpretation.
- **Sources:** cc09_008_cqf8nH54bb8 ~00:46:50.
- **Quote:** "trades down up to 33 Pips or thereabouts"
- **Conflicts:** none.
- **[our interpretation]:** index use; the weakening rule.
- **Rulebook fix:** L16: add the 1/3-ADR Judas depth (FX; index test).
- **BUILD SPEC (setups_models, tag first):**
  - In `_scan_core`, tag each sweep with `judas_adr = |sweep extreme - midnight open| / ADR5`; with `judas_depth_max > 0`, reject sweeps deeper than that fraction on the bias side (test 0.33, 0.5).
  - Params: `judas_depth_max: float = 0.0`.
  - Test: `test_judas_depth_fraction`. Open 4000, ADR5 30, sweep low 3988: tag 0.4; rejected at 0.33.

### 163. LLT3-cot-nodule-levels
- **rule_id / kind:** new, missing_rule. Scope: general (needs COT data). judgment = true.
- **Rule:** For each nodule (a run of consecutive weeks with commercial_net on the other side of its 6/12-month basis from the prior run), record the futures' price range over those weeks. Mark it as an HTF PD array: support for a buying nodule, resistance for a selling one. Use it for bias and targets. ICT does not specify the exact candle. Our interpretation: the OB of the lowest (buying) or highest (selling) week inside the nodule.
- **Sources:** cc10_001_9H4iaaQXV5Y ~00:30:31.
- **Quote:** "those levels are significant in the future"
- **Conflicts:** none.
- **Rulebook fix:** B20: add nodule price ranges as HTF levels.
- **BUILD SPEC:** none (COT is not loaded; B20.1 `cot_tag` loader is listed in bias_htf; add nodule levels after it exists).

### 164. LLT3-or-forms-day-extreme
- **rule_id / kind:** T12, shortened. Scope: general. judgment = true.
- **Rule:** Index: at 10:30 mark the OR60 (09:30-10:30) low/high as the probable LOD/HOD if it formed by a stop run on a known pool, or by a fair-value setup (bullish/bearish OB, trade into a liquidity void, FVG fill). Then favor the opposite direction for the session. Bonds [bonds-only]: same logic for 08:00-09:00. Test as a conditional stat.
- **Sources:** cc10_006_CGbSpa_9Z9Y ~00:03:50; cc10_010_ORbtHOUzAIM ~00:03:18.
- **Quote:** "It can be a run on stops or fair value setup."
- **Conflicts:** T4 2023 index OR = 09:30-10:00; CC uses 09:30-10:30.
- **[our interpretation]:** "formed by" = the OR60 extreme is within 1 tick of a swept pool or inside a 5m/15m array.
- **Rulebook fix:** T12/T4: add the formation mechanism and the window conflict.
- **BUILD SPEC (bias_htf):**
  - At 630 in `run_day`: if the OR60 low swept a pool (`mark_levels` keys) or sits inside a bullish array (`array_cands` types) and the OR60 high did not, set `or60_side` = +1 (mirror -1); with `or60_bias`, `want` = `or60_side` from 10:30 when the daily bias is neutral or agrees. Report the conditional stat (HOD/LOD in OR60 by condition) in `study.py`.
  - Params: `or60_bias: bool = False`.
  - Test: `test_or60_extreme_by_stop_run`. OR60 low sweeps PDL: or60_side +1.

### 165. LLT3-0800-0900-pool-stock-open
- **rule_id / kind:** L1, missing_rule. Scope: general (index carryover is ours). judgment = true.
- **Rule:** Bonds [bonds-only]: the 08:00-09:00 high/low are liquidity pools that tend to be raided around the 09:30 stock open (cc10_006). Index carryover (our interpretation, test only): mark ES 08:00-09:00 high/low as `or0809_pool` AM sweep pools and expect a raid of one edge at or after 09:30 followed by an M0 reversal.
- **Sources:** cc10_006_CGbSpa_9Z9Y ~00:04:06.
- **Quote:** "the location for liquidity pools to build around for the Stock Market opening"
- **Conflicts:** none.
- **Rulebook fix:** L1: add the 08:00-09:00 range as a bond pool; index use as a test.
- **BUILD SPEC (levels_detectors):**
  - Covered mechanically by `session_ors` (item 13) with (480, 60); add the alias `or0809_pool: bool = False` that appends (480, 60) to it and makes those pools eligible as AM sweep pools in `mark_levels`.
  - Params: `or0809_pool: bool = False`.
  - Test: `test_or0809_pool`. 08:00-09:00 low 4000: AM sell-side pool 4000 from 09:00.

### 166. LLT3-bond-or-light-volume-run
- **rule_id / kind:** new, missing_rule. Scope: bonds_only. judgment = true.
- **Rule:** Bonds: OR = 08:00-09:00 NY, built from bodies plus wicks, and it includes nearby earlier highs/lows (e.g. equal highs formed 00:00-02:00). Keep OR high/low as liquidity references through the afternoon, evening and Asian session. If price runs beyond the OR high on lower volume than the OR's peak volume bar, expect failure and a retrace into the nearest FVG below (close inside it). Mirror for the OR low.
- **Sources:** cc10_006_CGbSpa_9Z9Y ~00:10:13.
- **Quote:** "it ran the stops above that range and failed to go any higher"
- **Conflicts:** none.
- **Rulebook fix:** add under [bonds-only].
- **BUILD SPEC:** none (bonds_only).

### 167. LLT3-bond-target-ticks
- **rule_id / kind:** new, missing_rule. Scope: bonds_only. judgment = true.
- **Rule:** ZB: tick = 1/32 = $31.25; handle = 32 ticks = $1000/contract. Normal intraday target 5-8 ticks; 16 ticks = a good day; 32 ticks only on large-range days. On consolidation days aim for ~8 ticks but place the limit beyond it (e.g. 16 ticks) as a bonus (cc10_008 ~14:53). Room filter of >= ~8 ticks is our interpretation.
- **Sources:** cc10_006_CGbSpa_9Z9Y ~00:15:09.
- **Quote:** "five to eight ticks as they intraday day trade there's certainly nothing wrong with that"
- **Conflicts:** none.
- **Rulebook fix:** add under [bonds-only].
- **BUILD SPEC:** none (bonds_only).

### 168. LLT3-pm-measured-move-am-leg
- **rule_id / kind:** T13, missing_rule. Scope: general. judgment = false.
- **Rule:** Two-session up-close day (daily/4h order flow bullish, no HTF premium array reached): AM leg = AM high - AM low (the low at the discount array). If lunch holds above the AM low (shallow retrace, or a lunch-low sweep / drop into a discount FVG), PM objective = PM swing low + AM leg (equal-distance second leg), used as T2/runner. Lunch may not consolidate at all on strong catalyst days. Down-close mirror. Index source cc10_013; bond analogue cc10_007 (AM 08:00-12:00), where the PM leg comes faster.
- **Sources:** cc10_007_JpV-J31mxhg ~00:08:34; cc10_013_P5pyzmgZA1s ~00:02:31.
- **Quote:** "a second leg of equal distance seen from the am session"
- **Conflicts:** none.
- **Rulebook fix:** T13: add the PM equal-leg objective.
- **BUILD SPEC (targets_partials):**
  - For PM trades (session "PM") with `pm_am_leg` and `want` +1: if the lunch low > AM low, add rung = (the trade's sweep low, or PM swing low) + (am_hl[0] - am_hl[1]) as kind "proj". Mirror.
  - Params: `pm_am_leg: bool = False`.
  - Test: `test_pm_equal_leg_target`. AM 4000-4030, PM low 4020: rung 4050.

### 169. LLT3-consolidation-day-overnight-targets
- **rule_id / kind:** L1, missing_condition. Scope: general. judgment = false.
- **Rule:** On a predicted consolidation day, NY-session targets are the overnight liquidity: London 02:00-05:00 high/low, the overnight high/low and short-term swing highs/lows formed overnight (low-resistance runs). Both London extremes can be raided for AM opportunities. Trade them in the AM only, done by 11:00 (N8). Nearest-untaken selection is our interpretation. Shown on bonds (cc10_008 ~16:07).
- **Sources:** cc10_008_RgpxhuVp5Xg ~00:16:19.
- **Quote:** "that's where your liquidity is going to be"
- **Conflicts:** none.
- **Rulebook fix:** L1/N8: add the consolidation-day overnight target set.
- **BUILD SPEC (targets_partials):**
  - With `consol_overnight_targets` and the day tagged consolidation (N8.1/N8.3 classifier, listed), restrict `_targets` pools to London H/L, overnight H/L (`pmh`/`pml`, `pre_at`) and overnight 5m pivots (`pool_swings` limited to bars before 09:30); single target (nearest), AM only, done at 660.
  - Params: `consol_overnight_targets: bool = False`.
  - Test: `test_consol_day_overnight_pools_only`. Consolidation tag: ladder = nearest overnight pool only.

### 170. LLT3-wide-or-bias-end
- **rule_id / kind:** T4, shortened. Scope: index. judgment = true.
- **Rule:** OR60 = 09:30-10:30 NY high/low. If OR60 is extended/wide (threshold is our interpretation, e.g. >= 1.5x the 20-session median), expect one end to be violated later in the day: the OR60 high on a bullish day, the OR60 low on a bearish day, regardless of which way the OR itself moved. Example: turtle soup below the OR low later in the morning, then a rally back to the OR high. Without a bias, no target from this rule.
- **Sources:** cc10_010_ORbtHOUzAIM ~00:06:15.
- **Quote:** "we'll look for that upper end of the opening range to be violated or traded to"
- **Conflicts:** T4 summarises cc10_010 as "opposite end gets run" (direction of the OR, not bias).
- **Rulebook fix:** T4: the end is chosen by daily bias.
- **BUILD SPEC (targets_partials):**
  - Listed: L3 `or_extra` (built). With `wide_or_draw`, after 630 if OR60 range >= `wide_or_mult` x the 20-session median OR60, add the OR60 end in the `want` direction as the locked draw (pool kind) for the rest of the day.
  - Params: `wide_or_draw: bool = False`, `wide_or_mult: float = 1.5`.
  - Test: `test_wide_or_bias_end`. Wide OR 4000-4040, want +1: draw 4040 even if the OR moved down.

### 171. LLT3-pm-target-am-rejection-block
- **rule_id / kind:** L14, missing_condition. Scope: index. judgment = false.
- **Rule:** Add to T9/L14: PM long off a same-day AM/lunch bullish OB (already T9). First PM target = the nearest bearish rejection block formed in the AM session above (A17 zone; first partial at its body edge, L11). Next = AM high/HOD, typically 15:00-16:00 (T12). The PM can also violate the AM rejection block and keep rallying. Short mirror.
- **Sources:** cc10_012_qZg_5bac518 ~00:04:34.
- **Quote:** "price rallies away from it bullish order block up into a rejection block"
- **Conflicts:** none.
- **Rulebook fix:** T9/L14: add the AM rejection block as the first PM target.
- **BUILD SPEC (targets_partials):**
  - For PM-session trades with `pm_am_rb`, run `levels.rejection_blocks` on today's 5m bars 570-720 and add the nearest bearish RB beyond entry (body edge kind "array", wick kind "pool") before the AM high rung.
  - Params: `pm_am_rb: bool = False`.
  - Test: `test_pm_first_target_am_rejection_block`. AM RB body 4050 wick 4056, AM high 4060: rungs 4050, 4056, 4060.

### 172. LLT3-pm-reversal-launch-array-filter
- **rule_id / kind:** T13, missing_rule. Scope: index. judgment = false.
- **Rule:** AM rally, PM reversal: find the PD array the AM rally launched from. If it is a 4h/daily/weekly discount array, expect it to hold when the PM decline returns to it, and allow a PM long there. If it is only a 15m/60m array, expect price to trade through it, with the PM short target below it. Mirror for AM decline + PM rally.
- **Sources:** cc10_013_P5pyzmgZA1s ~00:08:50.
- **Quote:** "if it's not a four hour or a daily or higher than that discount array expected to trade through"
- **Conflicts:** none.
- **Rulebook fix:** T13: add the launch-array filter.
- **BUILD SPEC (targets_partials):**
  - At 13:30 record `am_launch` = the array containing the AM low (TF from `_htf_tag` / `htf` arrays). With `pm_launch_filter`: if its TF in {4h, D, W}, PM shorts' final target = that array's near edge and PM longs may arm there; if 15m/1h, PM shorts' ladder extends beyond it to the next pool.
  - Params: `pm_launch_filter: bool = False`.
  - Test: `test_pm_reversal_launch_tf`. AM low in a daily BISI: PM short final = its top; in a 15m BISI: extends below.

### 173. LLT3-consolidation-lunch-vs-am-extreme
- **rule_id / kind:** T13, missing_rule. Scope: index. judgment = false.
- **Rule:** Consolidation (neutral order flow, no news), AM rally then PM decline: if the AM high traded into an HTF (1h/4h+) premium array, the PM raids only the lunch high; else it raids the intraday (AM) high. Then it reaches for the day's/intraday or London sell stops. Mirror for AM decline then PM rally. Alternative outcome: the PM just consolidates into the close.
- **Sources:** cc10_013_P5pyzmgZA1s ~00:13:28.
- **Quote:** "it's likely that it won't go back up there because they've already defended that level"
- **Conflicts:** none.
- **Rulebook fix:** T13: add the lunch-vs-AM raid filter.
- **BUILD SPEC (setups_models):**
  - On consolidation-tagged days (N8), PM sweep pick: with `pm_raid_filter`, if the AM high is inside a 1h/4h premium array, the only eligible PM short sweep pool is the lunch high (`sess["lunch"]`); else the AM high. Targets: day low / London low.
  - Params: `pm_raid_filter: bool = False`.
  - Test: `test_pm_raid_lunch_high_when_am_hit_htf`. AM high in a 1h SIBI: PM sweep of the AM high not armed; lunch high armed.

### 174. LLT3-lunch-hl-raid-not-target
- **rule_id / kind:** L3, wrong. Scope: index. judgment = false.
- **Rule:** Remove cc10_013 from L3's "lunch REL/REH are the PM's targets" (015/067 may still support it). Add from cc10_013: the PM typically first runs the lunch-hour extreme opposite to its coming move (or, on trending days, drops/rises into a discount/premium FVG instead; on reversal and consolidation days it may run the intraday extreme per the HTF filter). It then targets the opposite liquidity: trending = continue into the close; reversal = reverse into the close; consolidation = the day's/London opposite stops. Use lunch H/L as the PM entry-sweep level.
- **Sources:** cc10_013_P5pyzmgZA1s ~00:01:50.
- **Quote:** "the PM Trend runs the lunch hour lows cell stops or drops into a fair value discount array"
- **Conflicts:** L3 (015, 067, cc10_013) lunch REL/REH as PM targets vs cc10_013 lunch as the raid level; keep 015/067 for the target reading.
- **Rulebook fix:** L3: drop the cc10_013 citation; add the lunch raid reading under T13.
- **BUILD SPEC (setups_models):**
  - Built: `pm_off_lunch` (lunch high as the draw). Add `pm_lunch_raid`: in the PM session, the lunch extreme opposite to `want` is a sweep pool (PM entry sweep), and it is removed from the PM target ladder for that side.
  - Params: `pm_lunch_raid: bool = False`.
  - Test: `test_pm_lunch_low_is_sweep_pool`. want +1 PM: a lunch-low sweep arms a long; the lunch high stays a long target.

### 175. LLT3-session-targets-15m-60m
- **rule_id / kind:** X1, missing_rule. Scope: index. judgment = false.
- **Rule:** X1 addition: on trending (two-session) days, each session's objective (AM and PM) is most likely an opposing 15m or 60m PD array (premium array for longs, discount for shorts). The PM can stall short of it, retrace, then reach it in the last hour, so hold toward the close (cc10_014 ~3:11-5:08). Exit per X2 buffers. No conflict with L9, which already allows HTF FVG targets.
- **Sources:** cc10_014_yWBxZsbmK1U ~00:04:18.
- **Quote:** "most likely a 15 minute or a 60-minute PD array"
- **Conflicts:** none (the claimed L9 conflict is false).
- **Rulebook fix:** X1: add the session-objective TF.
- **BUILD SPEC (targets_partials):**
  - With `session_obj_tf`, the session's locked draw (`_lock_step`) prefers the nearest opposing 15m/1h array beyond price over pools; in the PM, a trade toward it is not flattened before 15:45 unless stopped (management exception flag `hold_to_obj`).
  - Params: `session_obj_tf: bool = False`.
  - Test: `test_session_draw_prefers_15m_60m_array`. 1h SIBI 4050 and a pool 4045: draw 4050.

### 176. LLT3-stock-low-resistance-distance
- **rule_id / kind:** L4, missing_rule. Scope: stocks. judgment = true.
- **Rule:** Stocks (weekly chart): keep a long candidate only if a clean old high (multi-year high or equal highs) sits close above price, price has not already blown through an intermediate short-term high (weak structure), and price is not too extended from its weekly/daily structure. Target = a low-resistance run through that old high. If the old high is far away (Disney: needed about $15, ~14%, to reach 120), expect lethargic, sideways or reversing action and drop the candidate. The distance threshold is our interpretation (parameter, e.g. <= ~10%); ICT gives no percentage.
- **Sources:** cc10_016_rcO8-nb3S0Q ~00:12:49.
- **Quote:** "you're going to see some lethargic price action"
- **Conflicts:** none.
- **[our interpretation]:** distance cap; "extended" = more than 2 weekly ATR above the last weekly pivot low.
- **Rulebook fix:** L4 (stocks): add the distance/extension filter.
- **BUILD SPEC (bias_htf, stocks screen):**
  - New `study.py` screen `stock_lrlr(symbol)` on weekly bars (Alpaca daily data aggregated): returns pass/fail with old high distance, broken intermediate-high flag and extension. Used only by a stock candidate list; no effect on index runs.
  - Params: `stock_old_high_max_pct: float = 0.10`.
  - Test: `test_stock_old_high_distance_filter`. Price 105, old high 120: fail at 10%; old high 113: pass.

### 177. LLT3-rounding-step-direction
- **rule_id / kind:** L17, shortened. Scope: fx_only. judgment = true.
- **Rule:** For each PD array level: premium (above price) -> round DOWN to the nearest level ending in 0 or 5; discount (below price) -> round UP to the nearest level ending in 0 or 5. A level already on a 0/5 stays (73.80 example). Do this as the checklist step just before setting the daily bias. The source is FX (pips); for index the increment is our interpretation (round_step parameter). The worked example (cc12_001 ~50:39: discount OB 73.82 -> 73.85) agrees with the slide rule, so there is no conflict.
- **Sources:** cc12_001_eIdnsgq-G7A ~00:34:13, ~00:50:39; cc12_002_Ad-votrg6WQ ~00:18:40; cc12_003_3B7Reg2Yiqs ~00:24:47.
- **Quote:** "calibrate to the nearest five or zero level"
- **Conflicts:** none (the claimed slide-vs-example conflict is false).
- **Rulebook fix:** L17: add the 0/5 granularity and the checklist position.
- **BUILD SPEC:** none (fx_only; the index side is the built L17 `round_step_pts`, toward price, off).

### 178. LLT3-impulse-retrace-expansion
- **rule_id / kind:** L13, missing_rule. Scope: general. judgment = true.
- **Rule:** Profile: impulse A->B, retracement to C (ideally into a discount array), then expansion that tends to run a little beyond the impulse length |B-A|. Projection (our interpretation): expected target ~ C + (B-A); further targets = 1.27/1.62 extensions of A-B, kept only where they overlap an opposing PD array or pool (L13). Mirror for bearish. It is a tendency, not a minimum.
- **Sources:** cc12_002_Ad-votrg6WQ ~00:44:24.
- **Quote:** "expansion swing tends to go a little bit more than the impulse swing"
- **Conflicts:** none.
- **Rulebook fix:** L13: add the swing profile behind the extensions.
- **BUILD SPEC (targets_partials):**
  - Add `mm_anchor="impulse"` (Ep08.9 `mm_targets` listed): A = the leg origin low before the MSS, B = the MSS leg high, C = the fill/sweep low of the retrace; rung C + (B - A) as kind "proj".
  - Params: extend `mm_anchor` values with "impulse".
  - Test: `test_impulse_expansion_target`. A 4000, B 4020, C 4010: rung 4030.

### 179. LLT3-dealing-range-rollover
- **rule_id / kind:** L14, missing_rule. Scope: general. judgment = false.
- **Rule:** When price trades beyond the range high: retire the old range as the dealing range, but keep its levels (high, EQ, arrays) as discount arrays/support below. The new range high = the next unmitigated premium array above (old high, then rejection block, FVG, OB, in the order price meets them). Recompute EQ on the new range. Mirror for a break below. If price later falls back through an old array (e.g. a bullish OB fails), the next draw is the rebalancing of the one-sided delivery beyond it.
- **Sources:** cc12_002_Ad-votrg6WQ ~00:22:26.
- **Quote:** "once this range has been broken ... this range is no longer valid"
- **Conflicts:** none.
- **Rulebook fix:** L14: add the range rollover.
- **BUILD SPEC (bias_htf):**
  - Where the dealing range is computed (A21 `pd_day_range` / `htf.table` pd columns): with `range_rollover`, when a bar trades beyond the range high, set the new high = the next unmitigated premium array/pool above (from `_targets` ordering), keep the old high and EQ as "array" levels below, and recompute EQ for `pd_zone` gates.
  - Params: `range_rollover: bool = False`.
  - Test: `test_dealing_range_rollover`. Range 4000-4100 broken, next SIBI 4130: new EQ 4065, old 4100 kept as a level.

### 180. LLT3-weekly-open-pd-array
- **rule_id / kind:** B13, shortened. Scope: general. judgment = false.
- **Rule:** wk_open_sun = first print Sunday 18:00 NY; wk_open_mon = open of the 1H bar at Monday 00:00 NY. Keep both all week. Bearish week: shorts only when price trades above at least one (ideally both) opens AND sits in a premium PD array. Bullish week: longs only below at least one (ideally both) AND in a discount PD array.
- **Sources:** cc12_003_3B7Reg2Yiqs ~00:20:57.
- **Quote:** "trade up above both of those prices or at least one of them"
- **Conflicts:** none.
- **Rulebook fix:** B13: "at least one of the two opens" and the PD-array condition.
- **BUILD SPEC (bias_htf):**
  - Listed: B13 `weekly_open` filter (sun18/mon00/either). New: `weekly_open_array`: with the filter on, additionally require the entry (or sweep extreme) to lie inside a premium array (shorts) / discount array (longs) from `array_cands` or `htf` arrays; tag `wo_both` when beyond both opens.
  - Params: `weekly_open_array: bool = False`.
  - Test: `test_weekly_open_needs_array`. Bearish week, entry above the Monday open but no array: rejected; inside a 15m SIBI: accepted.
