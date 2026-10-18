# Rulebook gaps: Silver Bullet

Topic `silver_bullet`. Every item below is a verified gap between ICT's captions and `mentorship_rules.md`. When the checker gave a corrected rule, that corrected rule is the one written here; when it gave none, the claim's full rule is used. "[our interpretation]" marks thresholds or readings that ICT does not state.

Conventions:
- Times are New York. Params times are minutes from midnight (180 = 03:00, 570 = 09:30, 600 = 10:00, 660 = 11:00, 840 = 14:00, 900 = 15:00, 915 = 15:15, 945 = 15:45).
- Work package: **silver_bullet** (`rule_coverage.md` section 3) owns `sb_model.py` only and merges last. It calls the shared `_targets`, `_eq_levels`, `blocked()` and the `levels.py` / `setups.py` helpers; it does not edit them. Where a spec needs a change outside `sb_model.py` it names the owning package.
- `sb_model.py` works in side space (`sd.sign`, mirrored arrays): every long rule below is written once and gives the short by mirroring. Hooks: `run_sb` (window loop, pending order, position management), `_arm` (leg extreme `li`, MSS ref, FVG pick `gaps[-1]`, stop, room / draw checks), `immediate_rebalance`.
- New Params switches default off and go in a commented `# silver_bullet (rulebook gaps)` block at the end of `Params` (strategy.py ~65-705); string switches also go in the switch list (~722) for the sweeps.
- Already built and reused below: `sb_room_pts`, `sb_target_mode`, `sb_mgmt`, `sb_runner`, `sb_rebalance_ext` (M3.10), `sb_draw_pools_only` (A2), `sb_london`, `draw_lock` (#9), `htf_resist_cap` (#7), `am_exit` (#8), `ctx.chop` (#10), `levels.breaker_zone`, `levels.inversion_fvgs`, `levels.balanced_ranges` / `bpr_rule` (A11), `levels.order_block_blend`, `levels.wick_ce`, `levels.volume_imbalances`, `setups.disp_ok_sb`, `strategy._smt`. Still only specced in rule_coverage (not built): the M3 umbrella (`sb_mss_required`, `sb_fvg_pick`, `sb_one_per_day`, `sb_entry`, `sb_stop`), M3.5 (`sb_need_sweep`, `sb_sweep_max_pts`), M3.8 (057 stop), M3.9 (`sb_cascade`), M3.11 (`sb_runner_if_weekly`), D2 (`sb_fvg_in_window`, `sb_fvg_from`, `sb_evolve`). Specs below that touch these say so.
- Tests go in a new `tests/test_silver_bullet.py`, built on the synthetic-day helpers that `tests/test_review_fixes.py::test_sb_draw_mode_vs_fixed_and_rebalance_ext` uses (call `sb_model._arm` / `run_sb` directly). Each spec names its test.
- Items scoped `fx_only` or `needs_unavailable_data` get the rulebook fix only.

Summary: 22 items, 19 new build specs. Items without a build spec:
- 1 fx_only: L15-sb-fx-room.
- 1 needs unavailable data: M3-sb-entry-timeframe (sub-minute bars). Its 2m part is noted as an optional study.
- 1 already listed in rule_coverage with the same content: M3-sb-fvg-from-0930-leg. `sb_model.py` already arms from the 09:30 leg (`leg_from=570`, docstring "it may come from the 09:30-10:00 leg (058 ~44:37, 065B)") and D2's `sb_fvg_from` switch covers the in-window-only alternative. Only the rulebook text is new.

---

### 1. M3-sb-ifvg-entry-array
- **rule_id / kind:** M3 / missing_condition. Scope: index. judgment = true.
- **Rule:** Inside an SB window, besides the new displacement FVG: an earlier same-day FVG (often 5m) extended forward that the in-window displacement closes through becomes an IFVG (A8 validity applies). Its near edge is a valid SB entry. Highest grade when it overlaps a breaker (A13) in the bias direction (076's "Reaper", NQ; 092 London 03:07 with a 30s FVG inside the overlap). Entry: a limit at the near edge, or a market buy on a down-close candle trading into it for longs (076); mirror for shorts. Stop below the entry candle's low (076) or beyond the breaker. Any add on a later FVG is optional; it was not taken in 076. L15 room still applies. Tag `sb_ifvg`.
- **Sources:** 044_LN1nfYp4dBw ~38:17, ~43:20, ~58:32 (commentary, not a taken trade; he was reading a 5m chart); 076_cgsltOB736E ~23:03-29:12 (NQ); 092_9MLRE-n6St8 ~21:36-22:42, ~39:47-49:16.
- **Quotes:** "what time do we trade for a silver bullet 10 o'clock to 11. displacement down closed candle as it's trading down I'm buying it" (076).
- **Conflicts:** M3 says the first FVG left by in-window displacement is the entry; these examples enter on a pre-existing array that the displacement inverts. M10 (IFVG) and M0 ("any PD array") exist but are not tied to the SB.
- **[our interpretation]:** the "overlaps a breaker" test (any price overlap between the IFVG and `breaker_zone`); "same-day" = since 18:00 ETH start.
- **Rulebook fix (M3):** add "Entry arrays: besides the new displacement FVG, an earlier same-day FVG (often 5m) that the in-window displacement closes through is an IFVG (A8) and its near edge is an SB entry; best when it overlaps a breaker in the bias direction (076 'SB on steroids', 092 London). Limit at the near edge, or market on a down-close candle into it (076). Stop below the entry candle's low or beyond the breaker. Room (L15) applies."
- **BUILD SPEC (silver_bullet):**
  - Where: `sb_model._arm`, after the MSS test (`kb` known). When `p.sb_ifvg`, build bearish FVGs (side space: gaps facing against the trade) from 1m bars since the ETH start plus 5m FVGs from `ctx` resampled bars (`L.fvgs` on the 5m frame, known only after the 5m candle closes). Keep those created before `li` and still open at `li`, whose far edge the displacement closed through between `li` and `i` (`levels.ifvg_passes` / A8 validity from setups_models `ifvg_filter`). Candidate entry = IFVG near edge (top in side space after inversion = the old SIBI's high for longs). Compare with the normal FVG candidate; `p.sb_ifvg="add"` keeps both and takes the one with the later formation, `"prefer"` takes the IFVG when present.
  - Grade: if `L.breaker_zone(o,h,l,c, k0, li, i, "bull")` overlaps the IFVG, tag `sb_ifvg_breaker` (the Reaper case; reuse `levels.reaper` when `p.sb_ifvg_reaper`).
  - Stop: `p.sb_ifvg_stop = "candle" | "breaker"`: low of the bar `i` that trades into the IFVG minus `stop_buffer`, or the breaker zone low minus `stop_buffer`.
  - Market entry (076): `p.sb_ifvg_market` - in `run_sb` pending block, fill at the close of a down-close bar inside the window whose low trades into the IFVG.
  - Tag: Trade field `sb_entry_kind` ("fvg" / "ifvg" / "ifvg_breaker"; add it with a default in the owner-directives block of `Trade` ~935).
  - Params: `sb_ifvg: str = ""` ("" / "add" / "prefer"), `sb_ifvg_reaper: bool = False`, `sb_ifvg_stop: str = "candle"`, `sb_ifvg_market: bool = False`.
  - Test: `test_sb_ifvg_entry_through_old_5m_fvg`. A 5m SIBI at 08:30 stays open; at 10:05 a displacement closes above its high; a limit at that high fills at 10:20 and is tagged `ifvg`; with `sb_ifvg=""` the same day takes only the new FVG. Second case adds a bullish breaker overlapping the IFVG and checks the `ifvg_breaker` tag and breaker stop.

### 2. L15-sb-room-overshoot
- **rule_id / kind:** L15 / shortened. Scope: index. judgment = true.
- **Rule:** The 10-handle framework is the best-case delivery to and through the draw, not the entry-to-exit range. best_case = |D - E| + overshoot beyond a liquidity pool (059 uses ~3 ES pts; the amount is our interpretation of one example). The framework check (>= 10 ES pts) uses best_case; the take-profit stays at the pool or ~5 pts. The conflict matters only under the 10-pt setting (M3 and the L15 switch), not under the default `min_draw_pts` / `sb_room_pts` = 5.
- **Sources:** 054_tRq1hyGGtl4 ~0:36-1:45, ~11:03-11:14; 059_ZfnY2SH3G24 ~20:34-21:12.
- **Quotes:** "this framework is the best case price delivery that you expect to see not ... your actual trade entry to exit range" (054).
- **Conflicts:** L15 (owner correction #2) and M3 measure min room to the draw's exit price; 054/059 count the overshoot beyond the pool. With room = 10 the bot rejects 059 (7.75 pts to the pool).
- **[our interpretation]:** overshoot = 3 ES pts, only for pool kinds (not for FVG/array draws).
- **Rulebook fix (L15 / M3):** "The 10-handle (and 5-handle) framework is the best-case run, measured to the pool plus the expected run through it (059: stops at 4120, ~3 handles beyond counts), not to the exit price. The exit stays at the pool / ~5 pts."
- **BUILD SPEC (silver_bullet):**
  - Where: `sb_model._arm`, both room checks (`draw - entry < max(p.sb_room_pts, ext_pts)` in fixed mode, `t1 - entry < p.sb_room_pts` in draw mode). Replace the left side with `best = (raw_draw - entry) + (p.sb_room_overshoot_pts * p.es_pt if kind in POOL_KINDS else 0)`, where `raw_draw` is the draw level before `exit_before` / `pool_beyond` is applied (keep the raw `(v, kind)` of `dr[0]`). Exits (`t1`, ladder) unchanged.
  - Params: `sb_room_overshoot_pts: float = 0.0` (test 0 / 3).
  - Test: `test_sb_room_overshoot_059`. Entry 4127.75, sell-side pool 4120, `sb_room_pts=10`: no order with overshoot 0, order with overshoot 3 and `t1` still at the pool exit price.

### 3. L15-sb-room-untaken-target-org
- **rule_id / kind:** L15 / missing_condition. Scope: index. judgment = false (part (b) is our interpretation).
- **Rule:** Measure SB room from the entry to the nearest untaken pool or the near edge of an opposing FVG (the PM example used a discount FVG). The general "untaken target" rule is already in L14, so add only: (a) the room may not count past a low that was already swept; (b) if price at the window is consolidating inside today's ORG, the setup is not a classic SB [our interpretation of "inside of that opening range gap and we're consolidating"]; (c) a setup that fails these may be scalped to the nearer untaken lows, but it is not the classic 10-handle setup (bot default: skip). NWOG is not mentioned at this timestamp, so leave it out.
- **Sources:** 058_hcSGlyfgKgA ~54:20-55:20.
- **Quotes:** "10 handles is at this low or lower can it get below that I don't believe it can because we've already had this low taken out" (058).
- **Conflicts:** none.
- **[our interpretation]:** "consolidating inside the ORG" = the last N bars before the window open (default 6) all close inside the ORG and the window-open bar is inside it.
- **Rulebook fix (L15 / M3):** "Room counts only to the nearest untaken pool or the near edge of an opposing FVG, never past a low already swept today. Price consolidating inside today's ORG at the window = not a classic SB (058 ~54:43); it may be scalped to the nearer untaken pool (bot: skip)."
- **BUILD SPEC (silver_bullet):**
  - Where: `sb_model._arm` after `dr` is built. (a) When `p.sb_room_untaken`, take the first draw in `dr` as the room reference and drop any candidate beyond a pool already traded through between the ETH start and `i` (use the `seen` / `_thru` test `_targets` already applies to pools; extend it to the room reference so a far level beyond a swept pool cannot satisfy the room). Opposing FVG near edges come from `_targets` with the FVG kinds already returned; nothing new there. (b) When `p.sb_org_chop`, skip arming if today's ORG (`ctx.org[-1]`, known after 09:30) contains the closes of the `sb_org_chop_bars` bars before `a` and the bar at `a`; AM and PM windows both test the same ORG. (c) `p.sb_fail_mode = "skip" | "scalp"`: "scalp" places the order anyway with a single exit at the nearer untaken pool, half size (`shares // 2`, min 1 lot), tag `sb_scalp`.
  - Params: `sb_room_untaken: bool = False`, `sb_org_chop: bool = False`, `sb_org_chop_bars: int = 6`, `sb_fail_mode: str = "skip"`.
  - Test: `test_sb_room_not_past_swept_low_and_org_chop`. Short SB whose only 10-pt level lies beyond a low swept at 09:45: no order with `sb_room_untaken`. Second day consolidating inside the ORG at 10:00: no order with `sb_org_chop`, a scalp order with `sb_fail_mode="scalp"`.

### 4. L15-sb-fx-room
- **rule_id / kind:** L15 / missing_rule. Scope: fx_only. judgment = false.
- **Rule:** FX SB (out of bot scope): the framework (best-case delivery to the draw) must be >= 15 pips; the expected take is about 10 pips. Equivalences: 5 index handles = 10 pips, 10 handles = 20 pips. Windows are the same as for index. (Spread and runner details are not in the source.)
- **Sources:** 054_tRq1hyGGtl4 ~0:48-2:35; 058_hcSGlyfgKgA ~37:16.
- **Quotes:** "10 handles for indices is the same to me as 20 Pips in Forex" (054).
- **Conflicts:** none.
- **Rulebook fix (FX-only section, ~1243):** replace "pip-sized stops and room rules" with the numbers above.
- **BUILD SPEC:** none (fx_only).

### 5. M0-sb-no-sweep-discount-retrace
- **rule_id / kind:** M0 / unlisted_contradiction. Scope: index. judgment = false.
- **Rule:** Exception to M0 step 3 (switch `sb_require_sweep=False`): after the pool in the bias direction has been taken (048: buy-side run at 08:30), a retrace into a discount PD array (bullish breaker / the week's initial FVG) can stand in for the Judas raid. An unswept REL below need not be run. Then wait for the break of the opposing FVG (it must trade above it) and enter the first bullish FVG beyond it in 10:00-11:00. A breaker itself implies an earlier small low was taken, so the claim is only that the obvious REL is not required. Mirror for shorts.
- **Sources:** 048_gGxVE8zUIRQ ~6:54, ~26:50-27:40, ~1:36:06.
- **Quotes:** "Why didn't it go down here for these relative equal lows because it doesn't need to it was going down here to pick up discount pricing" (048).
- **Conflicts:** M0 step 3 requires a raid on the pool against the bias; 048's trade had none.
- **Rulebook fix (M0 step 3):** add "Exception (048 ~1:36): once the bias-side pool has run, a retrace into a discount breaker / the week's initial FVG replaces the raid; the obvious REL need not be swept."
- **BUILD SPEC (silver_bullet; builds on M3.5 `sb_need_sweep`, not yet built):**
  - Note: `run_sb` does not require a sweep today (it only tags `swept`), so the 048 trade is already allowed. The spec makes the exception explicit for when `sb_need_sweep=True`.
  - Where: `sb_model._arm`, where `swept` is computed. When `p.sb_need_sweep` and `swept == "none"`, accept the setup if `p.sb_sweep_alt == "discount_array"` and all of: (1) the bias-side pool (PDH / session high in side space) traded before `li` today; (2) the low at `li` sits inside a bullish `L.breaker_zone` or the week's first 1m FVG after the Sunday open (find it from `ctx` bars since the NWOG; levels_detectors has no helper, so compute it locally in `sb_model`); (3) `li` is in the discount half of the dealing range from the ETH start low to the session high [our reading of "discount"]; (4) the MSS reference is the opposing FVG's top (`setups.leg_sibi(h,l,o,c,k0,li)`) and the entry FVG's bottom is above it. Tag `swept="discount_array"`.
  - Params: `sb_sweep_alt: str = ""` ("" / "discount_array").
  - Test: `test_sb_no_sweep_discount_breaker_048`. Bias-side high run at 08:30, retrace into a bullish breaker without taking the REL below, break of the SIBI at 10:10, FVG fill at 10:25: an order with `sb_need_sweep=True, sb_sweep_alt="discount_array"`, none with `sb_sweep_alt=""`.

### 6. M3-sb-bpr-below-break
- **rule_id / kind:** M3 / shortened. Scope: index. judgment = false.
- **Rule:** A bullish FVG that sits below the level price was required to break (the opposing FVG/SIBI it had to trade above), and that is offset by a bearish FVG (BPR, A11), is not an SB entry, and price does not need to retrace to it, so don't use it as an expected retrace level. Valid SB entry = the first bullish FVG formed after the break, above the break level, entered 10:00-11:00. Mirror for shorts.
- **Sources:** 048_gGxVE8zUIRQ ~1:34:40-1:35:15.
- **Quotes:** "it can't be this as a fair value Gap because it's below what we're requiring to be broken to the upside ... it's a balanced price range" (048).
- **Conflicts:** none.
- **Rulebook fix (M3):** after "the FVG must sit beyond the break level" add "An FVG below the break level offset by an opposing FVG is a BPR (A11): not an entry, and not a level price must revisit (048 ~1:34:50)."
- **BUILD SPEC (silver_bullet):**
  - Where: `sb_model._arm`, the `gaps` filter. Today it keeps gaps with `g.top > ref`, which lets an FVG straddle or sit partly below the break. When `p.sb_bpr_exclude`: (1) the break level is `max(ref, opposing SIBI top)` where the SIBI is `setups.leg_sibi(...)` between `k0` and `li` if present; require `g.bottom > break_level` and `g.i >= kb` (formed after the break); (2) drop any gap that overlaps a bearish FVG formed since `k0` (`L.balanced_ranges(h, l, p.bpr_max_gap_bars, o, c, p.fvg_c2_dir)` overlap test). Excluded gaps are also removed from the "price must retrace" assumption: the evolving re-arm does not keep a pending order on them.
  - Params: `sb_bpr_exclude: bool = False`.
  - Test: `test_sb_bpr_below_break_not_entry`. A bullish FVG below the SIBI top overlapping a bearish FVG plus a second bullish FVG above the SIBI top after the break: with the switch the order is at the second FVG; without it at the newest open FVG (current behaviour).

### 7. A7-sb-immediate-rebalance-branch
- **rule_id / kind:** A7 / shortened. Scope: index. judgment = false (the tag and wider targets are our interpretation).
- **Rule:** In the SB window: an immediate rebalance (no FVG left) usually means no SB retrace fill, because price runs toward the larger target; don't chase it under SB rules (any market entry falls under M11 and is not from this source). If a standard FVG forms, take the simple SB: limit in the FVG, exit at the planned target, and you are done for the AM session (one AM SB trade a day is already in M3). The "low resistance" tag and the wider targets are our interpretation.
- **Sources:** 048_gGxVE8zUIRQ ~1:31:00-1:31:45, ~1:35:14.
- **Quotes:** "if it would have been an immediate rebalance there probably wouldn't have been a silver bullet trade" (048).
- **Conflicts:** none.
- **Rulebook fix (A7 / M3):** "Immediate rebalance in the SB window: usually no retrace fill (runaway); do not chase under SB rules. A standard FVG: take the simple SB to its target and be done for the AM (048 ~1:35)."
- **BUILD SPEC (silver_bullet; builds on M3.10 `sb_rebalance_ext`, built):**
  - Already covered: with no FVG `_arm` returns None, so no chase; M3.10 already extends the draw after an immediate rebalance. New parts only:
  - (a) Tag: when `immediate_rebalance(...)` is true in the window, set Trade `imm_rebal=True` (field exists, A7) on any SB trade of that window and log a no-trade row `sb_runaway` in the `locks`/log list when the window ends without a fill.
  - (b) "Done for the AM": `p.sb_am_done` - after an SB AM trade exits at `t1` or beyond, `backtest.combine` drops main-engine AM trades of the same day whose entry time is after the SB exit (combine is shared with setups_models; add the filter as a final pass keyed on `setup == "sb_am"`).
  - Params: `sb_am_done: bool = False`.
  - Test: `test_sb_am_done_drops_later_am_trades`. A day with an SB AM win exiting 10:40 and a main-engine AM entry at 10:55: dropped with the switch, kept without it.

### 8. M3-sb-supercharge-runner
- **rule_id / kind:** M3 / missing_condition. Scope: index. judgment = true.
- **Rule:** supercharge = daily not ranging AND day in Mon-Wed (through Wednesday NY) AND the weekly profile expects the week's low (high) early in the week (classic bullish: Tuesday London low), not yet clearly in AND the seasonal tendency (B23) agrees for the coming weeks. If supercharge: take a portion off at the SB window target and leave 1 contract as a runner to the HTF draw. Otherwise take the full exit at the SB target. (No "stop to BE after the first partial": ICT does not state it.)
- **Sources:** 048_gGxVE8zUIRQ ~2:02:20-2:03:30, ~2:13:30.
- **Quotes:** "a classic bullish weekly profile would be a Tuesday low of the week in London ... if the low really hasn't materialized ... by Wednesday ... Silver Bullet trades will be phenomenal" (048).
- **Conflicts:** none.
- **[our interpretation]:** "daily not ranging" = the daily table's `flip`/bias column non-zero and the last 3 daily bodies not all inside the prior 5-day range; "week's low not yet clearly in" = the week's low so far is not more than 0.5x ADR5 below the current price.
- **Rulebook fix (M3 exits):** replace "weekly profile aligned -> 1 runner" with the five conditions above (048 ~2:02).
- **BUILD SPEC (silver_bullet; extends M3.11 `sb_runner_if_weekly`, not yet built; seasonal input from bias_htf):**
  - Where: `sb_model.run_sb`, at fill time (pending -> pos). Compute `supercharge` from: `day.weekday() <= 2` (Wed only for the AM window); daily not ranging from `ctx.htf` row (bias_htf `htf.table`); week extreme from `ctx` weekly bars (`htf.weeks`) vs `strategy.adr5`; seasonal = `ctx.seasonal_side` (new column, bias_htf B23: average sign of the next 10 trading-day return for this calendar window over the prior 10 years of daily ES; until built the check is skipped when `p.sb_supercharge_seasonal=False`).
  - Effect: if supercharge, the position uses `t1` for all but `p.lot` units and `t2` = the HTF draw (`ctx.lock[session]["target"]` if locked, else the first `_targets` level of kind HTF); stop is not moved to BE (set a flag so the `t1_done -> stop=entry` line is skipped). Else force a full exit at `t1` (no runner even if `sb_runner`).
  - Params: `sb_supercharge: bool = False`, `sb_supercharge_seasonal: bool = False`.
  - Test: `test_sb_supercharge_runner_mon_wed`. Tuesday, week low not yet in, daily trending: one unit left after `t1` with the stop not at BE. Thursday same day shape: full exit at `t1`.

### 9. M3-sb-ob-entry
- **rule_id / kind:** M3 / missing_condition. Scope: index. judgment = true.
- **Rule:** Optional SB variant: at 10:00-11:00 with the HTF draw set, a short may be entered while price trades inside a 5m bearish OB (A12) that formed before the window (049: at 10:00, on a high-impact 10:00 news day, NQ). Treat it as a scalp: cover at the next short-term low, stop above the OB, tag `sb_ob`. The FVG entry stays standard. Mirror for longs.
- **Sources:** 049_St9FJHRVdq8 ~2:00-2:50.
- **Quotes:** "I use this order block here while we're inside that order block I went short" (049).
- **Conflicts:** none (M0 step 5 lists OB generally, not as an SB entry).
- **[our interpretation]:** "next short-term low" = the most recent 1m pivot low (`sd.pl` in side space) beyond the entry; 5m OB = `L.order_block_blend` on the 5m frame over the leg into the pre-window extreme.
- **Rulebook fix (M3 entries):** "Variant (049, scalp): inside a pre-window 5m OB in the bias direction at 10:00-11:00 with the HTF draw set; cover at the next short-term low; stop beyond the OB."
- **BUILD SPEC (silver_bullet; one value of the M3 umbrella `sb_entry`):**
  - Where: new helper `_arm_ob(ctx, sd, i, k0, p, lock, a)` in `sb_model.py`, called from `run_sb` beside `_arm` when `"ob" in p.sb_entry_arrays`. Requires a locked/HTF draw (`lock` dict with side == `sd.sign`, or `ctx.htf` bias when `draw_lock="off"`). Build the 5m OB from 5m bars closed before `a` (last opposite-close 5m candle before the leg to the pre-window extreme). Arm a limit at the OB near edge valid only for `a <= t < b`; stop = OB far edge + `stop_buffer`; single exit at the next 1m pivot low beyond entry (side space), min room `p.sb_ob_min_pts`; tag `sb_entry_kind="ob"`. One per window shared with the FVG path (the existing `break` after a closed trade).
  - Params: `sb_entry_arrays: tuple = ("fvg",)` (values "fvg", "ob", "confluence"; the IFVG entry has its own `sb_ifvg` switch, item 1), `sb_ob_min_pts: float = 2.0`.
  - Test: `test_sb_ob_entry_at_window_open`. A 5m bearish OB formed 09:45-09:50, price inside it at 10:00 with a bearish lock: a short fills at 10:00-10:01 and exits at the next 1m low; with `("fvg",)` no OB trade.

### 10. M3-sb-three-array-confluence
- **rule_id / kind:** M3 / missing_condition. Scope: index. judgment = true.
- **Rule:** In 10:00-11:00 with the draw above: after the retrace, a long is supported where several PD arrays agree (wick CE, volume imbalance, MT of the last down-close candle / bullish OB; 090: ~4512). The idea holds while no closing price goes below that MT (wicks allowed). ICT frames these as support levels ("I'm not saying buy it"), not a mandated limit. Stop below the candle forming the FVG low and below the OB MT; target buy-side. The timeframes (1h wick, daily VI) and a "~1 pt" tolerance are not verified in the source. Mirror for shorts.
- **Sources:** 090_bhYcXBI3z9U ~1:45:00-1:48:00, ~2:01:02, ~2:14:20.
- **Quotes:** "this is the Silver Bullet between 11 and 10 I outlined how you would use it using ... three different PD arrays" (090).
- **Conflicts:** none.
- **[our interpretation]:** "agree" = at least 2 of the 3 levels within `sb_conf_tol_pts` (default 1.0 ES pt) of each other; arrays taken from 1m-1h (wick CE), 1m-daily (VI).
- **Rulebook fix (M3):** "Confluence variant (090 ~1:45-2:01): a long is supported where wick CE, VI and the last down-close candle's MT agree; valid while no close below that MT; stop below the FVG-low candle and the OB MT."
- **BUILD SPEC (silver_bullet; `sb_entry_arrays` value "confluence"):**
  - Where: `sb_model._arm`, after the FVG `g` and the OB `ob` are found. When `"confluence" in p.sb_entry_arrays`: collect wick CEs (`L.wick_ce`) of 1m/5m/1h candles between `k0` and `i`, VI edges (`L.volume_imbalances` on 1m and the daily bars from `ctx.htf`), and `ob.mt`. If >= `p.sb_conf_min` of them lie within `sb_conf_tol_pts` of each other and below the FVG top, set entry = their mean (instead of `g.top`) when `p.sb_conf_mode="entry"`, or keep `g.top` and only tag (`"tag"`). In `run_sb`, a pending/filled confluence trade is cancelled/exited when a 1m close prints below `ob.mt` (wicks allowed). Stop stays `min(l[g.i-2], ob.mt) - stop_buffer` (already the 090 stop).
  - Params: `sb_conf_min: int = 2`, `sb_conf_tol_pts: float = 1.0`, `sb_conf_mode: str = "tag"`.
  - Test: `test_sb_three_array_confluence_090`. Wick CE, VI edge and OB MT within 0.75 pt: order at their mean in "entry" mode; a later 1m close below the MT cancels the pending order; a wick below does not.

### 11. M3-sb-entry-timeframe
- **rule_id / kind:** M3 / missing_rule. Scope: needs_unavailable_data. judgment = false.
- **Rule:** SB FVG detection: scan top-down 15m, 5m, 4m, 3m, 2m, 1m and take the first qualifying FVG found in the bias direction (065 gives the order). 063 filled on a 2m FVG and added on a 2m breaker. Seconds charts only if nothing appears at 1m or above, and only with a 1m + 5m chart for context (092). That needs sub-minute data the bot lacks, so the bot stops at 1m.
- **Sources:** 065_rx15_eN9sxI ~4:48:20, ~5:02; 063_qA9SCu4gGaU ~27:45; 092_9MLRE-n6St8 ~57:09.
- **Quotes:** "if you're trading in the one hour spectrum of 10 a.m to 11 A.M you start with your 15 minute down to five four three two one" (065).
- **Conflicts:** 065 (~5:02) says new traders should not use sub-1m charts; 092 says without 30s charts some Silver Bullets are missed.
- **Rulebook fix (M3):** "Execution timeframe: scan 15m, 5m, 4m, 3m, 2m, 1m top-down for the first FVG in the bias direction; seconds charts only if none at >= 1m, with 1m + 5m open (065, 092). Bot: 1m (no sub-minute data)."
- **BUILD SPEC:** none (needs sub-minute bars). Optional study only, not a spec: an `sb_tf` (1 / 2) resample of the 1m frame inside `run_sb` is possible with current data if the 2m part is wanted later.

### 12. M3-sb-fvg-from-0930-leg
- **rule_id / kind:** M3 / missing_condition. Scope: general (said while discussing EURUSD/DXY). judgment = false.
- **Rule:** AM SB: the bias comes from HTF before the session. At 10:00, look back at the leg from the 09:30 open to the 10:00 extreme in the bias direction (rally to the 10:00 high if bullish, drop to the 10:00 low if bearish). Eligible FVGs are those inside that leg plus any formed 10:00-11:00 in the bias direction. Limit entry only 10:00-11:00, on the retrace into the FVG.
- **Sources:** 065_rx15_eN9sxI ~5:14-5:17.
- **Quotes:** "the fair value Gap could form in the move from 9 30's opening down to 10 o'clocks low so that price leg wherever the fair value would reside there it can return" (065).
- **Conflicts:** none.
- **Rulebook fix (M3 / D2):** replace "may have formed earlier" with "may come from the 09:30-to-10:00 leg in the HTF bias direction, or form in 10:00-11:00; the entry is only 10:00-11:00 (065 ~5:16)."
- **BUILD SPEC:** none. Already listed in rule_coverage with the same content: `run_sb` arms from `leg_from=570` (PM 810) with fills only in the window, and D2's `sb_fvg_from` switch covers the in-window-only alternative.

### 13. M3-sb-premise-htf-fvg-or-smt-mss
- **rule_id / kind:** M3 / missing_condition. Scope: index. judgment = true.
- **Rule:** Optional SB filters (test separately): (a) `htf_array`: before/at the window, price has traded into a 15m FVG in discount (longs) / premium (shorts) and broken a swing the other way (MSS); (b) `smt`: one index makes a lower low into a predefined level while the other makes a higher low (1m, confirmed 15m), then MSS above the short-term high that led to the low. Then enter the first FVG of that leg retraced into within the window. Target REH/BSL, NDOG edges, 15m OB MT, or the opposing premium FVG. Mirror for shorts.
- **Sources:** 054_tRq1hyGGtl4 ~14:20-15:30 (PM SB); 093_CcNOk_3O5wk ~8:40-9:40.
- **Quotes:** "the market creates the smt diversions NASDAQ trades down to our low the very low I was calling for rallies up shift in Market structure here fair value you got there's your silver bullet" (093).
- **Conflicts:** none. These are demonstrated examples, not stated requirements.
- **[our interpretation]:** "predefined level" = the session's locked draw / a pool in `ctx.pd`; discount/premium = below/above 50% of the ETH-start-to-now range.
- **Rulebook fix (M3):** replace "MSS shown but never stated as required" with "Demonstrated premises (optional filters): a tag of a 15m discount FVG then MSS (054 PM), or ES/NQ SMT at the predefined level then MSS (093)."
- **BUILD SPEC (silver_bullet):**
  - Where: `sb_model._arm`, after `li` and the MSS test. `p.sb_premise`: "htf_array" - the low at `li` traded into a 15m bullish FVG (`ctx.conf` 15m rows, or `htf._arrays` on 15m bars) whose top is below the range EQ; "smt" - call `strategy._smt(ctx, sd, i, k, lo_seg, session, pctx, psides, ppos, p)` at `li` and require a non-confirmation (`False`); requires passing `pctx, psides, ppos` into `run_sb` (signature change in `run_day` ~2941, shared with setups_models' SMT wiring - additive, keyword args with None defaults). "either" accepts both. Fail -> return None. Tag `sb_premise`. Targets unchanged (they come from `_targets`).
  - Params: `sb_premise: str = ""` ("" / "htf_array" / "smt" / "either").
  - Test: `test_sb_premise_htf_fvg_and_smt`. Day A: low tags a 15m discount FVG then MSS: order with "htf_array", none on a twin day whose low misses the FVG. Day B: ES lower low, NQ partner higher low: order with "smt"; partner also lower low: none.

### 14. M3-sb-multiple-entries-per-window
- **rule_id / kind:** M3 / unlisted_contradiction. Scope: index. judgment = true.
- **Rule:** Param `sb_max_per_window` (test 1 vs 2). While the draw is untaken: a return into the filled SB FVG (still reclaimed, no body close through its far edge) allows a re-entry/add (decreasing size, E12; 080). A new FVG/VI on the next leg allows an IOFED add (080). The PM window allows up to two SB entries (056). After 15:00, one more same-rule entry in 15:15-15:45 only if a liquidity target is still unengaged that day (056; T7). Deactivate once the target trades. Note: 047's "one AM SB" is a preference ("if I were only trading once"), not a cap. Re-entry after a stop is X13.
- **Sources:** 056_NeZlyG8FZLQ ~15:00-15:40; 080_XODINFwpeaw ~17:20-17:50; 060_ZtLMTXv-Dr0 ~1:21:18 (SBs form daily and in many ways).
- **Quotes:** "this is your PM session Silver Bullet you get two chances here one two rallies and then the final Market on close macro" (056).
- **Conflicts:** 047 ~8:00 one AM SB a day (M3, X15) - a preference, weaker than stated; X13/X14 one trade per session.
- **[our interpretation]:** add size = half the first unit count (E12 decreasing), min 1 lot.
- **Rulebook fix (M3 count / X15):** "One AM SB a day is a preference (047 'if I was only going to trade one time'). While the draw is untaken: re-entry/add on a return into the filled SB FVG, IOFED add on the next FVG/VI (080); PM gives two chances, plus one in 15:15-15:45 if a target is unengaged (056)."
- **BUILD SPEC (silver_bullet; relates to the M3 umbrella `sb_one_per_day`):**
  - Where: `run_sb`. Replace the hard `break  # one Silver Bullet per window` with a counter: after a trade closes, keep looping while `n_window < p.sb_max_per_window` and the window is open and the draw (`t1`'s level / lock target) has not traded; the re-arm then uses `_arm` as usual. Adds while a position is open: when `p.sb_adds`, (a) a return into the entry FVG (low <= FVG top, no 1m close below its bottom) adds `max(p.lot, shares//2)` at the FVG top, (b) a new same-side FVG or body VI (`L.volume_imbalances`) formed after the fill adds at its near edge; adds share the stop and exits (append to the same Trade like `strategy._arm_add` does; reuse that helper's bookkeeping pattern, do not call it). PM extension: `p.sb_moc_extra` adds a third window (915, 945) with session "PM" and setup `sb_moc`, armed only if the PM draw / lock is not delivered (`lock["delivered"]` false) and no PM SB hit its target.
  - Params: `sb_max_per_window: int = 1`, `sb_adds: bool = False`, `sb_moc_extra: bool = False`.
  - Test: `test_sb_two_per_window_and_moc_extra`. PM window with two retrace-and-rally legs and an untaken BSL: one trade at 1, two at 2. A third entry at 15:20 appears only with `sb_moc_extra` and an undelivered lock. Separate case: return into the filled FVG adds half size with `sb_adds`.

### 15. M3-sb-opposite-direction-same-window
- **rule_id / kind:** M3 / unlisted_contradiction. Scope: general (EURUSD 1m example). judgment = true.
- **Rule:** Switch `sb_reverse_after_target` (default off): after an SB reaches a draw that is an HTF array (OB edge / FVG CE) where price stalls, and the entry FVG is traded back through (IFVG, A8), allow ONE opposite SB in the same window, requiring MSS beyond the low/high that started the run, a new FVG (evolving allowed), entry inside the window, and the room filter.
- **Sources:** 058_hcSGlyfgKgA ~44:00-47:30 (illustrative, not executed).
- **Quotes:** "this was a qualified ICT Silver Bullet for the long side... this right here is an evolving Silver Bullet" (058).
- **Conflicts:** 047 one AM SB a day; B3 one direction only (and the owner #9 one-draw-per-session lock).
- **[our interpretation]:** "stalls" = the target bar is the window's extreme for at least 3 bars; the opposite trade ignores the session lock's side (it is a counter-draw trade) but uses its own room check.
- **Rulebook fix (M3):** "After a qualified SB reaches an HTF array and its entry FVG inverts, an opposite 'evolving' SB in the same window may form (058 ~44-47, illustrative); requires MSS beyond the run's origin, a new FVG, room."
- **BUILD SPEC (silver_bullet):**
  - Where: `run_sb`, after a trade exits at `t1` or beyond. When `p.sb_reverse_after_target` and the target's kind (from `_arm`'s `dr`) is an HTF array kind (conf/htf FVG or OB, not a pool) and the window is open: set `rev_from = i`, `rev_side = -sd.sign`, `rev_origin = l[li]` (side space of the first trade). Continue the loop; arm only the opposite side, with `k0 = li` of the first trade so `_arm`'s leg extreme is the first trade's high, and require (a) a close through the first trade's entry FVG bottom (IFVG), (b) an MSS close beyond `rev_origin` (the low that started the first run, mirrored), using `_arm`'s MSS test on the opposite side, (c) the usual room. Bypass the lock side filter for this one arm (`lk=None`). Max one reverse per window. Tag `sb_reverse`.
  - Params: `sb_reverse_after_target: bool = False`.
  - Test: `test_sb_reverse_after_htf_target`. Long SB exits at a 15m FVG CE at 10:30, the entry FVG is closed through, MSS below the run's low, new bearish FVG at 10:45: a short fills before 11:00 with the switch; none without it; none when the target was a plain pool.

### 16. M3-sb-which-fvg-in-leg
- **rule_id / kind:** M3 / unlisted_contradiction. Scope: index. judgment = false.
- **Rule:** Option `sb_fvg_pick = 'first' | 'any_in_leg'`: with `any_in_leg`, every FVG formed in the 10:00-11:00 displacement leg toward the draw (before the draw is hit) is an entry candidate; take the first whose retrace fills; a later FVG remains valid if an earlier one was not traded. Keep the per-window cap.
- **Sources:** 093_CcNOk_3O5wk ~9:15-9:40.
- **Quotes:** "between 10 and 11 there's your silver bullet you don't like that one no problem you can trade that one" (093).
- **Conflicts:** M3 (048 ~57:36): the first FVG in the bias direction during the hour is the entry; D2(c) frames the choice as first-only vs evolving.
- **Rulebook fix (M3 / D2(c)):** add a third option: "any FVG in the leg (093 ~9:17): each successive FVG toward the draw is tradable, also after an earlier one was retraced into."
- **BUILD SPEC (silver_bullet; adds a value to the M3/D2 `sb_fvg_pick` switch):**
  - Where: `sb_model._arm`, the `gaps` filter and pick. Current behaviour ("evolving") drops gaps already traded back into (`l[g.i+1:i+1].min() > g.top`) and picks the newest. `"any_in_leg"`: keep every open gap formed between `li` and `i` before the draw traded, return them all (list) and let `run_sb` hold one limit per gap (dict keyed by `fvg_i`); the first that fills becomes the position and cancels the rest. A gap already retraced into but not closed through stays a candidate for its next retrace. `"first"`: the oldest qualifying gap only, no evolving.
  - Params: `sb_fvg_pick: str = "evolving"` ("evolving" = current / "first" / "any_in_leg").
  - Test: `test_sb_fvg_pick_any_in_leg`. Leg with FVG1 (retraced into at 10:12 without a fill because the order was not yet armed), FVG2, FVG3; price retraces into FVG1 again at 10:30: fill at FVG1 with "any_in_leg", at FVG3's edge (or none) with "evolving".

### 17. E5-sb-cancel-threshold
- **rule_id / kind:** E5 / wrong. Scope: index. judgment = true.
- **Rule:** Pending SB limit: D = first draw. A run of 1-2 ticks beyond D before the fill is wanted and does not cancel (057 ~4:18). Cancel the whole order if price trades through the cancel level before the fill. In 057 that was 4203, ICT's original TP, 3 ticks beyond the 4203.75 draw; he reasons that the FVG would then be too far from price. Bot: cancel when price trades beyond D by >= `cancel_ticks` (default 3, test 2-4) [our interpretation of a single example].
- **Sources:** 057_DkOuO0eNwUA ~3:35-3:46, ~4:18-4:30 (4203.75 and the 3 ticks come from the chart notes, not the captions).
- **Quotes:** "the trades below uh 4203 then I'll just cancel the entire trade it would be too far down for me to to consider that fair value Gap" (057).
- **Conflicts:** M3 "Cancel if price trades through the target before the fill" vs "A shallow 1-tick run under sell-side before the retrace is wanted" (both 057).
- **Rulebook fix (M3 / E5):** replace "cancel if the target trades before the fill" with "cancel if price trades ~3 ticks beyond the first draw before the fill (057: 4203 vs a 4203.75 draw); a 1-2 tick run beyond it is wanted."
- **BUILD SPEC (silver_bullet):**
  - Where: `run_sb` pending block, the line `elif sd.h[i] >= pending["t1"] and sd.l[i] >= pending["entry"]: pending = None`. Today it cancels when the exit price `t1` trades, which can be below the draw (exit_before) - stricter than ICT. When `p.sb_cancel_ticks > 0`, store the raw draw `D` in the pending dict (`_arm` returns `draw_raw = dr[0][0]`) and cancel only when `sd.h[i] >= D + p.sb_cancel_ticks * 0.25 * p.es_pt` before the fill. Also tag the fill with `sb_pre_run_ticks` = max ticks beyond D before the fill (feeds M3.5's depth tag).
  - Params: `sb_cancel_ticks: int = 0` (0 = current behaviour; test 2 / 3 / 4).
  - Test: `test_sb_cancel_threshold_057`. Short pending at 4205.75, draw 4203.75: a 1-tick run to 4203.50 then the retrace fills with `sb_cancel_ticks=3`; a run to 4203.00 cancels; with 0 the 1-tick run cancels (current).

### 18. M3-sb-evolving-large-range-candle
- **rule_id / kind:** M3 / missing_condition. Scope: index. judgment = true.
- **Rule:** Flag the first in-window FVG low-confidence if the candle before the displacement leg has range >= 2x mean 1m range of the prior 20 bars [our threshold]. Keep its limit; if a later 1m candle closes leaving a new same-direction FVG further along while the first is untouched, cancel and re-place at the new FVG's near edge with stop just beyond the new FVG. Never chase at market.
- **Sources:** 057_DkOuO0eNwUA ~2:16-2:45, ~4:40-5:40.
- **Quotes:** "because we have that large range of closed candle to the left of all this decline ... that might become a balanced price range and it may not even enter back into that" (057).
- **Conflicts:** none.
- **Rulebook fix (M3 evolving SB):** add "Warning sign: an FVG next to a large-range candle may act as a BPR and not be revisited (057 ~2:16); move the order only when a candle closes leaving a new FVG; never chase."
- **BUILD SPEC (silver_bullet; refines M3.4 evolving, built):**
  - Note: `run_sb` already re-arms to the newest untouched FVG on each closed bar, so "move only when a candle closes leaving a new FVG" is the current mechanics. New parts: the flag and the stop on re-place.
  - Where: `sb_model._arm`. When `p.sb_lrc_mult > 0`: compute `big = (h[g.i-2]-l[g.i-2]) >= p.sb_lrc_mult * mean(h-l over the 20 bars before g.i-2)` for the chosen gap; return `lrc=True`. In `run_sb`, `p.sb_lrc_mode`: "tag" (Trade field `sb_lrc`), "wait" (do not arm a gap with `lrc=True` until a later gap exists; i.e. only arm a flagged gap if it is not the first in the leg), "skip" (never arm flagged gaps). On re-place to a newer gap the stop already follows the new gap (`_arm` recomputes it from the new gap's first candle); the test pins that behaviour.
  - Params: `sb_lrc_mult: float = 0.0` (test 2.0), `sb_lrc_mode: str = "tag"`.
  - Test: `test_sb_large_range_candle_flag`. First FVG after a 3x-range candle: tagged in "tag"; no order on it in "wait" until a second FVG forms, then the order sits at the second FVG with its stop.

### 19. E5-sb-stop-placement-width
- **rule_id / kind:** E5 / missing_condition. Scope: index. judgment = true.
- **Rule:** SB short stop = above the high of the candle/swing that ran into the premium array and formed the entry FVG (+1 tick) (092 [chart: 03:00 candle]; 057: 2 pts above entry / above the evolved FVG). If that stop is too wide, cut size, or skip and wait for a closer FVG (092; 057: ~6 pts rejected, 2 accepted). Bot: `max_sb_stop_pts` (default 4 ES pts [our interpretation]). Once filled inside the window, accept drawdown up to the stop (068). Mirror for longs.
- **Sources:** 057_DkOuO0eNwUA ~2:54-3:09; 092_9MLRE-n6St8 ~55:30-56:00 (NQ points); 068_V0uV6lcgobQ ~17:29-17:40.
- **Quotes:** "where would you stop be it would have to be above this candle's high well that's too much risk don't take the trade" (092).
- **Conflicts:** 057 rejects a ~6-pt stop as too much drawdown; 068 accepts drawdown after the fill.
- **Rulebook fix (E5 / M3 stops):** "SB stop above the candle/swing that ran into the premium array and formed the entry FVG. Too wide (057: ~6 pts no, 2 pts yes) -> cut size or skip and wait for a closer FVG (092). After the fill accept drawdown to the stop (068)."
- **BUILD SPEC (silver_bullet; adds a value to M3.8 `sb_stop`, not yet built):**
  - Where: `sb_model._arm`, stop and risk block. `p.sb_stop = "swing"`: stop = the leg extreme `l[li]` (side space: the high that ran into the premium array) - `stop_buffer` (1 tick), instead of `min(l[g.i-2], ob.mt)`. Width rule: if `risk > p.sb_max_stop_pts * p.es_pt`, `p.sb_wide = "skip"` returns None (the evolving re-arm will try the next closer FVG on later bars), `"size"` keeps the order with `shares` computed from `sb_max_stop_pts` risk budget (`_first_units(p, equity, risk, entry)` already scales by risk; additionally cap at `floor(shares * sb_max_stop_pts*es_pt / risk)`). The existing `max_risk_pts` gate stays as the outer bound. Drawdown after the fill: no change (the position already holds to the stop).
  - Params: `sb_stop: str = "fvg_ob"` (current 090; add "swing"), `sb_max_stop_pts: float = 0.0` (0 = off; test 4), `sb_wide: str = "skip"`.
  - Test: `test_sb_swing_stop_and_max_width`. Short with a swing high 6 pts above the FVG edge: no order with `sb_max_stop_pts=4, sb_wide="skip"`; a smaller order with "size"; a later evolved FVG 2 pts below the high fills with stop at the high + 1 tick.

### 20. M3-sb-eq-target-discount-array
- **rule_id / kind:** M3 / missing_rule. Scope: index. judgment = false.
- **Rule:** SB "simple rules" (069 ~15:05), used when the trade can't be managed: range = swing low to swing high of the leg into the entry. EQ = 50%. Short only from premium (an FVG/imbalance above EQ inside the window). Target = first discount PD array below EQ (FVG/ORG/NWOG/imbalance; in 069 the ORG), exit in full there. Long = mirror. Single-source example (069).
- **Sources:** 069_Sf_uYZBWTrA ~15:03-15:57.
- **Quotes:** "simple Silver Bullet rules that I taught you which would be take the low to the high find equilibrium what PDA rag would be a discount array below 50" (069).
- **Conflicts:** none (M3's target is "the opposing untapped pool"; the below-50% target appears only in M2 / M11).
- **Rulebook fix (M3):** add "Simple SB rules (069 ~15:05): range low to high, EQ = 50%; enter in premium (shorts) / discount (longs); full exit at the first PD array beyond EQ (069: the ORG)."
- **BUILD SPEC (silver_bullet + uses targets_partials' `_targets` output):**
  - Where: `sb_model._arm`. When `p.sb_simple`: range of the leg into the entry, in side space: `hi = max(h[k0:li+1])` (the swing the Judas came from), `lo = l[li]`, `eq = (hi+lo)/2`. Require entry (`g.top`) below EQ (discount for longs; premium for shorts after mirroring). Target = first level in `dr` above EQ whose kind is an array/gap kind (FVG, ORG, NWOG, NDOG, VI from `_targets`), single full exit (`levels=[t1]`, `t2=None`, fracs `(1.0,)` like the sloppy scalp path). Room and RR checks still apply.
  - Params: `sb_simple: bool = False`.
  - Test: `test_sb_simple_eq_target_069`. Short leg 4150->4130, FVG at 4145 (premium), ORG at 4136: order at 4145 with one exit at the ORG near edge; an FVG at 4137 (discount) gives no order.

### 21. M3-sb-consolidation-wait-displacement
- **rule_id / kind:** M3 / missing_condition. Scope: index. judgment = true.
- **Rule:** If price in the SB window is consolidating, don't take an entry until a displacement (energetic, one-directional) candle leaves the range toward the draw. Then enter on the FVG that displacement creates. FVGs formed inside the range don't count as the window's "first FVG" [our interpretation of "wait for displacement"]. Room still >= 4-5 ES handles per L15/M3.
- **Sources:** 072_AKg_r0DIa3k ~35:36-35:57 (PM SB example).
- **Quotes:** "when you take a silver bullet if you're seeing consolidation like this have this in your notes wait for displacement" (072).
- **Conflicts:** none.
- **[our interpretation]:** consolidation = the high-low range of the last 10 1m bars is <= 2.0 ES pts; displacement = a close beyond that range with body >= 2x the mean body of the range bars.
- **Rulebook fix (M3):** "Consolidating window (072 ~35:41): wait for a displacement candle out of the range toward the draw; enter its FVG; FVGs inside the range do not count."
- **BUILD SPEC (silver_bullet):**
  - Where: `sb_model._arm`, gap filter. When `p.sb_cons_wait`: find the latest consolidation box ending before `i` (helper `_cons_box(sd, a_idx, i, p)` in `sb_model.py`: rolling `sb_cons_bars` window with range <= `sb_cons_pts` ES pts); if one exists, keep only gaps whose middle candle `g.i-1` closed beyond the box top in side space with body >= `sb_cons_body_mult` x the box's mean body. Gaps formed inside the box are dropped. The intraday `ctx.chop` (owner #10) is a day-level test and is not reused.
  - Params: `sb_cons_wait: bool = False`, `sb_cons_bars: int = 10`, `sb_cons_pts: float = 2.0`, `sb_cons_body_mult: float = 2.0`.
  - Test: `test_sb_consolidation_wait_displacement_072`. 14:00-14:20 range of 1.5 pts with a small FVG inside it, then a 3-pt displacement candle out at 14:22 leaving an FVG: with the switch the order sits at the 14:22 FVG, not the in-range one.

### 22. L14-sb-nwog-draw-old-and-expansion
- **rule_id / kind:** L14 / missing_rule. Scope: index. judgment = false (the expansion target is our interpretation).
- **Rule:** L14 SB draw list: "NWOG" = return to the current or any older retained NWOG (per L5), or an expansion away from a current/old NWOG after price reacts at it. For the expansion case, the target is the next draw in that direction from the same list (PDH/PDL, session H/L, PWH/PWL, FVG) [target choice is our interpretation].
- **Sources:** 054_tRq1hyGGtl4 ~5:13-5:26.
- **Quotes:** "returning to a current or old new week opening Gap so that would be treated as a draw on liquidity or an expansion away from the current or old new week opening Gap" (054).
- **Conflicts:** none. Part (a) is already covered: L5 keeps all NWOGs (`nwog_days=60`, `_nwogs`), and `_targets` already offers them as draws.
- **Rulebook fix (L14 SB draw list):** "NWOG: a return to the current or any older retained NWOG, or an expansion away from one after price reacts at it (054 ~5:17); the expansion targets the next draw in that direction."
- **BUILD SPEC (silver_bullet; reads `ctx.nwog` / `_nwogs`, owned by levels_detectors):**
  - Where: `sb_model._arm`, as a premise/tag. When `p.sb_nwog_expansion`: the leg extreme `l[li]` (side space) traded into an NWOG zone from `strategy._nwogs(ctx, i)` (any of its levels within `eq_tol_pts`, or inside the gap) and the MSS left it -> tag `sb_nwog="expansion"`; with `p.sb_nwog_expansion == "require"`, skip SB setups whose leg extreme did not react at an NWOG. Draw = unchanged `_targets` list (the next draw beyond entry), which already matches the "next draw in that direction" reading; nothing new needed for targets.
  - Params: `sb_nwog_expansion: str = ""` ("" / "tag" / "require").
  - Test: `test_sb_nwog_expansion_tag`. Leg low reacts at an older NWOG's lower edge, MSS, FVG fill: tagged "expansion"; with "require" a twin day whose low is 10 pts away from any NWOG gives no order.
