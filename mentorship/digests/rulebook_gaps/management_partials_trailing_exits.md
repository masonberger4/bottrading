# Rulebook gaps: management, partials, trailing and exits

Topic `management_partials_trailing_exits`. Every item below is a verified gap between ICT's captions and `mentorship_rules.md`. Where the checker gave a corrected rule, that corrected rule is the one written here. Where it gave none, the claim's full rule is used. "[our interpretation]" marks thresholds or readings that ICT does not state.

Conventions:
- Times are New York. Prices are in ES points unless stated. The engine converts with `p.es_pt` (SPY ~ ES/10), and one ES tick = 0.25 pt.
- New Params switches default off (rule_coverage.md section 3). Each work package adds its fields in its own commented block at the end of `Params` (strategy.py ~65-705) and validates string switches in `__post_init__` (~705).
- Code anchors (current `mentorship` branch):
  - Exit prices: `_exit_px` (strategy.py ~1496: pools `+pool_beyond_pts`, arrays `-exit_before_pts`, "exact" at the level); `exit_before_pts=0.5`, `pool_beyond_pts=0.25`, `exit_mode="split"` (~85, ~150).
  - Targets: `_targets` (~1318) and the `_scan_core` target merge (~4150-4210). Ladder split: `_split` (~2095: 50/25/25, or 80/20 on slow / news-ahead days). `pos["level_kinds"]` is carried into the position.
  - Management: the run_day position loop (~2590-2740):
    - ladder fills `h >= level` (~2614);
    - `be_on` t1/expansion (~2624-2632); `ladder_trail` fvg/hit/prior (~2626, ~2640, ~2724);
    - `ce_hold`, `breaker_mt`, `lvx` exits (~2655-2670); `fvg_abort`, `pd3_exit` (~2676-2684);
    - `time_stop_min` (~2685); `am_exit` (~2693); `pm_done_by` (~2705); flatten (~2707).
  - Post-trade: `_after_close` (~1858). Silver Bullet: `SB._arm` / run_sb (sb_model.py ~31, ~213). HTF arrays: `htf.table` (~95), `htf._arrays` (~66). Detectors: `levels.py` (`breaker_zone`, `wick_ce`, `rejection_blocks`, `balanced_ranges`, `pivots`, `swing_tiers`).
- Work packages are the names in `rule_coverage.md` section 3:
  - Most items here belong to **management_exits** (the run_day position loop, `_after_close`, done flags) or **targets_partials** (`_targets`, `_exit_px`, the ladder split and the `_scan_core` target merge).
  - Session and day-mode items go to **news_calendar_times** / **day_week_context**, SB items to **silver_bullet**, new setup filters to **setups_models**, entry depth to **entries_stops_sizing**, and HTF / swing / position studies to **bias_htf**.
- Merge order (section 3, item 3): targets_partials ladder changes first, then management_exits.
- Fill model: the ladder currently fills a rung on a touch (`h >= level`). E3 says a resting limit fills only on 1 tick through. Item 6 adds that as a switch, and every at-edge / at-pool variant below should be tested with it on.
- Tests go in new files `tests/test_management_exits.py` and `tests/test_targets_partials.py` unless a spec names another one. Each spec names its test function.
- Items scoped `fx_only`, `bonds_only` or `needs_unavailable_data` get the rulebook fix only, with no build spec. Intraday DXY / FX, commodity calendar spreads and war-climate flags count as unavailable.
- Swing, position, weekly and daily-chart models are parked under M17. Their `general`-scope build specs are research studies on daily / 4h bars (`study.py`, `htf.py`), not live `run_day` branches.

Summary: 145 items, 129 new build specs. Items without a build spec:
- 7 fx_only: X2-fx-target-buffers, M12-turtle-soup-max-sweep, X3-cbdr-projection-units, X3-fixed-distance-first-partial, M17-cbdr-model-hold-to-array, X3-four-levels-75-80-off, fx-asia-open-scalp-full-exit.
- 2 bonds_only: L9-bond-pm-far-edge-fill-target, bond-megatrade-fall-high-exit-and-roll.
- 4 that need data we do not have: X3-dxy-target-partial, exit-intermarket-divergence-close-all, B18-smt-partial-size-precondition, new-spread-divergence-trail.
- 3 already listed in rule_coverage.md with the same content:
  - X4-stop-better-than-be = X4 `be_pad_pts`.
  - X3-sd05-partial-under-5-handles = X3d `sd_half_partial` exempt from min_rr.
  - X3-rejection-block-partial-rel = L11 `rb_targets` ladder mode.
  - These get rulebook text fixes and a spec note only.
- Extended rather than new: X5-day-trade-stop-no-trail adds the selection rule and size cut to X5c `trade_type="day"`. It still gets its own spec for the new parts.

Shared pieces this topic adds (build first, management_exits unless noted):
- `pos_r(pos) -> float`: open profit in R (`(price - avg) / (avg - init_stop)`), using a new `pos["init_stop"]` set at the fill. Items 13, 59, 132 and 135 use it.
- `raise_stop(pos, new, why)`: the single place that tightens a stop. It enforces "never lower", appends `why` to `pos["stop_log"]` (for tests and reports) and refuses a level at or through the current close. Every stop-move item uses it instead of writing `pos["stop"]` directly.
- `partial_close(pos, tr, ts, px, frac, why)`: closes `frac` of the units left (lot-rounded, at least 1 lot, all if fewer remain) with an exit reason. Items that "take a partial" outside the ladder use it.
- `exit_px_mode(v, kind, p)` (targets_partials): extends `_exit_px` with the per-kind modes of items 1-3 and 7. `_exit_px` calls it when any new mode is on, so the default path is unchanged.
- `trade_mode` on `pos` ("session" default, "day", "scalp", "full_pull", "hold_runner"): set at the fill from Params and day context and read by the BE, trail, am_exit and time-stop branches. Items 17, 35, 116 and 127 use it.

---

## A. Exit prices and buffers (X2, E1, D5)

### 1. X2-pdarray-exit-at-or-inside-edge
- **rule_id / kind:** X2 / D5. Unlisted contradiction. Scope: index. judgment = true.
- **Rule:** Parameter `fvg_target_level`:
  - 'before_edge' (default): 0.5 ES pt before the near edge.
  - 'at_edge': limit exactly at the near edge, filling only on 1 tick through per E3 (003 ~53:30, 049 ~5:42).
  - 'deep': the final runner's limit sits inside the target array toward its far edge (041 ~1:45, NWOG).
  - Partials stay before or at the near edge; only the last runner uses 'deep'.
  - Record that 003's at-edge limit (11075.50) went unfilled, as evidence for 'before_edge'.
- **Sources:** 003_ojy5ApHhEu4 ~00:53:30; 041_UPKUqW_eaas ~00:01:45; 049_St9FJHRVdq8 ~00:05:37. (002, 018, 069 and 071 were cited by the claim but are dropped: not spoken, or chart-only.)
- **Quotes:** "I just put my limit over up there just at the bottom of that daily volume and balance" (003); "adjusted my limit order to get towards the top end of that new week opening Gap" (041).
- **Conflicts:** X2/D5 and Ep 08 say exit before the edge and never target an FVG's exact high or low. 003's missed at-edge limit supports 'before'. See also item 50 (runner peel into the upper half of the NWOG) and item 144 (L9-bond-pm-far-edge-fill-target).
- **[our interpretation]:** how deep 'deep' goes. Test the far-quarter point (near edge + 0.75 x height).
- **Rulebook fix:** X2: move 049 from 'before' to 'at edge'. D5: add 003 and 049 (at edge) and 041 (deep runner in the NWOG). Keep 018 under 'beyond' (+0.25 for fees). Note 003's unfilled at-edge order as the case for 'before_edge'.
- **BUILD SPEC (targets_partials):**
  - Where: `exit_px_mode` for kind "array" when the level is an FVG / VI / NWOG near edge:
    - 'at_edge' returns `v`;
    - 'deep' returns `v` for every rung except the last;
    - the last rung (the runner) becomes `near + fvg_deep_frac x (far - near)`. The far edge must be carried with the level, so add `far` to the level tuple in `_targets` for gap rows.
  - Params: `fvg_target_level: str = "before_edge"` ("before_edge" / "at_edge" / "deep"); `fvg_deep_frac: float = 0.75`.
  - Test: `test_fvg_target_level`. Long into a 10-pt FVG above with a 3-rung ladder:
    - 'before_edge' puts rung 1 at near - 0.5;
    - 'at_edge' puts it at near, and with `exit_fill="limit_through"` (item 6) a bar whose high equals near does not fill;
    - 'deep' puts the last rung at near + 7.5.

### 2. X2-pool-exit-at-or-before
- **rule_id / kind:** X2 / D5. Unlisted contradiction. Scope: general. judgment = true.
- **Rule:** Parameter `pool_exit`:
  - 'beyond': 1 tick to 1.25 ES pt beyond (006).
  - 'at': limit at the exact pool price (037).
  - 'before': 1-2 ticks short of the pool (063 ~29:41, 101 ~1:28:51, 102 ~1:32:29). Also the default on FOMC / whipsaw days (065 ~5:43:45).
  - REH clusters (067): scale out above each sub-high and put the final unit below the last high (offset unspecified; test 1-2 ticks).
  - Climate switch (102 ~1:30:22-1:32:35, any target type): in a normal climate, take 80% off 1-2 ticks before the target. In a fear / war-shock climate, take 80% off before the target and hold the rest past it on a trail.
- **Sources:** 037_wu0sQarBRrI ~00:53:34; 063_qA9SCu4gGaU ~00:29:41; 065_rx15_eN9sxI ~05:43:00; 067_vuBRMFhFZAY ~01:09:17; 006_VKkn8uckkW0 ~00:33:37; 101_VElIka5sk0E ~01:28:47 (the claim had ~0:28:47); 102_uzPM1CuSSx8 ~01:32:22.
- **Quotes:** "42.90 ... two ticks below the 4290.50 60 Minute old high" (063); "I'll still get out of 80 and I will go one tick or two below" (102).
- **Conflicts:** 006 (1.25 pts beyond buy-side) vs 037, 063, 065, 067, 101, 102 (at or before). D5's split recommends 'beyond' for pools, but 063 and 101 (already in its option A) are pool targets.
- **[our interpretation]:** the final REH-cluster offset. The fear-climate branch needs a war / shock flag, which we do not have, so it is documented only.
- **Rulebook fix:** X2/D5: reclassify 063 and 101 as pool sources, fix the 101 timestamp to ~1:28:47, add 037 ('at'), 065 (FOMC 'before') and 067 / 102 ('before'), and widen 'beyond' to 1.25 pt (006). Add the 102 climate switch to X3.
- **BUILD SPEC (targets_partials):**
  - Where: `exit_px_mode` for kinds in `POOL_KINDS` (strategy.py ~1464):
    - 'beyond' = today's `v + pool_beyond_pts`;
    - 'at' = `v`;
    - 'before' = `v - pool_before_ticks x 0.25 x es_pt`.
    - With `pool_exit_fomc_before`, use 'before' on FOMC days (`"fomc" in events(day)`), whatever `pool_exit` says.
  - REH cluster: when `rel_eq` levels within `eq_tol_pts` stack in the ladder, all but the highest stay as rungs at their own price; the highest uses 'before'.
  - Params: `pool_exit: str = "beyond"`, `pool_before_ticks: int = 2`, `pool_exit_fomc_before: bool = False`.
  - Test: `test_pool_exit_modes`. A 4290.50 old high gives exits at 4290.75 / 4290.50 / 4290.00 for the three modes. On an FOMC-tagged day with the switch on, it gives 4290.00 even with `pool_exit="beyond"`.

### 3. X2-projection-target-1tick-before
- **rule_id / kind:** X2. Missing condition. Scope: general. judgment = false.
- **Rule:** For target type 'projection' (SD / fib extension, measured move), place the exit limit 1 tick before the projected level (012). Expect that price may print up to 1 tick past the level (030). In backtests, fill only on a trade through the limit (E3). Test buffers of 1 tick, 0.25, 0.5 and 1 ES pt, and log how often price stops just short of the level.
- **Sources:** 012_HkiPAi1Mdu8 ~00:29:40; 030_ZdnGlropfmU ~00:24:14.
- **Quotes:** "I had a limit order to get out at 39 62.75" (012); "it printed the price I wanted it but it didn't give me the exit" (030).
- **Conflicts:** none.
- **Rulebook fix:** X2: add "projection targets (SD / fib / measured move): limit 1 tick before the projected level (012); the level may print 1 tick past (030)". L12: cross-reference.
- **BUILD SPEC (targets_partials):**
  - Where: SD and measured-move levels in `_targets` get kind "proj" instead of "array". `exit_px_mode` gives "proj" `v - proj_before_pts`. Kind "proj" is added to every non-pool branch that tests `kind == "array"`.
  - Params: `proj_kind: bool = False` (tag only when on), `proj_before_pts: float = 0.25`.
  - Report: a `near_miss` column per trade (max favourable excursion fell within 1 pt short of a "proj" rung that did not fill).
  - Test: `test_proj_before`. An SD target at 3962.50 on a short exits at 3962.75. A bar whose low is 3962.75 fills only when `exit_fill="touch"`.

### 4. X2-exit-buffer-range
- **rule_id / kind:** X2 / D5. Shortened. Scope: index. judgment = false.
- **Rule:** Exit buffer is 0.5 to 1.5 ES pts before the target, with 0.25 pt as the aggressive variant (070 ~1:05:10). In 070 it was applied to an old-high / SD confluence target, so it is not specific to FVG edges. Test exit_buffer in {0.25, 0.5, 1.0, 1.5}.
- **Sources:** 070_1HtRfFYiwO0 ~01:05:10.
- **Quote:** "anywhere between one and a half handles to a half of handle" (070).
- **Conflicts:** none.
- **Rulebook fix:** X2: change "0.5-1 pt before (070 ~1:05:36)" to "0.5-1.5 pts before, 0.25 aggressive (070 ~1:05:10); used on an old-high / SD confluence".
- **BUILD SPEC (targets_partials, study only):**
  - No new code. `exit_before_pts` already exists.
  - Add a `study.py` grid preset `exit_buffer_grid`: exit_before_pts in {0.25, 0.5, 1.0, 1.5}, crossed with `exit_mode` in {"split", "before"} so the buffer also hits pools (070's target was a pool).
  - Test: `test_exit_buffer_grid_preset`. The preset expands to 8 Params objects, each passing `__post_init__`.

### 5. X2-best-case-resting-limit
- **rule_id / kind:** X2 / E1. Missing condition. Scope: general. judgment = true.
- **Rule:**
  - On entry, rest the exit limit at a best-case level beyond the objective O (cc10_008 scalps: 2 x O; 009: above the 4030 objective, the exact level is chart-only).
  - When price prints beyond O, take the bulk (009: 9 of 14) at market.
  - Hold the remainder toward the best-case limit only if momentum continues [our interpretation]. In 009 the remainder was closed by mistake, not held.
  - Leftover units exit at the best-case limit or by the time rules.
- **Sources:** 009_tnxvmHq8xEg ~00:01:06 (and ~18:18); cc10_008_RgpxhuVp5Xg ~00:14:20.
- **Quotes:** "I always like to use the best case scenario exit" (009); "always allow your limit exits to exceed your targets" (cc10_008).
- **Conflicts:** X2 says exit before PD-array targets; this places the resting exit beyond the objective.
- **Rulebook fix:** X2: add a "best-case resting limit" variant (009, cc10_008) and list the conflict with the before-target buffer.
- **BUILD SPEC (management_exits):**
  - Where: at the fill, if `best_case_limit`, set `pos["best_case"] = O + best_case_mult x (O - avg)`, where O = the last ladder rung.
  - In the ladder loop, when the bar's high prints beyond O (h > O), close `best_case_bulk` of the units at `max(O, o)` with reason "bulk_O". Then:
    - if the bar that crossed O closed beyond it with range >= 1.5 x the median of the last 20 bars [our interpretation of "momentum"], keep the rest with `raise_stop(pos, O_prev_rung, "lock")` and a limit at `pos["best_case"]`;
    - otherwise close the rest at the bar's close.
  - Params: `best_case_limit: bool = False`, `best_case_mult: float = 1.0` (2 x O = 1.0 extra objective distance), `best_case_bulk: float = 0.65`.
  - Test: `test_best_case_limit`. Long, avg 4020, O 4030, best case 4040:
    - a displacement bar to 4033 closes 65% at 4030 and keeps 35% with the limit at 4040;
    - a weak bar to 4031 closing at 4029 closes 65%, then the rest at 4029.

### 6. E1-manual-touch-exits
- **rule_id / kind:** E1. Unlisted contradiction. Scope: index. judgment = true.
- **Rule:** Fill-model option `exit_fill`:
  - 'limit_through': resting limit that fills on 1 tick through, per E3.
  - 'touch': for precise partial levels, when price touches or comes within 1 tick of the level, exit at market at the level minus slippage (026 ~22:05, ~24:18).
- **Sources:** 026_GFdWahZUNOw ~00:22:05, ~00:24:18 (037 ~54:03 is similar).
- **Quote:** "I don't like when I use a limit order when I'm trying to be very very precise" (026).
- **Conflicts:** 026 manual exits vs E1 resting limits (009, 057, 049).
- **Rulebook fix:** E1: "Precise partials may be taken manually at market on touch (026, 037 ~54:03); resting limits otherwise."
- **BUILD SPEC (management_exits):**
  - Where: the ladder loop condition `h >= lv_[k]` (~2614) becomes `_rung_hit(h, lv, p)`:
    - 'touch' (today's behaviour, kept as the default so results do not move): `h >= lv`;
    - 'limit_through': `h >= lv + 0.25 x es_pt`;
    - 'touch_1tick': `h >= lv - 0.25 x es_pt`, filled at `lv - exit_slip_ticks x tick`.
  - The same helper is used by the t1t2 branch (~2633), SB exits in sb_model.py and the new partial helpers.
  - Params: `exit_fill: str = "touch"` ("touch" / "limit_through" / "touch_1tick"), `exit_slip_ticks: int = 1`.
  - Test: `test_exit_fill_modes`. A rung at 4100 against bar highs of 4099.75, 4100 and 4100.25:
    - 'limit_through' fills only on 4100.25;
    - 'touch' fills on 4100 and 4100.25;
    - 'touch_1tick' fills on all three at 4099.75.

### 7. X2-exit-buffer-before-day-extreme
- **rule_id / kind:** X2. Missing rule. Scope: general. judgment = true.
- **Rule:** When the target is the projected day extreme (the ADR5 high on a bull day, the ADR5 low on a bear day), place the final or bulk exit limit before the level by a buffer, so it fills while price is still moving the trade's way. This applies especially where ADR / SD / extension levels converge with a 15-60m PD array.
  - FX buffers: 15 pips for the plain ADR5 high / low (cc09_007); 10 pips where ADR extensions or SD levels converge with a 15-60m array (cc12_004).
  - Index buffer [our interpretation]: ~10-20% of ADR5, or ~2-3 ES pts.
  - Never leave a unit targeting the exact extreme. Leaving 25-30 pips (FX) on the table is acceptable.
- **Sources:** cc09_007_-oMtfDvc18Y ~00:17:04; cc12_004_Oec_0NM_OeY ~00:18:54.
- **Quotes:** "scaling the bulk of it off about 15 Pips before that number" (cc09_007); "that's the reason why I want to get out 10 Pips before" (cc12_004).
- **Conflicts:** 15 pips (cc09_007) vs 10 pips (cc12_004). Both are FX; there is no index value.
- **Rulebook fix:** X2: add "projected day extreme (ADR5 high/low, converging SD/extension + 15-60m array): exit a fixed buffer before it (FX 15 / 10 pips)". L16: cross-reference.
- **BUILD SPEC (targets_partials):**
  - Where: L16 `adr_target` (section 3, not yet built) adds the level `day_low + adr5` (long) as kind "adr". `exit_px_mode` gives "adr" `v - adr_before_frac x adr5`. If an htf 15m / 60m array edge lies within that buffer, use the array edge minus `exit_before_pts`, whichever is nearer to price.
  - Uses `adr5()` (strategy.py ~828).
  - Params: `adr_before_frac: float = 0.15` (study grid {0.10, 0.15, 0.20}).
  - Test: `test_adr_before`. ADR5 = 40, day low 4000: the "adr" rung exits at 4034. A 60m bearish FVG with near edge 4033 moves it to 4032.5.

### 8. X2-fx-target-buffers
- **rule_id / kind:** X2. Missing condition. Scope: fx_only. judgment = true.
- **Rule:** FX only (the rulebook lists pip room rules as FX-only, out of the index bot's scope).
  - Pool targets (old low or high): TP = 10 pips beyond the level, which needs about 4 more pips for spread to fill (cc01_005).
  - Weekly projected objective: exit 5 pips before it (cc07_008).
  - Drop the cc02_004 '+20 pips' variant as ambiguous.
  - The index analogue (test pool + k pts) is our interpretation.
- **Sources:** cc01_005_YuefjnUKQdM ~00:17:49; cc07_008_LBlK6JB0QS0 ~00:11:27 (cc02_004 ~3:55 dropped).
- **Quote:** "you got at least four pips below that for spread" (cc01_005).
- **Conflicts:** beyond the pool by 10 pips vs 5 pips before the weekly objective.
- **Rulebook fix:** X2: add an FX-only note with these buffers under the "out of scope: pip room rules" list.
- **BUILD SPEC:** none (fx_only). Item 2's `pool_exit="beyond"` with `pool_beyond_pts` already covers the index test of "pool + k pts".

---

## B. Breakeven and stop moves (X4, X5, D14)

### 9. X4-stop-better-than-be (already listed)
- **rule_id / kind:** X4. Shortened. Scope: index. judgment = true.
- **Rule:** `be_offset` parameter: at the first partial, stop = entry + offset for longs (entry - offset for shorts), with offset in {0, 0.25, 0.75, 1.0} ES pts. Sources: 027 '+1'; 041 and 056 'better than even'; 105 BE + commissions as the minimum. Optional step-up at later partials (041, chart-only).
- **Sources:** 027_STEGBblm4dI ~00:40:10; 041_UPKUqW_eaas ~00:01:38; 056_NeZlyG8FZLQ ~00:11:35.
- **Quote:** "first partial There is five and stop is rolled to better than even" (041).
- **Conflicts:** X4 / bot flat breakeven; 044: one stop move, then no trailing.
- **Rulebook fix:** X4: "at the first partial, the stop goes to better than even: about +0.75 to +1 pt (027 '+1', 041, 056), at least BE + commissions (105)".
- **BUILD SPEC:** already listed. Section 3 management_exits Low **X4** "Add `be_pad_pts` with a cost pad" is the same switch. Spec note for that build: let `be_pad_pts` take values {0, 0.25, 0.75, 1.0} in the study grid, apply it to both `be_on` branches (~2624, ~2629), and floor it at the round-trip cost (`2 x cost_per_share` in price units). The step-up at later partials is chart-only and is not built.

### 10. X4-be-vi-then-new-ssl
- **rule_id / kind:** X4 / D14. Missing condition. Scope: index. judgment = false.
- **Rule:** Short (longs are the mirror). No partial is required.
  - Step 1: once price trades below the nearest volume imbalance under entry and does not get back above it, move the stop to just above the breaker (042 ~52:21).
  - Step 2: once price makes new sell-side (prints below the most recent swing low after entry), remove the risk with the stop at or better than entry ('stopped in profit', 042 ~55:08).
  - Test as `be_mode='vi_then_new_ssl'`.
- **Sources:** 042_hQ379EuyNKQ ~00:52:21, ~00:55:08.
- **Quote:** "now you reduce the risk put it right above the breaker" (042).
- **Conflicts:** X4 default: BE only after the first partial.
- **Rulebook fix:** X4 / D14 option B: replace "042 (chart example of earlier BE)" with the two spoken triggers above.
- **BUILD SPEC (management_exits):**
  - Where: at the fill store:
    - `pos["vi_below"]` = the nearest VI (`levels.volume_imbalances`) formed in the displacement beyond entry (below entry for a short, above for a long);
    - `pos["bz_far"]` = the breaker's far edge (`tr.bz_top` / `bz_bottom`, already on the trade);
    - `pos["swing_ref"]` = the most recent `levels.pivots` low after the fill (side space).
  - Each bar, when `be_mode == "vi_then_new_ssl"`:
    - Step 1: the bar trades through `vi_below`'s far side and the next bar's close stays beyond it. Call `raise_stop(pos, bz_far + stop_buffer, "vi")`.
    - Step 2: the bar trades beyond `swing_ref`. Call `raise_stop(pos, avg, "new_ssl")`.
  - Params: `be_mode: str = "partial"` ("partial" = today's `be_on`; also "vi_then_new_ssl", "through_opposing_fvg" (item 11), "adr_frac" (item 14)).
  - Test: `test_be_vi_then_new_ssl`. Synthetic short:
    - a bar through the VI followed by a close below it moves the stop to breaker high + buffer;
    - a later print below the swing low moves it to entry;
    - a wick back above the VI before step 2 leaves the stop unchanged.

### 11. X4-be-without-partials
- **rule_id / kind:** X4. Unlisted contradiction. Scope: general. judgment = true.
- **Rule:** For full-pull (low-resistance) trades with no partials:
  - When price trades through the far edge of the nearest opposing FVG between entry and target (for a short, below the low of the bullish FVG / BISI), move the stop to better than BE and leave it until the target (089 ~8:35).
  - If there is no opposing FVG, the source gives no trigger (102 only says "manage it to where I can take the risk away"). Test a fallback such as a new FVG forming beyond entry.
  - Longs are the mirror. Option `be_mode='through_opposing_fvg'`.
  - List the X3 full-pull vs X4 conflict.
- **Sources:** 089_h0yOpwSilnE ~00:08:35; 102_uzPM1CuSSx8 ~02:18:40.
- **Quote:** "accelerate through the low end of that shaded area now just move the stop to better than break even" (089).
- **Conflicts:** X4 requires the first partial first; 076 hold-runner mode never moves the stop.
- **Rulebook fix:** X4: "with no partials (full pull), BE+ once price trades through the far edge of the nearest opposing FVG toward the target (089 ~8:35)". X3: list the full-pull vs X4 conflict.
- **BUILD SPEC (management_exits):**
  - Where: at the fill, `pos["opp_fvg"]` = the nearest gap of the opposite polarity (in side space, a gap above entry that formed before the fill and below T) from `sd.gaps`.
  - Each bar with `be_mode == "through_opposing_fvg"` (or `pos["trade_mode"] == "full_pull"`), when price trades beyond `opp_fvg`'s far edge, call `raise_stop(pos, avg + be_pad_pts, "opp_fvg")` once.
  - Fallback when `opp_fvg` is None: the first same-direction FVG formed after the fill entirely beyond entry [our interpretation].
  - Params: `be_mode` value "through_opposing_fvg" (item 10's field).
  - Test: `test_be_through_opposing_fvg`. A long with a bearish FVG at 4105-4107 between entry 4100 and target 4115:
    - the stop stays at its initial level at 4106.5;
    - it moves to entry + pad once the high exceeds 4107;
    - with no opposing FVG, it moves on the first new bullish FVG above 4100.

### 12. X4-be-plus-cap-htf-fvg
- **rule_id / kind:** X4. Missing condition. Scope: general. judgment = true.
- **Rule:** Long. Discretionary (105, NFP day).
  - After the first partial, stop = entry_avg + commissions + 1-2 ticks, and no higher while the HTF (4h) entry FVG's high sits above it, because price may retest it. No trailing under newer LTF FVGs in this phase.
  - When the NEXT partial fills (a limit just beyond the first buy-side pool), raise the stop to 1 tick below the CE of the wick at that pool.
  - After a further partial, the stop for the remaining runner(s) may go to the HTF FVG high.
  - Each raise happens only after a partial fills, and the stop is never lowered.
- **Sources:** 105_A97shZGPE2I ~00:10:50, ~01:00:51 (and ~1:13:50).
- **Quote:** "why am I not jamming it all the way back up here because it could respect the same 4-Hour fair value Gap High" (105).
- **Conflicts:** none listed.
- **Rulebook fix:** X4: replace "105 BE + commissions" with the three-step sequence above, each step gated on a partial fill.
- **BUILD SPEC (management_exits):**
  - Where: at the fill, `pos["htf_entry_hi"]` = the top of the HTF entry array when the entry came from an htf / nested gap (`ctx.conf` rows, tf >= 60).
  - With `be_cap_htf`:
    - At partial #1, set the stop to `avg + be_pad_pts`, capped at `htf_entry_hi - stop_buffer`, and suppress `ladder_trail` FVG trailing until partial #2.
    - At partial #2, raise to `wick_ce(bar at that pool) - tick`. The wick CE is the CE of the upper wick of the highest bar between partials #1 and #2, using `levels.wick_ce`.
    - At partial #3, raise to `htf_entry_hi`.
  - Params: `be_cap_htf: bool = False`.
  - Test: `test_be_cap_htf`. A long from a 4h FVG with top 4560:
    - partial #1 at 4570 sets the stop to avg + pad, and it is never above 4560;
    - a new 5m FVG before partial #2 does not move it;
    - partial #2 moves it to the wick CE - tick;
    - partial #3 moves it to 4560 only if that is higher.

### 13. X4-be-by-timeframe
- **rule_id / kind:** X4. Missing rule. Scope: general. judgment = false.
- **Rule:**
  - Execution TF daily or higher (swing / position): no early BE and no FVG trailing. Keep the initial stop until the market has moved a significant distance (ICT gives no number; 1-2R is our interpretation), or use only the 40-day trail (20-day after 3/4 of the expected range) for position trades. Reduce exposure through partials.
  - Intraday: BE per X4, earlier BE allowed.
- **Sources:** 098_PejS-nZTQlE ~00:16:07; cc05_013_crPpMwgwa7k ~00:18:29; cc05_018_okN5p701T7Y ~00:13:19.
- **Quote:** "break even on long-term trading is just the worst thing" (cc05_018).
- **Conflicts:** cc05_018 position trades use the 40/20-day trail rather than a BE step; cc06_008 swing BE after D/3 plus the first partial.
- **Rulebook fix:** X4 / D14: add a scope line, "intraday only; daily+ swing/position trades keep the initial stop until a significant move (098, cc05_013) or use the 40/20-day trail (cc05_018)".
- **BUILD SPEC (bias_htf, study only):**
  - Where: a new `study.py` function `swing_mgmt_study(df_daily, entries, mode)` shared by items 15, 31, 32, 33, 135, 136, 138, 139, 140 and 141. It replays daily entries from `htf.table` signals on daily bars with pluggable management.
  - `mode="no_be"`: keep the initial stop until `pos_r >= swing_be_r`, then BE. Compare against `mode="be_t1"`.
  - Params (study config, not the intraday Params): `swing_be_r: float = 1.5`.
  - Test: `test_swing_no_be`. On a synthetic daily path that dips to entry after +1R and then runs to target, "be_t1" is stopped at BE while "no_be" reaches the target.

### 14. D14-be-after-adr-fraction
- **rule_id / kind:** D14. Wrong. Scope: general (the source is CC London-session FX day trades). judgment = false.
- **Rule:** [CC, London-session FX day trades] Leave the initial stop untouched (no BE, BE+5 or BE+20) until open profit is at least 0.4-0.5 x the expected daily range, whether or not a partial has been taken, then move to BE. The reason is to avoid double-pass stop-outs. Reading "the daily range" as ADR5 is our interpretation.
- **Sources:** cc08_007_5Z_3NbclMSY ~00:14:14.
- **Quote:** "leave your stop at initial until you get to at least 40 to 50 of the daily range" (cc08_007).
- **Conflicts:** D14's citation of cc08_007 under "after the first partial".
- **Rulebook fix:** D14: move cc08_007 out of "BE A: after the first partial and expansion" into its own option, "BE C: after 40-50% of the daily range (CC, FX London)". X4 does not cite cc08_007, so no change there.
- **BUILD SPEC (management_exits):**
  - Where: `be_mode == "adr_frac"`. At the fill store `pos["adr"] = adr5(hist[-5:])`.
  - Each bar, if `best - avg >= be_adr x adr`, call `raise_stop(pos, avg, "adr_frac")` once.
  - The `be_on` branches (~2624, ~2629) are skipped in this mode.
  - Params: `be_mode` value "adr_frac", `be_adr: float = 0.4` (grid {0.4, 0.5}).
  - Test: `test_be_adr_frac`. ADR5 = 40: a partial at +8 leaves the stop unchanged, and +16 moves it to entry.

### 15. X4-swing-stop-thirds-partial-quarter
- **rule_id / kind:** X4. Missing rule. Scope: general (swing, M17-parked). judgment = true.
- **Rule:** [Swing trades on M/W/D arrays] D = |objective - entry|.
  - At favourable excursion >= 0.25D, close 20-30% (default 25%).
  - Leave the stop at initial until excursion >= D/3. Then move it to BE only if the first partial has been taken, never before.
  - At 0.5D, look to re-add the quarter on a short-term retrace.
  - At the objective (or 75-80% of it), take the full position off or trail below the most recent 4h short-term low.
- **Sources:** cc06_008_VL4YLTRerHY ~00:16:32.
- **Quote:** "leave stop loss from initial placement until price has moved 1/3 of your intended trade direction" (cc06_008).
- **Conflicts:** ICT gives 1/4 and 1/3 back to back without reconciling them.
- **Rulebook fix:** X4: replace "cc06_008 BE after first partial" with the swing sequence above. D13: keep cc06_008 under "about half or less" (20-30%). It is correctly listed.
- **BUILD SPEC (bias_htf, study only):**
  - Where: `swing_mgmt_study` (item 13) `mode="thirds"`:
    - partial `swing_p1` at 0.25D;
    - stop frozen until 0.333D, then BE if the partial is done;
    - re-add the same size at the first 4h retrace low after 0.5D;
    - full exit at D, or the 4h trail from 0.75D (item 31).
  - Study config: `swing_p1: float = 0.25`.
  - Test: `test_swing_thirds`. A path hits 0.25D (25% closed), dips without reaching 0.333D (stop still initial), then reaches 0.4D (stop to BE).

### 16. X5-runner-stop-half-open-profit
- **rule_id / kind:** X4 / X5. Missing condition. Scope: index. judgment = true.
- **Rule:** Discretionary ("in my opinion").
  - After the bulk (~80%) partial fills, runner stop = max(entry, EQ - 1 tick) for longs. EQ = 50% of the leg from the trade's swing low to the high at partial time. The anchors are our interpretation (036, ES).
  - FX variant (065): stop at entry + 0.5 x open profit.
  - Set it once and leave it. Shorts mirror.
- **Sources:** 036_n37ozsUreR0 ~01:01:33; 065_rx15_eN9sxI ~02:56:01.
- **Quote:** "your stop should be just about below midpoint of this range of price action" (036).
- **Conflicts:** none.
- **Rulebook fix:** X5: add "after the bulk partial, the runner's stop just below the leg's equilibrium (036), or half the open profit (065, FX)".
- **BUILD SPEC (management_exits):**
  - Where: in the ladder loop, after a rung fill that brings the cumulative closed fraction to >= `runner_eq_after` (default 0.75), and once only:
    - with `runner_stop="leg_eq"`: `eq = (sw_low + best) / 2`, where `sw_low` is the sweep extreme (`tr` already carries it as `pos["ext"]`). Call `raise_stop(pos, max(avg, eq - tick), "leg_eq")` and set `pos["no_trail"] = True` so `ladder_trail` stops moving it;
    - with `runner_stop="half_profit"`: use `avg + 0.5 x (c - avg)` instead.
  - Params: `runner_stop: str = ""` ("" / "leg_eq" / "half_profit"), `runner_eq_after: float = 0.75`.
  - Test: `test_runner_leg_eq`. A sweep low of 4060, 80% closed at 4077 with best 4078, avg 4065: the stop goes to 4068.75, and a later new FVG does not move it.

### 17. X5-day-trade-stop-no-trail
- **rule_id / kind:** X5. Missing condition. Scope: index. judgment = false.
- **Rule:** Add to X5's day-trade line:
  - Choose day mode only when you expect the daily range to expand and close near its extreme in the bias direction.
  - Day-trade long stop: below the lower of the 08:30 open and the 08:30 1m wick CE, beyond the already-swept pre-release sell-side pool. Never raise it under a later pre-noon low.
  - Size = risk$ / stop distance, smaller than session size (not max contracts).
  - Reduce exposure only through partials.
- **Sources:** 064__YTK5uXBe4o ~01:45:14 (and ~1:40:54).
- **Quote:** "You would not as a day trader put your stop loss below that low" (064).
- **Conflicts:** none.
- **Rulebook fix:** X5: add the selection condition, the reduced size and "beyond the already-swept dealing-range sell-side" to the day-trade line.
- **BUILD SPEC (management_exits, extends X5c):**
  - Where: section 3 X5c builds `trade_type="day"` (08:30 open / wick-CE stop, no trail, no BE). This item adds three things:
    - (a) Selection: `pos["trade_mode"] = "day"` only when `day_mode_auto` is on, the `htf.table` bias agrees, and the day's expected range is "expansion" (proxy [our interpretation]: the ADR5-relative range at the fill is under 0.5 x ADR5 and the next HTF draw lies >= 0.75 x ADR5 away).
    - (b) Stop = `min(open_0830, wick_ce_0830) - stop_buffer`, and also beyond the low of the pre-08:30 dealing range if that low was swept before the fill.
    - (c) Size multiplier `day_mode_size` applied in `_first_units`.
  - In this mode `raise_stop` is blocked before 12:00 except via partials.
  - Params: `day_mode_auto: bool = False`, `day_mode_size: float = 0.5`.
  - Test: `test_day_mode_stop`. A day-mode long:
    - the stop is below the 08:30 wick CE;
    - a new 1m FVG at 10:30 does not move it;
    - the size is half the session-mode size for the same stop distance.

### 18. X5-event-tight-lock-020
- **rule_id / kind:** X5. Missing rule. Scope: index. judgment = true.
- **Rule:** When a high-impact event (e.g. FOMC) is the next day and the bulk partial (~80%) is already off, move the remainder's stop up tight to lock in profit. Put it above the nearest fresh FVG below price, not under it, and accept being stopped out. On other days use the normal X5 trailing.
- **Sources:** 020_MqOVbd1oqZk ~00:09:40.
- **Quote:** "our stop is admittedly very close but I don't care because at this point in tomorrow's fomc it can do anything" (020).
- **Conflicts:** X5: never trail into or just under a fresh FVG.
- **Rulebook fix:** X5: add an exception, "event next day and the bulk already off: lock profit tight above the nearest fresh FVG (020)".
- **BUILD SPEC (management_exits):**
  - Where: after a rung fill that brings the closed fraction to >= 0.75, if `event_eve_lock` and `events(next_trading_day(day)) & {"fomc", "cpi", "jobs"}`:
    - g = the most recent same-direction gap formed after the fill and below price;
    - call `raise_stop(pos, g.top + stop_buffer, "event_lock")` (above the gap, not under it);
    - set `pos["no_trail"] = True`.
  - Params: `event_eve_lock: bool = False`.
  - Test: `test_event_eve_lock`. Day before FOMC, 80% off, a bullish FVG 4110-4112 below price 4118: the stop goes to 4112 + buffer. On a day without an event-eve tag, the normal FVG trail puts it under 4110.

### 19. X5-trail-after-protected-gap-confirmed
- **rule_id / kind:** X5. Missing condition. Scope: general. judgment = false.
- **Rule:** Long (short is the mirror). Protected zone P = the first breakaway FVG / BPR after the MSS.
  - Until P is confirmed, keep the stop at its initial level. For an entry on the retrace into P, keep it beyond the extreme of the retrace candle.
  - Trail the stop to P only after (a) a new same-direction FVG forms beyond P (003), or (b) price runs to a new extreme past the post-gap swing while part of P stays unfilled (062). Then "let it roll".
  - The exact offset from P is our parameter.
  - If P fills completely it is not breakaway: wait for a new break and a new FVG.
- **Sources:** 003_ojy5ApHhEu4 ~00:41:35; 062_sfRO5LrTgTA ~00:39:12.
- **Quote:** "I like that Gap being there above the Shaded area that's pink ... so I'm moving the stop up" (003).
- **Conflicts:** none.
- **Rulebook fix:** X5: add the confirmation trigger (a) / (b) to "trail under the first breakaway FVG".
- **BUILD SPEC (management_exits):**
  - Where: at the fill, `pos["P"]` = the entry gap (or the BPR from `levels.balanced_ranges` when the entry came from one).
  - With `trail_confirm`:
    - (a) a new same-direction gap with bottom > P.top, or (b) a high > the post-gap swing high (`levels.pivots`) with min(low since the gap) > P.bottom. On either, call `raise_stop(pos, P.bottom - stop_buffer, "P_confirmed")`.
    - If a bar trades below P.bottom before confirmation, clear `pos["P"]`, so it is not breakaway.
    - Before confirmation, `ladder_trail` FVG moves are suppressed.
  - Params: `trail_confirm: bool = False`.
  - Test: `test_trail_confirm`. Entry gap 4100-4102:
    - a new gap 4104-4105 moves the stop to 4100 - buffer;
    - a run to a new high with 4101 untouched also moves it;
    - a dip to 4099.75 first leaves the stop initial and disables P.

### 20. X5-tight-stop-under-swept-pool-near-target
- **rule_id / kind:** X5 / X3. Missing rule. Scope: general. judgment = true.
- **Rule:** Long (short is the mirror).
  - Once the last intermediate pool before the final target has run and the bulk (about 80-90%) is off, move the remainder's stop up aggressively, tight just beneath that swept pool. In 021 that was 4088-4089 with price about 11 pts above, 1-2 ES pts under the level; the exact distance is our parameter.
  - Hold for the final target or the stop.
  - If stopped, no re-entry on that idea. If the target prints, exit everything (X2) and stop for the day (X12).
- **Sources:** 003_ojy5ApHhEu4 ~01:09:14; 021_DVxC7UAHzwk ~00:44:11.
- **Quote:** "a stop loss that would be extremely tight which would be anywhere between 4089 even to 4088" (021).
- **Conflicts:** none.
- **Rulebook fix:** X5: add "after the last intermediate pool runs and the bulk is off, a tight stop just under that pool (003, 021)".
- **BUILD SPEC (management_exits):**
  - Where: in the ladder loop, when the rung just filled is the last pool-kind rung before the final rung (`pos["level_kinds"]`), and the closed fraction is >= `pool_lock_after`:
    - call `raise_stop(pos, level - pool_lock_pts x es_pt, "pool_lock")`;
    - set `pos["no_reentry"] = True`. `_after_close` then sets `done[tr.session] = True` on a stop exit;
    - on a final-rung fill, set the X12 day-done flag (`done["AM"] = done["PM"] = True`) when `pool_lock_day_done`.
  - Params: `pool_lock_after: float = 0.8`, `pool_lock_pts: float = 1.5` (0 = off), `pool_lock_day_done: bool = False`.
  - Test: `test_pool_lock`. Rungs 4085 (pool) / 4089.75 (pool) / 4108 (final), with 80% closed at 4089.75: the stop goes to 4088.25; a stop exit blocks re-entry that session; a 4108 fill ends the day.

### 21. X5-no-trail-into-new-inefficiency
- **rule_id / kind:** X5. Missing condition. Scope: general. judgment = true.
- **Rule:**
  - After price passes the add cutoff (the midpoint of the discount leg for a short, or of the premium leg for a long, per 022), take no new entries.
  - A VI or FVG formed after that point is not a trail level. Keep the stop at the planned anchor (leg extreme, the opposing candle's MT, the nearest wick CE, or the swing low under the inefficient leg), even after partials, so the exit limits can fill.
  - Trail to a newer FVG or swing only after price trades through the targeted pool (067: "once it runs that high").
- **Sources:** 022_ALMsQytQ1fg ~01:12:22; 067_vuBRMFhFZAY ~01:19:24.
- **Quote:** "I'm not going to put my stop loss below that volume imbalance. I'm not going to trail it down there" (022).
- **Conflicts:** X5 "trail under each newer FVG after partials"; the bot build trails under FVGs after each partial.
- **Rulebook fix:** X5: replace "under each newer FVG after each partial" with "no trail to inefficiencies formed after the add cutoff; trail only after the targeted pool runs (022, 067)", and list the conflict.
- **BUILD SPEC (management_exits):**
  - Where: the FVG trail (~2724). With `trail_after_pool`, skip the trail while `pos["pool_hit"]` is False.
  - `pos["pool_hit"]` becomes True when a pool-kind rung (`pos["level_kinds"]`) fills, or the bar's high exceeds the first pool-kind level.
  - Gaps formed after `pos["cutoff_i"]` (the first bar beyond the leg's 50% line; the E12 add cutoff is already computed for adds) are ignored for trailing until `pool_hit`.
  - Params: `trail_after_pool: bool = False`.
  - Test: `test_trail_after_pool`. A long with an array rung filled first and a new FVG forming: the stop is unchanged. After the pool rung fills, the next new FVG moves it.

### 22. X5-trailed-stops-run-after-sb-target
- **rule_id / kind:** X5. Missing rule. Scope: index. judgment = true.
- **Rule:** Descriptive, index (055).
  - After an AM SB long reaches its buy-side target, expect a quick run back down through the nearby sell-side, into the upper quadrant (75% level) of the HTF (daily) discount FVG. This takes out trailed stops before the larger move toward the daily premium FVG.
  - Implication (our inference, not stated): a tight trail under the SB leg is likely to be hit, so bank the SB target (5 handles) rather than trail a runner tightly.
  - Treating that quadrant as an add or re-entry zone is unsourced and would only be a test hypothesis.
- **Sources:** 055_qiv8pkcNvGk ~00:14:35.
- **Quote:** "smart money can accumulate new Longs while trailed stop losses get taken out" (055).
- **Conflicts:** 064: trailed AM stops are run at lunch.
- **Rulebook fix:** X5 / T8: add "trailed-stop runs also follow the AM SB target (055), into the upper quadrant of the daily discount FVG", next to the lunch run (064).
- **BUILD SPEC (silver_bullet, study + switch):**
  - Where: sb_model.py run_sb exit handling. With `sb_runner_trail="none"`, an SB runner keeps its initial stop (no FVG trail) until it exits at the target or at am_exit.
  - Study tag `post_sb_flush` on each SB win: did price trade back into the daily discount FVG's 75% line (`htf.table` arrays) within 60 min of the target fill? Report its frequency.
  - Params: `sb_runner_trail: str = "fvg"` ("fvg" / "none").
  - Test: `test_sb_runner_no_trail`. An SB long with a runner: a new FVG after the target leaves the runner's stop unchanged under "none" and moves it under "fvg". The tag fires on a synthetic flush into a daily FVG's 75% line.

### 23. X5-raise-stop-conditional-structure
- **rule_id / kind:** X5. Missing condition. Scope: index. judgment = true.
- **Rule:** Long (short is the mirror). Keep the initial stop until a trigger fires:
  - (1) 009: price reacts at the VI (retests it and turns up). Stop to VI low - 1 tick.
  - (2) 009: price trades through the bodies of the swing high that preceded entry. Stop to just below the low of the post-entry down-close candle (OB), since a return into the entry FVG is no longer expected.
  - (3) 018: the short-term high above entry is broken, aggressively, ideally leaving a 5m FVG. Stop to the breaker zone's low - 1 tick, which stays below the breaker MT.
  - Promote (1) and (2) from Appendix A (Ep 07) into X5. Drop the invented consolidation-BE threshold; X4's "BE when stalling (009)" covers it as a chart-only note.
- **Sources:** 009_tnxvmHq8xEg ~00:07:10, ~00:09:35; 018_eTMS36H7HA0 ~00:01:38.
- **Quote:** "the short-term High has to be broken then I can raise my stop to the bottom of the breaker" (018).
- **Conflicts:** X5 "don't trail early". Trigger (3) overlaps item 27 (096).
- **Rulebook fix:** X5: add the three triggers, citing Appendix A Ep 07 for (1)-(2) and 018 for (3).
- **BUILD SPEC (management_exits):**
  - Trigger (2) is already built as `ep07_trail` (~2650: trades through the swing body, stop to the retracement low). The new parts are (1) and (3).
  - With `raise_on_vi`: at the fill, store the nearest VI below entry. When a bar's low enters that VI and its close is above the VI top, call `raise_stop(pos, vi.bottom - tick, "vi_react")` once.
  - With `raise_on_sth_break`: at the fill, store `sth` = the most recent pivot high above entry and the breaker zone (`levels.breaker_zone`). When a bar's high exceeds `sth`, call `raise_stop(pos, bz.bottom - tick, "sth_break")`. With `raise_need_5m_fvg`, only do it once a 5m gap (setup_minutes aggregation) has formed in the break.
  - Params: `raise_on_vi: bool = False`, `raise_on_sth_break: bool = False`, `raise_need_5m_fvg: bool = False`.
  - Test: `test_raise_conditional`. VI 4010-4011:
    - a bar with low 4010.5 and close 4012 moves the stop to 4009.75;
    - a close at 4010.75 does not;
    - a break of `sth` moves the stop to the breaker bottom - tick.

### 24. X5-trail-swing-low-at-intermediate-level
- **rule_id / kind:** X5. Missing rule. Scope: general. judgment = true.
- **Rule:** After partials, when price reaches an intermediate PD array where a reversal is plausible (in 060, the new-day / opening-range gap area short of the final buy-side), trail the stop to just below the latest 1m swing low (long). Hold the last unit for the final draw, exiting on that stop. Do not close the whole position at the intermediate level.
- **Sources:** 060_ZtLMTXv-Dr0 ~00:54:30.
- **Quote:** "if it's going to reverse it's going to reverse there" (060).
- **Conflicts:** none.
- **Rulebook fix:** X5: add "at an intermediate array short of the draw, after partials: trail under the latest 1m swing low and hold the last unit (060)".
- **BUILD SPEC (management_exits):**
  - Where: in the ladder loop, after any non-final rung of kind "array" (including NDOG / ORG gap levels from `htf.opening_gaps`) fills with `trail_swing_at_array`, call `raise_stop(pos, last_pivot_low - tick, "swing_at_array")`. `last_pivot_low` is the most recent `levels.pivots(n=1)` low since the fill.
  - Params: `trail_swing_at_array: bool = False`.
  - Test: `test_trail_swing_at_array`. Rungs at an ORG level (array) and a final pool, with a 1m pivot low at 4095 before the array fill: the stop goes to 4094.75 and the last unit stays open.

### 25. X5-071-trail-anchors
- **rule_id / kind:** X5. Missing rule. Scope: index. judgment = true.
- **Rule:** Short (long is the mirror); only tighten. Additional trail anchors from 071, in the order ICT used them:
  - (a) 1 tick above the MT of the most recent up-close candle before the latest down leg (his "favorite" trail location);
  - (b) just above relatively equal ("smooth") highs that formed during a pause, accepting that they may be run;
  - (c) for the last units after partials, just above the rejection block (the wicks of the last closed candle(s), A17).
  - The exact trigger for each step (new low, number of equal highs) is our parameterisation.
- **Sources:** 071_3FGFEuaDSOc ~00:14:42, ~00:31:55, ~00:36:47.
- **Quote:** "just above mean threshold of that last up close candle ... favorite location for a trail stop" (071).
- **Conflicts:** none.
- **Rulebook fix:** X5: add the three anchors (071) beside the FVG trail.
- **BUILD SPEC (management_exits):** `ladder_trail` gets new values.
  - "candle_mt": on each new extreme beyond the prior one since the fill, call `raise_stop` to 1 tick beyond the body MT (D4 `mt_mode`) of the last opposite-close candle before the leg that made the extreme.
  - "eq_pause": when 2+ pivots against the trade within `eq_tol_pts` (`levels.equal_levels`) form after the fill and lie between price and the stop, call `raise_stop` to 1 tick beyond the furthest of them.
  - "rej_block": after the last non-final rung fills, call `raise_stop` to 1 tick beyond the furthest wick of the last 1-2 closed bars (`levels.rejection_blocks(n=2)`).
  - Combined value "071" runs all three in order.
  - Params: `ladder_trail` values "candle_mt" / "eq_pause" / "rej_block" / "071" (validate in `__post_init__`).
  - Test: `test_trail_071`. A synthetic short:
    - a new low moves the stop above the last up-close candle's MT;
    - two equal pivot highs move it above them;
    - after the penultimate rung, it sits above the last bar's wick.

### 26. X5-ob-open-after-retests
- **rule_id / kind:** X5. Missing rule. Scope: index. judgment = true.
- **Rule:** Long open. The defending bullish OB = the down-close candle whose open price has been retested.
  - After price first trades above it, count retests: a bar that trades to within 1 tick of the open and is immediately followed by a move higher.
  - After 3 such retests, raise the stop to just below that open (1 tick), because a return there implies lower prices.
  - This is the maximum raise until new 1m structure forms (see item 27). Mirror for shorts.
  - List the conflict with 048 (repeated taps weaken an array).
- **Sources:** 085_6-KNSUN-UaU ~00:17:52.
- **Quote:** "it need not trade back there why because we already had one two three times to it" (085).
- **Conflicts:** 048: a 3rd tap makes an array unreliable (item 101).
- **Rulebook fix:** X5: add the 3-retest raise (085) and cross-reference X9 / item 50.
- **BUILD SPEC (management_exits):**
  - Where: at the fill, `pos["ob_open"]` = the open of the entry OB's down-close candle (`levels.order_block` already gives it for OB entries; for FVG entries use the last down-close candle before the displacement).
  - Count bars after the fill with `low <= ob_open + tick` and `low >= ob_open - tick` whose next bar's high exceeds theirs. At `ob_retests` hits, call `raise_stop(pos, ob_open - tick, "ob_open")` and set `pos["freeze"] = True` (item 27 lifts the freeze).
  - Params: `ob_retests: int = 0` (0 = off; test 3).
  - Test: `test_ob_open_retests`. OB open 4400: three touches at 4400 / 4400.25 / 4399.75, each followed by a higher bar, move the stop to 4399.75 on the third. Two touches do nothing.

### 27. X5-structure-trail-and-cap
- **rule_id / kind:** X5. Missing rule. Scope: index. judgment = false.
- **Rule:** Long.
  - Once price clears the short-term structure high formed after the entry (096: clears it; Ep 07: trades through the bodies of the prior swing high), move the stop to just below the low of the retracement into the entry array (the breaker or its MT, the OB, the BPR). This may happen before T1 and is not breakeven.
  - The stop then stays frozen until new 1m structure forms: a new higher swing low and a break of the high that followed it. Only then may it be raised again, under that swing low or its wick CE, and never into or just under an FVG created by that break (X5, 085 ~21:24).
  - Never lower the stop. Mirror for shorts.
  - List the conflict with X4/D14 (no stop move before the first partial) and X5 (day trades keep their initial stop).
- **Sources:** 085_6-KNSUN-UaU ~00:16:22; 096_tjnir-o4rsQ ~00:04:35.
- **Quote:** "that's the highest it should be raised to until new structure is placed in this time frame" (085).
- **Conflicts:** X4/D14: no stop move before the first partial. X5: day trades keep their initial stop. Overlaps item 23 trigger (3).
- **Rulebook fix:** X5: add the structure trail with its freeze (085, 096), promote the Ep 07 appendix rule, and list both conflicts.
- **BUILD SPEC (management_exits):**
  - Where: `ladder_trail="structure"`.
  - At the fill: `sth` = the latest pivot high after the entry array was touched; `retr_low` = the lowest low since the fill (already stored for `ep07_trail` as `pos["retr_low"]`).
  - Step 1: when the bar's high exceeds `sth`, call `raise_stop(pos, retr_low - tick, "structure")` and set `freeze = True`.
  - Unfreeze when a new 1m pivot low L > stop forms and a later bar exceeds the pivot high that followed L. Then call `raise_stop(pos, min(L, wick_ce(L bar)) - tick)`, unless that level lies inside a gap formed by the break bar, in which case use the gap bottom - tick.
  - Repeat. Skipped when `pos["trade_mode"] == "day"`.
  - Params: `ladder_trail` value "structure".
  - Test: `test_structure_trail`. Entry 4100, retrace low 4097, sth 4104:
    - a break of 4104 moves the stop to 4096.75, and later bars without new structure leave it there;
    - a new pivot low at 4103 and a break of the following high move it to 4102.75.

### 28. X5-roll-after-wick-ce-cleared
- **rule_id / kind:** X5. Missing condition. Scope: index. judgment = false.
- **Rule:** Long.
  - Find the nearest overhead candle whose upper wick blocks the path; its CE = (max(open, close) + high) / 2.
  - Do not raise the stop until price trades through and above that CE (085 ~26:11, ~31:34). A body close above it is our stricter option, not ICT's.
  - Then trail per X5: below the last defended low or wick CE, never into a fresh post-MSS FVG. Mirror for shorts.
- **Sources:** 085_6-KNSUN-UaU ~00:26:11, ~00:31:34.
- **Quote:** "I chased it too soon it did not Pierce and trade through the other side north of the consequent encouragement of this Wick" (085).
- **Conflicts:** none.
- **Rulebook fix:** X5: give "don't trail early (085 ~26:46)" its trigger, "not before price trades above the overhead wick's CE".
- **BUILD SPEC (management_exits):**
  - Where: a gate in `raise_stop` used by every trail mode when `trail_wick_gate` is on.
  - At the fill and after each stop move, `pos["wick_gate"]` = the CE of the upper wick of the highest bar between the fill and now that sits above price with an upper wick >= 25% of its range [our interpretation of "blocks the path"].
  - Trail moves (not BE) are refused until a bar's high (or close, with `trail_wick_gate="close"`) exceeds `wick_gate`.
  - Params: `trail_wick_gate: str = ""` ("" / "trade" / "close").
  - Test: `test_trail_wick_gate`. An overhead bar 4110-4120 with body top 4114 gives CE 4117:
    - a new FVG while the high is under 4117 leaves the stop unchanged;
    - a bar to 4117.25 allows the next trail.

### 29. X5-stop-to-ob-mt-after-run
- **rule_id / kind:** X5. Missing rule. Scope: general. judgment = true.
- **Rule:**
  - After entry at a bullish OB, once price has moved away, move the stop to OB_MT minus a buffer. "Moved away" is our interpretation: at least 2x the OB body height above entry, or a new swing high above the validating candle.
  - MT follows `mt_mode`. The slide says "total range"; D4 elsewhere uses the body.
  - Bearish mirror. Parameter `ob_stop_to_mt_after_run`.
- **Sources:** cc04_003_PIYh0CxoY9c ~00:02:00.
- **Quote:** "just below the 50 percent of the order block total range is also considered to be a good location to raise the stop" (cc04_003).
- **Conflicts:** the slide says total range; D4 elsewhere uses the body.
- **Rulebook fix:** X5: add "after price runs away from the entry OB, the stop may go just below the OB's 50% (cc04_003 slide; range vs body per D4)".
- **BUILD SPEC (management_exits):**
  - Where: OB entries (`_ob_entry`, ~3706, which set `pos["ob"]`).
  - With `ob_stop_to_mt_after_run`, when `best - avg >= 2 x body_height` or a pivot high above the validating candle's high has formed, call `raise_stop(pos, ob_mt - stop_buffer, "ob_mt_run")` once. `ob_mt` follows `mt_mode` ("body" / "range").
  - Params: `ob_stop_to_mt_after_run: bool = False`.
  - Test: `test_ob_stop_to_mt`. An OB with body 4000-4004 and range 3998-4005, entry 4004 with the stop below 3998: a run to 4012 moves the stop to 4002 - buffer (body) or 4001.5 - buffer (range). A run to 4007 does nothing.

### 30. X5-friday-tight-trail
- **rule_id / kind:** X5. Shortened. Scope: index. judgment = true.
- **Rule:** Friday, position still open and target not reached late in the day: do not carry it over the weekend. Trail the stop tightly behind price and let the stop take you out, and flatten before the close if the stop is not hit (no weekend positions). Exactly where to place the tight trail is our choice (e.g. the latest small swing or the last FVG). Source: 103, one anecdote.
- **Sources:** 103_IU673ZUGuxI ~00:30:33.
- **Quote:** "by trilling the stop loss real real tight and letting it take me out" (103).
- **Conflicts:** none.
- **Rulebook fix:** Friday rules: add "late Friday, open trade short of target: tight trail out rather than a market close (103)".
- **BUILD SPEC (day_week_context + management_exits):**
  - Where: in the run_day loop, when `day.weekday() == 4`, `t >= fri_trail_from` and `pos["left"]`: each bar, call `raise_stop(pos, pivot_low_1m - tick, "fri_trail")`, using the latest `levels.pivots(n=1)` low after the fill. The flatten at `flat` (~2707) still closes the rest.
  - Params: `fri_trail_from: int = 0` (0 = off; test 900 = 15:00).
  - Test: `test_friday_trail`. A Friday long open at 15:00 with 1m pivot lows rising: the stop ratchets under each new pivot. On Thursday nothing moves.

### 31. X5-swing-final-exit-4h-trail
- **rule_id / kind:** X5. Missing rule. Scope: general (swing). judgment = true.
- **Rule:** Exit all remaining size with a limit at the objective. Once excursion >= 0.75-0.80D, trail 1 tick below the most recent confirmed 4h 3-bar swing low and only ratchet it upward. Short mirror.
- **Sources:** cc06_008_VL4YLTRerHY ~00:17:10.
- **Quote:** "take full position off at intended premium array objective or 75 to 80% and Trail stop loss below the most recent 4-Hour short-term low" (cc06_008).
- **Conflicts:** none.
- **Rulebook fix:** X5: add a swing line (cc06_008): full exit at the objective, or a 4h swing-low trail from 75-80% of the move.
- **BUILD SPEC (bias_htf, study only):**
  - Where: `swing_mgmt_study` (item 13) `trail="4h"`. Aggregate 4h bars with `htf.sessions`-style resampling.
  - From progress >= `swing_trail_from`, stop = the last confirmed `levels.pivots(n=1)` 4h low - tick, ratchet only. Limit exit at D.
  - Study config: `swing_trail_from: float = 0.75`.
  - Test: `test_swing_4h_trail`. Synthetic 4h bars: the trail starts only after 0.75D and never decreases.

### 32. X5-swing-eq-stop-runs
- **rule_id / kind:** X5. Missing rule. Scope: general (swing). judgment = true.
- **Rule:** R = [entry array, objective], EQ = midpoint.
  - Phase 1: once price is above EQ, expect a pullback stop run into or just above EQ. Do not trail above the EQ zone before it happens.
  - Phase 2: once the high made near the midpoint is exceeded, expect a pullback retesting it. Do not trail above it.
  - Phase 3: after that, expect a direct run to the objective; trail under 4h swing lows.
  - The pattern is fractal by quadrants.
- **Sources:** cc06_008_VL4YLTRerHY ~00:17:23; add ~25:55-32:50 of the same video.
- **Quote:** "the market Canon will likely make a run for sell stops at or just above 50% of the range you hold through" (cc06_008).
- **Conflicts:** none.
- **Rulebook fix:** X5: add the swing three-phase stop-run expectation with sources cc06_008 ~17:23 and ~25:55-32:50.
- **BUILD SPEC (bias_htf, study only):**
  - Where: `swing_mgmt_study` `trail="phased"`:
    - the stop may not rise above EQ - buffer until a pullback to <= EQ + 0.05R occurs after price first exceeds EQ;
    - it may not rise above H_mid (the high made near EQ) until a retest pullback after H_mid is exceeded;
    - then the 4h trail (item 31) applies.
  - Report how often each phase's stop run occurs on daily data.
  - Test: `test_swing_phased_trail`. A path that rises past EQ, pulls back to EQ, breaks H_mid, retests it, then runs: the stop levels follow the three caps in order.

### 33. new-position-40-20-day-trail
- **rule_id / kind:** new. Missing rule. Scope: general (position, M17-parked). judgment = false.
- **Rule:** Long.
  - Stop = below the lowest daily low of the last 40 trading days (inclusive of the trade day), with a small discretionary buffer. ICT's example rounds a 250-pip risk to 260; no fixed % is given. Recompute daily and only tighten.
  - progress = (price - origin) / (objective - origin). Once progress >= trail_switch, use the 20-day lowest low instead.
  - trail_switch in {0.5 (default: the bullish slide's first statement + the USDJPY example), 0.75 (the bullish slide's second statement + the bearish slide)}.
  - Shorts mirror with highs. No breakeven step.
- **Sources:** cc05_018_okN5p701T7Y ~00:05:52, ~00:07:48, ~00:13:59, ~00:25:10.
- **Quote:** "trailing your stop loss below the lowest low in the last 40 trading days" (cc05_018).
- **Conflicts:** within cc05_018, 0.5 vs 0.75 as the switch threshold.
- **Rulebook fix:** M17: add the 40/20-day position trail with both thresholds and the conflict. X4: note "no BE on position trades".
- **BUILD SPEC (bias_htf, study only):**
  - Where: `swing_mgmt_study` `trail="donchian"`:
    - stop = `min(low[-40:]) - pos_buffer`, ratchet only;
    - from progress >= `trail_switch`, use `min(low[-20:])`;
    - no BE.
  - Study config: `trail_switch: float = 0.5`, `pos_buffer_frac: float = 0.04` [our interpretation of the 250 -> 260 rounding].
  - Test: `test_donchian_trail`. A daily series: the stop equals the 40-day low before the switch and the 20-day low after it, and never decreases.

---

## C. Partials, ladders and runners (X3, D13, L12-L16)

### 34. X3-new-vs-experienced-partials
- **rule_id / kind:** X3 / D13. Missing rule. Scope: general. judgment = true.
- **Rule:**
  - partial_mode='new' (bot default; the bot is the "new trader"): take most of the position at the first partial (ICT: "the most"; 75-80% is our number). The terminus is the nearest low-hanging-fruit pool, with all or nearly all units out there.
  - partial_mode='experienced': a smaller first partial, a runner to the far draw, or holding to the full terminus set at entry.
- **Sources:** 022_ALMsQytQ1fg ~00:53:36; 025_7RiUUCqQ3SY ~00:57:20; 065_rx15_eN9sxI ~02:34:01; 067_vuBRMFhFZAY ~01:03:59.
- **Quotes:** "in the beginning when you're first learning take the most off" (065); "Terminus while you're first learning is the easiest loow hanging fruit objective" (067).
- **Conflicts:** D13 option B (about half or less at the first pool: 004, 018, 041) is ICT's own experienced-trader execution, not the new-trader default.
- **Rulebook fix:** X3 / D13: add the new-vs-experienced split. Recommend 'new' for the bot. Relabel D13 option B as "experienced".
- **BUILD SPEC (targets_partials):**
  - Where: `_split` (~2095). With `partial_mode="new"`, return (`new_first`, 1 - `new_first`) and cut the ladder at the first pool-kind level, so the last rung is the nearest pool (`pos["level_kinds"]`; the same trim used at ~4290).
  - "experienced" = today's ladder.
  - "terminus" = a single rung at the last level (no intermediate partials).
  - Params: `partial_mode: str = ""` ("" = today / "new" / "experienced" / "terminus" / "quarters", item 42), `new_first: float = 0.8`.
  - Test: `test_partial_mode_new`. Levels [array 4105, pool 4110, pool 4120]:
    - "new" gives fracs (0.8, 0.2) and rungs [4105, 4110 + beyond];
    - "terminus" gives one rung at the 4120 pool.

### 35. X3-full-pull-vs-mandatory-partial
- **rule_id / kind:** X3. Unlisted contradiction. Scope: general. judgment = true.
- **Rule:**
  - Default (new trader / bot): close a partial (~50%) at the first obvious pool on the way to the target (092 "how I mentor you"; cc02_003 "always pay yourself, never all-or-nothing").
  - Options to test:
    - (a) Speed exception (092): if price breaks the first pool with large-range candles, skip the partial and hold for the deeper target. Our proxy: the break bar and the next bar are both >= 1.5x the median 20-bar range and close beyond.
    - (b) full_pull in a low-resistance run (102, 089): no partials; the stop moves to BE+ once price expands; close 100% just beyond the first liquidity target. 089 did this even while expecting lower.
    - (c) hold_runner (076): a big-range day driven by the HTF. The initial stop is never moved, there is no trail and no partials, and the exit comes into the last hour when the day's extreme is expected.
  - High-resistance runs (a consolidation or BPR in the path, 102) and high-volatility conditions (092): more partials at wick CEs and candle extremes, and allow for a fake bounce before the final pool.
  - List the conflict: cc02_003 / 092 (pay yourself) vs 076 / 089 / 102 (full pulls). 089's full pull was driven by a dollar goal, not run resistance.
- **Sources:** 076_cgsltOB736E ~00:26:32; 089_h0yOpwSilnE ~00:08:46; 092_9MLRE-n6St8 ~01:30:11; 102_uzPM1CuSSx8 ~02:18:40; cc02_003_pctqB3UD6dk ~00:15:05. (076 ~19:21 is about the IFVG, not exits, and is dropped.)
- **Quotes:** "don't worry about trailing it don't worry about trying to take Parcels just let it go" (076); "if you're binary It's All or Nothing you're never going to be as good" (cc02_003).
- **Conflicts:** 076 / 089 / 102 allow no partials vs 092 / cc02_003. cc03_003 / cc04_002 say never collapse the whole trade at intermediate highs (item 38).
- **Rulebook fix:** X3: replace "full pull in low resistance, partials in high resistance, discretionary" with the default plus options (a)-(c), and the conflict list. Note that 102 supports X3's resistance framing.
- **BUILD SPEC (targets_partials + management_exits):** extends section 3 X3f `resistance_mode`.
  - Where: `exit_mode2` sets `pos["trade_mode"]` at the fill.
  - "pay_first" (the candidate default): the first pool-kind rung gets at least 0.5. The speed exception `speed_skip` applies there: when the bar crossing that pool and the next bar both have range >= 1.5x `median(range[-20:])` and close beyond it, drop that rung's fraction into the next rung.
  - "full_pull": a single rung at the first pool beyond, plus item 11's BE.
  - "hold_runner": no rungs except the final; stop frozen; exit at the final level or at 15:00-`flat`.
  - Params: `exit_mode2: str = ""` ("" / "pay_first" / "full_pull" / "hold_runner"), `speed_skip: bool = False`.
  - Test: `test_exit_mode2`.
    - "pay_first" with two big-range bars through the first pool closes nothing there and adds that fraction to rung 2;
    - "full_pull" closes 100% at the first pool;
    - "hold_runner" ignores new FVGs and is still open at 14:59.

### 36. X3-htf-target-bank-partial
- **rule_id / kind:** X3. Missing rule. Scope: general. judgment = true.
- **Rule:**
  - Applies when an open position reaches the HTF (daily / weekly) PD array that was its draw (inside it or at its edge), or when its planned target prints while price sits at that array with continuation judged 50/50.
  - Close about half of the remaining units. Keep the rest with the stop in profit.
  - Block new same-direction adds and new counter-direction entries at that array.
  - Reconcile with X12, which closes everything only when the session objective itself is hit.
- **Sources:** 050_F509lJRrYIM ~00:09:50; 099_v_iJlBKYmUc ~00:22:50.
- **Quotes:** "it's 50 50 so I'm gonna take three contracts off of the six remaining" (050); "doesn't mean close your entire position doesn't mean take new shorts on" (099).
- **Conflicts:** X12 (session objective hit: close everything).
- **Rulebook fix:** X3: add the HTF-draw bank rule (050, 099) and the X12 reconciliation.
- **BUILD SPEC (management_exits):**
  - Where: at the fill, `pos["htf_draw"]` = the near edge of the `htf.table` draw array for the bias direction (the bias_htf `want` draw already in DayCtx).
  - With `htf_bank`, when price trades into it, once: `partial_close(pos, tr, ts, c, htf_bank, "htf_bank")`, `raise_stop(pos, avg + be_pad_pts, "htf_bank")`, and set `pos["no_adds"] = True`.
  - Also mark `state["htf_touch"][dir] = i`. `_scan_core` then rejects counter-direction setups whose entry array lies inside that HTF array for the rest of the session.
  - Params: `htf_bank: float = 0.0` (0 = off; test 0.5).
  - Test: `test_htf_bank`. A long with a daily FVG draw at 4150, 6 units left:
    - a bar to 4151 closes 3 units and moves the stop to BE+;
    - a short setup armed inside that FVG later in the session is rejected.

### 37. X3-pool-below-untraded-htf-partial
- **rule_id / kind:** X3. Missing rule. Scope: general. judgment = true.
- **Rule:**
  - If price takes a liquidity pool (REH / REL, old high or low) while an HTF (daily / weekly) PD array in the same direction is still untouched beyond it, the pool is a partial, not the final target.
  - Close one partial there and hold the rest for the HTF array.
  - Do not take a reversal (turtle-soup-style) setup off that sweep.
  - For NWOG sequences, apply the existing L5 halfway rule to decide whether NWOG #1 is a mile marker or the final target (cross-reference L5; no new NWOG logic needed).
- **Sources:** 061_wWvXWmC_gqU ~02:19:41 (051 ~16:40 already in L5).
- **Quote:** "I'm not going to look at these equal highs being traded to and then reject and go lower that's just a partial" (061).
- **Conflicts:** none.
- **Rulebook fix:** X3: add "a pool short of an untouched same-direction HTF array is a partial, not the final; no reversal trade off that sweep (061)".
- **BUILD SPEC (targets_partials + setups_models):**
  - targets_partials: in the `_scan_core` target merge (~4150-4210), with `pool_milestone`, a pool rung that lies before an untouched `htf.table` same-direction array within reach keeps fraction `pool_milestone` (not 1.0, even when it is the ladder's last pool), and the HTF array's near edge (`exit_px_mode` kind "array") is appended as the final rung.
  - setups_models: a counter-direction sweep setup in `_scan` whose swept pool lies between price and an untouched HTF array in the bias direction is rejected (`reject="htf_untraded"`).
  - Params: `pool_milestone: float = 0.0` (0 = off; test 0.5).
  - Test: `test_pool_milestone`. A long with REH 4120 and an untouched daily FVG at 4130:
    - the ladder ends at the FVG edge with 50% at 4120;
    - a turtle-soup short off the 4120 sweep is rejected.

### 38. X3-no-collapse-intermediate-pools
- **rule_id / kind:** X3. Unlisted contradiction. Scope: general. judgment = true.
- **Rule:**
  - While the HTF draw (a pool or array, e.g. the near edge of a monthly FVG) is untaken and price keeps taking successive short-term highs, take at most partials at intermediate highs and never collapse the whole trade.
  - Do not exit on reversal candle patterns or on indicator (oscillator) divergence. SMT warnings per X3 still apply.
  - Close the rest at the HTF draw.
- **Sources:** cc03_003_t2VNzJZ4hK4 ~00:25:28; cc04_002_npL3ZXJ5zOU ~00:16:04.
- **Quote:** "we don't collapse the trade entirely we don't look for reversal patterns we do not look for divergence" (cc03_003).
- **Conflicts:** X3 full pull (089 closes 100% at the first sell-side target). The claim's "036/045 intermarket close-all" entries are not in the rulebook (corrected).
- **Rulebook fix:** X3: add the no-collapse rule and list the conflict with the full pull. Note that it does not override SMT warnings.
- **BUILD SPEC (targets_partials):**
  - Where: a ladder guard in the ladder loop (~2614). With `no_collapse_htf`, while `pos["htf_draw"]` (item 36) is untouched, a non-final rung never closes the last `no_collapse_keep` of the original units; the remainder rides to the HTF draw rung.
  - No indicator exits exist in the engine, so nothing else changes.
  - Params: `no_collapse_htf: bool = False`, `no_collapse_keep: float = 0.2`.
  - Test: `test_no_collapse`. A 3-rung ladder whose fractions would close 100% at rung 2 with the daily draw untouched leaves 20% open for the draw rung.

### 39. D13-speed-bump-ladder-004
- **rule_id / kind:** D13 / X3. Unlisted contradiction. Scope: index. judgment = true.
- **Rule:**
  - Classify an intermediate level between entry and the pre-marked draw as a speed bump: an expected pause, not a reversal level.
  - At a speed bump close a small piece (about 2/9, ~22%) and leave the stop unchanged.
  - Close about 3/9 above the next level and about 3/9 at the draw (the buy-side pool, exit per X2). Run 1 unit to the next HTF PD array beyond the draw (the daily volume imbalance as the "terminus"). Being stopped on the runner is acceptable.
  - Add 004 to D13 option B. Test partial_ladder=(0.22, 0.33, 0.33, runner 0.11) vs partial=0.5.
  - The runner close time follows X10 (our rule, not stated in 004).
- **Sources:** 004_AUbdCTzc19k ~00:01:00 (chart annotations; no captions).
- **Quote:** chart note "This is a Speed Bump not a reversal level" (004).
- **Conflicts:** D13 option A (80-90% at the first pool) vs 004's small first partial.
- **Rulebook fix:** D13: add 004 to option B with the 2/3/3/1 ladder. X3: define "speed bump".
- **BUILD SPEC (targets_partials):**
  - Where: `_split`. `ladder_fracs` already accepts any tuple; add the preset `ladder_preset="004"` -> (0.22, 0.33, 0.33, 0.12).
  - In the target merge, the 4th rung = the nearest HTF array beyond the draw (`final_htf`, section 3 Ep03.22). Rungs before the draw that are not pools are tagged "bump"; a "bump" fill does not trigger `be_on="t1"` or the ladder trail.
  - Params: `ladder_preset: str = ""`.
  - Test: `test_ladder_004`. 9 units, levels [bump 4098, array 4118, pool 4148, daily VI 4160]:
    - fills of 2 / 3 / 3 / 1 units;
    - the stop is unchanged after the bump fill.

### 40. X3-partial-size-by-energy
- **rule_id / kind:** X3. Missing condition. Scope: index. judgment = true.
- **Rule:** Size the first partial by delivery quality.
  - (a) If price only pokes through the intervening reference high (the 09:30 high) without energy or speed, so a retrace into the entry OB is possible, take about half.
  - (b) If you expect no continuation beyond the target ("no continuation on the outside"), take the bulk (about 2/3, 9 of 14).
  - Bot proxies, such as whether a displacement FVG is present and the room to the next draw, are implementation choices to test.
- **Sources:** 009_tnxvmHq8xEg ~00:11:26 (and ~17:20).
- **Quote:** "we haven't done it with a great deal of energy so ... I'm looking at taking off six or half" (009).
- **Conflicts:** none.
- **Rulebook fix:** X3: replace "9 of 14 (009)" with the two conditions above.
- **BUILD SPEC (targets_partials):**
  - Where: `_split`, given the fill bar and the levels. With `energy_split`:
    - (a) if the bar(s) that crossed the 09:30 high (`_idx_at(ctx, 570)` high) before the fill left no same-direction gap, first fraction = 0.5;
    - (b) elif no pool or array lies within `energy_room_pts` beyond T1, first fraction = 0.65;
    - else today's split.
  - Params: `energy_split: bool = False`, `energy_room_pts: float = 5.0`.
  - Test: `test_energy_split`. A gapless poke through the 09:30 high gives 0.5. No level within 5 pts beyond T1 gives 0.65.

### 41. X3-five-handle-first-partial-before-draw
- **rule_id / kind:** X3 / L12. Missing rule. Scope: index. judgment = true.
- **Rule:** Long (short is the mirror).
  - P1 = avg_entry + 5.00 + 0.25 ES pts (fees), taken even if the draw has not been reached (036, 018).
  - P2 = avg_entry + 10 (060).
  - Exit the remainder as price trades into the target PD array or liquidity void, without waiting for the extreme beyond it (060).
  - This is a partial schedule, consistent with owner correction #2 (5 handles is minimum room, the draw is the target).
  - In backtests, fill limits where the spread would realistically fill, not at the bar extreme.
  - Drop the -1 SD alternative unless a source is found.
- **Sources:** 036_n37ozsUreR0 ~00:49:59; 060_ZtLMTXv-Dr0 ~01:14:58; 018_eTMS36H7HA0 ~00:02:52.
- **Quotes:** "that's five handles this would be a perfect opportunity ... to take a partial" (036); "you can book five take a partial at 10" (060).
- **Conflicts:** 018's at-edge fill vs X2 (item 1).
- **Rulebook fix:** X3: add the +5.25 / +10 partial schedule (036, 018, 060), distinct from L15's minimum room.
- **BUILD SPEC (targets_partials):**
  - Where: the `_scan_core` target merge. With `fixed_partials`, insert rungs at `avg + 5.25` and `avg + 10` (side space, kind "fixed"; `exit_px_mode` returns `v` for "fixed") before any farther level, sorted by price. Their fractions come from `fixed_partial_fracs`, and the draw rungs share the rest.
  - `exit_fill="limit_through"` (item 6) gives the realistic fill.
  - Unlike X14a `day_target_pts`, this is not a target and does not count toward `min_draw_pts`.
  - Params: `fixed_partials: tuple = ()` (test (5.25, 10.0)), `fixed_partial_fracs: tuple = (0.25, 0.25)`.
  - Test: `test_fixed_partials`. Avg 4054, draw FVG at 4070: rungs [4059.25, 4064, 4069.5] with fractions 0.25 / 0.25 / 0.5. The draw alone still decides `min_draw_pts`.

### 42. X3-gradient-ladder-htf-target
- **rule_id / kind:** X3. Missing rule. Scope: general. judgment = true.
- **Rule:**
  - (a) HTF FVG / imbalance target: partials at the near edge, the 25% gradient, the CE, then the next gradient level (75%), each less the spread / X2 buffer (065, shown on FX).
  - (b) Target beyond the first pool: the first partial just beyond the first REH. Grade the range from that high to the HTF array into gradients with layered resting exits. The final unit goes just before the HTF array's near edge, and the last unit may stop out (070).
  - (c) Two targets with the first expected to break: divide the range between them into quarters (an implied dealing range) and scale at the quarter levels (098, daily / swing context).
  - Drop the "majority on Fridays" clause (not sourced).
- **Sources:** 065_rx15_eN9sxI ~03:53:00; 070_1HtRfFYiwO0 ~00:32:22; 098_PejS-nZTQlE ~00:26:26.
- **Quote:** "I did gradients ... I layered out the odors and then I had one ultimately just below the weekly volume" (070).
- **Conflicts:** X3 (026): next partial halfway between targets.
- **Rulebook fix:** X3: add the gradient ladder (a)-(c) next to the halfway rule.
- **BUILD SPEC (targets_partials):**
  - Where: target merge. `partial_mode="quarters"` (item 34's field) rewrites the ladder:
    - (a) if the final level is an HTF gap (carrying `far`, item 1), rungs = near, near + 0.25h, CE, near + 0.75h, each via `exit_px_mode`;
    - (b) if a pool precedes it, rungs = pool (beyond), then the 25 / 50 / 75% points of [pool, HTF near edge], then HTF near - `exit_before_pts`;
    - (c) for two pool targets, the 25 / 50 / 75% points between them, then T2.
  - Equal fractions. Rungs are capped by `ladder_max_levels` (section 3 X3a).
  - Test: `test_quarters_ladder`. A weekly FVG 4500-4520 gives rungs at 4499.5 / 4504.5 / 4509.5 / 4514.5. A pool at 4480 with an HTF edge at 4500 gives 4480.25 / 4485 / 4490 / 4495 / 4499.5.

### 43. X3-037-three-unit-ladder
- **rule_id / kind:** X3. Missing rule. Scope: index. judgment = true.
- **Rule:** Long with 3 units:
  - 1/3 at the nearest old short-term high (exact price);
  - 1/3 when price trades 1 tick into the first bearish FVG above (its near edge), at market;
  - the final 1/3 at that FVG's CE or its upper edge - 1 tick.
  - On a day like this (pre-news), most of the position should be off inside that first premium FVG.
  - The fib projection of the swing is only confluence for how far the move can stretch.
- **Sources:** 037_wu0sQarBRrI ~00:53:54.
- **Quote:** "aim for the midpoint or the upper end of the fair value Gap less one tick" (037).
- **Conflicts:** none.
- **Rulebook fix:** X3: add the 037 ladder (it is cited only for SMT today).
- **BUILD SPEC (targets_partials):**
  - Where: `ladder_preset="037"`. Rungs = [nearest pool (kind "pool", `pool_exit="at"` for this rung), first bearish FVG above near + tick (kind "fixed"), that FVG's far edge - tick (or CE with `ladder037_ce`)], fractions (1/3, 1/3, 1/3).
  - On news-ahead days (`_split`'s `ahead`), use (0.4, 0.4, 0.2).
  - Params: `ladder_preset` value "037", `ladder037_ce: bool = False`.
  - Test: `test_ladder_037`. Old high 4022, FVG 4025-4029: rungs 4022 / 4025.25 / 4028.75 (or 4027 with the CE switch).

### 44. X3-041-projection-first-then-nwog
- **rule_id / kind:** X3 / L12. Shortened. Scope: index. judgment = true.
- **Rule:** Long with the NWOG above as the draw:
  - T1 = the SD swing projection lying before the NWOG; take 1/3 there (5 of 15), then move the stop to better than breakeven.
  - Scale the rest in pieces as price enters the NWOG. The final contract rests on a limit near the NWOG's top end.
  - The projection anchor is not stated (D23).
- **Sources:** 041_UPKUqW_eaas ~00:01:16.
- **Quote:** "That Swing projection Target is my first Target I'll take five contracts out there" (041).
- **Conflicts:** none.
- **Rulebook fix:** X3: replace "041 1/3" with the ordered ladder (projection 1/3 -> scale into the NWOG -> last contract near its top).
- **BUILD SPEC (targets_partials):**
  - Where: `ladder_preset="041"`. Rungs = [first `sd_levels` projection below the NWOG near edge (kind "proj", item 3), NWOG near edge, NWOG CE, NWOG near + 0.75h ('deep', item 1)], fractions (0.33, 0.27, 0.2, 0.2).
  - `be_pad_pts` applies after rung 1 when `be_on="t1"`.
  - Needs NWOG levels from `htf.gaps_for_day` with `far`.
  - Test: `test_ladder_041`. Projection 4010, NWOG 4015-4025: rungs 4009.5 / 4014.5 / 4019.5 / 4022.5, with 5 of 15 units at rung 1.

### 45. X3-resting-1lot-partials-vi-final
- **rule_id / kind:** X3. Shortened. Scope: index. judgment = true.
- **Rule:** Long with 5 units. At entry, place sell limits:
  - 1 unit at or just above the nearest short-term high;
  - 1 unit at the next high or PD array;
  - the balance at the next opposing volume imbalance below the best-case high (the obvious buy-side pool).
  - Price does not need to trade above the best-case high. Mirror for shorts.
  - Source: 096, an index demo on 1m / 15s charts.
- **Sources:** 096_tjnir-o4rsQ ~00:05:34.
- **Quote:** "you can do the balance in here and not even required to trade above this high" (096).
- **Conflicts:** none.
- **Rulebook fix:** X3: add the 096 ladder (1 / 1 / balance at the VI short of the best-case high).
- **BUILD SPEC (targets_partials):**
  - Where: `ladder_preset="096"`. Rungs = [nearest pivot high + tick, next level, near edge of the first bearish VI (`vi_arrays`, built) below the last pool], fractions (0.2, 0.2, 0.6). The pool itself is dropped from the ladder.
  - If no VI exists, fall back to today's ladder.
  - Test: `test_ladder_096`. Pivot 4101, next level 4104, VI 4108-4109 under the 4112 pool: rungs 4101.25 / 4103.5 / 4107.5, and the 4112 pool is not a rung.

### 46. X3-layered-pool-ladder-runner
- **rule_id / kind:** X3. Shortened. Scope: general. judgment = true.
- **Rule:**
  - Scale out into stacked buy-side pools, nearest first. Take a partial beyond the first old high, take more at the nearest old weekly high, and leave a small runner for the external high.
  - Whether to take a partial or everything at the first old high depends on how big the move already is. ICT gives no threshold; ADR or planned R is our interpretation.
  - Source context: HTF swing (weekly levels, DXY). ICT also re-adds the closed partials on the next retrace into a bullish OB. That conflicts with E12 and belongs to the parked swing model.
- **Sources:** cc04_003_PIYh0CxoY9c ~00:30:19, ~00:11:24; cc04_011_Gnw54f9v6SA ~00:19:00.
- **Quote:** "take a little bit more profits out at an old weekly high here ... and then leave a little bit on" (cc04_003).
- **Conflicts:** the re-add vs E12 (see item 135).
- **Rulebook fix:** X3: add "include the nearest old weekly high as a rung; leave a small runner for the external high (cc04_003)".
- **BUILD SPEC (targets_partials):**
  - Where: `_targets`. With `weekly_hl_rung`, add the prior week's high / low (`htf.weeks`) as a pool-kind level.
  - In the ladder, when the move from the sweep extreme to the first pool already exceeds `collapse_adr_frac x adr5`, the first pool takes all units (fraction 1.0) [our interpretation]. Otherwise the last rung keeps `runner_frac` as the runner to the farthest pool.
  - Params: `weekly_hl_rung: bool = False`, `collapse_adr_frac: float = 0.0` (0 = off; test 1.0), `runner_frac: float = 0.0`.
  - Test: `test_weekly_hl_rung`.
    - The prior week's high appears as a pool rung;
    - with ADR5 = 40 and a 45-pt move to the first pool, all units close there;
    - with a 20-pt move, the runner remains.

### 47. X3-best-case-80-85-capture
- **rule_id / kind:** X3. Shortened. Scope: general. judgment = true.
- **Rule:**
  - Project the best-case final level for the trade, before or at entry. Aim to capture 80-85% of that run, using several partials spread over ~85-100% of it.
  - Exit into strength, while price is still moving the trade's way, and accept giving up the extreme. Leftover units may stop out.
- **Sources:** 013_V1thfpo-R9U ~00:30:23.
- **Quote:** "I'm going to try to get 80 85 percent of that price run" (013).
- **Conflicts:** cc02_003: half of the projected range is an acceptable runner outcome (item 48).
- **Rulebook fix:** X3: expand "aim to capture 80-85% (013)" with the scale-out zone across 85-100% of the run.
- **BUILD SPEC (targets_partials):**
  - Where: with section 3 X3h `capture_frac`, add a ladder mode `capture_zone`: best case B = the final level. The last `capture_n` rungs are replaced by equal rungs at `avg + f x (B - avg)` for f in linspace(0.85, 1.0, capture_n).
  - The report adds `capture` = realised average exit distance / (B - avg).
  - Params: `capture_zone: bool = False`, `capture_n: int = 3`.
  - Test: `test_capture_zone`. Avg 4000, B 4040: rungs 4034 / 4037 / 4040 and capture = 0.925 on a full fill.

### 48. X3-half-range-runner-success
- **rule_id / kind:** X3. Unlisted contradiction. Scope: general. judgment = true.
- **Rule:**
  - Projected range = from the entry area to the HTF target pool. The aim stays the lion's portion (X3: 80-85%).
  - A runner exit at 50% or more of the range counts as an acceptable outcome, not a failure.
  - Test a runner exit at 0.5 x range against the full HTF target. Label this a floor beside X3, not a conflict.
- **Sources:** cc02_003_pctqB3UD6dk ~00:07:06.
- **Quote:** "we don't need the absolute high and we don't need the absolute low" (cc02_003).
- **Conflicts:** X3 (013): 80-85% capture (a floor, not a contradiction).
- **Rulebook fix:** X3: add "50% of the projected range is an acceptable runner outcome (cc02_003)".
- **BUILD SPEC (targets_partials, report + study):**
  - Report: a per-trade flag `half_range_ok` = the runner's exit is >= 0.5 x (final - avg).
  - Study switch `runner_at_half`: the last rung becomes `avg + 0.5 x (final - avg)` when that lies beyond the previous rung.
  - Params: `runner_at_half: bool = False`.
  - Test: `test_runner_at_half`. Avg 4000, final 4060, previous rung 4020: the last rung is 4030. With a previous rung at 4035 the switch leaves the ladder unchanged.

### 49. X3-running-down-equity-trigger
- **rule_id / kind:** X3. Shortened. Scope: general. judgment = false.
- **Rule:** Long (short is the mirror).
  - Arm once price is approaching the target, or progress >= 0.75 of the way to the objective.
  - Then, each time a short-term (swing) high forms and a later bar trades above it, exit one tranche (limit just above the short-term high).
  - Rationale: algorithmic offset / distribution into buy stops above each short-term high.
  - Switch `rde_partials`, recommended for learning traders. Drop the three-drives clause (not in the sources).
- **Sources:** 063_qA9SCu4gGaU ~00:26:23; 064__YTK5uXBe4o ~01:03:42.
- **Quote:** "anytime you make a short-term high and you run above that short-term High you want to be taking partials" (063).
- **Conflicts:** none.
- **Rulebook fix:** X3: replace "a piece at each new high near each pool" with the arming threshold and trigger above.
- **BUILD SPEC (management_exits):** fills in section 3 X3a `run_down`.
  - Where: run_day loop. With `rde_partials`, arm when `(h - avg) / (final - avg) >= rde_arm`.
  - While armed, each confirmed `levels.pivots(n=1)` high formed after arming that a later bar exceeds triggers `partial_close(pos, tr, ts, pivot + tick, rde_frac, "rde")`, using a fraction of the units at arming time. The final ladder rung is unchanged.
  - Params: `rde_partials: bool = False`, `rde_arm: float = 0.75`, `rde_frac: float = 0.2`.
  - Test: `test_rde_partials`. Avg 4000, final 4040, armed at 4030:
    - pivot highs at 4032 and 4035, each exceeded later, close 20% each at 4032.25 / 4035.25;
    - a pivot formed before arming does not trigger.

### 50. X3-020-runner-peel-singles
- **rule_id / kind:** X3. Shortened. Scope: index. judgment = true.
- **Rule:** After the bulk partial (80% at the NWOG CE), switch to 1-contract exits in the upper half of the target gap:
  - 1 at market when a 1m candle trades 1 tick above an REH cluster;
  - 1 on the next 1m higher high;
  - 1 about halfway from current price to the gap's top;
  - 1 at the top;
  - roll the stop on the final unit and let it stop out.
- **Sources:** 020_MqOVbd1oqZk ~00:10:25, ~00:11:38, ~00:12:45, ~00:13:22.
- **Quote:** "I'll drop my contract selection down to one contracts and I'll start peeling them off" (020).
- **Conflicts:** none.
- **Rulebook fix:** X3: replace "80% at NWOG CE (020)" with the full runner protocol.
- **BUILD SPEC (management_exits):**
  - Where: with `peel_singles`, after the closed fraction reaches >= 0.75 and while price is above the target gap's CE (gap rungs carry `far`, item 1), each bar:
    - if `h >= reh + tick` for an unpeeled `rel_eq` level inside the gap, or `h >` the previous bar's high, `partial_close` one lot ("peel"), at most one per bar;
    - when the remaining units == 1, `raise_stop` to the latest 1m pivot low - tick and stop peeling.
  - The gap far edge stays a limit for any unit left.
  - Params: `peel_singles: bool = False`.
  - Test: `test_peel_singles`. 5 units left above the NWOG CE: an REH poke peels 1 and each of two higher highs peels 1. With 1 left, the stop moves under the pivot and no more peels happen.

### 51. X3-runner-htf-target
- **rule_id / kind:** X3. Missing rule. Scope: general. judgment = true.
- **Rule:**
  - Rank opposing pools by the timeframe of the swing that made them (execution TF < 15m < 60m < daily / weekly). T1 = the pool on the execution TF.
  - After the main partials, keep 1 unit (or a small remainder) as a runner and move its stop to a profitable level. Put its limit at the HTF level that framed the trade (an hourly pool, or the weekly opposing array for swing trades) plus a couple of handles (~2 ES pts) beyond it.
  - Optionally take part of the runner off at each intermediate higher-grade pool (e.g. the 15m pool).
  - Exempting HTF runner targets from the X2 "before PD arrays" buffer is our interpretation.
- **Sources:** 099_v_iJlBKYmUc ~00:37:57; cc02_003_pctqB3UD6dk ~00:03:26; cc02_002_Zsg8IeBtfu0 ~00:08:33; cc07_001_mQA8jCem9d0 ~00:08:54. (099 ~1:10:21 has none of the quoted text and is dropped.)
- **Quote:** "put your target your limit order at the higher time frame level plus a couple handles" (099).
- **Conflicts:** X2 exit before PD-array targets; the bot's T2 = the next pool.
- **Rulebook fix:** X3: add the runner protocol and the pool grading by timeframe. X2: note the HTF runner exception [our interpretation].
- **BUILD SPEC (targets_partials):**
  - Where: `_targets` tags each pool with its source TF (`tf` = 1 for exec pivots, 15 / 60 from `htf` pivots via `levels.tf_pivots`, D / W from pdh / weekly).
  - With `runner_htf`, the final rung = the nearest 60m-or-higher pool beyond the last exec-TF rung, at `v + runner_htf_pts`, with fraction `runner_frac` (item 46). After the previous rung fills, `raise_stop` to that rung - `stop_buffer`. Intermediate 15m pools become extra rungs taking half of the runner when `runner_htf_steps` is on.
  - Params: `runner_htf: bool = False`, `runner_htf_pts: float = 2.0`, `runner_htf_steps: bool = False`.
  - Test: `test_runner_htf`. 1m pool 4105, 15m pool 4110, 60m pool 4120: the final rung is 4122 with the runner fraction. The 15m pool takes half the runner only with steps on.

### 52. X3-027-pm-runner-macro
- **rule_id / kind:** X3 / T7. Missing rule. Scope: index. judgment = true.
- **Rule:** PM last-hour long after the first partial (buy-side taken):
  - (1) move the stop to +1 pt;
  - (2) rest a partial limit just above the next untaken high (about +0.25-0.5 pt);
  - (3) keep 1 runner for the ~15:45-15:50 last-hour macro;
  - (4) close it before 16:00 (T11).
  - Add 15:45-15:50 to T7 as a macro window; today it appears only in the tag list.
- **Sources:** 027_STEGBblm4dI ~00:40:28.
- **Quote:** "when it gets close to this 345 350 Type window the macro in the last hour can start really setting this thing higher" (027).
- **Conflicts:** T7 lists the MOC macro as 15:15-15:45.
- **Rulebook fix:** T7: add 15:45-15:50 as a macro window. X3: add the PM last-hour runner plan (027).
- **BUILD SPEC (management_exits + news_calendar_times):**
  - news_calendar_times: add `(945, 950)` to the macro windows table that feeds the tags.
  - management_exits: for PM trades with `pm_macro_runner`, at the first partial `raise_stop(pos, avg + 1.0 x es_pt)`. Set the next rung to the next untaken pool + `pool_beyond_pts`. The ladder's last unit is held (not closed by the final rung) until 15:50, then closed at the bar close; `flat` still applies.
  - Params: `pm_macro_runner: bool = False`.
  - Test: `test_pm_macro_runner`. A PM long with 3 units:
    - partial 1 moves the stop to +1;
    - the day-high rung closes 1;
    - the last unit is still open at 15:49 and closed at 15:50.

### 53. X3-runner-swing-low-must-hold
- **rule_id / kind:** X3. Missing condition. Scope: general. judgment = false.
- **Rule:** Long (short is the mirror), while running down equity:
  - after each new high takes out the previous high, record the swing low between the two highs. That swing low must hold.
  - A trade back below it is a reversal warning: take most or all of the rest off (ICT says only "problematic"; the action is ours).
  - Retrace depth is handled by X7 (FVG low, then wick CE; three arrays broken = close or reduce) and is not part of this rule.
- **Sources:** 027_STEGBblm4dI ~00:43:52 (027 ~38:18 is already X7).
- **Quote:** "this High took out that high we don't want to see any kind of reversal so this this low here needs to stay in place" (027).
- **Conflicts:** none.
- **Rulebook fix:** X3: add the between-highs swing-low hold condition (027 ~43:52).
- **BUILD SPEC (management_exits):**
  - Where: with `hh_low_hold`, after the first partial track 1m pivots. When a pivot high H2 > H1 (the previous pivot high after the fill) is exceeded, set `pos["hh_low"]` = the lowest low between H1 and H2.
  - A bar trading below `hh_low` triggers `partial_close(pos, tr, ts, min(o, hh_low), hh_low_frac, "hh_low")`. With frac 1.0 this closes everything.
  - Params: `hh_low_hold: bool = False`, `hh_low_frac: float = 1.0`.
  - Test: `test_hh_low_hold`. Pivot highs 4100 then 4104 with a low of 4098 between: a later bar to 4097.75 closes the rest. A bar to 4098.25 does not.

### 54. X3-marginal-lower-lows-warning
- **rule_id / kind:** X3. Missing condition. Scope: general. judgment = true.
- **Rule:** Short (long is the mirror).
  - Take a partial at each new session low (running down equity).
  - If new lows come only as marginal breaks, not as a large-range expansion into the target, expect a reversal or retrace upward. The partials already taken are the protection: don't add, and expect to sit through the bounce or exit the rest (discretionary).
  - A healthy break smashes the low and does not just poke below it and come back (046 ~1:01:52).
- **Sources:** 046_VLis0LcbUaQ ~01:00:39 (and ~1:01:52).
- **Quote:** "failing to make a big explosive capitulation that runs into a Target you're probably going to be watching a reversal" (046).
- **Conflicts:** none.
- **Rulebook fix:** X3: add the marginal-new-extremes warning (046) to running down equity.
- **BUILD SPEC (management_exits):**
  - Where: with `marginal_ext_warn`, count bars that make a new extreme beyond the prior session extreme by less than `marginal_pts` and close back inside it.
  - At `marginal_n` such bars before the final rung: set `pos["no_adds"] = True`. If `marginal_exit`, `partial_close` the rest ("marginal").
  - Params: `marginal_ext_warn: bool = False`, `marginal_pts: float = 1.0`, `marginal_n: int = 2` [our interpretation], `marginal_exit: bool = False`.
  - Test: `test_marginal_ext`. Two pokes 0.5 pt below the low that close back above it block adds, and with the exit switch they close the rest. A 3-pt smash through the low does not count.

### 55. X3-runner-stall-exits
- **rule_id / kind:** X3. Missing rule. Scope: index. judgment = true.
- **Rule:** Final AM runners stalled short of the target (lethargic 1m delivery):
  - (a) If price trades back into and rebalances the most recent opposite-close candle, take 1 unit off, so a trailed-stop exit doesn't hit the full remainder.
  - (b) If price runs just beyond a minor relative equal high / low and fails back inside it, close the rest.
  - Otherwise hold for the target or the trailed stop, and close the last unit before noon (X10).
- **Sources:** 003_ojy5ApHhEu4 ~01:17:52 (and ~1:11:37-1:13:30).
- **Quote:** "if it runs above that relative equal High to the left and fails then I'm done" (003).
- **Conflicts:** none.
- **Rulebook fix:** X3: add the two stall exits (003).
- **BUILD SPEC (management_exits):**
  - Where: with `stall_exits`, active after the closed fraction >= 0.75 and once `stall_bars` bars pass without a new extreme in the trade's direction [our interpretation of "lethargic"]:
    - (a) a bar trading back into the body of the most recent opposite-close candle triggers `partial_close(..., 1 lot, "stall_rebal")` once;
    - (b) a bar trading beyond a `rel_eq` level (eq_tol) from the last 30 bars against the trade, followed by a close back inside it, closes all ("stall_reh").
  - Params: `stall_exits: bool = False`, `stall_bars: int = 10`.
  - Test: `test_stall_exits`. A long with 2 units left and 10 bars without a new high:
    - a bar into the last down-close body closes 1 unit;
    - a poke above an REH followed by a close back below closes the last unit.

### 56. X3-gap-speed-bump-before-pool
- **rule_id / kind:** X3. Missing condition. Scope: general. judgment = true.
- **Rule:**
  - When a small unfilled FVG or gap lies between price and the target pool, flag it as a possible stall: price may trade through it, pull back into the range, and take the pool only later.
  - Bot option (our extension, not ICT's words): `gap_speed_bump_partial`, which takes a partial just past that gap instead of holding the full size to the pool. Default off; test it.
- **Sources:** 072_AKg_r0DIa3k ~00:28:41.
- **Quote:** "going through this Gap and rip higher and defer a run below that low" (072).
- **Conflicts:** none.
- **Rulebook fix:** X3 / A5: add "an unfilled small gap on the path to the pool can stall price (072); anticipation, one source".
- **BUILD SPEC (targets_partials):**
  - Where: target merge. With `gap_speed_bump_partial > 0`, take the first unfilled gap of height <= `bump_max_pts` lying between price and the first pool rung (either polarity). Insert a "bump" rung (item 39) at its far edge + tick with that fraction.
  - Params: `gap_speed_bump_partial: float = 0.0` (test 0.25), `bump_max_pts: float = 2.0`.
  - Test: `test_gap_bump_rung`. A 1-pt gap 4103-4104 before the 4110 pool inserts a 25% rung at 4104.25. A 3-pt gap does not.

### 57. X3-sd05-partial-under-5-handles (already listed)
- **rule_id / kind:** X3 / L12. Missing condition. Scope: general. judgment = false.
- **Rule:**
  - Anchor the fib from the impulse run's low to its high (long). First partial at high + 0.5(high - low) on any timeframe, even if under 5 handles (mandatory for new traders). -1 SD = measured move.
  - Journal how often -0.5 and -1 SD are reached vs not (sd05_hit, sd1_hit).
- **Sources:** 064__YTK5uXBe4o ~01:34:40.
- **Quote:** "I don't care if it's not even five handles, you have to learn to take something there" (064).
- **Conflicts:** L15 / X14 5-handle minimum; 090 fulcrum "trail" mode skips the -0.5 SD partial (item 66).
- **Rulebook fix:** X3 / L12: "-0.5 SD is a partial even under 5 handles, any timeframe (064); journal hit rates".
- **BUILD SPEC:** already listed. Section 3 targets_partials X3d "Add `sd_half_partial` (exempt from min_rr) and `halfway_partial`" is the same rule. Spec note for that build: the exemption must also cover `min_draw_pts` (owner #2), and the trade report gains `sd05_hit` / `sd1_hit` booleans (max favourable excursion vs the two levels), whether or not the switch is on.

### 58. X3-rejection-block-partial-rel (already listed)
- **rule_id / kind:** L11 / X3. Shortened. Scope: general. judgment = false.
- **Rule:** If the target is an REL pool formed by several long-wick candles, take a partial at the rejection block (the lowest close among the cluster's down-close candles); the remainder may target the wick lows. REH is the mirror.
- **Sources:** 059_ZfnY2SH3G24 ~00:09:38.
- **Quote:** "it's many times better to have a partial... at the rejection block if you have multiple wicks" (059).
- **Conflicts:** none.
- **Rulebook fix:** L11: replace "cover at the old low's lowest body" with "multi-wick REL: a PARTIAL at the rejection block, the remainder toward the wick lows (059)".
- **BUILD SPEC:** already listed. Section 3 targets_partials L11 "Add `rb_targets` ladder/replace at the body edge": its "ladder" mode is this rule. Spec note: gate "ladder" on the pool being a `rel_eq` cluster of >= 2 bars whose wick (beyond the body) is >= 50% of the bar range [our interpretation of "multiple wicks"], and give the body-edge rung 0.5 of the units at that level.

### 59. X3-r-multiple-partials
- **rule_id / kind:** X3. Missing rule. Scope: general. judgment = true.
- **Rule:** Optional `partial_trigger='r_multiple'`.
  - cc02_001: 50% at 1R (or 100%), stop to BE at 2R, 25-50% more at the R level where the nearer buy-stop pool is cleared (3R in the example), runner to just beyond the far pool (5R).
  - cc02_003: 50% at 3R even if the nearest pool lies beyond it. With a 2x wider stop, the first partial keeps the same price distance (30 pips = 1.5R), not 3R.
  - Any range-fraction formula is our interpretation.
- **Sources:** cc02_001_mjVHmE1gVMg ~00:24:10; cc02_003_pctqB3UD6dk ~00:03:00, ~00:16:10.
- **Quote:** "take half of that position off as we get three to one" (cc02_003).
- **Conflicts:** X3 puts partials at liquidity pools; cc02_001 (1R) vs cc02_003 (3R).
- **Rulebook fix:** X3: add the R-multiple ladders (cc02_001, cc02_003) as CC variants. Fix the M12 / X3 cc02_001 entries to include the second partial.
- **BUILD SPEC (targets_partials + management_exits):**
  - Where: with `partial_trigger="r_multiple"`, rungs come from `r_ladder` (a tuple of (R, frac)) as kind "fixed" at `avg + R x (avg - init_stop)`, merged with the pool rungs.
  - `be_at` (already used by M12.3 cc_1h_ob, ~2648) is set to `avg + r_be x risk`. A rung whose R lies beyond the nearest pool is kept (the cc02_003 "before the pool" case).
  - Presets: "cc02_001" = ((1, 0.5), (3, 0.25)) with r_be=2 and the runner to the far pool; "cc02_003" = ((3, 0.5),).
  - Params: `partial_trigger: str = ""`, `r_ladder: tuple = ()`, `r_be: float = 0.0`.
  - Test: `test_r_ladder`. Risk 4: "cc02_001" gives rungs at avg+4 / avg+12 and moves the stop to BE at avg+8. "cc02_003" puts a rung at avg+12 even with a pool at avg+16.

### 60. X3-partial-60m-eq
- **rule_id / kind:** X3. Missing rule. Scope: general. judgment = true.
- **Rule:** Identify the 60m dealing range containing price. When an open long rallies to its 50% level (a short drops to it), take a partial.
- **Sources:** cc08_007_5Z_3NbclMSY ~00:17:13.
- **Quote:** "take something off at 50 of the price range you're trading in on a 60 Minute basis" (cc08_007).
- **Conflicts:** none.
- **Rulebook fix:** X3: add "partial at the 60m dealing range's EQ (cc08_007)".
- **BUILD SPEC (targets_partials):**
  - Where: `_targets`. With `eq60_rung`, the 60m dealing range = the last confirmed 60m pivot high and low bracketing price (`levels.tf_pivots(m=60)`). If its EQ lies between entry and the final level, add it as kind "array" with fraction `eq60_frac` (taken from rung 1's share).
  - Params: `eq60_rung: bool = False`, `eq60_frac: float = 0.25`.
  - Test: `test_eq60_rung`. 60m pivots at 4080 / 4120 with entry 4090 and target 4115 insert a rung at 4099.5. With entry 4105 there is no rung (EQ is behind price).

### 61. X3-first-profit-premium-subrange
- **rule_id / kind:** X3. Missing rule. Scope: general. judgment = false.
- **Rule:** Long entered in a sub-range's discount half: after price trades above the sub-range EQ, place the first partial at the nearest 4h or 1h bearish PD array (OB, SIBI, rejection block, old high) in the premium half. Shorts mirror.
- **Sources:** cc07_005_y0lVKWLsZeM ~00:09:58.
- **Quote:** "any first profit would be best taken ... once it enters the premium range" (cc07_005).
- **Conflicts:** none.
- **Rulebook fix:** X3 / A21: add "first profit at a 4h/1h premium array inside the sub-range's premium half (cc07_005)".
- **BUILD SPEC (targets_partials):**
  - Where: `_targets`. With `subrange_first`, the sub-range = the daily consolidation quadrant containing the entry (`htf.table` daily range split into quarters). Rung 1 = the nearest 60m / 240m bearish array (`ctx.conf` rows with tf >= 60) whose near edge lies above the sub-range EQ and below the final level. Earlier rungs below the EQ are dropped.
  - Params: `subrange_first: bool = False`.
  - Test: `test_subrange_first`. A quadrant of 4000-4040 (EQ 4020) with a 60m SIBI at 4026 and an array at 4015: rung 1 = 4025.5 and 4015 is dropped.

### 62. X3-scaleout-skip-and-confluence
- **rule_id / kind:** X3. Missing condition. Scope: general. judgment = true.
- **Rule:**
  - Treat the scale-out list as a menu. Before entry, note which levels are likely to come into play for this trade, and use only those (not every condition will be present).
  - Prefer scale-out levels that coincide with an opposing PD array (premium for longs, discount for shorts).
  - A 1.27 or 1.618 extension or a 100% measured move coinciding with any scale-out level strengthens it as a partial.
  - Specific skip rules are not from the source.
- **Sources:** cc08_007_5Z_3NbclMSY ~00:19:41, ~00:27:39.
- **Quote:** "any projection on the FIB 127 168 and 100 percent symmetrical price swing ... really amplifies for profit taking" (cc08_007).
- **Conflicts:** L13: extensions only where they overlap an opposing PD array.
- **Rulebook fix:** X3: add "use only the scale-out levels that apply; prefer those that coincide with an opposing array, 1.27 / 1.618 or a 100% measured move (cc08_007)". L13: add the 100% measured move.
- **BUILD SPEC (targets_partials):**
  - Where: target merge. With `confluence_weight`, each rung gets a score: +1 if it lies within `eq_tol_pts` of an opposing array edge (`ctx.conf`), and +1 if it lies within `eq_tol_pts` of a 1.27 / 1.618 / 1.0 extension of the entry leg (sweep extreme -> leg high).
  - Fractions are redistributed in proportion to (1 + score). With `confluence_only`, rungs with score 0 are dropped except the final rung.
  - Params: `confluence_weight: bool = False`, `confluence_only: bool = False`.
  - Test: `test_confluence_weight`. Rungs A (score 2), B (score 0) and final (score 1) with base fractions (1/3, 1/3, 1/3) become (3/6, 1/6, 2/6). `confluence_only` drops B.

### 63. X3-scale-through-void
- **rule_id / kind:** X3. Missing condition. Scope: general. judgment = true.
- **Rule:**
  - If the draw is a liquidity void, or the void plus the old-high pools above it, spread exits through the area. Never hold the full position for the far edge or a complete fill.
  - The exact points (near edge, CE, just before the far edge) are our interpretation, to be tested.
  - A10 currently classes the CC one-sided-candle range as a displacement leg, not a void, so the rule needs to name which void definition it uses.
- **Sources:** cc01_006_SiVmoeyOWZE ~00:24:21.
- **Quote:** "when you buy things down in here a deep discount you have to scale some of it out" (cc01_006).
- **Conflicts:** none.
- **Rulebook fix:** X3: add "void draw: scale out through it, never hold all for the far edge (cc01_006)". A10: state the void definition used.
- **BUILD SPEC (targets_partials):**
  - Where: with section 3 A10 `void_targets` (it uses `levels.voids`), add `void_ladder`: a void used as the draw expands into three rungs, near edge / CE / far edge - `exit_before_pts`, each 1/3 of that level's share.
  - The void definition is `levels.voids` (the A10 void, not the CC one-sided range).
  - Params: `void_ladder: bool = False`.
  - Test: `test_void_ladder`. A void 4100-4120 as the final level gives rungs 4099.5 / 4109.5 / 4119.5.

### 64. X3-hs-fade-targets
- **rule_id / kind:** X3. Missing rule. Scope: general. judgment = false.
- **Rule:**
  - H&S fade, only with an HTF bias against the pattern: buy the sell stops below the neckline or equal lows.
  - The first partial is optional, at the right-shoulder high. The main objective = the buy stops just above the head.
  - Inverse H&S mirrors this when the HTF is bearish.
  - Ignoring the classical neckline measured move is our interpretation.
- **Sources:** cc03_008_w8lbrvZXUVY ~00:07:34, ~00:06:48.
- **Quote:** "you can actually take your first profit at the right shoulder on both these patterns" (cc03_008).
- **Conflicts:** none.
- **Rulebook fix:** add a pattern note to M12 (turtle soup) / X3: "H&S fade: T1 right shoulder (optional), T2 above the head (cc03_008)".
- **BUILD SPEC (setups_models + targets_partials):**
  - setups_models: in `levels.py`, `head_shoulders(pivots_h, pivots_l, tol)` returns (left shoulder, head, right shoulder, neckline) from the last three pivot highs when the middle one is highest and the outer two lie within `hs_tol_pts`. A turtle-soup long (built `levels.turtle_soup`) whose swept level is that pattern's neckline or equal lows, with `htf.table` bias long, is tagged `hs_fade`.
  - targets_partials: for `hs_fade` trades, rungs = [right shoulder high (kind "pool", frac 0.33), head high + `pool_beyond_pts` (final)].
  - Params: `hs_fade: bool = False`, `hs_tol_pts: float = 2.0`.
  - Test: `test_hs_fade`. Pivot highs 4100 / 4110 / 4101 over a neckline at 4090: a sweep below 4090 with a long bias tags `hs_fade`, with rungs 4101.25 and 4110.25.

### 65. X3-mm-model-target
- **rule_id / kind:** X3. Shortened. Scope: general. judgment = false.
- **Rule:**
  - MM sell model: when price drops back into the original consolidation, take 80% of the position off, including any pyramided second-stage units. Hold the remaining 20% to see whether price can go deeper, toward the next sell-side objective.
  - Buy model is the mirror (80% off on the return to the original consolidation from below).
- **Sources:** 104_iKsIbUblSWM ~00:53:35.
- **Quote:** "then we drop down into original consolidation 80% of the trade would come off" (104).
- **Conflicts:** none.
- **Rulebook fix:** M1 / X3: add "MM model: 80% off on the return into the original consolidation (104)".
- **BUILD SPEC (targets_partials):**
  - Where: section 3 Ep08.9 `mm_targets` (MM model trades). Add `mm_first`: rung 1 = the original consolidation's near boundary (the `mm_anchor` "ref" range edge), with fraction 0.8. The final rung is the next pool beyond (fraction 0.2).
  - Params: `mm_first: float = 0.0` (test 0.8).
  - Test: `test_mm_first`. An MM sell whose original consolidation spans 4100-4110 gives rung 1 at 4110 - `exit_before_pts` with 80%.

### 66. X3-fulcrum-exit-modes
- **rule_id / kind:** X3. Missing condition. Scope: general. judgment = true.
- **Rule:** Parameter `fulcrum_exit`:
  - 'ladder' (bot default): partial 1 just past the fulcrum low's sell stops, half of the remainder at -0.5 SD, the rest at -1 SD plus spread.
  - 'trail' (a firm bias / clear sell program, not a post-holiday or indecisive / stagnant session): no partials, a single exit at -1 SD, trailing the stop properly (X5) (090 ~1:32:54).
- **Sources:** 090_bhYcXBI3z9U ~01:32:54.
- **Quote:** "no partials below this low hold for the whole show down here and just use a trail stop loss" (090).
- **Conflicts:** X3: -0.5 SD is always a first partial (064).
- **Rulebook fix:** X3 / L12: add the two fulcrum exit modes and list the conflict with "-0.5 SD always".
- **BUILD SPEC (targets_partials):**
  - Where: trades from the fulcrum anchor (`sd_anchor="fulcrum"`, section 3 L12).
    - `fulcrum_exit="ladder"`: rungs = [fulcrum pool + beyond (frac 0.33), -0.5 SD (0.33), -1 SD - `exit_before_pts` (final)].
    - "trail": a single rung at -1 SD, the FVG trail active from the fill (`p.trail`-style, no t1 gate), and `sd_half_partial` ignored.
  - "trail" is allowed only when the `htf.table` bias is set and the day is not post-holiday (the `calendar` holiday-adjacent tag).
  - Params: `fulcrum_exit: str = ""`.
  - Test: `test_fulcrum_exit`. "ladder" gives three rungs. "trail" gives one rung, and the stop trails under the first new FVG before any partial.

### 67. X3-nfp-wick-ce-ladder-close-test
- **rule_id / kind:** X3. Shortened. Scope: index. judgment = true.
- **Rule:** NFP-day long, 10 units (an exception to N1). W = the CE of the wick that the 08:30 raid traded into (inside the 4H FVG).
  - (1) 1 unit limit at W; once filled, stop to BE + commissions.
  - (2) Judge each 5m close against W: after one close above, if the next 5m candle fails to close above W, sell 3 units at market to fund the trade.
  - (3) Take further units off at limits just beyond the next pools (here 3 units, then 1 above the relative-equal pool).
  - (4) Keep about 2 units as a runner with the stop at the 4H FVG high, and close it if price ramps hard into the final target.
- **Sources:** 105_A97shZGPE2I ~00:09:03, ~00:23:32.
- **Quote:** "if this doesn't close above it I will take three contracts off just to fund the position" (105).
- **Conflicts:** D13 ladders 80/20 and 50/25/25.
- **Rulebook fix:** X3: add the 105 ladder (1 / 3 funding / 3 / 1 + 2 runners) and the 5m close test.
- **BUILD SPEC (management_exits):**
  - Where: with `wick_ce_close_test`, when the first rung is a wick-CE rung (`wick_partial` / X3c, kind "wick"), its fraction = 0.1 and BE + pad follows.
  - After that fill, build 5m closes from the 1m bars (every 5th bar close): after one 5m close above W, the next 5m close at or below W triggers `partial_close(..., 0.3, "fund")` once.
  - The ladder continues with the pool rungs. The final 0.2 keeps the stop from item 12 (the 4h FVG high).
  - Params: `wick_ce_close_test: bool = False`.
  - Test: `test_wick_ce_close_test`. 10 units:
    - the W fill closes 1;
    - a 5m close above W and then one below closes 3;
    - two closes above in a row close nothing.

### 68. L16-adr5-60-80-closed
- **rule_id / kind:** L16. Shortened. Scope: general. judgment = false.
- **Rule:**
  - When price reaches the ADR5 projection, have 60-80% of the position closed in total (unconditionally, not only before 10:00), and hold the rest as a runner for later in the day.
  - Projecting the ADR5 from the day's low (longs) or high (shorts) is our interpretation.
- **Sources:** cc08_007_5Z_3NbclMSY ~00:17:25.
- **Quote:** "take or have had taken 60 to 80 percent off at five day average daily range projections" (cc08_007).
- **Conflicts:** L16: the 80% rule applies only when the ADR is reached before 10:00.
- **Rulebook fix:** L16: make the 60-80% rule unconditional (cc08_007). Keep "before 10:00" as cc08_001's earlier-time note.
- **BUILD SPEC (management_exits):** extends section 3 L16 `adr_early`.
  - Where: with `adr_closed_min > 0`, on the first bar where `h >= day_low + adr5` (long), if the closed fraction < `adr_closed_min`, `partial_close` up to that fraction ("adr_true_up"). This happens once, at any time of day.
  - Params: `adr_closed_min: float = 0.0` (test 0.7).
  - Test: `test_adr_closed_min`. ADR5 = 40, day low 4000, 30% closed so far: a bar to 4040 at 13:00 closes enough to reach 70% closed. Before reaching it, nothing happens.

### 69. X3-dxy-target-partial
- **rule_id / kind:** X3 / B19. Missing rule. Scope: needs_unavailable_data. judgment = true.
- **Rule:**
  - While short ES / NQ (long is the mirror), track DXY's own HTF target ladder. In 035 that is the daily rejection block (trade to and through the old swing-high close), then the CE of the wick.
  - When DXY trades into its next ladder level, take a partial on the index (ICT gives no size; the size is our parameter). DXY may consolidate there, so hold the rest for the index's own target.
  - Needs intraday DXY data.
- **Sources:** 035_kFIOp8Tprdc ~00:24:19.
- **Quote:** "that's probably a good time to be doing what taking a partial profit" (035).
- **Conflicts:** none.
- **Rulebook fix:** X3 / B19: add the DXY-target partial trigger, noted as needing intraday DXY.
- **BUILD SPEC:** none (needs intraday DXY).

### 70. X3-cbdr-projection-units
- **rule_id / kind:** X3. Missing rule. Scope: fx_only. judgment = true.
- **Rule:** [fx-only]
  - On CBDR projection days (CBDR 20-30 pips, < 40, with directional bias), the target is the first SD unit that overlaps an opposing PD array within the expected time window (the session where the range caps, e.g. London close). PD arrays decide the turn, not the projection itself.
  - Take the first partial at 1 SD, and another when price closes into the opposing FVG / void. Leave a small remainder to see if there is room for more.
  - The rule for stepping to the next unit and the exact time caps are our interpretation.
- **Sources:** cc08_004_JKzEhfwV1dY ~00:23:17, ~00:22:31.
- **Quote:** "one standard deviation that one alone would have been enough" (cc08_004).
- **Conflicts:** none.
- **Rulebook fix:** L13 (fx-only CBDR note): add the unit-selection and partial sequence.
- **BUILD SPEC:** none (fx_only; CBDR SDs are out of scope per M17).

### 71. X3-fixed-distance-first-partial
- **rule_id / kind:** X3. Missing rule. Scope: fx_only. judgment = true.
- **Rule:** [fx-only]
  - On every day trade, bank "something" (size unspecified; 25-50% is our choice) at +20-30 pips (+20 in the scalping lesson). After that, take the next partial only after a further 2 SD of the Asian range or CBDR.
  - Index translations (e.g. 5 ES pts, 2x the overnight-range width) are our interpretation.
- **Sources:** cc08_007_5Z_3NbclMSY ~00:16:32; cc09_003_km0haQkTalc ~00:01:22.
- **Quote:** "you're always going to try to take something off and gain at 20 to 30 Pips" (cc08_007).
- **Conflicts:** none.
- **Rulebook fix:** X3: add the FX fixed-distance first partial under the FX-only list.
- **BUILD SPEC:** none (fx_only). The index analogue is already testable as item 41's `fixed_partials=(5.25,)`.

### 72. X3-four-levels-75-80-off
- **rule_id / kind:** X3. Missing rule. Scope: fx_only. judgment = true.
- **Rule:** [fx-only]
  - Count levels from entry (floor pivots / M-levels, or for CBDR shorts the CBDR low as level 1 of 4). Once four levels have filled, have about 75-80% of the position closed.
  - Leave 25-30% only if enough session time remains for a larger-range day (e.g. a London trade carried into NY).
  - Exit timing for the remainder is not specified in the source.
- **Sources:** cc09_002_zanmou0ic5U ~00:07:02.
- **Quote:** "about 75 to 80% of your trade, should have been taken off" (cc09_002).
- **Conflicts:** none.
- **Rulebook fix:** L13 (fx-only floor pivots): add the four-levels rule.
- **BUILD SPEC:** none (fx_only).

---

## D. Model-specific exits and targets (M3-M16, L4, L13, A12, A15, X1)

### 73. M3-sb-simple-vs-day-trade
- **rule_id / kind:** M3 / E12. Missing rule. Scope: index. judgment = false.
- **Rule:**
  - mode 'sb_simple' (unmanaged): one entry (split limits OK), stop above the CE of the higher of two FVGs, fixed limit exits at the first discount PD array (the ORG / imbalance below the NWOG low), no adds, no runner.
  - mode 'day_trade' (managed): the same entry, plus a pyramid limit at the next FVG / SIBI in the displacement on its retrace (E12 decreasing sizes). Keep the position through lunch and target the deeper objective (here the NWOG CE / lower target). Flat by 16:00 per T11 (069 ~14:58-17:46).
- **Sources:** 069_Sf_uYZBWTrA ~00:15:57.
- **Quote:** "if it would have been a day traded I could have been managing I would have taken additional entries" (069).
- **Conflicts:** none.
- **Rulebook fix:** M3: add the unmanaged vs managed SB modes (069).
- **BUILD SPEC (silver_bullet):**
  - Where: sb_model.py. `sb_mgmt` already has "fixed" / "ladder" (Params ~214). Add `sb_mgmt="day_trade"`:
    - no `am_exit` for SB-AM (overrides `am_exit_extras` for that trade only);
    - adds armed through the shared `_arm_add` on the next same-direction FVG in the displacement leg (E12 fractions);
    - final target = the deeper `htf.gaps_for_day` NWOG CE when it lies beyond the first discount array, else the first array.
  - "fixed" stays the unmanaged mode with the `ce2` stop (built).
  - Params: `sb_mgmt` value "day_trade".
  - Test: `test_sb_day_trade`. An AM SB short:
    - with "fixed", it closes all at the first discount array and nothing remains at 12:00;
    - with "day_trade", an add arms on the next SIBI, the trade is still open at 12:30, and it closes at the NWOG CE.

### 74. M11-immediate-rebalance-management
- **rule_id / kind:** M11. Shortened. Scope: index. judgment = false.
- **Rule:** Immediate-rebalance short (long mirror), adding to M11:
  - Skip on Fridays and when a high-impact release (e.g. 10:00) is still pending that session (100 ~1:36:10).
  - Take the first partial just beyond the nearest sell-side lows and hold the rest only if price accelerates.
  - The time stop stays per X9 (expansion on the rebalance candle or the next, else exit; 092 ~1:41:37).
  - The range-EQ exit stays per M11 / X8 (100 ~1:37:18).
- **Sources:** 092_9MLRE-n6St8 ~01:41:37; 100_GJeEU2oIh24 ~01:36:14.
- **Quote:** "looking for a run below here first partial and then I look to see if it could accelerate" (100).
- **Conflicts:** none.
- **Rulebook fix:** M11: add the Friday / pending-news filters and the first-partial-at-nearest-lows rule.
- **BUILD SPEC (setups_models + targets_partials):**
  - setups_models: in the immediate-rebalance branch (`levels.immediate_rebalances`, sb_model.py `immediate_rebalance` ~202), reject when `day.weekday() == 4` or a 10:00 release is still ahead (`events(day) & NEWS_1000` and `t < 600`). Switch `ir_filters`.
  - targets_partials: IR trades get rungs = [nearest pivot low - `pool_beyond_pts` (frac 0.5), existing target]. The remainder is held only if the bar that fills rung 1 has range >= 1.5x the median 20-bar range; otherwise it closes at that bar's close (`ir_accel_hold`).
  - Params: `ir_filters: bool = False`, `ir_accel_hold: bool = False`.
  - Test: `test_ir_mgmt`.
    - An IR short on a Friday is rejected; on Tuesday at 09:45 with a 10:00 release it is rejected.
    - At 10:15 it is taken, rung 1 closes 50%, and a small rung-1 bar closes the rest.

### 75. M14-tgif-management
- **rule_id / kind:** M14. Unlisted contradiction. Scope: index. judgment = true.
- **Rule:** Short TGIF (bullish week). R = weekHigh - weekLow, Lx = H - x*R.
  - Partial at L20, partial at L22.5 (upper gradient), most of the position at L25. Then roll the stop to the latest swing high and run the remainder to L27.5, then L30 (the deep "low objective"; 089 printed within ~1 NQ handle of it).
  - A first L20 touch does not end the setup: it stays valid until 16:00, and further entries in the PM SB window (14:00-15:00) on retraces into bearish arrays are allowed while the week high holds.
  - In the last hour, if a swing low forms inside the 20-30% band, hold through retraces that stay inside the band (e.g. runs of short-term REH) and cover everything with a limit just below that low (X2 buffer).
  - Flat by 16:00. A bearish week is the mirror.
  - ["Most" sizing and any AM-window re-entry are our choices.]
- **Sources:** 066_wTR-vhOdMgo ~00:48:02, ~00:43:49, ~00:45:47; 089_h0yOpwSilnE ~00:05:34.
- **Quotes:** "if it gets to 50 take most of your trade off then roll your stop to the most recent swing high" (066); "time ends with this shaded area here at the close" (066).
- **Conflicts:** M14 "most off at 25%" vs 089's 30% as the final objective (weak: 30% is the runner's goal).
- **Rulebook fix:** M14: add the stop roll and runner to 27.5 / 30%, validity to 16:00 with PM SB re-entries, the last-hour full cover below a band swing low, and 089 as the 30% evidence.
- **BUILD SPEC (targets_partials + management_exits):** extends section 3 M14.2 `tgif_zone` / M14.4 `tgif_exits`.
  - targets_partials: `tgif_exits="066"` rungs = L20 (0.15), L22.5 (0.15), L25 (0.5), L27.5 (0.1), L30 (0.1).
  - management_exits:
    - after the L25 fill, `raise_stop(pos, last_pivot_high + tick, "tgif_roll")`;
    - TGIF `done` is not set by a first L20 touch, and new TGIF entries are allowed in `sb_windows[1]` while the week high holds;
    - from 15:00, once a 1m pivot low forms inside [L30, L20], a resting cover at pivot low - `exit_before_pts` replaces the remaining rungs.
  - Params: `tgif_exits` value "066", `tgif_reentry_pm: bool = False`, `tgif_last_hour_cover: bool = False`.
  - Test: `test_tgif_066`. A week H 4600 / L 4500 gives rungs 4580 / 4577.5 / 4575 / 4572.5 / 4570.
    - After L25 the stop sits above the last pivot high;
    - a 15:20 pivot low at 4574 sets the cover at 4574.5 for all units left.

### 76. M14-tgif-draw-hit-first-sd-depth
- **rule_id / kind:** M14 / L13. Missing rule. Scope: index. judgment = true.
- **Rule:**
  - Consider TGIF only after price has traded to the named weekly draw (the liquidity, here the June 16 high, or the projected level) that Friday. Reaching a generic premium array is not enough.
  - When a bearish breaker then forms after that high (A = high, B = low), project B - k(A - B) for k = 1, 2. The retrace / exit level is the SD that lands inside an earlier bullish breaker or FVG (-2 SD in 070 ~53:04-53:43).
- **Sources:** 070_1HtRfFYiwO0 ~00:50:36.
- **Quote:** "you have to see it get to the liquidity and fulfill its weekly range before it wants to pull back in" (070).
- **Conflicts:** none.
- **Rulebook fix:** M14: replace "reached an HTF premium array" with "traded to the named weekly draw that Friday". L13: add the breaker-leg SD exit inside an earlier breaker / FVG.
- **BUILD SPEC (setups_models + targets_partials):**
  - setups_models: with `tgif_need_draw`, the TGIF gate (M14.2) also requires that Friday's high >= the weekly draw from `htf.table` (bias_htf weekly draw), touched before the entry bar.
  - targets_partials: for TGIF trades with `tgif_sd_exit`, take the first bearish breaker formed after the Friday high (`levels.breakers`). For k in (1, 2), the level B - k(A - B) becomes a rung if it lies inside an earlier bullish breaker or gap (`ctx.conf`); the first such level is the final rung.
  - Params: `tgif_need_draw: bool = False`, `tgif_sd_exit: bool = False`.
  - Test: `test_tgif_draw_sd`.
    - A Friday that never reaches the weekly draw gives no TGIF setup.
    - With the draw hit, a breaker A 4500 / B 4492 and an earlier bullish FVG 4475-4478: -2 SD = 4476 lies inside the FVG and becomes the final rung.

### 77. M15-ma-deuce-ladder
- **rule_id / kind:** M15. Shortened. Scope: index. judgment = true.
- **Rule:** Ma Deuce exits:
  - partial 1 at the daily BISI CE;
  - partial 2 at its lower 25% quadrant;
  - then the final exit at the nearby 1h single-candle BISI low (~10 handles away).
  - The daily BISI low is the best case only and is not required. Split sizes follow X3.
- **Sources:** 091_1PkTGkOjoGo ~00:23:31.
- **Quote:** "first partial would be here at consequent encroachment and you let it run some more to get down to the lower quadrant" (091).
- **Conflicts:** none.
- **Rulebook fix:** M15: state that the three targets are successive partials and that the daily BISI low is best case only.
- **BUILD SPEC (setups_models):**
  - Where: the Ma Deuce branch (setups_models package, built 2026-10-18). Its target list = [daily BISI CE, BISI low + 0.25 x height, the nearest 1h BISI low (`htf` 60m gap rows) beyond that], with `_split` fractions. The daily BISI low is dropped unless no 1h array exists.
  - Params: `ma_deuce_ladder: bool = False`.
  - Test: `test_ma_deuce_ladder`. A daily BISI 4400-4440 and a 1h BISI low at 4421 give rungs 4420 / 4410 / 4421 sorted in side space, and the final rung is not 4400.

### 78. M16-sick-sister-exit-ladder
- **rule_id / kind:** M16. Shortened. Scope: index. judgment = true.
- **Rule:** Sick-sister long. Levels:
  - T1 = just above the nearer unrun high;
  - T2 = the midpoint between the nearer and farther highs;
  - T3 = the farther high.
  - Exit the bulk or all just above T1, because once that buy side is taken the laggard may rejoin the sisters' weakness. Any remainder exits by T2. T3 is the theoretical draw and not required (053 ~5:52-6:31).
  - Shorts are the mirror. [Buffer per X2; the split is ours.]
- **Sources:** 053_VSSwM6rDIg0 ~00:06:21.
- **Quote:** "once it takes out the buy side it could want to rejoin what has been seen in the es and the Dow" (053).
- **Conflicts:** none.
- **Rulebook fix:** M16: add the midway level and the reason for exiting at T1.
- **BUILD SPEC (setups_models):**
  - Where: the M16 sick-sister branch (`time_exit` M16.1 exists, ~2671). Rungs = [nearer high + `pool_beyond_pts` (frac `ss_t1_frac`), midpoint (rest)]. The farther high is not a rung.
  - Params: `ss_t1_frac: float = 0.8`.
  - Test: `test_sick_sister_ladder`. Highs 4100 / 4110 give rungs 4100.25 (80%) and 4105 (20%), with no rung at 4110.

### 79. L13-multi-sd-breaker-confluence
- **rule_id / kind:** L13 / L12. Missing rule. Scope: index. judgment = true.
- **Rule:**
  - For each breaker A-B leg (1m and 5m) in the trade direction, compute B + k(B - A) for k in {1, 1.5, ..., 7.5}. Keep the levels that fall inside the HTF draw range (e.g. the old high up to the weekly VI).
  - A level that lands on the HTF pool confirms that pool will be reached.
  - Where levels from 2+ legs fall within about 1 pt, use that cluster as the exit, with a 0.25-1.5 pt buffer (X2) (070 ~1:01:47-1:05:22).
  - This is an exception to L12's "first SD beyond the pool only" for breaker legs.
- **Sources:** 070_1HtRfFYiwO0 ~01:04:18.
- **Quote:** "use all the breakers for any standard deviation idea ... you want to see a Confluence of levels" (070).
- **Conflicts:** L12 keeps only the first SD level beyond the pool.
- **Rulebook fix:** L13: add multi-k breaker-leg projections and the cluster exit (070), as an exception to L12.
- **BUILD SPEC (targets_partials):** extends section 3 L13 `proj_breaker`.
  - Where: `_targets`. With `proj_breaker_multi`, collect `levels.breakers` legs on 1m and 5m since the session start in the trade direction. Generate the k-levels, keeping those between the first pool and the HTF draw's far level.
  - Cluster with tolerance `sd_cluster_ticks` (section 3 L12). Clusters with >= 2 legs become kind "proj" rungs (item 3), and a cluster within 1 pt of a pool tags that pool `confirmed=True` (report only).
  - Params: `proj_breaker_multi: bool = False`, `proj_k_max: float = 7.5`.
  - Test: `test_proj_breaker_multi`. Two legs whose 6.5 and 4.0 projections land 0.75 pt apart produce one "proj" rung. A single-leg level produces none.

### 80. L4-lrlr-ceiling
- **rule_id / kind:** L4. Missing rule. Scope: general. judgment = false.
- **Rule:**
  - Bullish LRLR zone: from the break of the short-term high up to U = the broken old low. Inside it, each new buy signal targets the next short-term high's buy stops.
  - At or above U the run is high-resistance: do not count targets above U as low-resistance, and take the final exit at or just below U (our interpretation).
  - Bearish mirror: the lower bound is the level where the short-term high was broken.
  - Drop the news exception unless it is sourced elsewhere.
- **Sources:** cc01_007_22XkhpJR5eA ~00:13:38.
- **Quote:** "anything higher than this price point here becomes a high resistance liquidity run" (cc01_007).
- **Conflicts:** none.
- **Rulebook fix:** L4: give the LRLR zone its ceiling (the broken old low) and say that targets above it are HRLR.
- **BUILD SPEC (targets_partials):** extends section 3 L4 `lrlr_max`.
  - Where: `_targets`. With `lrlr_ceiling`, U = the most recent old low that price broke before the reversal (the lowest `levels.swing_tiers` low that a bar later closed below, prior to the sweep). In side space, levels beyond U are tagged "hrlr".
  - The final rung is capped at U - `exit_before_pts` unless `lrlr_allow_beyond` is on.
  - Params: `lrlr_ceiling: bool = False`, `lrlr_allow_beyond: bool = False`.
  - Test: `test_lrlr_ceiling`. A broken old low at 4050 with targets 4040 / 4060: the ladder ends at 4049.5, and 4060 is tagged "hrlr" and dropped.

### 81. A12-opposing-ob-time-of-day
- **rule_id / kind:** A12. Missing condition. Scope: general. judgment = true.
- **Rule:** Long reaching a bearish OB.
  - Inside a profit-taking time of day, take profit at the OB. After that, a re-entry or continuation through the old high comes only after the next sessions retrace.
  - Outside profit-taking time, do not treat the bearish OB as a target. Expect a pause or consolidation there and hold for the run above the old high (external range liquidity).
  - Which index windows count as profit-taking time is our interpretation (for example 10:00-11:00, 11:30-12:00, 15:00-16:00); ICT's example is FX.
- **Sources:** cc04_003_PIYh0CxoY9c ~00:34:17, ~00:34:59.
- **Quote:** "if you hit a bearish order block during a time of day when profit taking should take place ... you may not get that run above an old high" (cc04_003).
- **Conflicts:** none.
- **Rulebook fix:** A12: make opposing OBs targets only inside profit-taking times; outside them they are pauses (cc04_003).
- **BUILD SPEC (targets_partials):**
  - Where: when the ladder loop reaches a rung whose kind is "ob" (opposing OB from A22 `matrix_targets` / `_targets` OB rows) and `ob_target_tod` is on: if the bar time is outside `ob_pt_windows`, skip the rung (`pos["k"] += 1` without a fill) and keep its fraction for the next rung.
  - Params: `ob_target_tod: bool = False`, `ob_pt_windows: tuple = ((600, 660), (690, 720), (900, 960))`.
  - Test: `test_ob_target_tod`. A bearish OB rung touched at 10:20 fills. The same touch at 13:40 is skipped and its fraction moves to the next pool rung.

### 82. A15-mitigation-block-targets
- **rule_id / kind:** A15. Missing rule. Scope: general. judgment = false.
- **Rule:** Mitigation-block short targets:
  - first, the sell-side liquidity below the short-term low formed after the break (exit just beyond it, per X2);
  - then the nearest HTF support (old high or low, bullish OB, or the liquidity-void MT as in the example).
  - At HTF support, close the whole trade and stand aside until a new setup develops. Mirror for longs.
- **Sources:** cc04_004_FOUzW0QmsfI ~00:08:13.
- **Quote:** "run the liquidity Out Below this short term low here and potentially as low as our higher time frame support level" (cc04_004).
- **Conflicts:** none.
- **Rulebook fix:** A15: add the two targets and the collapse at HTF support (cc04_004).
- **BUILD SPEC (setups_models + targets_partials):**
  - Where: mitigation-block entries (`levels.mitigation_blocks`, setups_models). Rungs = [the post-break low C - `pool_beyond_pts` (kind "pool"), the nearest HTF support below (`htf.table` arrays, pdl, void MT) as the final rung].
  - After the final fill, `done[session] = True` (`mb_done_at_htf`).
  - Params: `mb_targets: bool = False`, `mb_done_at_htf: bool = False`.
  - Test: `test_mb_targets`. A mitigation short with C = 4080 and a daily bullish OB top at 4070 gives rungs 4079.75 and 4070.5, and the session is done after the 4070.5 fill.

### 83. A15-mitigation-block-body-hold
- **rule_id / kind:** A15. Missing condition. Scope: general. judgment = true.
- **Rule:** Bearish mitigation block:
  - Sell the retest into the last down-close candle (the whole candle is the zone).
  - A valid retest leaves the candle body unviolated; wicks or small overshoots into it are fine. The stop goes above the mitigation candle's high.
  - Exiting early on a body close beyond the body is our interpretation, not stated. Bullish mirror.
- **Sources:** cc04_004_FOUzW0QmsfI ~00:14:29.
- **Quote:** "notice the body of the candle is not violated this is Hallmark characteristics" (cc04_004).
- **Conflicts:** none.
- **Rulebook fix:** A15: add "valid retest: the body is not violated; the stop goes above the candle high (cc04_004)".
- **BUILD SPEC (setups_models + management_exits):**
  - setups_models: mitigation-block entries use a stop at the candle high + `stop_buffer`.
  - management_exits: with `mb_body_exit` [our interpretation], a body close above the mitigation candle's body top before T1 exits at the close ("mb_body"), via the `lvx` exit table (~2663) with `pre_t1=True`.
  - Params: `mb_body_exit: bool = False`.
  - Test: `test_mb_body_hold`. Mitigation candle body 4100-4104, high 4106:
    - a wick to 4105 with a close at 4103 holds;
    - a close at 4104.5 exits with the switch on and holds with it off.

### 84. X1-consol-sweep-target-eq
- **rule_id / kind:** new. Missing rule. Scope: general. judgment = false.
- **Rule:**
  - Consolidation outer-edge sweep: price trades below the range's old low RL while daily / 4h order flow is bullish, or above RH while bearish.
  - Target = range EQ = (RH + RL) / 2, with a full or bulk exit there. Do not anticipate or hold for the opposite extreme; it is at most an optional runner [our interpretation]. The leg to EQ is the trade even if price turns at EQ.
  - Requires HTF (daily / 4h) order flow in the trade's direction.
  - Drop the "inside-range fade targets the opposite extreme" clause, which this source does not support.
- **Sources:** cc09_004_g7jchu4g31c ~00:12:29.
- **Quote:** "we do not anticipate or always hold for the opposite end of the consolidation" (cc09_004).
- **Conflicts:** X1 (target = next opposing liquidity) would put this trade's target at the opposite range extreme. L4 targets the pool below the leg's EQ.
- **Rulebook fix:** X1: add the exception "an outer-edge sweep of a consolidation targets the range EQ (cc09_004)".
- **BUILD SPEC (targets_partials):**
  - Where: target merge. With `consol_eq_target`, when the swept pool is the low (high) of a consolidation range detected before the sweep, the final rung = EQ - `exit_before_pts`, and farther rungs are dropped (or kept as a `runner_frac` runner).
  - Consolidation range = the bar range of the last `consol_bars` bars before the sweep, under `consol_adr_frac x adr5` [our interpretation].
  - Requires `htf.table` bias in the trade direction.
  - Params: `consol_eq_target: bool = False`, `consol_bars: int = 60`, `consol_adr_frac: float = 0.35`.
  - Test: `test_consol_eq_target`. A range 4100-4110 over 60 bars, a sweep to 4099 with a bullish bias: the final rung is 4104.5 and 4110 is not a rung.

### 85. new-vb-post-fill-management
- **rule_id / kind:** new. Missing rule. Scope: index. judgment = true.
- **Rule:** Bullish vacuum block, after the gap is 100% filled.
  - Buy at the fill (the close of the last up candle before the gap); the stop goes below the lowest low.
  - On the rally, price must cut cleanly through the up candle at the gap without hesitating. If it stalls there, treat that candle as a bearish OB and take profit.
  - After the rally, price should not trade back below the pre-gap candle's close. If it does, take a partial. If it keeps correcting lower, close the whole trade.
  - Bearish mirror.
- **Sources:** cc04_009_shPGUz9pU-A ~00:11:48, ~00:14:09.
- **Quote:** "we want to see that low be cleanly broke through we don't want to see it hesitate here" (cc04_009).
- **Conflicts:** none.
- **Rulebook fix:** L8: add the vacuum-block trade and its management (cc04_009). The source is about vacuum blocks, not volume imbalances.
- **BUILD SPEC (setups_models + management_exits):**
  - setups_models: a `vb_trade` branch. `levels.vacuum_block` (built) gives the gap. Once a bar fully fills it, arm a limit at the pre-gap up candle's close, with the stop below the fill's lowest low.
  - management_exits:
    - `pos["vb_candle"]` = the up candle at the gap. If 2+ consecutive bars fail to close above its high once price reaches it, close 50% ("vb_stall").
    - After price has traded above it, a close below the pre-gap close triggers `partial_close` 50% ("vb_back"). A second close lower than that closes all.
  - Params: `vb_trade: bool = False`.
  - Test: `test_vb_trade`.
    - A gap 4100-4105 fully filled to 4099 arms a buy at the pre-gap close 4100;
    - two closes under the gap candle's high close 50%;
    - a later close below 4100 closes 50% of the rest, and a lower close closes all.

### 86. new-counter-bias-scalp-exit
- **rule_id / kind:** new / B3. Missing rule. Scope: index. judgment = true.
- **Rule:**
  - Counter-bias scalp (e.g. a short on a day with a bullish daily bias): target only the nearest opposing pool (the low the FVG points to).
  - Be completely flat once that pool is run or price trades below the midnight open (above it on a bearish day), whichever comes first.
  - Never hold a counter-bias position below or above the midnight open expecting continuation, because that is where smart money accumulates with the bias (013 ~14:18-15:26).
  - [Our design: opt-in only, no runners.]
- **Sources:** 013_V1thfpo-R9U ~00:15:07.
- **Quote:** "you don't want to hold on to your shorts" (013).
- **Conflicts:** B3 allows one direction only.
- **Rulebook fix:** B3: add the counter-bias scalp exit rule (013) as an opt-in exception.
- **BUILD SPEC (setups_models + management_exits):**
  - setups_models: with `counter_scalp`, `_scan` may arm a setup against `htf.table` bias. It is tagged `counter=True`, its ladder is cut to the first pool rung (fraction 1.0), and it uses half risk.
  - management_exits: for `counter` positions, a bar trading through the midnight open (`levels.opens` "midnight") in the trade direction exits at `min(o, open)` ("counter_mo").
  - Params: `counter_scalp: bool = False`.
  - Test: `test_counter_scalp`. On a bullish-bias day, a short with the midnight open at 4036.75 and the nearest low at 4034 exits at 4036.75 when that trades first. If 4034 trades first, it exits there in full.

### 87. M13-ote-leave-discount-fast
- **rule_id / kind:** M13. Missing rule. Scope: general. judgment = true.
- **Rule:**
  - After an OTE fill, price should leave the 62-79% band quickly (our proxy: within N leg-TF bars, N tested; otherwise cut half).
  - After the bounce, a pullback that holds at or above the leg EQ is consolidation before expansion toward the buy stops above the short-term highs. It is not an exit.
  - The stop stays beyond the leg's swing low per M13. The "79% close" stop is unsourced, so drop it or label it our interpretation.
- **Sources:** cc01_004_qC0LogyIk2I ~00:50:18, ~00:16:28, ~00:48:48.
- **Quote:** "consolidation which is always going to be at equilibrium to expansion" (cc01_004).
- **Conflicts:** none.
- **Rulebook fix:** M13: add "leave the OTE band quickly; a later return that holds at the leg EQ is consolidation, not an exit (cc01_004)".
- **BUILD SPEC (management_exits):**
  - Where: OTE entries (`levels.ote_band`, setups_models). With `ote_leave_bars > 0`, if after that many bars no close lies above the band's 62% line, `partial_close` 50% ("ote_slow").
  - EQ pullbacks need no code (no exit exists). The test locks that in.
  - Params: `ote_leave_bars: int = 0` (test 3).
  - Test: `test_ote_leave`.
    - An OTE fill followed by 3 bars still inside the band cuts half;
    - a fill followed by a close above the 62% line on bar 2, then a pullback to the leg EQ, exits nothing.

### 88. M4-immediate-response-swept-extreme
- **rule_id / kind:** M4. Missing condition. Scope: general. judgment = true.
- **Rule:** Breaker / failure swing (CC, daily position context):
  - After price runs below old low L1 into the HTF support level, it should reject immediately and not linger below L1. On the daily, the run below and the rejection should happen within that day's candle (it wicks away).
  - If price trades below L1 and hangs around, the setup is suspect.
  - Entry is on the return to the breaking point after the bullish MSS.
  - A bar count on lower timeframes is our interpretation. Bearish mirror.
- **Sources:** cc05_005_xRjKtUEKkSE ~00:14:40.
- **Quote:** "you want to see an immediate response away from that level" (cc05_005).
- **Conflicts:** none.
- **Rulebook fix:** M4: add the immediate-rejection condition to the CC breaker / failure swing (cc05_005).
- **BUILD SPEC (setups_models):**
  - Where: the `_scan` sweep block. With `sweep_max_linger > 0`, a sweep whose bars close beyond the swept level (below L1 for a long) more than `sweep_max_linger` times before the MSS is not valid (`reject="linger"`).
  - On daily study runs (`levels.failure_swing`), require the sweep day to close back above L1.
  - Params: `sweep_max_linger: int = 0` (test 2).
  - Test: `test_sweep_linger`. Three closes below L1 before the MSS reject the setup. One close below, then a reclaim, keeps it.

### 89. M12-turtle-soup-max-sweep
- **rule_id / kind:** M12. Missing rule. Scope: fx_only. judgment = true.
- **Rule:** Turtle-soup long at old low L (15m / 30m FX).
  - Expect a 10-20 pip sweep, buy 10-20 pips under L, stop 30-50 pips.
  - A run of more than about 25 pips below L means it is probably a real decline rather than a stop run: cancel an unfilled order. Exiting a filled one before the stop is our interpretation.
  - Index scaling is our interpretation (bot: `ts_max_pts`).
- **Sources:** cc04_011_Gnw54f9v6SA ~00:11:30.
- **Quote:** "if it starts moving beyond 25 Pips ... it's probably not just a stop run" (cc04_011).
- **Conflicts:** none.
- **Rulebook fix:** M12: add the FX sweep-depth invalidation (cc04_011) and point to the bot's `ts_max_pts` as the index analogue.
- **BUILD SPEC:** none (fx_only; the index analogue already exists as `ts_max_pts`).

---

## E. In-trade invalidation and warnings (X6-X9, A13, B18)

### 90. X7-three-array-exit-trigger
- **rule_id / kind:** X7. Wrong. Scope: general. judgment = true.
- **Rule:** At entry, list the three nearest arrays against the trade, nearest first: A1, A2, A3.
  - Examples, long: 045 = VI, FVG, MT of the last down-close OB; 105 = wick CE, the candle high below it, the OB body; 026 = VI etc., then the MT of the candle that started the leg.
  - A1 may be traded through. Trading into A2 is a warning.
  - Exit, parameter `three_array_mode`:
    - 'trade' (026 / 078): price trades through all three, then close everything before the stop;
    - 'close' (045): a body close below A3 (the OB MT), then abort or take half off (new-trader rule);
    - 'into' (105): price trades into A3's body, then close everything even if price later recovers.
  - Proximity exception (078, NQ live): if A3 sits very close above or below A2, close everything when price reaches A2. The "very close" threshold is undefined; any number is ours.
  - This is a trade exit only; it says nothing about flipping bias.
- **Sources:** 026_GFdWahZUNOw ~00:28:00; 045_DNi9S3_NA44 ~01:57:01; 078_FQqwmDJOtxk ~01:03:02; 105_A97shZGPE2I ~01:24:00.
- **Quotes:** "if it breaks through three of them then I'm probably not on side anymore" (026); "you either abort the trade or take half off" (045).
- **Conflicts:** X7 text (body closes through all three) vs 026 / 078 (trades through) vs 045 / 098 (a body close below the OB MT, abort or half) vs 105 (trades into the third array's body).
- **Rulebook fix:** X7: replace "body closes through all three (026)" with the three modes and the proximity exception, citing each source. B8: re-check the 078 citation as a bias flip.
- **BUILD SPEC (management_exits):** extends section 3 X7a `pd3` list / X7b `pd3_half`.
  - Where: at the fill, `pos["pd3"]` = the 3 nearest opposing arrays (VI, gap, OB MT, wick CE, breaker) from `ctx.conf` / `sd.gaps`, sorted by distance (X7a). The existing `pd3_exit` (~2680) counts broken gaps only.
  - New `three_array_mode`:
    - "trade": low < A3 far edge -> close all ("pd3_trade");
    - "close": close < A3 level -> `partial_close` `pd3_close_frac` once ("pd3_close");
    - "into": low <= A3 body top -> close all ("pd3_into").
  - Proximity: if |A3 - A2| <= `pd3_near_pts`, the trigger moves to A2.
  - Params: `three_array_mode: str = ""`, `pd3_close_frac: float = 0.5`, `pd3_near_pts: float = 0.0` (0 = off; test 1.0).
  - Test: `test_three_array_modes`. A long with A1 VI 4100, A2 FVG 4098, A3 OB MT 4095 (body top 4096):
    - a low of 4095.5 exits under "into" only;
    - a close at 4094.75 halves under "close";
    - a low of 4094 exits under "trade";
    - with A3 at 4097.5 and `pd3_near_pts=1`, a low of 4098 exits.

### 91. X8-hold-above-broken-session-highs
- **rule_id / kind:** X8. Missing condition. Scope: index. judgment = true.
- **Rule:** Long.
  - After the trigger level breaks and price accelerates through the 09:30 high and the ~09:53 swing high toward the first target, price should stay above those broken highs.
  - Losing them (our reading: a 1m body close back below the higher of the two) is a warning.
  - The response, whether a partial or a stop tightened to below that high, is our interpretation; ICT does not state it.
- **Sources:** 009_tnxvmHq8xEg ~00:17:38.
- **Quote:** "I'm watching how we stay above the high that was formed at 9 30 and 9 53 or so" (009).
- **Conflicts:** none.
- **Rulebook fix:** X8: add the later hold condition (009 ~17:38) after the existing 009 ~15:36 rule.
- **BUILD SPEC (management_exits):**
  - Where: at the fill, `pos["broken_hi"]` = max(the 09:30 bar high, the latest pivot high since 09:30) when both lie below the entry or are exceeded after it.
  - Once the high has been exceeded, a 1m close below `broken_hi` triggers `held_hi_action`: "tighten" -> `raise_stop(pos, l - stop_buffer, "lost_hi")` (the broken high is above the close, so the stop goes under the bar low); "partial" -> `partial_close` 0.5 ("lost_hi").
  - Params: `held_hi_action: str = ""` ("" / "tighten" / "partial").
  - Test: `test_held_hi`. A 09:30 high at 4020 and a 09:53 high at 4022, exceeded: a close at 4021.5 halves under "partial". A close at 4022.25 does nothing.

### 92. X8-nwog-ce-pullback-hold
- **rule_id / kind:** X8 / A5. Missing condition. Scope: index. judgment = true.
- **Rule:** Long into an NWOG above, after the bulk partial at its CE.
  - The pullback should find support and re-accumulate without dropping below the NWOG's lower quarter (low + 0.25 x (high - low)). The level is our reading of "lower quarter of the CE to the low".
  - If it holds and expands higher, peel off the runners one at a time on each new high into the upper half and the far edge.
  - Losing that quarter means the expected re-accumulation failed. The remainder's stop is set tightly (see item 18), so exit the runners.
- **Sources:** 020_MqOVbd1oqZk ~00:09:23.
- **Quote:** "I want to see it reaccumulate and start expand higher" (020).
- **Conflicts:** none.
- **Rulebook fix:** X8 / A5: add the NWOG-target pullback hold (020).
- **BUILD SPEC (management_exits):**
  - Where: when a rung at an NWOG CE fills (gap rows carry `far`, item 1), set `pos["gap_q"] = low + 0.25 x (high - low)`.
  - A bar trading below `gap_q` closes the rest ("gap_q"). If it holds, item 50's peel logic runs.
  - Params: `gap_q_hold: bool = False`.
  - Test: `test_gap_q_hold`. NWOG 4100-4120 with CE 4110 filled: a pullback to 4105.5 holds, and a bar to 4104.75 closes the runners.

### 93. X8-fast-through-next-reference
- **rule_id / kind:** X8 / A20. Missing rule. Scope: general. judgment = true.
- **Rule:** Long in progress (short is the mirror). The next reference is the nearest pool, VI or REH above.
  - OK: price expands through it with speed, leaving an FVG, or touches it, opens a new candle and expands.
  - Warning (high-resistance run): price stops short and comes back to find support before retrying, or goes above and closes back into the range or the prior FVG.
  - On a warning, pare risk (take partials or reduce, 022) rather than demand the target. After T1, exit the remainder.
  - The speed and bar-count thresholds are undefined and are test parameters.
- **Sources:** 006_VKkn8uckkW0 ~00:53:30; 022_ALMsQytQ1fg ~01:40:24, ~02:38:38.
- **Quote:** "I want to see it go through it and not come back and touch it" (022).
- **Conflicts:** none.
- **Rulebook fix:** X8: add the in-trade speed check at each intermediate reference (006, 022). A20: cross-reference.
- **BUILD SPEC (management_exits):**
  - Where: each bar, `ref` = the next unhit level in `pos["levels"]` (any kind) or the next VI above.
  - Classify when price first trades beyond `ref`:
    - "ok" if that bar or the next leaves a gap above `ref`, or its range >= `speed_k x median(range[-20:])`;
    - "fail" if, within `speed_bars`, a close comes back below `ref`;
    - also "fail" if price comes within 1 pt of `ref`, then closes 3 bars lower without touching it.
  - On "fail": before T1, `partial_close` `speed_pare`; after T1, close all ("slow_ref").
  - Params: `ref_speed_check: bool = False`, `speed_k: float = 1.5`, `speed_bars: int = 3`, `speed_pare: float = 0.5`.
  - Test: `test_ref_speed`. A break of 4038.75 with a gap above it is "ok". A break followed by a close back below within 2 bars halves before T1 and closes all after T1.

### 94. X8-opposing-array-torn-through
- **rule_id / kind:** X8 / A12. Missing rule. Scope: general. judgment = true.
- **Rule:** Long (short is the mirror). For each bearish OB or FVG between price and the target, mark its MT (OB) or CE (FVG).
  - Confirmation: price quickly trades into the body and through the MT / CE within the current or the next 1m candle. When that next candle opens it should run higher immediately, and the touching candle's low must hold.
  - Failure: price bounces off short of the MT / CE, meanders, retraces into the entry FVG, or trades below the touching candle's low. That is a warning that it may consolidate or reverse: no adds, and manage per X7 / X9.
  - The stop stays below the entry FVG.
- **Sources:** 027_STEGBblm4dI ~00:31:40, ~00:34:04, ~00:35:02.
- **Quote:** "it needs to quickly go into the candle's body and go right through the midpoint" (027).
- **Conflicts:** none.
- **Rulebook fix:** X8: add the opposing-array tear-through confirmation (027). A12: cross-reference.
- **BUILD SPEC (management_exits):**
  - Where: at the fill, `pos["opp_arrays"]` = the opposing OB / gap rows between entry and the final level (`ctx.conf`, `sd.gaps`).
  - When a bar touches one (high >= its near edge), start a 2-bar window. Confirmed if a high >= MT / CE occurs within it and no later low < the touch bar's low before that. Otherwise set `pos["no_adds"] = True` and tag `pos["warn"] += 1` (X7a warn tag).
  - Params: `opp_tear_check: bool = False`.
  - Test: `test_opp_tear`. A bearish FVG 4105-4108 (CE 4106.5):
    - a touch at 4105.5 followed by 4107 on the next bar confirms;
    - a touch followed by a low under the touch bar's low blocks adds.

### 95. X8-broken-fvg-edge-bump-once
- **rule_id / kind:** X8 / A8. Missing rule. Scope: index. judgment = true.
- **Rule:** Short (long is the mirror). E = the low of the bullish FVG / BISI that price just broke down through.
  - A first retrace up to E is permissible, and ICT even added 1 contract there (071 ~15:17-16:05).
  - A second bump of E is unwanted: no more adds and no target changes. Leave the resting limit orders and the trailed stop in place, and accept a stop-out (071 ~30:16).
- **Sources:** 071_3FGFEuaDSOc ~00:30:16 (and ~15:10-16:05).
- **Quote:** "I don't want to see that bump it again" (071).
- **Conflicts:** none.
- **Rulebook fix:** X8 / A8: add "the broken FVG edge may be bumped once (an add location); a second bump is a warning (071)".
- **BUILD SPEC (management_exits):**
  - Where: at the fill, `pos["broken_edge"]` = the far edge of the opposing gap that price broke through in the entry leg.
  - Count bars after the fill whose high reaches within 1 tick of it. On bump #1, allow an add (setups `add_ok`) when `edge_bump_add` is on. On bump #2, set `pos["no_adds"] = True` and freeze the ladder levels (no `_resist_live` changes).
  - Params: `edge_bump_add: bool = False`, `edge_bump_guard: bool = False`.
  - Test: `test_edge_bump`. Broken edge 4400: the first bump at 4399.75 arms an add, and the second bump blocks further adds.

### 96. X8-late-day-fvg-lost-hod-in
- **rule_id / kind:** X8 / T11. Missing rule. Scope: index. judgment = false.
- **Rule:** Late-day long runner after a run on the highs: take the small FVG formed on the pullback from the highs.
  - While price is below it, it is resistance only, never an entry.
  - If price trades back above it, it must act as support. If price trades back down through it (ICT says only "goes back down through it"; bodies through is our reading), the high of day is in: close the runner.
  - Otherwise hold for a higher high and close just before 16:00.
- **Sources:** 027_STEGBblm4dI ~00:57:44.
- **Quote:** "if it goes back down through it then we're probably done for the day and the highs in place" (027).
- **Conflicts:** none.
- **Rulebook fix:** X8 / T11: add the late-day FVG flip and runner exit (027 ~55:36-58:40).
- **BUILD SPEC (management_exits):**
  - Where: from 15:00 (`last_hour[0]`), for open runners. `g` = the latest bearish gap formed after the session high.
  - Once a bar closes above `g.top`, mark it support. A later close below `g.bottom` closes all ("hod_in"). Entries in the trade direction are blocked while price is below `g`.
  - Params: `late_fvg_flip: bool = False`.
  - Test: `test_late_fvg_flip`. At 15:10 a bearish gap 4100-4101 forms. A close at 4101.5, then a close at 4099.75, exits. Without the reclaim, nothing exits.

### 97. X8-061-continuation-after-both-pools
- **rule_id / kind:** X8. Missing condition. Scope: general. judgment = true.
- **Rule:** Bearish (bullish is the mirror).
  - Once the leg has taken both BSL and SSL, continuation lower is valid only while price stays below the last up-close daily OB candle (using its open as the level) AND in the lower half of the daily FVG containing it (below its CE).
  - If price trades above either one, stand aside: no new shorts, and expect consolidation.
  - This is a filter, not an entry trigger. The source is an FX (EUR/USD) daily example. See also N6 (after both pools, retrace to the CE between them).
- **Sources:** 061_wWvXWmC_gqU ~01:46:40.
- **Quote:** "if it trades Above This candle here I would be sitting still" (061).
- **Conflicts:** none.
- **Rulebook fix:** X8: add the both-pools continuation filter and cross-reference N6.
- **BUILD SPEC (bias_htf):**
  - Where: `htf.table` gains a daily column `both_pools` (that day or the leg took both the prior high and the prior low) and a level `cont_cap` = min(the last up-close daily OB open, the containing daily FVG CE) for bearish.
  - `_scan` bias gate: with `both_pools_gate`, shorts are rejected when price > `cont_cap` on a `both_pools` day (longs mirror).
  - Params: `both_pools_gate: bool = False`.
  - Test: `test_both_pools_gate`. On a daily series where yesterday took both pools, with OB open 1.0850 and FVG CE 1.0840 (scaled), a short armed at 1.0845 is rejected and one at 1.0835 is allowed.

### 98. X8-sister-index-breaker-hold
- **rule_id / kind:** X8. Missing condition. Scope: index. judgment = true.
- **Rule:**
  - While long ES, track NQ. If NQ has a bullish breaker (A13) in the same leg and NQ 1m bodies hold above it, keep holding (085 ~19:11).
  - [Our interpretation] If an NQ body closes below the breaker zone or NQ trades below the breaker's low, count it as one array against the trade (X7).
  - Mirror for shorts.
- **Sources:** 085_6-KNSUN-UaU ~00:19:11.
- **Quote:** "the bodies have respected that bullish breaker so this low should never be taken out" (085).
- **Conflicts:** none.
- **Rulebook fix:** X8: add the sister-index breaker hold (085).
- **BUILD SPEC (management_exits):**
  - Where: run_day already loads sides for the instruments used in `backtest.combine` (SMT tie-break, B18.3). With `sister_breaker_hold`, at the fill take the sister's `levels.breaker_zone` in the same leg.
  - Each bar, a sister close below the zone bottom adds 1 to `pos["warn"]` (it feeds item 90's count). Without sister data, the switch is a no-op.
  - Params: `sister_breaker_hold: bool = False`.
  - Test: `test_sister_breaker`. With an NQ breaker 15000-15010, an NQ close at 14999 raises the ES position's warn count by 1, and a close at 15001 does not.

### 99. X8-profitable-stall-exit
- **rule_id / kind:** X8. Missing rule. Scope: general. judgment = true.
- **Rule:**
  - Context: an intraweek move (mostly Mon / Tue) that is large and fast compared with ADR5 and is trading into an HTF PD array.
  - If a profitable trade stops delivering there, close it and look for a new entry in the same direction.
  - If no strong new entry forms, treat the week as a likely intraweek market reversal profile (a Wed / Thu reversal) and stop pressing the original direction.
  - All stall detection (bars without a new extreme, a body close back through the latest FVG / OB) and any re-entry deadline are our interpretation; ICT gives none.
- **Sources:** cc07_007_jvc105qaCJs ~00:22:33.
- **Quote:** "even though you're profitable chances are it's probably better for you to get out of it" (cc07_007).
- **Conflicts:** none.
- **Rulebook fix:** X8: add the profitable-stall exit in the intraweek reversal context (cc07_007).
- **BUILD SPEC (management_exits + day_week_context):**
  - Where: with `stall_at_htf`, active when the week's range so far >= 1.5 x ADR5 by Tuesday close (day_week_context weekly state in `BT.run`) and price is inside an `htf.table` array.
  - An open trade in profit that makes no new extreme for `stall_at_htf_bars` bars closes at market ("htf_stall"). If no new same-direction setup fills in the next session, set the weekly flag `reversal_watch`, which blocks that direction for the week.
  - Params: `stall_at_htf: bool = False`, `stall_at_htf_bars: int = 30`.
  - Test: `test_stall_at_htf`. A Tuesday long in profit inside a daily FVG with 30 bars and no new high exits. With no new long by Wednesday close, Thursday longs are blocked.

### 100. X9-lethargic-or-choppy-trade
- **rule_id / kind:** X9. Shortened. Scope: general. judgment = true.
- **Rule:**
  - If the trade turns uncertain, lethargic or choppy after entry (no immediate dynamic response; overlapping back-and-forth candles; the model no longer looks one-sided), first cut risk: halve the position (100: the new-trader default) or bail entirely (cc03_003).
  - If the position is already 1 minimum unit, close it (100).
  - If the session itself is identified as sloppy chop, close 100% at market regardless of P&L (022).
  - Option `after_chop_exit`:
    - 'end_session' (022 "cut bait": flat and no new pursuit that session);
    - 'reentry_allowed' (cc03_003: a later re-entry on a new continuation pattern).
  - If no recapitalised session OBs form during the trade, treat it as probably offside (cc03_003).
  - Any "within N candles / X R" threshold is a test parameter.
- **Sources:** 022_ALMsQytQ1fg ~01:52:48, ~02:06:07; 100_GJeEU2oIh24 ~01:02:20; cc03_003_t2VNzJZ4hK4 ~00:13:49, ~00:43:35.
- **Quote:** "As soon as you discover that you're in these types of environments, close your trade." (022)
- **Conflicts:** 022 (close 100% and end the session) vs cc03_003 (halve or bail and re-enter); 085 says never close and then re-enter on the same leg (item 130).
- **Rulebook fix:** X9: expand "lethargic -> cut half" with the min-size close, the chop full close and the two after-chop options.
- **BUILD SPEC (management_exits):** extends section 3 X9d `time_stop_frac` (fire-once half cut with a min-size close).
  - Where: when the intraday `Chop` detector (strategy.py ~2041, `chop.on`) turns on while a position is open and `chop_close` is on, close all ("chop_close").
  - Then `after_chop_exit`: "end_session" -> `done[session] = True`; "reentry_allowed" -> leave `done` and set `state["reentered"]`-style half risk (X13b) for the next same-side setup.
  - Params: `chop_close: bool = False`, `after_chop_exit: str = "end_session"`.
  - Test: `test_chop_close`. Chop turns on during an open long, which closes. Under "end_session", a later AM setup is not armed; under "reentry_allowed", it is armed at half risk.

### 101. X9-repeated-array-taps
- **rule_id / kind:** X9 / A13. Unlisted contradiction. Scope: index. judgment = true.
- **Rule:** Count taps of the entry breaker.
  - Entry gate (048, index; strongest when the indices are not moving in tandem): after the 2nd tap, require price to trade above the opposing FVG in the current or the next setup-TF candle without breaking the tap low. If it does not, or a 3rd tap occurs, mark the breaker "worn" and do not enter.
  - In-trade (063): a held position from a breaker may tolerate repeated re-tests (3 in 063) as long as the stop and breaker hold. Do not use a tap count as a time stop on an open trade without testing it.
  - Test parameter: `breaker_max_taps_for_entry` = 2 vs none.
- **Sources:** 048_gGxVE8zUIRQ ~00:32:51; 063_qA9SCu4gGaU ~00:28:54.
- **Quote:** "it spends multiple times in it because once twice three times and then finally rips" (063).
- **Conflicts:** 048 (a 3rd tap = unreliable, pre-entry) vs 063 (held through 3 taps). See also item 26 (085: 3 retests justify raising the stop).
- **Rulebook fix:** A13: add the tap-count entry gate (048). X9: note that held positions may tolerate re-tests (063).
- **BUILD SPEC (setups_models):**
  - Where: breaker entries in `_scan` (`levels.breaker_zone`). Count bars since the zone formed whose low enters the zone and whose next bar closes above it (taps).
  - With `breaker_max_taps_for_entry=2`: at tap 2, start a 2-bar window. The entry is allowed only if a high > the nearest opposing FVG's top occurs in that window with no low below the tap-2 low. Tap 3 or more marks the zone worn and rejects the setup.
  - Params: `breaker_max_taps_for_entry: int = 0`.
  - Test: `test_breaker_taps`. Two taps followed by a break of the SIBI top within 2 bars allow the entry. A third tap rejects it.

### 102. X9-071-move-away-from-up-close-pair
- **rule_id / kind:** X9. Missing condition. Scope: index. judgment = true.
- **Rule:** Short (long is the mirror).
  - Find the last two consecutive up-close candles and the small gap between them. Price may tag that gap once or twice.
  - Once it trades below the open of the lower candle, it must keep moving away (lower) on that candle or the next 1-2 1m candles.
  - If it stalls there instead, accept a likely stop-out: keep the stop as is, don't widen it and don't add (the no-add part is our inference). Do not exit early on this alone.
- **Sources:** 071_3FGFEuaDSOc ~00:33:10.
- **Quote:** "I want to see price move away from that when it does that if it doesn't then I have to accept the fact that I may get stopped" (071).
- **Conflicts:** none.
- **Rulebook fix:** X9: add the up-close-pair structure to the 071 ~32:41 citation.
- **BUILD SPEC (management_exits):**
  - Where: with `upclose_pair_guard`, at the fill find the last two consecutive up-close bars before entry. After a bar trades below the lower one's open, if none of the next 2 bars makes a new low, set `pos["no_adds"] = True` and block any stop widening (stops never widen anyway; this only blocks adds).
  - Params: `upclose_pair_guard: bool = False`.
  - Test: `test_upclose_pair`. After the break of the lower open, two bars without a new low block adds. A new low on the next bar does not.

### 103. X9-speed-after-fulcrum-break
- **rule_id / kind:** X9. Missing condition. Scope: general. judgment = true.
- **Rule:**
  - After the pool or fulcrum breaks in the trade direction, price should speed through it and aggressively into -0.5 SD (090 ~1:31:35).
  - [Our interpretation] Test a window of N 1m candles (e.g. 5) without a body closing back beyond the broken level. If it stalls, take the first partial at once and tighten or exit.
- **Sources:** 090_bhYcXBI3z9U ~01:31:35.
- **Quote:** "I would want to see speed aggressively into negative ... point five standard deviation" (090).
- **Conflicts:** none.
- **Rulebook fix:** X9: add the post-break speed check for fulcrum / pool breaks (090).
- **BUILD SPEC (management_exits):**
  - Where: fulcrum-anchored trades (item 66). After the bar that breaks the fulcrum pool, if -0.5 SD is not reached within `fulcrum_speed_bars` bars, or a body closes back beyond the broken level first, close the first rung's fraction at market ("fulcrum_slow") and `raise_stop` to the bar extreme + buffer.
  - Params: `fulcrum_speed_bars: int = 0` (test 5).
  - Test: `test_fulcrum_speed`. -0.5 SD reached on bar 3 does nothing extra. Five bars without reaching it close the first fraction.

### 104. A13-breaker-far-edge-partial
- **rule_id / kind:** A13. Missing rule. Scope: general. judgment = true.
- **Rule:** Bearish breaker zone [BL, BH], MT = (BL + BH) / 2.
  - Expect the reaction at BL or MT (or at an REH / FVG inside the zone); BH should not be reached.
  - If a short taken off this breaker (or one whose context is this breaker) sees price trade through BH: scale out part of the position (ICT: "scale something off"; bot default 50%, test 25%), keep the rest on the original stop, and mark the idea weaker.
  - Bullish mirror.
- **Sources:** 078_FQqwmDJOtxk ~00:55:36, ~00:19:13.
- **Quote:** "if it does that and I'm in a trade I will scale something off" (078).
- **Conflicts:** none.
- **Rulebook fix:** A13: add "the breaker is traded at its low or MT; trading through the far edge = scale something off (078)".
- **BUILD SPEC (management_exits):**
  - Where: breaker trades carry `tr.bz_top` / `bz_bottom` (built). With `breaker_far_partial > 0`, the first bar trading beyond the far edge (BH for a short) triggers `partial_close(..., breaker_far_partial, "bz_far")` once and sets `pos["no_adds"] = True`.
  - Params: `breaker_far_partial: float = 0.0` (test 0.5 / 0.25).
  - Test: `test_breaker_far_partial`. A short with a breaker 4400-4410 and the stop at 4415: a bar to 4410.25 closes 50% and the stop stays at 4415.

### 105. A13-breaker-close-beyond-higher-array
- **rule_id / kind:** A13. Missing condition. Scope: index. judgment = true.
- **Rule:** Bearish breaker:
  - If a bearish OB (or FVG) sits a few points above the breaker high, allow price (including a candle body intrabar) to trade just outside the breaker without invalidating it. Put the stop above that higher array, not the breaker.
  - The idea stays valid if the candle closes back inside the breaker. Invalidate on a body close above the higher array.
  - With no higher array, A13 / X6 apply as written. The Reaper is not codeable (A24), so the bot uses OB / FVG only. Bullish mirror.
- **Sources:** 081_0xYpeVRi_qs ~00:14:11.
- **Quote:** "give it permission... to trade just outside" (081).
- **Conflicts:** X6 aborts on a body close beyond plus the next candle beyond.
- **Rulebook fix:** A13 / X6: add the higher-array exception (081).
- **BUILD SPEC (entries_stops_sizing + management_exits):**
  - entries_stops_sizing: for breaker entries with `bz_higher_array`, if a same-polarity OB / gap (`ctx.conf`) lies within `bz_higher_pts` beyond the breaker's far edge, the stop = that array's far edge + buffer.
  - management_exits: the `breaker_mt` / `fvg_abort` exits for that trade use the higher array's far edge instead of the breaker's.
  - Params: `bz_higher_array: bool = False`, `bz_higher_pts: float = 5.0`.
  - Test: `test_bz_higher_array`. A breaker 4400-4410 with a bearish OB 4412-4415: the stop = 4415 + buffer. A close at 4411 does not abort; a close at 4415.5 does.

### 106. new-strength-no-return-discount-array
- **rule_id / kind:** new. Missing rule. Scope: general. judgment = true.
- **Rule:** Long after entry. OB1 = the nearest bullish order block below price.
  - If price makes a new high without trading back into OB1's body, grade the move strong and hold the remaining units for the full pool targets (no early scale-outs).
  - If price does trade into OB1 and holds, the bullish narrative stands but the move is less energetic, and normal partials apply.
  - What counts as failing is left to the existing invalidation rules (X6-X8).
- **Sources:** 105_A97shZGPE2I ~00:17:00.
- **Quote:** "not patient enough to even want to go back down into that discount array that means it's exceedingly bullish" (105).
- **Conflicts:** none.
- **Rulebook fix:** X3: add the strength grade (105) as a partial-size modifier.
- **BUILD SPEC (targets_partials):**
  - Where: at the fill, `pos["ob1"]` = the nearest bullish OB below price (`levels.order_block` on the post-fill pullback, or the entry OB).
  - With `strength_hold`, when a new high is made with no low inside OB1's body since the fill, the remaining non-pool rungs are dropped (pool rungs kept) and `pos["strength"] = "strong"`. Otherwise the ladder is unchanged.
  - Params: `strength_hold: bool = False`.
  - Test: `test_strength_hold`. An OB1 body of 4550-4553 never revisited: array rungs are removed and the pool rungs stay. With a dip to 4552, the ladder is unchanged.

### 107. new-small-fvg-last-line
- **rule_id / kind:** new. Missing rule. Scope: general. judgment = true.
- **Rule:** Long, partials taken. G = the most recent small 5m bullish FVG that price retraces into.
  - Expect price to leave G within this candle or the next.
  - The longer price lingers in G, or if a 5m body closes below G, expect a retrace to the top of the HTF (4H) FVG below: no adds, and the stop stays at or below that HTF FVG high rather than tighter.
  - X7 / X8 still govern any exit. The candle-count threshold is ours, e.g. 2 candles.
- **Sources:** 105_A97shZGPE2I ~00:37:35.
- **Quote:** "the longer we spend time in this little area the more likely we are to trade back down into the top of that fair value gap on the 4 Hour chart" (105).
- **Conflicts:** none.
- **Rulebook fix:** X8: add the small-FVG linger warning (105).
- **BUILD SPEC (management_exits):**
  - Where: with `small_fvg_linger > 0`, after T1, take the latest 5m gap (aggregated) that price enters. If price stays inside it for more than `small_fvg_linger` 5m bars, or a 5m close comes below it, set `pos["no_adds"] = True` and `pos["stop_cap"] = htf_entry_hi` (item 12). `raise_stop` refuses levels above `stop_cap` from then on.
  - Params: `small_fvg_linger: int = 0` (test 2).
  - Test: `test_small_fvg_linger`. Three 5m bars inside the gap set the cap, and a later trail attempt above the 4h FVG high is refused.

### 108. new-no-down-close-urgency
- **rule_id / kind:** new. Missing rule. Scope: general. judgment = true.
- **Rule:** Long (short is the mirror, with up-close candles).
  - If the expansion leg prints no down-close 1m candle, read it as urgency and keep the farther target (T2).
  - Have most of the position off by then and keep a very tight stop on the runner (about 1 pt below price).
  - With no down-close candle there is no pullback to pyramid on (our corollary).
  - The source example is FOMC day, analysis only.
- **Sources:** 021_DVxC7UAHzwk ~00:43:53.
- **Quote:** "it didn't offer it so it's in a hurry to get somewhere so I think 4108 and 4112 is doable" (021).
- **Conflicts:** none.
- **Rulebook fix:** add to X3: "no down-close candle in the expansion = urgency; keep T2 with a tight runner stop (021)".
- **BUILD SPEC (management_exits):**
  - Where: with `urgency_runner`, when T1 fills and no down-close bar has printed since the fill, the last rung keeps `runner_frac` (or 0.2) and the runner's stop = c - `urgency_stop_pts` x es_pt via `raise_stop`. Otherwise the ladder is unchanged.
  - Params: `urgency_runner: bool = False`, `urgency_stop_pts: float = 1.0`.
  - Test: `test_urgency_runner`. An all up-close leg to T1 keeps a 20% runner with the stop 1 pt under the close. One down-close bar in the leg leaves the ladder unchanged.

### 109. new-implied-range-behaviour
- **rule_id / kind:** new / E12. Missing rule. Scope: general. judgment = true.
- **Rule:** Long (short is the mirror). Implied range = from the inception low L to the target T, with levels at 25 / 50 / 75%.
  - Expect sideways consolidation (time distortion) around 50%: hold, and don't exit on time alone. No adds past EQ (E12).
  - Inside the top 25%, expect the fastest leg straight to T, with no sell-side raid and no retrace outside the last bullish OB body.
  - A deeper retrace or a sell-side raid there breaks the expected behaviour: reduce (our inference).
- **Sources:** 045_DNi9S3_NA44 ~03:02:00.
- **Quote:** "the algorithm is coded to allow for no deep retracements at the 25 upper 25 mark" (045).
- **Conflicts:** none.
- **Rulebook fix:** E12 / X8: add the implied-range behaviour (045 ~2:57-3:03).
- **BUILD SPEC (management_exits):**
  - Where: at the fill, `pos["ir_L"]` = the sweep extreme and T = the final level.
  - With `implied_range`: `time_stop_min` is suspended while price is between the 25% and 75% lines.
  - Above 75%: a bar trading below the latest pivot low formed above 75%, or below the last bullish OB body formed after the fill, triggers `partial_close` 0.5 ("ir_top_raid").
  - Params: `implied_range: bool = False`.
  - Test: `test_implied_range`.
    - The time stop does not fire while price sits at 50%;
    - in the top quarter, a raid of a fresh pivot low halves the position.

### 110. new-rolling-bpr-ceiling
- **rule_id / kind:** new. Missing rule. Scope: index. judgment = true.
- **Rule:** Short (long is the mirror).
  - After each new low L, the new BPR = [L, H], where H is the last retrace high (usually the prior BPR's mean threshold or a wick CE).
  - The next retrace may reach this BPR's mean threshold (by bodies), which is permissible.
  - Above H, the read is invalid: tighten the stop to above H or exit (our inference).
  - If a retrace fails short of the MT and price breaks lower, the new BPR runs from the new low up to that unhit MT or failed retrace high. Repeat on each new low.
- **Sources:** 026_GFdWahZUNOw ~01:53:06.
- **Quote:** "consequent encroachment becomes the high end of the New Balance price range" (026).
- **Conflicts:** none.
- **Rulebook fix:** add to X5: the rolling BPR ceiling (026 ~1:52:30-1:55:43), as distinct from the A11 FVG-overlap BPR.
- **BUILD SPEC (management_exits):**
  - Where: `ladder_trail="rolling_bpr"`. On each new low after the fill, H = the highest high of the last retrace (the max high between the previous low and this one), and `raise_stop(pos, H + tick, "bpr_roll")`. The body-MT of [L, H] is stored for the report.
  - If a retrace fails short of the previous MT, H is that retrace's high.
  - Params: `ladder_trail` value "rolling_bpr".
  - Test: `test_rolling_bpr`. Lows of 4100, then 4090, with a retrace high of 4096 between them: the stop goes to 4096.25. The next retrace to 4094 and a new low of 4085 move it to 4094.25.

### 111. new-laggard-slow-delivery
- **rule_id / kind:** new. Missing rule. Scope: index. judgment = true.
- **Rule:**
  - Tag a trade "laggard" when it is taken in the index moving in sympathy after the leader already reached its draw.
  - For laggard trades, loosen (do not drop) the X9 time stops and the X8 meander exit, e.g. allow a longer window [our interpretation, test values].
  - Hold while no body closes beyond the entry array's invalidation level. Use partials at intermediate pools, since it is a high-resistance run (X3).
- **Sources:** 090_bhYcXBI3z9U ~01:49:28.
- **Quote:** "you have to allow for a little bit more reluctance in price ... it won't be so Snappy" (090).
- **Conflicts:** the X9 time stops and the X8 meander exit (092).
- **Rulebook fix:** X9: add "laggard-index trades get a longer time window (090)".
- **BUILD SPEC (management_exits + setups_models):**
  - setups_models: in `backtest.combine` / the SMT tag, mark `tr.laggard = True` when the other index already traded through its draw level before this fill.
  - management_exits: laggard positions use `time_stop_min x laggard_mult` and `meander_bars x laggard_mult` (section 3 X8g).
  - Params: `laggard_mult: float = 1.0` (test 2.0).
  - Test: `test_laggard_time_stop`. With `time_stop_min=10` and mult 2, a laggard trade is still open at minute 15 and a normal trade is closed.

### 112. new-volume-divergence-exit
- **rule_id / kind:** new. Missing rule. Scope: general (sources are bond futures). judgment = true.
- **Rule:** Bond / commodity futures with real volume (cc10_006).
  - When price makes a new extreme beyond the prior one (for example beyond the 08:00-09:00 OR, where the day's highest volume usually prints) and the volume bar at the new extreme is lower than the volume behind the prior push, treat the move as weak: a stop run with no follow-through.
  - Expect a reversal back into the OR or the nearest FVG, then consolidation.
  - Bot use: a reversal / exit cue (take profits, or do not enter in the extreme's direction), as a test switch. Not for SPY / ES without validation.
- **Sources:** cc10_006_CGbSpa_9Z9Y ~00:06:00, ~00:07:52, ~00:09:45.
- **Quote:** "that lower low should have been met with a higher bar on volume this is a sign of impending weakness" (cc10_006).
- **Conflicts:** cc03_003 / cc04_002: do not exit on divergence while the HTF draw is untaken (item 38).
- **Rulebook fix:** add a new rule under X8 (bond / commodity futures): volume divergence at a new extreme = weak move (cc10_006), with the conflict.
- **BUILD SPEC (management_exits, study switch):**
  - Where: bars carry volume (databento / alpaca loaders). With `vol_div_exit`, when an open position's bar makes a new session extreme in the trade direction and its volume < `vol_div_ratio` x the volume of the bar that made the prior extreme, `partial_close` 0.5 ("vol_div"). Skipped while `no_collapse_htf` is on and the HTF draw is untouched.
  - Off by default and labelled bonds-sourced in the report.
  - Params: `vol_div_exit: bool = False`, `vol_div_ratio: float = 1.0`.
  - Test: `test_vol_div_exit`. A new high on 500 contracts vs a prior high on 900 halves the position. On 1000 contracts it does not.

### 113. exit-intermarket-divergence-close-all
- **rule_id / kind:** B19 / new. Missing rule. Scope: needs_unavailable_data. judgment = true.
- **Rule:** Long ES (shorts are the mirror).
  - (a) On a new ES swing high, if DXY's corresponding swing low is higher than its prior low (no symmetrical DXY lower low), exit all remaining units (036 had 20% left after the 80% partial).
  - (b) Whether or not a partial has been taken, if DXY rallies to a new short-term high while EURUSD and GBPUSD break to new lows, with index SMT present, exit the whole trade at market rather than wait for the stop (045).
  - There is no proxy without DXY or FX intraday data.
- **Sources:** 036_n37ozsUreR0 ~01:27:18; 045_DNi9S3_NA44 ~01:12:00.
- **Quote:** "this would completely close my trade entirely" (036).
- **Conflicts:** X3 SMT warning (bank about 50%); cc03_003 / cc04_002 (no divergence exits while the HTF draw is untaken).
- **Rulebook fix:** B19: add the in-trade DXY / FX non-confirmation full exit (036, 045), noted as needing intraday DXY / FX.
- **BUILD SPEC:** none (needs intraday DXY / FX).

### 114. B18-smt-partial-size-precondition
- **rule_id / kind:** B18 / X3. Missing condition. Scope: needs_unavailable_data. judgment = false.
- **Rule:** Short ES / NQ (longs are the mirror).
  - Case A (037): a sister index (YM) prints a new lower low while ES and NQ fail to make theirs. Treat it as a warning of consolidation or a short-term reversal: take most of the position off (>50%; the exact fraction is our parameter) and trail the remainder's stop to just above the latest short-term high.
  - Case B (046): the sister index has already run its sell stops (L1, then L2), and as ES / NQ approach the target it trades back to that low. It should go through with speed and distance. If it shows no willingness to break, take a large partial (~50%) and keep the other half for the target.
  - Neither case is a reversal entry.
- **Sources:** 037_wu0sQarBRrI ~00:33:44; 046_VLis0LcbUaQ ~01:09:15.
- **Quote:** "I would want to take more of the position off because it could mean it could create a retracement higher" (037).
- **Conflicts:** 037 "most of my position" vs 046 / X3 "~50%".
- **Rulebook fix:** X3: separate the two SMT cases as B18 already does, and add the 046 precondition and speed test and the 037 trailed stop.
- **BUILD SPEC:** none (scope as verified: needs YM intraday data). Section 3 X3g `smt_partial` (50% / 80%) is the closest existing switch for ES / NQ.

### 115. new-spread-divergence-trail
- **rule_id / kind:** new. Missing rule. Scope: needs_unavailable_data. judgment = true.
- **Rule:** Commodities only (cc10_004).
  - While long in a premium-driven rally, the nearby-vs-next-month spread should rise with price.
  - A higher high in price with a lower spread peak means institutional buying is unconfirmed: look to trail the stop and / or take some profits, then wait for a new bullish spread-divergence buy signal before re-entering. Mirror for shorts.
  - Requires spread data the bot does not have.
- **Sources:** cc10_004_WsolkBzpDOQ ~00:18:22.
- **Quote:** "that would be an indication that we would have to look for reasons to trail our stop loss" (cc10_004).
- **Conflicts:** cc03_003 / cc04_002 (no divergence exits while the HTF draw is untaken).
- **Rulebook fix:** add a commodities-only note: spread divergence at a new high = trail / take profits (cc10_004).
- **BUILD SPEC:** none (needs calendar-spread data).

---

## F. Session, day and time exits (D16, X10, X11, T13, B17, N8)

### 116. D16-am-trade-held-into-pm
- **rule_id / kind:** D16 / X10. Unlisted contradiction. Scope: index. judgment = true.
- **Rule:**
  - Fix D16's "no source" sentence. Keep am_exit=12:00 as the default (session mode).
  - Add trade_mode='day' as a test switch. Use it only when:
    - the HTF bias is aligned;
    - the final target is an HTF draw not reached by 12:00;
    - and the daily range is expected to expand and close near its extreme (064).
  - In day mode: no am_exit, the initial stop is kept, partials are taken through the day, and the position is flat by 16:00.
  - Sub-switch am_runner_hold_to=15:00: after ~90% off at the AM target, hold 1-2 runners with the rolled stop (085).
- **Sources:** 006_VKkn8uckkW0 ~00:38:59; 026_GFdWahZUNOw ~01:32:26; 064__YTK5uXBe4o ~01:40:54; 069_Sf_uYZBWTrA ~00:17:35 (hypothetical); 076_cgsltOB736E ~00:25:42; 085_6-KNSUN-UaU ~00:32:13; cc03_003_t2VNzJZ4hK4 ~00:35:31 (FX daily PO3).
- **Quotes:** "I have majority of the position open the entire day" (026); "day trading is position trading for the daily range" (064).
- **Conflicts:** D16 / X10 (Ep 03; 003: last AM unit off before noon; "no source holds an AM trade into the PM") vs 006, 026, 064, 069, 076, 085, cc03_003. Owner #8 (close, not tighten) is about the mode of the noon exit, not its timing, so a non-default day mode does not conflict with it. See items 117 and 118.
- **Rulebook fix:** D16: delete "No source holds an AM trade into the PM"; add option "day mode" with these sources and its conditions. X10: cross-reference.
- **BUILD SPEC (management_exits):**
  - Where: item 17's `pos["trade_mode"] = "day"` (selection by `day_mode_auto`) also exempts the position from `am_exit` (~2693) and from the pending-order noon guard (~2740).
  - Sub-switch: with `am_runner_hold_to > 0`, a session-mode AM position whose closed fraction is >= 0.85 at 12:00 keeps its remaining units (at most 2 lots) on the current stop. Those units close at `am_runner_hold_to` (e.g. 900).
  - Owner #8's "close" mode stays the default for everything else.
  - Params: `am_runner_hold_to: int = 0`.
  - Test: `test_day_mode_am_exit`.
    - A day-mode long is open at 12:05 and closes at the flatten time;
    - a session-mode long with 90% off at 11:30 and `am_runner_hold_to=900` keeps 2 lots past 12:00 and closes them at 15:00;
    - with 50% off, it closes at 12:00 as today.

### 117. D16-big-range-day-runner-past-noon
- **rule_id / kind:** D16. Unlisted contradiction. Scope: index. judgment = true.
- **Rule:**
  - If the day is classified as explosive (day range >= ADR5 by 10:00, or >= 1.25x ADR5 by 11:00 [our threshold]) or as a two-session up / down-close trend day, and price is still making new extremes in the trade's direction without a meaningful retrace: do not force the 12:00 AM exit. Keep the runner on its trailed stop up to the 15:00 bond close (optionally 16:00), then exit.
  - Caveat: cc10_014's AM guidance is still "hold to 10:30-11:00" within the two-session profile. The exemption from the 12:00 exit rests on cc09_006 (explosive days: the HOD can form as late as 15:00) and on cc10_014's general "hold for the maximum daily range".
  - The runner-past-noon rule and its thresholds are our interpretation.
- **Sources:** cc09_006_OVfn-gDk2dE ~00:12:51; cc10_014_yWBxZsbmK1U ~00:03:28.
- **Quote:** "on highly explosive up moves 10 o'clock isn't going to stop price" (cc09_006).
- **Conflicts:** D16 / X10 (am_exit=12:00; "no source holds AM into PM") vs cc09_006 and cc10_014. See items 116 and 118.
- **Rulebook fix:** D16: add the explosive / two-session exemption (cc09_006, cc10_014) and correct the "no source" statement (same fix as item 116).
- **BUILD SPEC (management_exits):**
  - Where: at 12:00 (~2693), with `explosive_runner`, skip `am_exit` for this position when:
    - (day range at 10:00 >= ADR5, or at 11:00 >= `explosive_frac` x ADR5) and the session extreme in the trade direction was made within the last 15 bars;
    - or the T13 profile tag is "two_session" (if built).
  - The position keeps its trailed stop and closes at `explosive_until`.
  - Params: `explosive_runner: bool = False`, `explosive_frac: float = 1.25`, `explosive_until: int = 900`.
  - Test: `test_explosive_runner`. ADR5 = 40 with a 45-pt range by 10:00 and a new high at 11:55: the runner is open at 12:01 and closed at 15:00. On a 25-pt day it is closed at 12:00.

### 118. L16-adr-contraction-runner
- **rule_id / kind:** L16. Missing condition. Scope: general. judgment = true.
- **Rule:**
  - (a) Flag: ADR5 contracted (FX < 60 pips; index [our interpretation]: bottom tercile of the 60-day ADR5) -> expect a large-range day soon in the IOF direction. This is a context tag, not a trigger.
  - (b) Trigger: if price has already covered >= ADR5 in the IOF direction by the New York open (FX ~07:00-08:00 NY; index [our interpretation] 09:30), bank most of the position and keep a runner exempt from the 12:00 am_exit, allowed to run to 13:00-14:00.
- **Sources:** cc09_008_cqf8nH54bb8 ~00:47:45.
- **Quote:** "we probably caught a tiger by the tail and we need to leave something on" (cc09_008).
- **Conflicts:** D16 am_exit=12:00 vs cc09_008 runner to 13:00-14:00.
- **Rulebook fix:** L16: add the contraction flag and the "ADR met by the NY open -> runner to 13:00-14:00" trigger, and list the D16 conflict.
- **BUILD SPEC (day_week_context + management_exits):**
  - day_week_context: a day tag `adr_contracted` = ADR5 in the bottom tercile of the last 60 days' ADR5 values (`adr5()` over a rolling window).
  - management_exits: with `adr_met_runner`, if at 09:30 the range from midnight in the bias direction is >= ADR5, AM positions get `am_exit` replaced by `adr_runner_until`, applied only to the last `runner_frac` of units after the closed fraction reaches >= 0.75.
  - Params: `adr_met_runner: bool = False`, `adr_runner_until: int = 840`.
  - Test: `test_adr_met_runner`. ADR5 = 30, midnight-to-09:30 rise = 32, long with 80% off by 11:00: the runner is open at 12:30 and closed at 14:00. With a 20-pt rise it closes at 12:00.

### 119. X11-last-hour-target-hit-done
- **rule_id / kind:** X11. Wrong. Scope: index. judgment = false.
- **Rule:**
  - From 15:00 on (the last hour, 15:00-15:50 per owner correction #1), if an open position reaches its planned target, close all remaining units at that target. Do not hold for an extension, because price tends to pull back into the range and leave a wick on the daily candle.
  - Before 15:00, a target hit is managed by the normal X3 partials rule, not by a forced exit.
  - Replace pm_done_by=900 ("exit at 15:00 if T1 filled") with "exit at target if the target is hit at or after 15:00".
  - Final flat time follows owner correction #1 (16:15 PM close) and T11.
- **Sources:** 006_VKkn8uckkW0 ~00:41:27.
- **Quote:** "if it gets to a Target like that be done be content with that because it's likely to pull back into the range" (006).
- **Conflicts:** cc10_012: on trend days the PM extreme forms at or after 15:00.
- **Rulebook fix:** X11: replace "target hit by 15:00 -> be done" with "a target hit at or after 15:00 -> close everything at the target". P1 bot item #10: replace the `pm_done_by=900` description.
- **BUILD SPEC (management_exits):**
  - Where: the ladder loop. With `last_hour_target_done` and `t >= last_hour[0]` (900), a fill of any rung closes all remaining units at that rung's price ("lh_target") instead of the rung's fraction.
  - `pm_done_by` stays as a test switch, documented as "15:00 deadline variant (not ICT's 006 rule)".
  - Params: `last_hour_target_done: bool = False`.
  - Test: `test_last_hour_target_done`. A PM long with 3 rungs:
    - rung 1 hit at 14:40 closes its fraction only;
    - rung 2 hit at 15:05 closes everything at rung 2's price.

### 120. X11-two-stage-pm-delivery
- **rule_id / kind:** X11. Missing rule. Scope: index. judgment = true.
- **Rule:**
  - Two-session profiles: if the PM move stalls before the 15m / 60m PD-array target and retraces, while the trade is not stopped and the PM entry array holds, keep the position and expect a second leg into the target during 15:00-16:00. Exit at the target, or flat by 16:00.
  - "Trade not stopped and PM entry array holds" is our interpretation. ICT's condition is the two-session up / down-close profile, with the 15m / 60m premium (bull) / discount (bear) array still unreached.
- **Sources:** cc10_014_yWBxZsbmK1U ~00:04:52.
- **Quote:** "look for an additional ramp up that last hour going into the close" (cc10_014).
- **Conflicts:** none.
- **Rulebook fix:** X11: add the two-stage PM delivery (cc10_014).
- **BUILD SPEC (management_exits):**
  - Where: PM positions on days tagged two-session (T13 profile classifier, day_week_context) with `pm_two_stage`. The X9 time stop and any stall exits (items 55, 99) are suspended until 15:00 while the final rung (a 15m / 60m `htf` array) is unhit and the close is above the PM entry array's far edge. From 15:00 normal rules apply. Flatten as usual.
  - Params: `pm_two_stage: bool = False`.
  - Test: `test_pm_two_stage`. A PM long that stalls at 14:20 and retraces without touching the entry array is still open at 14:50 with `time_stop_min=20`, and reaches the 60m target at 15:30.

### 121. T13-consolidation-pm-fizzle
- **rule_id / kind:** T13. Missing condition. Scope: index. judgment = true.
- **Rule:** On a consolidation profile the PM has three possible outcomes:
  - (a) run the lunch extreme, then reach for the day's opposite stops;
  - (b) run the intraday extreme, then reverse;
  - (c) the PM makes no move and drifts sideways from lunch into the close, because the AM already made all the movement.
  - Bot: if neither the lunch extreme nor the intraday extreme is swept after lunch, take no PM trade on a consolidation-profile day.
- **Sources:** cc10_013_P5pyzmgZA1s ~00:13:57.
- **Quote:** "it can make all the movement in the morning and then just fizzle out" (cc10_013).
- **Conflicts:** none.
- **Rulebook fix:** T13: add outcome (c) to the consolidation profile.
- **BUILD SPEC (day_week_context):**
  - Where: `blocked()` / the PM session gate. With `consol_pm_need_sweep`, on days tagged consolidation (section 3 X11c classifier at 13:30), PM setups are allowed only after a bar has traded beyond the lunch (12:00-13:30) high / low or the session high / low. Until then `done["PM"]` stays False but `_scan` rejects ("pm_fizzle").
  - Params: `consol_pm_need_sweep: bool = False`.
  - Test: `test_consol_pm_fizzle`. On a consolidation-tagged day, a PM setup at 14:10 with no sweep of the lunch extremes is rejected. After a 14:20 sweep of the lunch high, a short setup is allowed.

### 122. X10-pre-nfp-noon-exit
- **rule_id / kind:** X10. Missing condition. Scope: index. judgment = true.
- **Rule:** Short (long is the mirror). At about 12:00 ET (lunch), if:
  - (a) at least 2 planned targets have hit,
  - (b) price is near the far edge of the daily FVG being traded into,
  - (c) and the next session is NFP (or other high-impact news),
  - then assume the low of day is likely in. Close half of the remaining units and keep the rest under the existing stop.
  - Expect lunch to run the buy stops above the nearest short-term high. This sits alongside X10's close-before-noon rule.
- **Sources:** 050_F509lJRrYIM ~00:52:31.
- **Quote:** "I believe that we're probably at a low of the day because we're going into non-farm payroll Friday" (050).
- **Conflicts:** none.
- **Rulebook fix:** X10: add the event-eve noon half-close (050).
- **BUILD SPEC (news_calendar_times + management_exits):**
  - Where: just before the `am_exit` check (~2693), at the first bar >= 11:50, if `event_eve_noon` and `events(next_trading_day(day)) & {"jobs", "cpi", "fomc"}` and `pos["k"] >= 2` and price is within 25% of the daily FVG's far edge (`htf.table` arrays), `partial_close` 0.5 ("eve_noon").
  - With `am_exit_mode="close"` the rest then closes at 12:00 as today. This only changes behaviour when `am_exit` is off or day mode applies.
  - Params: `event_eve_noon: bool = False`.
  - Test: `test_event_eve_noon`. Thursday before NFP, a short with 2 rungs filled and price 1 pt above the daily FVG low halves at 11:50.

### 123. X10-cc-day-trade-exit-1400
- **rule_id / kind:** X10. Unlisted contradiction. Scope: general. judgment = false.
- **Rule:**
  - Option `day_exit=14:00` for the CC 2016 day-trader model: at the close of the first bar at or after 14:00 NY, close any open trade from that model, and allow no new entries for it after 14:00.
  - Keep the 2023 PM session (13:30-16:15) as a separate model.
  - Record this in Decision 16 as a CC-vs-2023 conflict and note the related cc10_014 consolidation-profile 14:00 exit (X11).
- **Sources:** cc03_001_UF5J0nEBc0E ~00:17:22.
- **Quote:** "intraday swing trading with exits by 2 pm new york time" (cc03_001).
- **Conflicts:** X11 / 2023: PM trades held to 15:00-16:00.
- **Rulebook fix:** D16: add option C, "CC 2016 day-trader model: flat by 14:00 (cc03_001)".
- **BUILD SPEC (management_exits):**
  - Where: trades from CC-model setups carry a `model` tag (turtle-soup variants `cc_limit` / `cc_1h_ob`, and other `cc_*` branches).
  - With `cc_day_exit > 0`, positions whose model starts with "cc_" close at the first bar with `t + tf >= cc_day_exit` ("cc_1400"), and CC setups are not armed after that time.
  - Params: `cc_day_exit: int = 0` (test 840).
  - Test: `test_cc_day_exit`. A `cc_limit` long open at 13:59 closes at 14:00. A 2023-model PM trade is unaffected.

### 124. X10-london-time-of-day-scaleouts
- **rule_id / kind:** X10. Missing rule. Scope: general. judgment = false.
- **Rule:** For positions opened in London (01:00-05:00):
  - take a partial at or just before 05:00 NY (cc08_001; cc08_007 says "at or just above the five o'clock hour"), because London lunch (05:00-07:00) tends to bring retracement, consolidation or reversal, and 04:30 / 05:00 releases are common;
  - take another partial at the short-term extreme forming into 07:00, because NY may reverse or retrace toward the 08:20 open;
  - take another during 10:00-11:00 while the leg is still moving in favour.
  - Ideally each coincides with an opposing PD array.
  - Treating 05:00-07:00 as no-new-entries is our interpretation, as is applying all of this to index futures (the source is FX).
- **Sources:** cc08_001_-cXnnHjy9s0 ~00:18:01; cc08_007_5Z_3NbclMSY ~00:18:59.
- **Quote:** "take something at or just before 5 a.m just in case we get a reversal" (cc08_001).
- **Conflicts:** none.
- **Rulebook fix:** X10 / T3: add the London time-of-day scale-outs and the London lunch window (cc08_001, cc08_007).
- **BUILD SPEC (management_exits):**
  - Where: positions from the London session (London SB, `session="LON"`, built with `am_exit_extras`).
  - With `london_tod_partials`, `partial_close` `london_tod_frac` at the first bar >= 04:55 ("lon_0500"), again at the first bar >= 06:55 ("lon_0700"), and again in 10:00-11:00 on the first bar that makes a new extreme ("lon_1000"). Each fires once and only if units remain.
  - Params: `london_tod_partials: bool = False`, `london_tod_frac: float = 0.25`.
  - Test: `test_london_tod`. A London long filled at 03:10 is reduced at 04:55, at 06:55 and on a 10:20 new high.

### 125. B17-consolidation-no-runners
- **rule_id / kind:** B17. Shortened. Scope: index. judgment = false.
- **Rule:**
  - While price is inside a multi-day daily consolidation range (B17), or the day is flagged consolidation: take partials at intraday targets (bulk at T1), no runners toward weekly or monthly objectives, and don't count on the farther pool.
  - After a buy-side bump (including the 14:00 OB re-entry), expect a sharp drop that may leave the farther high untouched (048 ~1:51:24; 053 ~9:25).
  - [Bot mapping: HTF targets and supercharge off is ours.]
- **Sources:** 048_gGxVE8zUIRQ ~01:51:24; 053_VSSwM6rDIg0 ~00:09:25.
- **Quote:** "you don't marry any trade and turn it into a long-term position" (048).
- **Conflicts:** none.
- **Rulebook fix:** B17: add the management consequence (bulk at T1, no HTF runners) for daily consolidation.
- **BUILD SPEC (targets_partials):**
  - Where: `_split` / target merge. With `consol_no_runner`, on days where the `htf.table` daily state is inside a multi-day range (the B17 tag), use `ladder_fracs_slow` (80/20), drop htf-kind final rungs (`htf_targets`, `final_htf`, `runner_htf`), and set `runner_frac = 0`.
  - Params: `consol_no_runner: bool = False`.
  - Test: `test_consol_no_runner`. On a B17-tagged day a long's ladder has no weekly-array rung and uses 80/20. On an untagged day it is unchanged.

### 126. N8-choppy-week-no-hold
- **rule_id / kind:** N8. Missing condition. Scope: index. judgment = true.
- **Rule:**
  - If on consecutive days each session first takes the prior day's high (in a bearish week; the prior day's low in a bullish week) before moving in the bias direction, classify the week as choppy delivery.
  - Take intraday targets only, and hold no runners overnight or multi-day.
  - Cross-reference N8 Seek & Destroy and N7 August, which add the seasonal context and the smaller size.
- **Sources:** 079__NWG_eJRBpU ~00:21:40.
- **Quote:** "every day the previous days high was taken out ... preventing anyone with a short-term Traders mindset" (079).
- **Conflicts:** none.
- **Rulebook fix:** N8: add the daily signature of choppy weekly delivery (079).
- **BUILD SPEC (day_week_context):**
  - Where: the `BT.run` weekly state. Tag `choppy_week` after 2 consecutive days in the week where the session first traded beyond the prior day's high (bearish bias) or low (bullish bias) before the day's extreme in the bias direction formed.
  - On a tagged day, `consol_no_runner` behaviour (item 125) applies, plus `runner_frac = 0`.
  - Params: `choppy_week_tag: bool = False`.
  - Test: `test_choppy_week`. A bearish week where Monday and Tuesday each took the prior day's high first is tagged on Wednesday, and Wednesday's ladder has no runner.

### 127. new-scalp-fixed-1to1-2h
- **rule_id / kind:** X3 / new. Unlisted contradiction. Scope: general. judgment = true.
- **Rule:** Scalp class. The sources are cc09 FX lessons, out of the M17 scope; index use is our interpretation, applied where the rulebook already names a "scalp" mode (B14, B17 sloppy_mode, N8).
  - Time entries on 5m. R:R about 1:1 (stop distance = target distance, occasionally slightly better).
  - Expected hold is 1-2h or less, with about 2h as the maximum, so exit at market 120 min after the fill.
  - FX size is 15-30 pips. The Asian turtle-soup variant (cc09_003) is a fixed 20 stop / 20 target, single exit, not graduated. Index size [our interpretation]: fixed ES pts or a fraction of ADR5.
  - A single full exit with no partials is ICT's for the Asia setup. Applying it to other scalps (and no BE or adds) is our interpretation.
  - Parameter exit_mode='fixed_1to1' applies only to setups tagged scalp.
- **Sources:** cc09_003_km0haQkTalc ~00:04:51; cc09_006_OVfn-gDk2dE ~00:03:58.
- **Quote:** "it's a fixed Target we are not graduating it" (cc09_003).
- **Conflicts:** the X3 / D13 / X4 ladder, BE and runner defaults. See also item 5 (cc10_008 scalps rest the limit at 2x the objective).
- **Rulebook fix:** define the scalp class (1:1, 5m timing, ~2h max hold, single exit for Asia scalps) where B14 / B17 / N8 refer to "scalp".
- **BUILD SPEC (management_exits + targets_partials):**
  - Where: positions with `pos["trade_mode"] == "scalp"` (set when `sloppy_mode == "scalp"` or an N8 / B14 scalp day applies, and `scalp_mode` is on):
    - a single rung at `avg + (avg - stop)` (1:1, kind "fixed");
    - no `be_on`, no trail, no adds;
    - time exit at `fill_t + scalp_max_min`.
  - Params: `scalp_mode: str = ""` ("" / "fixed_1to1"), `scalp_max_min: int = 120`.
  - Test: `test_scalp_mode`. A scalp long with risk 3 has a single rung at avg + 3, no adds arm, and it closes at fill + 120 min if neither the target nor the stop hits.

### 128. fx-asia-open-scalp-full-exit
- **rule_id / kind:** new. Missing rule. Scope: fx_only. judgment = false.
- **Rule:** [fx_only; out of bot scope per M17]
  - Asia-open scalp: only when price hovers just above an HTF discount array that New York failed to reach (or on a reversal profile), use the Asia open to buy, expecting the day's low.
  - Target 15-20 pips and exit 100% at target, with no runner and no second leg.
  - Our interpretation: be flat before 00:00 NY, because the London Judas swing after midnight tends to stop out held positions.
- **Sources:** cc09_006_OVfn-gDk2dE ~00:30:08.
- **Quote:** "take full exits on scalps in this time of day in other words don't leave portions on" (cc09_006).
- **Conflicts:** none.
- **Rulebook fix:** M17: add the Asia-open scalp exit under the fx-only list.
- **BUILD SPEC:** none (fx_only).

### 129. new-friday-near-draw-shallow-entry
- **rule_id / kind:** new. Missing rule. Scope: index. judgment = true.
- **Rule:**
  - If it is Friday and price is close to the HTF draw (our proxy: distance to the draw < 1x the A-B leg), don't wait for a deep retrace or a breaker MT / retest.
  - Use the shallowest entry: inside the A-B leg's up-close candles (the upper part of the breaker) or its first FVG (070 ~47:00-47:58). [Threshold ours.]
- **Sources:** 070_1HtRfFYiwO0 ~00:47:11.
- **Quote:** "it's really close to that June 16th High anyway so we don't want to see any deep retracements" (070).
- **Conflicts:** none.
- **Rulebook fix:** M4 / E-entries: add the Friday near-draw shallow-entry rule (070).
- **BUILD SPEC (entries_stops_sizing):**
  - Where: the `_scan_core` entry block (~3540). With `fri_shallow`, on a Friday where |draw - price| < the A-B leg height (`levels.breaker_zone` leg), the entry = the first FVG's near edge in the A-B leg (or the breaker's upper edge for longs) instead of `entry`/MT. `leg_pd` is skipped for that trade.
  - Params: `fri_shallow: bool = False`.
  - Test: `test_fri_shallow`. A Friday long with an 8-pt leg, the draw 6 pts away and a first FVG 4485-4487: the entry is 4487. On Thursday, the default entry applies.

---

## G. Trade discipline (re-entry, broker failure, recovery, scenario checks)

### 130. new-no-close-to-reenter
- **rule_id / kind:** new. Missing rule. Scope: general. judgment = false.
- **Rule:**
  - A manual or abort close (X6-X9) means the trade's direction is no longer wanted.
  - Never close a position in order to re-enter the same direction at a better price; to improve the average, add to the open position instead.
  - After an abort close, no same-direction re-entry on that leg. X13's half-risk re-entry applies only after a stop-out of an idea that has not unraveled.
  - A reversal after an abort follows D18's "offside flip" option.
- **Sources:** 085_6-KNSUN-UaU ~00:13:50.
- **Quote:** "I would never do that I would never close the trade if I want to add more to it" (085).
- **Conflicts:** X13 / cc03_003 allow a same-direction re-entry after bailing, on a new continuation pattern at half risk.
- **Rulebook fix:** X13: add "a manual or abort close abandons the direction for that leg (085); re-entry only after a stop-out".
- **BUILD SPEC (management_exits):**
  - Where: `_after_close` (~1858). With `abort_blocks_side`, if the last exit reason is in the abort set ("abort", "ce_close", "breaker_mt", "pd3*", "chop_close", "htf_stall", "time", "slow_ref", "lost_hi", "hh_low", "stall_reh"), set `state["blocked_side"][session] = tr.side` until a new structure shift in the same direction forms after the close (a new MSS bar index > the close index).
  - `reentry_half` is not applied after these exits.
  - Params: `abort_blocks_side: bool = False`.
  - Test: `test_abort_blocks_side`.
    - A long closed by `fvg_abort` blocks a long setup 3 bars later on the same leg;
    - a long stopped out is allowed to re-enter at half risk;
    - a short after the abort is allowed.

### 131. new-no-working-stop-close-exit
- **rule_id / kind:** new. Missing rule. Scope: general. judgment = true.
- **Rule:**
  - If the protective stop and target cannot be placed or confirmed at the broker after entry, do not hold for the far target.
  - Watch the position by hand, close at once if price moves against the entry, and exit everything at the nearest liquidity objective in the trade direction (the nearby low or high where the first partial would have gone).
  - Source: 093, one live-trade anecdote, so this is a judgment call.
- **Sources:** 093_CcNOk_3O5wk ~00:14:12.
- **Quote:** "I like to just take a very close proximity exit to this low here" (093).
- **Conflicts:** none.
- **Rulebook fix:** add an operational rule under E1: "no working stop at the broker -> nearest-objective full exit (093)".
- **BUILD SPEC (management_exits, live / paper only):**
  - Where: `paper.py` order handling. After an entry fill, if the stop order acknowledgement is not received within `stop_ack_sec`, mark the position `unprotected`:
    - cancel the ladder except rung 1 and resize rung 1 to 100%;
    - a bar close against the entry by more than 1 tick closes at market.
  - The backtest is unaffected.
  - Params: `stop_ack_sec: int = 0` (0 = off; test 10).
  - Test: `test_unprotected_exit` (paper-broker mock). A missing stop acknowledgement turns the ladder into one 100% rung at rung 1. An adverse close exits at market.

### 132. new-drawdown-recovery-exit
- **rule_id / kind:** new. Missing rule. Scope: general. judgment = false.
- **Rule:** Re-entry after a loss at half risk.
  - Mode 'new' (bot default): once open profit is at least the unrecovered loss (2R at half risk), close 100% and stand aside.
  - Mode 'experienced': at entry + 2R, move the stop to entry + 2R minus 1 tick and never below it; take full profit at entry + 3R.
- **Sources:** cc02_005_vWDElb65YHg ~00:11:33, ~00:11:06.
- **Quote:** "as your developing Trader you want to just take it off the table and just be thankful that you got it back" (cc02_005).
- **Conflicts:** none.
- **Rulebook fix:** E10 / X13: add the recovery-based exit (cc02_005).
- **BUILD SPEC (management_exits):**
  - Where: `_after_close` stores `state["unrecovered"]` = the $ loss of the last losing trade that session. The re-entry (X13b `reentry_half`) position gets `pos["recover"]` = that amount.
  - With `recovery_exit="new"`, when open $ profit >= `recover`, close all ("recovered") and set `done[session] = True`.
  - With "experienced": at +2R, `raise_stop(pos, avg + 2R - tick)`; a single rung at +3R.
  - Params: `recovery_exit: str = ""`.
  - Test: `test_recovery_exit`. A $1,000 loss, then a re-entry at half risk ($500 = 1R): "new" closes at +$1,000 open profit and ends the session. "experienced" locks +2R - tick and exits at +3R.

### 133. new-live-vs-analysis-mismatch
- **rule_id / kind:** new. Missing rule. Scope: general. judgment = true.
- **Rule:**
  - Before the session, record the expected scenario (bias, draw, expected raid side).
  - If live delivery clearly contradicts it before entry, cancel pending orders and stand aside, or switch sides only if a complete fresh setup forms. Example: the pool on the draw side is run first with displacement and a body close beyond it.
  - Do not hold an idea against what price is showing.
  - The exact contradiction triggers are our interpretation.
- **Sources:** cc01_003_B7_cjybYQ0g ~00:24:16.
- **Quote:** "you won't have the flexibility to switch gears or go to the sidelines" (cc01_003).
- **Conflicts:** cc07_008 (commit to the weekly idea until it no longer makes sense), which is compatible (item 134).
- **Rulebook fix:** add to B-rules: "live delivery contradicting the pre-session scenario -> cancel pending and stand aside (cc01_003)".
- **BUILD SPEC (bias_htf):**
  - Where: run_day at the session start stores `scenario = (want, draw, raid_side)` from `htf.table` / the bias block (~764-769). With `scenario_check`, if the draw-side pool (the pool between price and the draw) is taken first with a close beyond it and a same-direction gap, before any fill, then:
    - drop `pending`;
    - set `done[session] = True`, unless `scenario_flip` is on, in which case the bias for the rest of the session flips to the other side (new setups only).
  - Params: `scenario_check: bool = False`, `scenario_flip: bool = False`.
  - Test: `test_scenario_check`. For a short-bias day (raid side = buy-side first, draw = PDL), a break of the PDL with a close below it and a gap before any buy-side raid cancels the pending short-side order and ends the session. With flip on, long setups are allowed.

### 134. new-weekly-idea-persistence
- **rule_id / kind:** new. Missing rule. Scope: general. judgment = true.
- **Rule:**
  - Once the weekly bias is set, a Tue / Wed run beyond Monday's extreme against the bias is not by itself a flip: keep the weekly idea.
  - Drop it only when it no longer makes sense, i.e. a stated close-based invalidation (B7 / B8) or a recognized mid-week weekly reversal.
  - This fits cc01_003: both say hold the idea until price clearly contradicts it.
- **Sources:** cc07_008_LBlK6JB0QS0 ~00:33:56.
- **Quote:** "come hell or high water stick to that until it no longer makes sense" (cc07_008).
- **Conflicts:** cc01_003 (switch gears when live delivery contradicts the analysis); compatible.
- **Rulebook fix:** B9 "Not a flip" list: add "a Tue/Wed run of Monday's extreme against the weekly bias (cc07_008)".
- **BUILD SPEC (bias_htf):**
  - Where: `htf.table` weekly bias column / `_flip` (~253). With `weekly_persist`, a Tue / Wed daily close beyond Monday's extreme against the weekly bias does not change the weekly bias. Only the `flip_triggers` (close-based) do.
  - Today `weekly_bias` re-reads the week on each day.
  - Params: `weekly_persist: bool = False`.
  - Test: `test_weekly_persist`. A bearish week whose Tuesday trades and closes above Monday's high keeps the bearish weekly bias on Wednesday. A `flip_close_above` trigger flips it.

---

## H. Swing, position and other markets (M17-parked studies, bonds)

### 135. new-htf-partial-and-readd
- **rule_id / kind:** new. Unlisted contradiction. Scope: general (M17-parked). judgment = true.
- **Rule:** Position or swing trade in the primary trend.
  - At a level where resistance or a retracement is reasonably expected (an opposing HTF PD array, an old high or low, or the ~3-4 month quarterly-shift turn), take 1/4 to 3/4, or all, off.
  - When the retracement reaches a logically timed level (a discount PD array, or back to the original daily down-candle opening price), re-add the same size or slightly more.
  - Repeat until the monthly / weekly premium array.
  - Do not move the stop to BE early on HTF trades.
  - Parked with the swing idea; E12 still applies intraday.
- **Sources:** cc05_001_n7SPAK_tpN8 ~00:06:47; cc05_013_crPpMwgwa7k ~00:19:01; cc05_016_vb_Yc-gCBfU ~00:04:52.
- **Quote:** "taking some of the position off waiting for that retracement and then going back in" (cc05_001).
- **Conflicts:** E12: no adds after partials (006).
- **Rulebook fix:** M17: add the HTF partial-and-re-add rule and list the E12 conflict (intraday vs position).
- **BUILD SPEC (bias_htf, study only):**
  - Where: `swing_mgmt_study` (item 13) `readd=True`:
    - at each opposing daily / weekly array (from `htf.table`), close `readd_frac`;
    - re-add the same size with a limit at the original entry candle's open, or at the first daily bullish array touched after the partial;
    - stop at the initial level until `pos_r >= swing_be_r`;
    - final exit at the monthly / weekly premium array.
  - Study config: `readd_frac: float = 0.5`.
  - Test: `test_swing_readd`. A path with partial -> retrace to the entry open -> continuation shows size back at 100% after the re-add, and E12's intraday rule is untouched (separate code path).

### 136. new-position-hold-horizon
- **rule_id / kind:** new. Missing rule. Scope: general (M17-parked). judgment = true.
- **Rule:** Quarterly-shift position trade.
  - Plan a horizon of about 3 months (~63 trading days, our conversion) and expect completion in about half that; some run the full 3 months or a little longer.
  - Hold through intermediate retracements and do not move the stop to BE until price has moved a significant distance.
  - Exit at the target, the stop, or partials at logical levels (with re-adds).
  - Trade with the long-term trend; never pick tops. Parked with the swing idea.
- **Sources:** cc05_007_N8_8tEw2_44 ~00:06:55; cc05_013_crPpMwgwa7k ~00:27:13.
- **Quote:** "my time Horizon is about three months" (cc05_007).
- **Conflicts:** none.
- **Rulebook fix:** M17: add the position holding horizon.
- **BUILD SPEC (bias_htf, study only):**
  - Where: `swing_mgmt_study` `max_hold_days=63`: positions still open at day 63 close at market. Report the distribution of days-to-target (median vs the 30-day expectation).
  - Study config: `max_hold_days: int = 63`.
  - Test: `test_position_horizon`. A synthetic position never hitting target or stop closes on day 63, and the report shows days_held = 63.

### 137. M17-daily-limit-repeat-to-weekly
- **rule_id / kind:** M17. Missing rule. Scope: general (M17-parked). judgment = true.
- **Rule:**
  - Long target = the weekly premium PD array (e.g. a weekly bearish OB).
  - Until it is reached, each new closed down-close daily candle (with the other conditions met) arms a new buy limit at its close. Stop arming once the target is reached.
  - Expect profit within 1-2 daily bars after a fill; otherwise treat the setup as suspect (our interpretation).
  - Shorts mirror.
- **Sources:** cc05_017_WDattjFvNBc ~00:09:16, ~00:02:45.
- **Quote:** "you start seeing profitability almost immediately" (cc05_017).
- **Conflicts:** none.
- **Rulebook fix:** M17: add the long-term limit-at-down-close model with its weekly target and quick-response expectation.
- **BUILD SPEC (bias_htf, study only):**
  - Where: `study.py` `daily_limit_model(df_daily, weekly_arrays)`. While monthly / weekly bias (`htf.table`) is bullish and the weekly bearish array above is untouched, each down-close daily candle arms a limit at its close for the next day.
  - Each fill is tracked as a separate position with the target at the weekly array and a stop below the week's low. A position with no close above the fill price within `quick_bars` days is tagged "suspect".
  - Study config: `quick_bars: int = 2`.
  - Test: `test_daily_limit_model`. Three down-close days before the weekly array produce three limit entries. Arming stops after the array is touched.

### 138. M17-swing-horizon
- **rule_id / kind:** M17. Missing rule. Scope: general (M17-parked). judgment = true.
- **Rule:**
  - Swing trades: planned hold of 2 weeks to about 1 month. Do not judge or time-stop them on intraday or few-day horizons.
  - Take partials at intermediate pools (e.g. 4h relative equal lows) and hold the rest to the HTF array.
  - A trade that finishes in under about 2 weeks is labelled short-term (reporting only).
- **Sources:** cc06_004_osRUnIpGIJ0 ~00:30:09; cc06_005_soY9zX3gt2U ~00:21:27.
- **Quote:** "preferably two weeks to about a month" (cc06_004).
- **Conflicts:** none.
- **Rulebook fix:** M17: add the swing holding horizon.
- **BUILD SPEC (bias_htf, study only):**
  - Where: `swing_mgmt_study` `max_hold_days=22` for swing mode, no time stop before day 10, partials at 4h `rel_eq` pools (`levels.equal_levels` on 4h bars). Report the label "short_term" when days_held < 10.
  - Test: `test_swing_horizon_label`. A swing closed on day 6 is labelled short_term. One closed on day 15 is labelled swing.

### 139. B6-swing-in-trade-confirmation
- **rule_id / kind:** B6. Missing rule. Scope: general (swing). judgment = true.
- **Rule:** While long:
  - each 4H bearish breaker, mitigation block or up-close candle above should be traded through;
  - old highs should break with expansion and no retrace past 50% of the leg (our interpretation);
  - new bullish arrays should hold on retests.
  - If a 4H premium array holds and price retraces deeply, reduce or manage. Short mirror.
- **Sources:** cc06_003_g--tikwaupk ~00:24:16.
- **Quote:** "always confirm lower time frame for our premium arrays give way or fail as price moves in your favor" (cc06_003).
- **Conflicts:** none.
- **Rulebook fix:** B6: add the swing in-trade confirmation check (cc06_003).
- **BUILD SPEC (bias_htf, study only):**
  - Where: `swing_mgmt_study` `confirm4h=True`. For each 4h bearish array above entry (`levels.breakers`, `levels.mitigation_blocks` on 4h bars), record whether price traded through it within the trade.
  - If price touches an array, fails to trade through it, and then retraces more than 50% of the leg from the entry low to the touch high, close half ("4h_fail").
  - Test: `test_swing_confirm4h`. A 4h breaker that holds, followed by a 60% retrace, halves the position. A breaker that is traded through does nothing.

### 140. X3-swing-htf-array-scaleout
- **rule_id / kind:** X3. Shortened. Scope: general (swing). judgment = true.
- **Rule:**
  - Swing long, final target = the monthly premium array.
  - Take partials at each 4H, then daily, then weekly premium array reached, in price order, with size falling so that 25% or less remains inside the weekly / monthly premium range (our interpretation).
  - Short mirror.
- **Sources:** cc06_003_g--tikwaupk ~00:23:00.
- **Quote:** "you're going to take something off at the premium arrays on the four hour chart and at the daily chart and at the weekly chart" (cc06_003).
- **Conflicts:** none.
- **Rulebook fix:** X3: add the swing HTF-array scale-out ladder (cc06_003).
- **BUILD SPEC (bias_htf, study only):**
  - Where: `swing_mgmt_study` `ladder="htf_arrays"`. Rungs = the 4h, daily and weekly bearish arrays between entry and the monthly target, in price order. Fractions are set so that the remaining size is <= 25% once the weekly array is reached (e.g. 0.3 / 0.25 / 0.2, then 0.25 to the monthly target).
  - Test: `test_swing_htf_ladder`. Arrays at 4h 1.10, daily 1.12, weekly 1.15 and a monthly target of 1.20 give rungs in that order, with 25% left after 1.15.

### 141. X1-swing-opposing-ob-ladder
- **rule_id / kind:** X1. Missing rule. Scope: general (swing). judgment = true.
- **Rule:**
  - Swing short at a monthly premium array:
    - T1 = the MT of the nearest monthly last down-close candle below, even if already touched once;
    - T2 = that candle's low, especially when it forms relative equal lows with a neighbour.
  - Mirror for longs.
- **Sources:** cc06_006_JAjL7rUX2Iw ~00:26:29.
- **Quote:** "the first one you're going to be looking for the mean threshold of that last down candle" (cc06_006).
- **Conflicts:** none.
- **Rulebook fix:** X1 / L14: add the opposing-OB target ladder (MT, then low) for swing trades (cc06_006).
- **BUILD SPEC (bias_htf, study only):**
  - Where: `swing_mgmt_study` `ladder="opp_ob"`. The monthly OB comes from `levels.order_block` on monthly bars resampled from daily. T1 = its body MT (`mt_mode`), T2 = its low (plus the neighbouring low if within `eq_tol`).
  - Test: `test_swing_opp_ob`. A monthly down-close candle with body 1.3000-1.3400 and a low of 1.2950 gives rungs at 1.3200 and 1.2950.

### 142. T11-weekly-template-hold
- **rule_id / kind:** T11. Unlisted contradiction. Scope: general (M17-parked). judgment = false.
- **Rule:**
  - Weekly-template mode only (currently out of scope per M17): a position opened on the Tue / Wed weekly extreme is held overnight until the weekly target (a lower-TF opposing PD array overlapping a 1.27 / 1.68 projection) is hit, or into Thursday / Friday.
  - Day-trade mode keeps T11.
  - List as a conflict under T11 / M17. Weekend flattening is our assumption.
- **Sources:** cc07_003_hbE8S5FSdtQ ~00:13:14.
- **Quote:** "you hold for the opportunity to unfold until Thursday and maybe into Friday" (cc07_003).
- **Conflicts:** T11: flat before 16:00, no overnight holds.
- **Rulebook fix:** T11 / M17: list the weekly-template overnight hold as a conflict (cc07_003).
- **BUILD SPEC (bias_htf, study only):**
  - Where: `study.py` `weekly_template_study`. A Tue / Wed entry at the weekly extreme (daily bars, the `htf.table` weekly profile) is held across days until the weekly target, the stop, or Friday's close.
  - Report the hold time and the outcome vs a same-day flatten.
  - Test: `test_weekly_template_hold`. A Tuesday short is still open on Wednesday and closes at Thursday's target. Without a target hit, it closes at Friday's close.

### 143. M17-cbdr-model-hold-to-array
- **rule_id / kind:** M17. Missing rule. Scope: fx_only. judgment = true.
- **Rule:** [fx-only] 0 GMT model exit:
  - No intraday management. Hold until price reaches the higher-timeframe objective: a premium PD array for longs, a discount PD array for shorts. This applies to the swing use and the single-day use alike (in the day use he says to use HTF objectives for profit and "go to sleep").
  - Stop = ADR5 from the entry.
  - Optionally split the entry: half at the 0 GMT open, half at a 10-20 pip limit beyond it.
  - An end-of-day exit is not in the source.
- **Sources:** cc08_008_1MnfiqKx5Uo ~00:14:07.
- **Quote:** "you just let it rip ... until it trades to a premium PD array" (cc08_008).
- **Conflicts:** none.
- **Rulebook fix:** M17: add the 0 GMT model exit (the claim called it a CBDR model; it is the 0 GMT model).
- **BUILD SPEC:** none (fx_only).

### 144. L9-bond-pm-far-edge-fill-target
- **rule_id / kind:** L9. Unlisted contradiction. Scope: bonds_only. judgment = false.
- **Rule:** Bonds only (cc10_007).
  - A PM long off the AM bullish OB takes its partial at the full fill (far edge, 154.13) of the overhead FVG between the AM-session high and the last up-close candle of the 08:00 hour.
  - The runner targets the 08:00-09:00 opening-range high, which in the example printed only in the evening / Asian session, after the day session.
  - The index default stays L9 (near edge / CE). Add a far-edge fill as a test switch and list the conflict.
- **Sources:** cc10_007_JpV-J31mxhg ~00:15:48.
- **Quote:** "you can take portions off once the fair value Gap is filled" (cc10_007).
- **Conflicts:** L9 / X3 (near edge / CE, never the exact FVG extreme; Ep 08) vs cc10_007 (a partial at the full FVG fill).
- **Rulebook fix:** L9: list the bonds far-edge fill as a conflict.
- **BUILD SPEC:** none (bonds_only). The index test switch already exists as section 3 L9 `fvg_remainder` (far-edge test); item 1's `fvg_target_level="deep"` with `fvg_deep_frac=1.0` covers it too.

### 145. bond-megatrade-fall-high-exit-and-roll
- **rule_id / kind:** new. Missing rule. Scope: bonds_only. judgment = true.
- **Rule:** Bonds only (cc11_004).
  - A mega-trade long from the May-June low (confirmed by 5 / 10 / 30-yr SMT) aims for the fall highs.
  - Expect the intermediate-term high in Sep-Oct, but the rally may last only 1-2 months (2012: failed after a turtle soup above an old high at a premium array; 2016: topped in July).
  - Exit on an intermediate-term high in Sep-Oct, or earlier on failure at an HTF premium array.
  - If the trade is still open when the September contract expires, roll into December.
  - After the high, only short-term / swing trades for the rest of the year.
- **Sources:** cc11_004_At43V93rnDQ ~00:07:02, ~00:20:59.
- **Quote:** "rolled into December delivery to get more of a move" (cc11_004).
- **Conflicts:** none.
- **Rulebook fix:** B23 (seasonals): add the bond mega-trade exit window and the contract roll.
- **BUILD SPEC:** none (bonds_only).
