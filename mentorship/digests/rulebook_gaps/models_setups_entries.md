# Rulebook gaps: models, setups and entries

Topic `models_setups_entries`. Every item below is a verified gap between ICT's captions and `mentorship_rules.md`. When the checker gave a corrected rule, that corrected rule is the one written here; when it gave none, the claim's full rule is used. "[our interpretation]" marks thresholds or readings that ICT does not state.

Conventions:
- Times are New York. Params times are minutes from midnight (570 = 09:30, 600 = 10:00, 720 = 12:00, 780 = 13:00, 810 = 13:30, 900 = 15:00, 950 = 15:50).
- New Params switches default off (rule_coverage.md section 3). Each work package adds its fields in its own commented block at the end of `Params` (strategy.py ~65-705).
- Work packages are the names in `rule_coverage.md` section 3:
  - **setups_models** owns the `_scan_core` sweep/MSS block and the new setup branches. Most of those live in `setups.py` (`extra_setups`, `array_order`, `pre_break`, `cc_breaker_order`, `cc_failure_order`, `pm_reversal`, `pm_ep01`, `moc_run`, `sick_sister`, `finish_gates`) and `strategy.py` (`_scan_core` ~3308, `_turtle` ~3776, `_cc_1h_ob` ~3846, `_external` ~3904, `_breaker_order` ~3284, `_ob_pre` ~3691).
  - **entries_stops_sizing** owns the `_scan_core` entry/stop block, `_finish_order` (~3949), the `run_day` pending-fill and add-arming blocks (`_arm_add` ~2970, `_ob_add` ~2986) and `SB._arm`.
  - **targets_partials** owns `_targets` (~1318), `_lv_finish_targets` (~3641) and the target merge in `_finish_order`.
  - **management_exits** owns the `run_day` position loop and `_after_close` (~1858).
  - **levels_detectors** owns `levels.py` detectors, `htf.py:_arrays` and DayCtx pool construction.
  - **bias_htf** owns `htf.table`, the `run_day` bias block, `weekly_bias`, `backtest.INTERMARKET` and new data loaders.
  - **news_calendar_times / day_week_context** own `blocked()`, `calendar.py`, `day_context` and the session windows.
  - **silver_bullet** owns `sb_model.py`.
- Already built (owner directives, review pass, setups.py): `ob_entry` (pre_break default), `turtle_soup` (2023 / cc_limit / cc_1h_ob / or60 / external), `breaker_zone`, `cc_swings`, `adv_breaker`, `ts_breaker_pyramid`, `reclaimed_ob`, `entry_arrays`, `ifvg_061`, `cisd_ob_entries`, `wick_ce_entries`, `ote`, `ote_stack_tag`, `sick_sister`, `smt_entry`, `pm_reversal`, `pm_lunch_target`, `pm_lunch_org`, `pm_judas_array`, `pm_last_hour_model`, `last_hour_setup`, `three_drives`, `mmxm_ctx`, `vacuum_blocks`, `mit_targets`, `reentry_half`, `draw_lock`. A spec below that builds on one of them says so, and covers only what is new.
- Tests go in `tests/test_setups_models.py` (setups_models), `tests/test_levels_detectors.py` (levels_detectors) or a new `tests/test_entries_stops.py` / `tests/test_targets_partials.py` for those packages. Each spec names its test function.
- Items scoped `fx_only`, `bonds_only` or `needs_unavailable_data` get the rulebook fix only, with no build spec. Intraday DXY, sub-minute bars, bond futures, commodities, futures spreads and YM intraday count as unavailable.
- Swing, position and weekly models are parked under M17 (out of scope for the intraday bot). Their `general`-scope build specs are research studies on daily / 4h bars (`study.py`, `htf.py`), not live `_scan_core` branches. Stock items are research studies on daily stock bars from `alpaca_data.py`.

Summary: 229 items, 202 new build specs. Items without a build spec:
- 11 fx_only
- 6 bonds_only
- 6 that need data we do not have (sub-minute bars, intraday DXY, commodity/spread data)
- 2 already listed in rule_coverage with the same content:
  - M7-pm-short-back-below-lunch-high: M7 / M7.2 `pm_lunch_target` + `pm_lunch_org` are built. The displacement back below the lunch high is the MSS every `_scan_core` trade already needs.
  - M4-gray-area-no-entry: M4.5 `cc_swings` arms only on the break of the in-between swing, and no branch enters between the first reaction and that break.
- 2 text-only, needing no code:
  - M4-only-two-reversal-entry-locations: the bot has no pattern-based entries.
  - new-array-count-not-quality-filter: nothing in the bot scores by array count.

Many specs extend switches that are already built; each such spec says what it builds on and covers only the new part.

---

### 1. M5-lasthour-draw-frozen-noon
- **rule_id / kind:** M5 / missing_condition. Scope: index. judgment = true.
- **Rule:** For the last-hour setup, fix the draw (old high/low, REH/REL or an unfilled imbalance in the bias direction) during the AM session, before 12:00 NY. Do not re-pick it at entry time. From 15:00, take only setups that give a reason to expect a run to that pre-set draw. If it was already taken before 15:00, take no last-hour trade (T7).
- **Sources:** 001_XN8tuO4QIRw ~00:28:39.
- **Quote:** "a pool of liquidity which I had already made known publicly in the morning session so before lunchtime"
- **Conflicts:** none.
- **[our interpretation]:** 12:00 as a hard freeze; picking the nearest pool.
- **Rulebook fix:** M5: "The last-hour draw is set in the AM, before lunch (001 ~28:39), not at entry. If it trades before 15:00, no last-hour trade (T7)."
- **BUILD SPEC (setups_models; uses the owner #9 `draw_lock`):**
  - Where: `_lock_step` (~3028) and the LH slot in `run_day`. When `p.lh_draw_freeze`, record the AM lock (or, if none, the nearest untaken pool/imbalance on the AM bias side) at the first bar >= `lh_freeze_t`. The LH slot (`last_hour_own_slot`) uses that frozen draw as its lock and skips LH entries whose side does not point at it.
  - If the frozen draw trades before 15:00, mark the LH slot done.
  - Params: `lh_draw_freeze: bool = False`, `lh_freeze_t: int = 720`.
  - Test: `test_lh_draw_frozen_at_noon`. AM REH at 4010 untaken at 12:00, a nearer high forms at 13:40. An LH long at 15:20 must target 4010. A second case where 4010 trades at 14:30 gives no LH trade.

### 2. M1-three-entry-plans
- **rule_id / kind:** M1 / shortened. Scope: index. judgment = true.
- **Rule:** Three equally valid ways to trade the MM buy model, each worth testing separately. 'full' = buy the low-risk buy at the smart money reversal (OB/BISI after the short-term-low sweep) and hold to the return to the original consolidation's buy-side (HTF draw). 'mss_scalp' = wait for the MSS, buy the retrace into its FVG and exit at the first relative equal highs. 'pyramid' = buy at the low and add on each re-accumulation FVG that holds, scaling out at each pool.
- **Sources:** 003_ojy5ApHhEu4 ~01:28:27.
- **Quote:** "you could be a buyer down here and that could be your entire run"
- **Conflicts:** none. (The claim's "rulebook keeps only the early variant" is wrong: M1's default is the post-MSS FVG.)
- **[our interpretation]:** the exit level for each variant.
- **Rulebook fix:** M1: list the three plans (003 ~1:27:30-1:29:00), "a matter of preference", each a separate test.
- **BUILD SPEC (setups_models + targets_partials):**
  - `mm_plan` picks the plan on top of the existing paths: "full" = `ob_entry="pre_break"` + `mmxm_ctx` draw, single exit at the draw. "mss_scalp" = `ob_entry="post_mss"`, all units exit at the first rel-eq pool above (`_eq_levels`) via `_finish_order`'s ladder truncated to that level. "pyramid" = `ob_entry="pre_break"` + `add_on_vi`-style adds on each new same-side FVG that holds above the protected low, one ladder rung per pool.
  - Params: `mm_plan: str = ""` ("full" / "mss_scalp" / "pyramid"); validate in `__post_init__`.
  - Test: `test_mm_plan_variants`. One synthetic MMBM day run three times; assert entry kind, number of fills and exit levels per plan.

### 3. M4-unicorn-sequence-preopen-breaker
- **rule_id / kind:** M4 / A14, missing_condition. Scope: index. judgment = true.
- **Rule:** Before 09:30 mark the most recent bullish breaker on 5m/1m (zone = the up-close candle's range; in 007 the 07:35 5m candle) and extend it forward. At or shortly after the 09:30 open, require a wick run below the nearby sell-side under the breaker. Then require price to trade back inside the breaker zone before turning long. Entry: the FVG (near edge/CE) that forms inside the breaker's up-close candle range; add on later imbalances. Target: the pre-identified draw. Any timeout for the re-entry into the breaker is a parameter we choose.
- **Sources:** 007_bGtQOXrrK9c ~00:15:27, ~00:11:34.
- **Quote:** "takes out the sell side here then comes back inside the breaker so I switched gears"
- **Conflicts:** none.
- **[our interpretation]:** the re-entry timeout (default 15 bars).
- **Rulebook fix:** A14/M4: add the pre-open marking of the breaker and the "back inside the breaker" step (007 ~10:50-12:30, ~14:50-15:40).
- **BUILD SPEC (setups_models):**
  - Where: `_breaker` (~3256) / unicorn pick. When `p.unicorn_preopen`, the only breaker allowed for a unicorn after 09:30 is one formed before 09:30 (`levels.breakers` on 5m via `htf_bars(df, 5)`, zone from `breaker_zone`).
  - Sequence gate: sweep extreme at/after 09:30 below a pool under the zone; then a bar trading back inside the zone within `unicorn_back_bars`; only then the FVG inside the zone may arm (`unicorn_entry="overlap"` reused).
  - Params: `unicorn_preopen: bool = False`, `unicorn_back_bars: int = 15`.
  - Test: `test_unicorn_preopen_back_inside`. 07:35 5m breaker; 09:32 sweep; reclaim at 09:40 arms; a variant with no reclaim in 15 bars gives no order.

### 4. M4-accumulate-in-breaker-needs-bias-draw
- **rule_id / kind:** M4 / missing_condition. Scope: index. judgment = false.
- **Rule:** Allow entries inside a bullish breaker/consolidation before price breaks above it only if both hold: (a) the session bias is long; (b) a specific draw level above was named before the entry. If either is missing, take no entry inside the breaker. Do not substitute a breakout chase (E1/E5). Bearish = mirror.
- **Sources:** 007_bGtQOXrrK9c ~00:21:34.
- **Quote:** "if you know directional bias you know the next draw on liquidity"
- **Conflicts:** none.
- **Rulebook fix:** M4 (line 673) and the Ep 05 appendix: add the bias + named-draw condition.
- **BUILD SPEC (setups_models):**
  - Where: `adds_in_breaker` / `breaker_retest_add` and `cc_breaker_order` paths, plus `_breaker_order`. When `p.breaker_need_bias_draw`, an entry or add inside the breaker before its high breaks requires `lock["side"] == sd.sign` (owner #9 lock, set before the order) and a lock price above the zone.
  - Params: `breaker_need_bias_draw: bool = False`.
  - Test: `test_breaker_entry_needs_lock`. Same bars with lock side 0 gives no order; with a bullish lock above gives the order.

### 5. M1-sell-model-fail-to-reach-CE
- **rule_id / kind:** M1 / E2, shortened. Scope: index. judgment = true.
- **Rule:** Sell model (retrospective, 007): (1) price rallies into an HTF (1h) SIBI and forms REH near its high end. (2) A down move breaks the swing low (MSS) and leaves an FVG/SIBI, followed by a second MSS lower. (3) On the next rally into that SIBI, the candle whose high fails to reach the SIBI CE is the sell, at market on that candle. Targets: the sell-side below the original consolidation, then lower imbalances / the NWOG. Stop placement and close confirmation are not stated; use E6 defaults [our interpretation]. Long = mirror.
- **Sources:** 007_bGtQOXrrK9c ~00:20:36.
- **Quote:** "failure to get there that's a sell right there that candle"
- **Conflicts:** none. (Retrospective read of a day his own long was stopped.)
- **Rulebook fix:** M1 section 2: add the fail-to-reach-CE sell trigger (now only in the Ep 05 appendix, line 1360).
- **BUILD SPEC (setups_models + entries_stops_sizing):**
  - New branch in `setups.extra_setups`: `ce_fail_entry`. After a second MSS in the same direction (`mss_count=2` logic, Ep04.7), track the last SIBI of the leg. On the rally into it, the first bar with high > SIBI bottom and high < SIBI CE that closes down triggers a market order at its close (fill = next bar open). Stop = E6 (above the SIBI top + buffer).
  - Params: `ce_fail_entry: bool = False`.
  - Test: `test_ce_fail_sell`. Bar reaching 0.4 of the SIBI and closing down fills; a bar reaching the CE does not.

### 6. E12-second-stage-ob-at-MT
- **rule_id / kind:** E12 / missing_rule. Scope: index. judgment = false.
- **Rule:** After the first long, with an intact VI above the entry: the down-close candle whose low trades into the VI is a bullish OB. Place a buy limit at that candle's MT (D4). It is valid as an add (smaller than earlier units) or as a standalone entry. Stop below the VI low (A9), or the existing structural stop. The VI may be touched but not pierced: invalid on a body close below it.
- **Sources:** 009_tnxvmHq8xEg ~00:11:15, ~00:13:35.
- **Quote:** "or it could be a independent entry all together by itself"
- **Conflicts:** none.
- **Rulebook fix:** E12 (line 831): add the standalone use and the MT price.
- **BUILD SPEC (entries_stops_sizing):**
  - Where: `_ob_add` (~2986). When `p.vi_ob_add`, a down-close bar whose low enters an intact same-side VI (`sd.vis`) arms an add at its body MT; cancel on a body close below the VI bottom.
  - Standalone: with `p.vi_ob_entry` and no position, the same pattern after an MSS creates a new order (stop below the VI low) through `_finish_order`.
  - Params: `vi_ob_add: bool = False`, `vi_ob_entry: bool = False`.
  - Test: `test_vi_ob_add_at_mt`. Add fills at the MT; a body close below the VI cancels it.

### 7. E12-add-while-falling-toward-VI
- **rule_id / kind:** E12 / shortened. Scope: index. judgment = true.
- **Rule:** Long add: while the current 1m candle is down and heading toward an intact VI below, buy without waiting for a VI touch, either at market or with a limit around the VI top/midpoint. The stop stays below the VI low. Take profits on up candles (E4).
- **Sources:** 009_tnxvmHq8xEg ~00:08:03.
- **Quote:** "it may or may not touch the volume of balance again but I'm trying to trade as the candles going down"
- **Conflicts:** none.
- **[our interpretation]:** "around the VI top" = a limit `vi_add_above_pts` above the VI top.
- **Rulebook fix:** E12: "a VI touch is not required; add on the down candle heading to it (009 ~7:49-8:16)."
- **BUILD SPEC (entries_stops_sizing):**
  - Where: `_arm_add` (~2970). With `p.vi_add_early_pts > 0`, the add limit for a VI add is VI top + `vi_add_early_pts * es_pt`, filled only on a down bar (close < open at fill time, checked on the 1m bar).
  - Params: `vi_add_early_pts: float = 0.0`.
  - Test: `test_vi_add_without_touch`. A down bar reaching 0.5 pt above the VI fills the add.

### 8. M1-inside-fvg-expansion-only
- **rule_id / kind:** M1 / missing_condition. Scope: index. judgment = true.
- **Rule:** Context tag: when the day's objective is one pre-named fixed level (e.g. an old daily close) and a single expansion, not a trend day, is expected, the 'advanced' inside-FVG model is used. Enter inside the FVG toward its middle after the 09:30 sell-side purge, aim at that level, and take the bulk off at the level or higher (e.g. 9 of 14). ICT gives no rule for trend days.
- **Sources:** 009_tnxvmHq8xEg ~00:03:49.
- **Quote:** "I'm not looking for a trending day I'm just looking for an expansion up into the 40 30 level"
- **Conflicts:** none.
- **[our interpretation]:** "single expansion day" = the lock is a single daily level (old close/high/low) within ADR5 of the open; bulk = 65%.
- **Rulebook fix:** M1: add the context note (009 ~3:39-4:05, ~5:12).
- **BUILD SPEC (setups_models + targets_partials):**
  - When `p.expansion_ce_entry` and the session lock kind is a daily level within `adr5()` of the 09:30 open, use `entry="ce"` for that order and set the ladder to `expansion_bulk` at the lock and the rest at the next level.
  - Params: `expansion_ce_entry: bool = False`, `expansion_bulk: float = 0.65`.
  - Test: `test_expansion_ce_entry`. Lock = prior close 15 pts above; entry at the CE and 65% off at the lock.

### 9. M7-pm-1330-judas-full
- **rule_id / kind:** M7 / missing_condition. Scope: index. judgment = false.
- **Rule:** PM short, 13:30-16:15: require a bearish bias with undelivered HTF targets still below (in 010, a daily FVG). Mark the 13:30 open. Wait for price to rally above it into a premium array; a 5m FVG formed during lunch (12:00-13:30) and extended forward counts. After the rejection: lower, a rally to a short-term premium array, a short-term low formed. When that low is broken with displacement (MSS), take the leg from the post-13:30 high to the broken low and sell the first FVG at or above its 50%. Pyramid on later retraces into premium. Partials at the daily FVG top, then its CE, exiting 0.5-1 pt before each level. Mirror for longs.
- **Sources:** 010_cWekmMLqiNM ~00:57:47.
- **Quote:** "it still has undelivered targets down here"
- **Conflicts:** none.
- **Rulebook fix:** M7 (line 711): add the undelivered-HTF-target condition, the lunch 5m FVG as the premium array, and the post-Judas sequence.
- **BUILD SPEC (setups_models):**
  - Builds on `pm_judas_array` (M7.3). New: `pm_need_htf_target` requires an untouched same-direction daily FVG / old daily low in `htf.table` arrays below for PM shorts; `pm_lunch_fvg_array` adds 5m FVGs formed 12:00-13:30 (via `sd.zones_tf(idx, base, 5)`) to the arrays `pm_judas_array` accepts. Entry: `fvg_pick="m2"` (first FVG at or above leg EQ), already present.
  - Params: `pm_need_htf_target: bool = False`, `pm_lunch_fvg_array: bool = False`.
  - Test: `test_pm_judas_lunch_fvg`. PM rally into a 12:40 5m SIBI, MSS, sell at the M2 FVG; with no daily FVG below and `pm_need_htf_target`, no order.

### 10. M1M2-htf-array-replaces-sweep
- **rule_id / kind:** M1 / M2 / A19, unlisted_contradiction. Scope: index. judgment = true.
- **Rule:** Premise for an MMBM/2022-model reversal: either (a) a liquidity pool is taken, or (b) price reaches a pre-marked HTF (15m/1h+) PD array against the move (FVG or its CE, a prior long-wick CE coinciding with an FVG half, BPR or OB), tests it once or twice (011: CE twice), and bodies stay at or inside it. Then require displacement through the short-term high (longs) or low (shorts) formed during the test, leaving an FVG (MSS). Entry: the MSS FVG (with two FVGs, allow the higher one for shorts); adds at the CE of the next gap and at OB/consolidation support (E12). Target: the opposing pool. Bot switch: allow_htf_array_premise.
- **Sources:** 011_w0CYBeFTzcM ~00:08:49; 082_JpdNsPE0kWQ ~00:04:45.
- **Quote:** "the market teared up into that inefficiency broke lower shift in Market structure ... this is model 2022"
- **Conflicts:** M1 trigger and A19 require a swept short-term low; M2 requires buy-side taken. 011 (no sweep) and 082 (run into an HTF imbalance only).
- **Rulebook fix:** A19/M1/M2: add premise (b) and list the decision in Section 3.
- **BUILD SPEC (setups_models):**
  - Generalises `pm_judas_array` to all sessions. In the `_scan_core` sweep block, when `p.allow_htf_array_premise`, a bar whose extreme reaches a same-side 15m/60m array from `htf.table` / `confluence._zones` (FVG edge or CE, OB, BPR) with bodies not closing beyond the array creates a pseudo-sweep (`sd.sweep` with kind "htf_array"). The rest of the MSS / FVG path is unchanged; tag `premise="array"`.
  - Params: `allow_htf_array_premise: bool = False`, `premise_tfs: tuple = (15, 60)`.
  - Test: `test_htf_array_premise_no_sweep`. Price taps a 60m FVG CE twice with no pool taken, then breaks; an order arms only with the switch on.

### 11. new-falling-dagger-upper-half-buy
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** Experienced-only, off by default. Bullish HTF bias and a daily BISI that price is trading back into. The reaction should come in the upper half (above the daily FVG CE), and the lower-half imbalances, including the hourly FVGs there, are expected to stay open. A pre-MSS buy limit into the falling move inside the upper half (our interpretation: at the daily CE or an hourly/15m FVG low just above it). Stop (our interpretation): just below the daily FVG CE. Skip if price already filled a lower-half imbalance.
- **Sources:** 012_HkiPAi1Mdu8 ~00:20:06.
- **Quote:** "I can go right in there when it's just driving straight down like a falling dagger"
- **Conflicts:** E1 (never chase) and M0 (sweep and MSS first) vs a pre-MSS limit into a falling move.
- **Rulebook fix:** new rule after M0, labelled experienced-only, with the conflict listed in Section 3.
- **BUILD SPEC (setups_models):**
  - New branch `dagger_entry` in `setups.extra_setups`. Needs `htf.table` daily FVG (bull) with price inside its upper half and `bias == +1`. Place a buy limit at the daily CE (or the highest 60m/15m bullish FVG low between CE and the daily FVG top if `dagger_level="ltf"`), stop = CE - `stop_buffer`. Cancel if any bar trades below the CE before the fill or a lower-half 60m FVG has been filled today.
  - Params: `dagger_entry: bool = False`, `dagger_level: str = "ce"`.
  - Test: `test_dagger_limit_at_daily_ce`.

### 12. M12-0930-htf-fvg-stab-no-mss
- **rule_id / kind:** M12 / D10, missing_rule. Scope: index. judgment = true.
- **Rule:** Mark before the open an HTF (15m/60m) FVG beyond a pool of relatively equal lows (longs) or highs (shorts), with a strong daily narrative and a specific daily draw on the trade side. Trigger: price runs the pool (ideally in the 09:30 open; a deeper run before 09:30 is also accepted) and trades into the HTF FVG. Entry: limit in the FVG, no MSS or SMT required, even if the touching candle is a strong opposite-colored candle. Stop beyond the HTF FVG. Target the daily draw. Skip if the raid is shallow (N9) or a Fed-chair or other big event is due.
- **Sources:** 015_QKvjPltjsqU ~00:16:57, ~00:12:06; 038_4H74nXabvL0 ~00:21:57.
- **Quote:** "I would have went long right in that stab of this fair value gap on its own"
- **Conflicts:** M12 2023 (SMT), T4 (09:30-10:00 OR), M0 (MSS step). D10's default is already a pre-break OB entry.
- **Rulebook fix:** M12: add the HTF-FVG stab entry; list the conflicts.
- **BUILD SPEC (setups_models):**
  - Builds on `turtle_soup="2023"` (limit at a PD array, no MSS). New variant `turtle_soup="htf_stab"`: the array must be a 15m/60m FVG lying beyond a rel-eq pool (`_eq_levels`), limit at its near edge, stop beyond its far edge, target the session lock. Skip when `blocked()` returns a Fed-chair/FOMC day, and when the raid stops short of the FVG (N9 already).
  - Params: add "htf_stab" to the `turtle_soup` choices; `stab_tfs: tuple = (15, 60)`.
  - Test: `test_htf_stab_entry`. Rel-eq lows 4000, 15m FVG 3995-3992; a 09:31 bar to 3994 fills; a run to 3998 gives nothing.

### 13. B12-po3-low-after-0830-into-old-low
- **rule_id / kind:** B12 / missing_condition. Scope: index. judgment = false.
- **Rule:** B12 refinement (preference, not a hard filter): on a bullish day the ideal PO3 low forms when, at or after 08:30, price trades below the midnight open M and runs an old low below M (collecting sell-side). Rank such setups above dips below M that come before 08:30 or take no old low. Bearish = mirror.
- **Sources:** 013_V1thfpo-R9U ~00:04:52.
- **Quote:** "that's our trigger time so everything starts at that moment"
- **Conflicts:** none.
- **Rulebook fix:** B12: add the ideal-scenario ranking (013 ~4:52-5:35, ~8:45-9:25).
- **BUILD SPEC (setups_models):**
  - Tag only by default. In `finish_gates`, set `tags["po3_ideal"] = True` when the sweep extreme is at or after 510 (08:30), below the midnight open, and took a pool below it. `po3_ideal="require"` drops untagged PO3 orders.
  - Params: `po3_ideal: str = "off"` ("tag" / "require").
  - Test: `test_po3_ideal_tag`.

### 14. new-po3-midnight-open-resting-order
- **rule_id / kind:** new / missing_rule. Scope: index. judgment = true.
- **Rule:** If the daily bias set the night before is bullish: place an alert at, or a buy limit just below, the midnight open M. Size: the minimum (1 contract or 1 micro). Target 1: the day's high already formed at the time of the fill. Target 2: the HTF objective set the night before (e.g. the daily wick CE). No intraday management in between. ICT gives no stop; our interpretation: below the old low that the run under M takes. Bearish = mirror.
- **Sources:** 013_V1thfpo-R9U ~00:09:46.
- **Quote:** "there should be two of them the high today that's formed and then the target"
- **Conflicts:** E1 resting-limit rule is consistent; none listed.
- **[our interpretation]:** the stop.
- **Rulebook fix:** new rule under B12: "Non-intraday PO3 order (013 ~9:27-10:16)."
- **BUILD SPEC (setups_models):**
  - New branch `po3_resting` placed at 00:00 when the prior-close `htf.table` bias is nonzero: limit at M - `po3_rest_off_pts`, units = 1 (`lot`), no adds, ladder [day high at fill, htf objective], stop below the nearest old low under M - buffer. Managed by the normal loop with `po3_rest_mgmt="none"` (no BE, no trail).
  - Params: `po3_resting: bool = False`, `po3_rest_off_pts: float = 0.25`.
  - Test: `test_po3_resting_order`.

### 15. M5-lasthour-first-unit-at-old-low
- **rule_id / kind:** M5 / unlisted_contradiction. Scope: index. judgment = false.
- **Rule:** PM last hour (15:00-16:00), bullish bias, draw above set the night before. Unit 1 (full size, e.g. 10): buy limit at the nearest old low, filled when it is tagged, with no MSS yet. Unit 2 (same size): when a down-close candle trades back into the new bullish FVG on the rally. Planned further adds, smaller (e.g. 5): at the next FVG and at a bullish OB. Target: the HTF level from the prior night. Flat before 16:00.
- **Sources:** 013_V1thfpo-R9U ~00:26:58.
- **Quote:** "I went in with 10 contracts filled at 63 and a quarter which was the low here"
- **Conflicts:** M5 (MSS or bodies refusing the 60m FVG first) and D10 early-entry sources (003, 070, 022) vs 013's first unit at the old low before any MSS.
- **Rulebook fix:** M5: add the 013 old-low first unit; add 013 to the D10 source list.
- **BUILD SPEC (setups_models + entries_stops_sizing):**
  - In the LH slot, `lh_old_low_entry`: limit at the nearest untaken low below price (from `_sell_side` LH pools), filled on a 1-tick trade-through, before any MSS. After the fill, the first bullish FVG formed on the rally arms a same-size add on a down-close bar into it (`lh_add2_mult=1.0`); later adds use E12 half size.
  - Params: `lh_old_low_entry: bool = False`, `lh_add2_mult: float = 1.0`.
  - Test: `test_lh_old_low_first_unit`.

### 16. M6-pm-continuation-long-at-old-high
- **rule_id / kind:** M6 / missing_rule. Scope: index. judgment = false.
- **Rule:** Conditions: 13:00 or later; bias bullish; HTF objective above (old daily high, rejection block, daily level) not yet traded to; price has just traded above an intraday old high. Setup: a bullish 1m FVG whose range spans the old high's price. Entry: buy limit at the FVG's candle-3 low, filled on a 1-tick print through it. Add at the open of the first down-close candle that retraces into it. Stop below the FVG (our interpretation; ICT gives none). Target: the HTF objective (015: the daily rejection block, ~5 handles). Then arm the M6 reversal short.
- **Sources:** 015_QKvjPltjsqU ~00:31:57.
- **Quote:** "I will look for a fair value gap like this right at the old high."
- **Conflicts:** none.
- **Rulebook fix:** M6: add the continuation long that precedes the reversal.
- **BUILD SPEC (setups_models):**
  - New branch `pm_old_high_fvg` in `setups.extra_setups`, t >= 780: a same-side FVG whose range contains an intraday high taken in the last N bars, bias +1, `htf_done` false. Limit at the FVG top (candle-3 low), add at the first down-close retrace bar's open, stop below the FVG bottom - buffer, single target = the HTF objective. On the target fill, set `state["pm_rev_armed"]` so `pm_reversal` may run.
  - Params: `pm_old_high_fvg: bool = False`.
  - Test: `test_pm_old_high_fvg_long`.

### 17. M6-ifvg-must-stay-partly-open
- **rule_id / kind:** M6 / missing_condition. Scope: index. judgment = false.
- **Rule:** After the MSS down and a body close below the bullish FVG at the old high (inversion): place a sell limit at the FVG's lower edge or inside it. Valid only if the retrace candle's high stays below the FVG top, so part of the gap is never re-traded. Cancel if a candle body closes above the FVG top before the fill. Stop 1 tick above the FVG high. Take the very first retrace. Targets in order: nearest intraday liquidity, the old daily high, the 12:00-13:00 relative equal lows, then the next HTF FVG below.
- **Sources:** 015_QKvjPltjsqU ~00:33:56.
- **Quote:** "you want to see it leave some of that open"
- **Conflicts:** none.
- **[our interpretation]:** the body-close cancel.
- **Rulebook fix:** M6: add the leave-part-open condition and target order.
- **BUILD SPEC (setups_models):**
  - In `setups.pm_reversal`: `pm_rev_partial` exits the trade if any bar after fill trades above the IFVG top (gap fully re-traded), and cancels the pending order on a body close above the top. First retrace only (`pm_rev_first_only=True`). Targets: add the lunch rel-eq lows (`_eq_levels` on 720-780 bars) to the ladder after the old daily high.
  - Params: `pm_rev_partial: bool = False`.
  - Test: `test_pm_rev_gap_full_refill_exits`.

### 18. E2-far-edge-fvg-over-breaker
- **rule_id / kind:** E2 / wrong. Scope: index. judgment = false.
- **Rule:** When price retraces into a 5m bullish FVG that overlaps a bullish breaker / volume imbalance below, place the long limit at the 5m FVG's LOWER edge (the far edge; 018 core fill 4054.00). Stop below the volume imbalance. Once the short-term high breaks, the stop may be raised to the bottom of the breaker, staying below the breaker MT (4053.25). Carry the 5m FVG edges down to the 1m chart. Reclassify 018 in E2/D11 as a far-edge fill. Shorts = mirror.
- **Sources:** 018_eTMS36H7HA0 ~00:00:09.
- **Quote:** "if I can touch the bottom end down here I'm gonna buy that"
- **Conflicts:** E2/D11 list 018 as a near-edge fill; A5 calls the far edge the least likely retrace stop.
- **Rulebook fix:** E2/D11: move 018 to a "far edge when the HTF FVG overlaps a breaker/VI" case.
- **BUILD SPEC (entries_stops_sizing):**
  - In the `_scan_core` entry block, `entry="far_on_breaker"`: when the picked gap is a 5m FVG (from `sd.zones_tf(..., 5)`) and it overlaps `breaker_zone` or a same-side VI, the limit goes at the far edge + 1 tick; stop below the VI/breaker bottom. Else the normal `entry`.
  - Params: add "far_on_breaker" to `entry` choices.
  - Test: `test_far_edge_when_overlapping_breaker`.

### 19. new-pm-retracement-short-after-draw-delivered
- **rule_id / kind:** M7 / M3, missing_rule. Scope: index. judgment = true.
- **Rule:** Conditions: the day's predefined draw has been reached (AM, or 14:00-15:00). Then either (a) price body-closes below the 5m FVG that served as AM support (flip to resistance) and a 1m BPR or FVG forms at or under that resistance, or (b) a displacement candle down leaves a SIBI. Entry: sell limit at the BPR/SIBI near edge, filled 13:30-15:00, preferring ~14:00, never before 13:20. Require at least 10 handles to the next inefficiency/liquidity void below. Stop above the BPR high, the 5m FVG CE or the FVG candle. Targets: the sell-side under the relative equal lows, the nearest void, then the AM-origin low. Long = mirror.
- **Sources:** 019_ZrZJmwrMxFY ~00:20:53; 060_ZtLMTXv-Dr0 ~01:09:30.
- **Quote:** "that would be a short for a silver bullet because we hit our objective we broke down"
- **Conflicts:** M3 (SB displacement toward the draw) vs 060's opposite-direction SB after the objective is hit.
- **Rulebook fix:** M7: add the post-delivery PM retracement short; list the M3 conflict.
- **BUILD SPEC (setups_models + silver_bullet):**
  - setups_models: branch `pm_after_draw` in `setups.extra_setups`. Needs the session lock delivered (`done` / `htf_done`). Trigger (a) a body close below an AM 5m bullish FVG then a 1m BPR/FVG at or below it, or (b) any bearish MSS leaving a SIBI. Window 800-900, room >= `pm_after_room_pts` to the next void/FVG below. Targets: lunch rel-eq lows, nearest void, AM-origin low.
  - silver_bullet: `sb_counter_after_draw` lets `_arm` take the opposite side in 14:00-15:00 once the session draw is delivered, with the same 10-handle room rule.
  - Params: `pm_after_draw: bool = False`, `pm_after_room_pts: float = 10.0`, `sb_counter_after_draw: bool = False`.
  - Test: `test_pm_after_draw_short`, `test_sb_counter_after_draw`.

### 20. M1-ob-entry-after-mss
- **rule_id / kind:** M1 / missing_condition. Scope: index. judgment = false.
- **Rule:** MMBM entry variant (020 is a PM last-hour example, so it belongs to M5 / the general entries): after sell-side is run and a short-term high breaks upward, buy limit inside the FIRST down-close candle of the ensuing pullback (its high-to-open sensitive range, A12). Per A12, price may wick to that candle's MT; a body close through the MT invalidates. Target the buy-side above, then the next PD array (020: the NWOG low, then its CE).
- **Sources:** 020_MqOVbd1oqZk ~00:06:14, ~00:01:29.
- **Quote:** "I bought inside the first down closed candle as it was going down"
- **Conflicts:** none.
- **Rulebook fix:** M5 / E2: add the post-MSS first-pullback OB entry.
- **BUILD SPEC (setups_models):**
  - Add "ob_post" to `entry_arrays`: after the MSS, the first down-close bar of the pullback arms a limit at its high (`ob_entry_px` reused: body_top / mt), cancelled on a body close below its MT.
  - Params: extend the `entry_arrays` allowed set with "ob_post".
  - Test: `test_entry_arrays_ob_post`.

### 21. B5-multi-tf-fvg-scan
- **rule_id / kind:** M2 / B5, missing_condition. Scope: general. judgment = false.
- **Rule:** After the MSS, take the displacement leg (the high after the BSL run to the low that broke structure). Look for FVGs (and VIs) at or above the leg EQ on the 5, 4, 3, 2 and 1 minute bars of that leg. Work top-down from 15m to 5m to 1m until the imbalance or model is visible. When a higher-TF gap holds a narrower lower-TF gap, the lower-TF boundaries are the more sensitive level. The bot's search order (1m, then 3m, then 5m) is our interpretation.
- **Sources:** 022_ALMsQytQ1fg ~00:43:05, ~01:47:01; 055_qiv8pkcNvGk ~00:11:46.
- **Quote:** "you want to go through all your time frames. 5 4 3 2 1."
- **Conflicts:** none.
- **Rulebook fix:** M2: add the multi-TF scan of the leg.
- **BUILD SPEC (setups_models):**
  - In the `_scan_core` gap pick, when `p.leg_tfs` is non-empty and no 1m FVG qualifies at or above EQ, look for one on each TF in order using `sd.zones_tf(idx, base, m)`; take the first. Where a higher-TF gap contains a lower-TF gap, use the lower-TF edges.
  - Params: `leg_tfs: tuple = ()` (e.g. (2, 3, 4, 5)).
  - Test: `test_leg_tf_fallback_3m`. No 1m FVG in the leg, a 3m FVG above EQ arms the order.

### 22. M2-leg-eq-after-low-prints
- **rule_id / kind:** M2 / shortened. Scope: general. judgment = false.
- **Rule:** The leg runs from the high to the final low of the displacement that broke the short-term low. EQ is not fixed until that low prints, so recompute it on each new low. After that, a short is valid only when price trades meaningfully above EQ AND into an FVG inside the leg at or above EQ. A shallow poke above EQ that touches no such FVG is no entry. Long = mirror.
- **Sources:** 022_ALMsQytQ1fg ~00:47:17, ~00:49:31.
- **Quote:** "this level isn't the equilibrium until this low"
- **Conflicts:** none.
- **Rulebook fix:** M2: add the moving leg anchor and the "touch an FVG, not just EQ" rule.
- **BUILD SPEC (setups_models):**
  - In the M2 pick (`fvg_pick="m2"`), recompute `leg_lo` on every new extreme after the break and re-filter the candidate FVGs; cancel a pending order whose FVG falls below the new EQ. The fill rule already needs the FVG touch; add a test.
  - Params: `m2_live_eq: bool = False`.
  - Test: `test_m2_eq_moves_with_new_low`.

### 23. M2-pyramid-runup-leg-eq
- **rule_id / kind:** M2 / missing_condition. Scope: general. judgment = true.
- **Rule:** Large-pyramid option: anchor from the swing low that started the run-up into the BSL to the sweep high, and take EQ = midpoint. Prefer a sell-side VI at or above that EQ in the displacement down; with no VI, use the FVG there. The default stays the displacement-leg EQ.
- **Sources:** 022_ALMsQytQ1fg ~01:03:28.
- **Quote:** "I'll use this run up where it takes right before it drops down"
- **Conflicts:** none.
- **Rulebook fix:** M2: add the run-up anchor as an alternative.
- **BUILD SPEC (setups_models):**
  - `m2_anchor="runup"`: the EQ is computed from the swing low before the run into the swept pool (last pivot low before `sd.sweep` ext_i) to the sweep high; VI first, FVG second.
  - Params: `m2_anchor: str = "leg"`.
  - Test: `test_m2_runup_anchor`.

### 24. E1-close-proximity-entries
- **rule_id / kind:** E1 / missing_rule. Scope: general. judgment = false.
- **Rule:** With the draw known and inside an active macro or time window (shown for 10:50-11:10), after the MSS enter on the first trade into the nearest VI/FVG/candle created by the shift, as close inside the VI as possible. Do not wait for a breaker retest. (Filling on the creating candle is not stated.)
- **Sources:** 022_ALMsQytQ1fg ~03:08:33.
- **Quote:** "It's called close proximity entries. You don't need a breaker"
- **Conflicts:** none.
- **Rulebook fix:** E1: add close-proximity entries (macro window + known draw).
- **BUILD SPEC (entries_stops_sizing):**
  - `close_proximity`: inside the T6 macro windows (the module constant at strategy.py ~56; default only 10:50-11:10 via `close_prox_windows`) and with a session lock, the pick is the nearest-to-price VI/FVG created by the MSS leg, limit at its near edge; not the M2 EQ filter.
  - Params: `close_proximity: bool = False`, `close_prox_windows: tuple = ((650, 670),)`.
  - Test: `test_close_proximity_nearest_vi`.

### 25. sub-minute-entry-refinement
- **rule_id / kind:** M3 / M7, missing_rule. Scope: needs_unavailable_data. judgment = true.
- **Rule:** When the draw is predetermined and confirmed and the 1m entry zone is an OB or VI with no visible 1m FVG: inspect 45s/30s/15s/5s/1s bars inside that zone. Enter at the sub-minute FVG/OB found there, and read the MSS/FVG on the lowest TF available, not the 5m. Stop placement and any 1m approximation are our interpretation.
- **Sources:** 022_ALMsQytQ1fg ~03:13:12; 059_ZfnY2SH3G24 ~00:17:12; 067_vuBRMFhFZAY ~00:46:52.
- **Quote:** "wait for a shift in Market structure value Gap don't trust the five minute chart"
- **Conflicts:** none.
- **Rulebook fix:** M3/M7: "sub-minute refinement inside the 1m OB/VI (needs sub-minute data)".
- **BUILD SPEC:** none (needs sub-minute bars).

### 26. M2-implied-range-eq-gate
- **rule_id / kind:** M2 / E12, missing_rule. Scope: general. judgment = false.
- **Rule:** After buy-side is run (suspect high H), implied range = H to the target, EQ = midpoint. Treat H as valid only after price trades from premium into discount (below EQ). Then short on the return to EQ or premium at the first PD array (VI/FVG/OB) there. Entries and adds only above EQ, and adds continue while no structural short-term low has broken. Stop above the FVG/OB candle high. Cancelling if H trades first is our interpretation. Long = mirror.
- **Sources:** 025_7RiUUCqQ3SY ~00:46:41; 060_ZtLMTXv-Dr0 ~01:24:16.
- **Quote:** "we don't know if this high is going to be well taken out until we trade from premium to Discount"
- **Conflicts:** none.
- **Rulebook fix:** M2: add the implied-range confirmation and entry gate; E12 keeps the add cutoff.
- **BUILD SPEC (setups_models):**
  - `implied_range_gate`: after the MSS, compute EQ_i = (sweep high + session lock target)/2. Do not arm the M2 order until a bar trades below EQ_i; then accept only FVG/VI/OB entries at or above EQ_i. Adds (`_arm_add`) only above EQ_i while no new swing low below the post-MSS low. Cancel if H trades first.
  - Params: `implied_range_gate: bool = False`.
  - Test: `test_implied_range_needs_discount_first`.

### 27. E2-vi-primary-entry-array
- **rule_id / kind:** E2 / missing_rule. Scope: index. judgment = false.
- **Rule:** After a bearish MSS, if the displacement leg holds a bearish VI at or just above the leg/implied-range EQ, place the initial short inside the VI (between the two candles' close and open). It fills while an up-close candle trades into it. Use the FVG only when there is no such VI. Long = mirror.
- **Sources:** 025_7RiUUCqQ3SY ~00:49:04; 026_GFdWahZUNOw ~01:36:42.
- **Quote:** "as soon as it trades there right then and there while that candle is bullish"
- **Conflicts:** none.
- **Rulebook fix:** E2: VI first, FVG fallback, for the initial entry.
- **BUILD SPEC (entries_stops_sizing):**
  - `vi_first`: in the `_scan_core` gap pick, if a same-side VI (`sd.vis`) inside the leg sits at or above EQ (within `eq_tol_pts`), it is the entry zone (limit at its near edge); else the FVG pick. Uses levels_detectors' `volume_imbalances` wiring (`vi_arrays`).
  - Params: `vi_first: bool = False`.
  - Test: `test_vi_first_over_fvg`.

### 28. M7-pm-short-after-lunch-run-of-am-stops
- **rule_id / kind:** M7 / missing_rule. Scope: general. judgment = false.
- **Rule:** Bearish AM: after noon (run seen at about 13:30), wait for price to run above the most recent AM swing high (the trailed short stops), ideally back above the NWOG, with the overshoot often stopping at a VI above. Then wait for a break back below the NWOG/short-term low that leaves an FVG. Short the retrace to the FVG CE in premium of the post-run range. Partial at the intermediate REL, final target the AM session low. Long = mirror.
- **Sources:** 025_7RiUUCqQ3SY ~01:05:57.
- **Quote:** "induce new buyers that think of that opening Gap as a breakout"
- **Conflicts:** none. Hindsight review.
- **Rulebook fix:** M7: add the trailed-AM-stops PM template.
- **BUILD SPEC (setups_models):**
  - New PM pool kind `am_last_high` (the last AM swing high before 12:00) in `_sell_side` for PM sessions when `p.pm_am_stops`; the session target = the AM low. Entry `entry="ce"`. Rel-eq pools between become the first rung.
  - Params: `pm_am_stops: bool = False`.
  - Test: `test_pm_am_last_high_sweep_targets_am_low`.

### 29. A5-wick-ce-inside-fvg-exact-entry
- **rule_id / kind:** A5 / E2, missing_rule. Scope: general. judgment = false.
- **Rule:** For a short FVG [low, high], look left for prior candles whose upper or lower wick CE (A23) lies within [low, high]. If one exists, set the sell limit at that wick CE instead of the FVG edge, expecting a tick-exact touch (for the bot, 1 tick inside per E3). Long = mirror.
- **Sources:** 025_7RiUUCqQ3SY ~01:08:00.
- **Quote:** "extend it through this fair value Gap and you'll get the very tick high"
- **Conflicts:** none.
- **Rulebook fix:** A5: add the wick-CE-in-FVG refinement.
- **BUILD SPEC (entries_stops_sizing):**
  - `wick_ce_refine`: after the gap pick, scan the bars before the leg (last `wick_ce_lookback` bars, same session) for a wick CE (`levels.wick_ce` / `wick_midpoints`) inside the gap; if found, the limit = that CE -/+ 1 tick.
  - Params: `wick_ce_refine: bool = False`, `wick_ce_lookback: int = 120`.
  - Test: `test_wick_ce_refines_entry`.

### 30. E4-redelivery-wick-suffices
- **rule_id / kind:** E4 / unlisted_contradiction. Scope: index. judgment = false.
- **Rule:** Bearish: after a down-close candle D, the redelivery requirement is met by any later movement that trades up across D's full range (up-close body or just an upper wick) before a lower low. The candle need not close up. A short may be placed into that upward redelivery (inference). Long = mirror. List as a conflict with E4's 'at least one up-close candle'.
- **Sources:** 026_GFdWahZUNOw ~01:57:39.
- **Quote:** "it doesn't need to close with an up candle if it was a recent down closed candle"
- **Conflicts:** E4 "a short needs at least one up-close candle" vs 026.
- **Rulebook fix:** E4: add the wick-redelivery case; list the conflict in Section 3.
- **BUILD SPEC (entries_stops_sizing):**
  - E4's candle-color requirement is not coded yet. Add `e4_color` to the pending-fill block of `run_day`: a short fills only on an up-close bar (long: down-close). With `e4_wick_ok`, a fill bar whose high reaches the high of the most recent down-close bar also counts, whatever its close.
  - Params: `e4_color: bool = False`, `e4_wick_ok: bool = False`.
  - Test: `test_e4_wick_redelivery_counts`.

### 31. M5-lasthour-short-sequence
- **rule_id / kind:** M5 / missing_rule. Scope: index. judgment = false.
- **Rule:** 15:00-16:00 short (long = mirror). (1) Pre-mark a bearish VI/PD array above price, with the draw below. (2) From 15:00, price rallies into it and a candle's high respects it; trading above that high invalidates the setup. (3) Early confirmation: the next candle makes no higher high and does not touch the VI again, then its low is taken. (4) MSS: the short-term swing low formed after the reaction is pierced by at least 1 tick; no close needed. (5) Entry: sell the VI created by the displacement as soon as price trades back into it, even while that candle is up-close (026). Alternatively, sell the SIBI CE when it coincides with a bearish breaker (047). Add on an IOFED into the next SIBI. Stop above the rejection candle's high. Target: the draw / untapped sell-side, or the -3 SD projection of the MSS leg, typically reached 15:15-15:45. Entries 15:00-15:50 (T10, owner #1).
- **Sources:** 026_GFdWahZUNOw ~01:35:33; 047_441vklRYYR4 ~00:09:56.
- **Quote:** "this candle fails to make a higher high to that one or even touch back into that volume of balance"
- **Conflicts:** M5 puts the raid in 15:15-15:45; in 047 only the target lands in that window.
- **Rulebook fix:** M5: add the short sequence and the early-confirmation step; relax the raid-window note.
- **BUILD SPEC (setups_models):**
  - LH-slot branch `lh_array_short` in `setups.extra_setups` (t 900-950). Reference: a bearish VI/FVG above price, marked before 15:00. A bar whose high enters it without closing above it is the rejection bar R. The next bar must make no higher high and not touch the array; its low taken = early confirmation. The post-reaction swing low pierced by 1 tick = MSS. Entry via `vi_first` (item 27) into the displacement VI, else the SIBI CE. Stop above R's high; target the lock or -3 SD of the MSS leg.
  - Params: `lh_array_short: bool = False`.
  - Test: `test_lh_array_short_sequence` (both sides).

### 32. B16-nwog-gapup-return-then-mss
- **rule_id / kind:** B16 / missing_rule. Scope: index. judgment = false.
- **Rule:** If the Sunday open gaps above Friday's close and the bullish scenario is in play: wait for price to trade back all the way to Friday's close. After that touch, require a bullish LTF MSS (A19) before buying. Enter on the PD array the MSS leaves. Draw: the inefficiencies / buy-side above. A touch of the close with no MSS is not an entry. Bearish case: a gap down need not return to Friday's close; failing to fill even half the gap signals weakness (breakaway gap).
- **Sources:** 028_wWvFUW-jY4w ~01:22:36 (the claim said 00:22:36; also ~1:10-1:16).
- **Quote:** "I'm not trying to just simply go in there and blindly buy the retracement"
- **Conflicts:** none.
- **Rulebook fix:** B16: add the gap-up return-to-close-then-MSS protocol and the half-gap weakness note.
- **BUILD SPEC (setups_models; NWOG levels from levels_detectors `opening_gaps`):**
  - `nwog_fill_long`: in a gap-up week, long setups require that price has traded to the NWOG low (Friday close) at least once since the Sunday open, and that the sweep extreme is within `nwog_fill_tol_pts` of it. The normal MSS/FVG path follows. Tag `nwog_fill`.
  - Params: `nwog_fill_long: bool = False`, `nwog_fill_tol_pts: float = 2.0`.
  - Test: `test_nwog_fill_then_mss_long`.

### 33. M11-wick-ce-fade-short
- **rule_id / kind:** M11 / A23, missing_rule. Scope: index. judgment = true.
- **Rule:** Bearish bias. Upper-wick CE = (high + max(open, close)) / 2 of the reference candle. (a) Intrabar (028): after a down-close precursor and a wick at the high, when a new candle trades up toward that wick's CE, sell on a limit just below the CE, with no close confirmation. Stop just above the CE [our padding] or above the wick high. (b) Optional retrace variant (042): after a breakdown that left no FVG, sell the retrace into the long upper wick's CE (or the top of a marked zone above) before the targeted lows are taken. (c) Forecast trigger (084, 1h/15m): once price trades below the CE of a wick that ran buy-side, treat the CE as resistance and sell retraces into it. Target: the next sell-side pool / HTF imbalance. Only valid before the targeted lows trade. Context filter (084): if price trades above the nearest bearish IFVG overhead, doubt the weekly short draw. Long = mirror.
- **Sources:** 028_wWvFUW-jY4w ~00:18:38; 042_hQ379EuyNKQ ~00:33:56; 084_VdGihxSuSRk ~00:30:43.
- **Quote:** "I'm trusting that it won't even go through consequent encroachment"
- **Conflicts:** M11 needs the next candle to close beyond the CE; 028 enters intrabar.
- **Rulebook fix:** M11: add the short side and the three variants; list the conflict.
- **BUILD SPEC (setups_models):**
  - Builds on `wick_ce_entries` (M11c, long, close-confirmed). New `wick_ce_mode`:
    - "close" = existing behaviour.
    - "intrabar" = limit at CE - 1 tick from the next bar's open; stop at CE + `wick_ce_pad_pts`.
    - "retrace" = after an MSS that left no FVG, the sweep candle's wick CE is the entry.
  - Both sides. Variant (c) is "close" on 15m/60m candles (`wick_ce_tf`).
  - Params: `wick_ce_mode: str = "close"`, `wick_ce_pad_pts: float = 1.0`, `wick_ce_tf: int = 0`.
  - Tests: `test_wick_ce_short_intrabar`, `test_wick_ce_retrace_no_fvg`.

### 34. M5-lasthour-shallowest-unused-array
- **rule_id / kind:** M5 / shortened. Scope: index. judgment = true.
- **Rule:** After a bullish MSS (1 tick through the short-term high, no close needed) in the last hour, list the PD arrays in the leg from the swing low to the MSS candle high (OB = consecutive down-close candles, VI, FVG). Exclude any array price has already traded back into. Enter at the most sensitive (highest) remaining one; here, a VI near the top of the leg. Target the buy-side above. Stop: not stated [ours: below the OB MT / leg low]. Exit per T10/T11. Short = mirror.
- **Sources:** 030_ZdnGlropfmU ~00:21:36.
- **Quote:** "why would we want to see it come back down and touch it because it's already done so"
- **Conflicts:** none.
- **Rulebook fix:** M5: add the selection rule (shallowest unused array).
- **BUILD SPEC (setups_models):**
  - `entry_pick="shallowest_unused"` over the `entry_arrays` candidates (`setups.array_cands`): drop arrays already touched between their creation and the MSS bar, then pick the one nearest price.
  - Params: `entry_pick: str = "first"`.
  - Test: `test_shallowest_unused_array_pick`.

### 35. new-nwog-edge-to-ce-cookie-cutter
- **rule_id / kind:** new / missing_rule. Scope: index. judgment = true.
- **Rule:** Research tag nwog_edge_to_ce (ICT did not trade it in the source). When price trades to the high (low) of the current or previous week's NWOG and rejects it, target that NWOG's CE (~5+ ES pts away). Optionally use the lower quarter as an extension. Take profit just before the CE. Best on one-sided/trending days; skip choppy, aimless conditions.
- **Sources:** 030_ZdnGlropfmU ~01:09:40.
- **Quote:** "that's five handles as a new startup a student"
- **Conflicts:** none.
- **[our interpretation]:** "rejects" = a 1m MSS away from the edge; the chop filter = `Chop` (owner #10).
- **Rulebook fix:** L5: add a research note.
- **BUILD SPEC (setups_models):**
  - Branch `nwog_edge_ce`: NWOG edges (`_nwogs`) count as pools for the sweep test. The target is forced to the NWOG CE - `exit_before_pts`. Require >= 5 pts of room. Skip when `Chop.active_before(i)`.
  - Params: `nwog_edge_ce: bool = False`.
  - Test: `test_nwog_edge_to_ce`.

### 36. M8-short-after-reprice-to-prior-close
- **rule_id / kind:** M8 / missing_rule. Scope: index. judgment = true.
- **Rule:** Gap-down / bearish day: if price retraces up to the prior RTH close (ES 16:15 settlement) and then breaks a short-term low with displacement (MSS), short the retrace into the PD array that leg leaves [entry type ours]. Target the session low / the sell-side below. Window: before 12:00. Scenario-grade. The gap-up mirror is ours.
- **Sources:** 030_ZdnGlropfmU ~01:47:48.
- **Quote:** "if we can reprice up to this 41.50 and a quarter level and say it breaks down you have shift on Market structure"
- **Conflicts:** none.
- **Rulebook fix:** M8: add the follow-on short after the ORG fill.
- **BUILD SPEC (setups_models):**
  - `org_fill_reverse`: on a gap day, once touched, the ORG far edge (prior close, `_org_state`) counts as a sweep pool. The normal MSS/FVG path follows. Target = the session low. Entries only before 720.
  - Params: `org_fill_reverse: bool = False`.
  - Test: `test_org_fill_then_short`.

### 37. A12-entry-array-at-key-level
- **rule_id / kind:** A12 / missing_condition. Scope: index. judgment = true.
- **Rule:** An OB/FVG entry is preferred only when the OB candle formed at a predefined key level and displacement starts from that level. In 032 the level is the previous week's NWOG low; NDOG/NWOG/ORG edges and CEs and session levels are our generalisation. Skip OBs/FVGs that form mid-leg away from such a level. The proximity tolerance N (default 2 ticks) is ours.
- **Sources:** 032_SSWN6YSVyFY ~00:21:34.
- **Quote:** "I wanted to see it trade back to this key level which is the previous week's new week opening Gap"
- **Conflicts:** none.
- **Rulebook fix:** A12: add the location condition.
- **BUILD SPEC (setups_models):**
  - `ob_at_key` in `finish_gates`: the OB candle (the last opposite candle before the displacement) must have its extreme within `ob_key_ticks` of a key level. Key levels: NWOG/NDOG edges and CE (`_nwogs`), ORG edges, and session pools from `mark_levels`. Modes "tag" / "require".
  - Params: `ob_at_key: str = "off"`, `ob_key_ticks: int = 2`.
  - Test: `test_ob_at_key_level`.

### 38. E2-fvg-first-then-ob-open
- **rule_id / kind:** E2 / missing_condition. Scope: index. judgment = false.
- **Rule:** Short (long = mirror): when the entry FVG sits below the bearish OB (the last up-close candle at the key level), place entry #1 in the FVG. Place entry #2 at the OB candle's opening price in case price reaches it. Never wait for the OB alone. [Ours: #2 sized per E12, one stop above the OB per E6, cancel #2 once T1 fills.]
- **Sources:** 032_SSWN6YSVyFY ~00:23:46.
- **Quote:** "you allow for the price to trade up to that level because if it does then you do another entry there"
- **Conflicts:** none.
- **Rulebook fix:** E2: add the FVG-then-OB-open split.
- **BUILD SPEC (entries_stops_sizing):**
  - `fvg_then_ob` (with `ob_entry="post_mss"` or "both"): when the leg's OB sits beyond the picked FVG, create the FVG order plus a pending add at the OB open (`_arm_add`, E12 size). Both share one stop above the OB. Cancel the add when T1 fills.
  - Params: `fvg_then_ob: bool = False`.
  - Test: `test_fvg_first_then_ob_add`.

### 39. M4-breaker-needs-fvg-inside
- **rule_id / kind:** M4 / missing_condition. Scope: index. judgment = false.
- **Rule:** Add to M4 (2023 qualifier, 032 ~42:00): a breaker range alone is not an entry. It marks the maximum retracement (down to the breaker candle low for bullish). Trade only an FVG that lies inside or overlaps the breaker (= unicorn, A14), with a limit at its near edge or CE. Bodies should stay inside the FVG/breaker; wicks may overshoot. A body close below the breaker low invalidates. Make CC 'classic' breaker-only entries a switch, off by default for the 2023 model, and record it as a decision. Bearish = mirror.
- **Sources:** 032_SSWN6YSVyFY ~00:42:02.
- **Quote:** "by itself it means nothing"
- **Conflicts:** M4 classic "buy the first return to the bullish breaker" vs 032.
- **Rulebook fix:** M4: add the 2023 qualifier; Section 3 decision CC classic vs 2023.
- **BUILD SPEC (setups_models):**
  - Mostly already switchable: `unicorn_only` gives the 2023 behaviour and `breaker_entry="classic"` gives the CC one (both off).
  - New: `breaker_low_invalidate` cancels any breaker/unicorn order, and exits an open one, after a body close beyond the breaker candle's far extreme (not its MT).
  - Params: `breaker_low_invalidate: bool = False`.
  - Test: `test_breaker_body_close_below_low_cancels`.

### 40. A13-breaker-inversion-against
- **rule_id / kind:** A13 / missing_rule. Scope: general. judgment = true.
- **Rule:** While a bullish breaker holds (bodies respect it), take no shorts; an FVG above price alone does not qualify a short. If price trades below the breaker / dealing-range low:
  - If it rejects back inside the range, treat it as a stop run and keep the long idea.
  - If it accelerates lower and treats the breaker as an inversion (bodies close below it, then it acts as resistance), drop the long bias and stand aside. Do not reverse automatically (048).
  - A counter-trend short needs both a body break below the breaker and a later retrace up into it that rejects as resistance, ideally after buy-side above a short-term high is run into premium (033).
  - Mirror for longs against a bearish breaker.
- **Sources:** 033_KXx07qzW5u0 ~00:49:43; 048_gGxVE8zUIRQ ~01:54:11.
- **Quote:** "you can't just simply say oh we have a fair value Gap"
- **Conflicts:** 033 allows a short after break + retest; 048 says abandon and wait.
- **Rulebook fix:** A13: add the hold/no-counter rule and the inversion test.
- **BUILD SPEC (setups_models):**
  - Track the latest active same-session breaker per side (`breaker_zone`). With `breaker_block_counter`, shorts are blocked while a bullish breaker is unbroken on a body-close basis.
  - A body close below the breaker sets `state["breaker_inverted"]`, which blocks longs for the session. A short then needs a retrace into the zone and a bar closing back below it (the normal MSS path, with the zone as the sweep "array").
  - Params: `breaker_block_counter: bool = False`.
  - Tests: `test_breaker_blocks_counter_shorts`, `test_breaker_inversion_stands_aside`.

### 41. A17-rejection-block-short-protocol
- **rule_id / kind:** A17 / missing_rule. Scope: general. judgment = false.
- **Rule:** Bearish rejection-block short:
  1. Level = the close of the candle that made an old (daily) swing high.
  2. Price trades to and through that close (high > level).
  3. A 1m or 5m short-term swing low (3-candle pivot) is traded through by a wick; no close beyond it is required.
  4. A bearish FVG forms above that pierced low, inside the down leg.
  5. Enter short at the FVG per M2 (limit at the near edge, stop above the FVG/OB MT, target sell-side).

  If the HTF bias opposes the trade, do not trade it; use the level only as a partial-profit target for trades in the bias direction. Bullish = mirror.
- **Sources:** 035_kFIOp8Tprdc ~00:23:08.
- **Quote:** "a small short term one minute or five minute Candlestick swing low is pierced it does not need to close below it"
- **Conflicts:** none.
- **Rulebook fix:** A17: add the entry protocol and the against-bias = target-only rule.
- **BUILD SPEC (levels_detectors + setups_models):**
  - levels_detectors: wire `levels.rejection_blocks` on daily bars into `htf._arrays` as kind "rb" (level = the swing candle's close).
  - setups_models: with `p.rb_pools`, "rb" levels count as sweep pools and the MSS uses a wick pierce. Against the `htf.table` bias they go only to `_targets`, as rungs.
  - Params: `rb_pools: bool = False`.
  - Tests: `test_rb_close_pool_short`, `test_rb_against_bias_target_only`.

### 42. new-dxy-unicorn-es-long-trigger
- **rule_id / kind:** new / missing_rule. Scope: needs_unavailable_data. judgment = false.
- **Rule:** DXY 1m bearish breaker: swing high 1, a swing low, a higher swing high 2 that takes the buy-side above high 1, then a break below the swing low. The zone is the down-close candle at that swing low. If a 1m SIBI forms inside the zone and DXY retraces up into it, the overlap is DXY's "last line of defense". While DXY trades into it without closing above the FVG high, take ES long setups. If DXY closes above the FVG/breaker top, cancel the long or exit.
- **Sources:** 037_wu0sQarBRrI ~00:44:40.
- **Quote:** "that's like the last line of defense for me because it's inside the breaker"
- **Conflicts:** none.
- **Rulebook fix:** B19: add the DXY unicorn as an ES trigger/invalidation (needs DXY 1m data).
- **BUILD SPEC:** none (needs intraday DXY).

### 43. new-sweep-wick-ce-failure-swing-long
- **rule_id / kind:** A23 / new, missing_rule. Scope: index. judgment = true.
- **Rule:**
  1. Price runs sell-side below a REL/old low, ideally into a pre-marked NWOG/NDOG/ORG below it.
  2. The sweep candle (15m or 5m, overnight included) leaves a lower wick. Mark its CE per A23: (min(open, close) + low) / 2.
  3. Price bounces, later retraces to that wick CE without trading back to the sweep low (failure swing / higher low), then shifts structure.

  Entry: long at the wick CE, or at the post-MSS bullish OB/FVG once the CE holds. Stop/invalidation: below the sweep-wick low. Target: the unfilled overhead HTF FVG and the buy-side above it. Bearish = mirror. Do not trade it on FOMC/news-uncertainty days (038 was observe-only).
- **Sources:** 038_4H74nXabvL0 ~00:50:59; 080_XODINFwpeaw ~00:05:45, ~00:14:17.
- **Quote:** "this failure swing you can now anticipate"
- **Conflicts:** none.
- **Rulebook fix:** A23/M11: add the sweep-wick-CE failure-swing sequence.
- **BUILD SPEC (setups_models):**
  - Extend `wick_ce_entries` with `wick_ce_tf` (item 33) = 5 or 15: the sweep candle on that timeframe gives the CE. The order is placed when a later bar's low comes within 1 tick of the CE while the sweep low is intact. Stop below the sweep low. Skip FOMC days via `blocked()`.
  - Params: shares `wick_ce_tf` and `wick_ce_mode`; add `wick_ce_need_pool: bool = True` (the sweep must take a REL/old low).
  - Test: `test_15m_sweep_wick_ce_long`.

### 44. E5-stop-feasibility-at-entry-location
- **rule_id / kind:** E5 / missing_condition. Scope: index. judgment = true.
- **Rule:** Short (long = mirror). With a fixed risk budget S (042: 5 handles), place the limit only where entry + S clears the level price can normally retrace to (the breaker / higher FVG top), and only when the entry is in premium on an up-close candle (E4). If the first post-MSS FVG would need a stop above the latest short-term high (more risk than allowed), skip it. If price then rallies once more into premium (069: above the midnight open, into the FVG) without piercing that short-term high, and breaks lower again leaving FVGs, enter the new FVG with the stop just above the CE of the higher of the two gaps. Otherwise skip.
- **Sources:** 042_hQ379EuyNKQ ~00:48:56; 069_Sf_uYZBWTrA ~00:12:57.
- **Quote:** "my five handles doesn't provide me enough Shield"
- **Conflicts:** none.
- **Rulebook fix:** E5: add the concrete stop-feasibility test and the wait-for-the-second-break path.
- **BUILD SPEC (entries_stops_sizing):**
  - `max_stop_pts` in `_finish_order`: if the structural stop is farther than `max_stop_pts`, drop the order but keep the sweep alive (`sw` not reset). A later MSS (second break, lower high below the prior short-term high) can then arm with `stop_mode="ce2"` (exists).
  - Params: `max_stop_pts: float = 0.0`.
  - Test: `test_wide_stop_skipped_then_second_break`.

### 45. E2-iofed-breaker-exact-match
- **rule_id / kind:** E2 / E3, shortened. Scope: general. judgment = false.
- **Rule:** Bearish breaker/OB retrace: place the sell limit at, or 1 tick below, the high of the breaker candle(s). The retrace counts as an IOFED if price trades up to exactly that high without exceeding it. For bot fills, put the limit 1 tick inside the level so an exact match fills under E3. Long = mirror.
- **Sources:** 043_NkwqJBzgQwo ~00:16:21.
- **Quote:** "all it has to do is match that price"
- **Conflicts:** E3 (a fill needs 1 tick through) vs 043 (matching is enough).
- **Rulebook fix:** E2: add the IOFED-at-breaker case. E3: note the 1-tick-inside placement.
- **BUILD SPEC (entries_stops_sizing):**
  - `breaker_iofed`: breaker orders (`_breaker_order`, `cc_breaker_order`) place the limit 1 tick inside the breaker candle extreme.
  - Params: `breaker_iofed: bool = False`.
  - Test: `test_breaker_iofed_exact_match_fills`.

### 46. M7-pm-mss-after-1300-targets
- **rule_id / kind:** M7 / shortened. Scope: index. judgment = true.
- **Rule:** After 13:00, a bullish MSS with displacement targets the successive buy-side pools formed during lunch and before it: lunch highs, then earlier AM swing highs, up to an old high or an SD projection in premium (e.g. -1.5 SD). ICT ties it to a daily-consolidation context (043). Bearish = mirror.
- **Sources:** 043_NkwqJBzgQwo ~00:13:28.
- **Quote:** "now we're gonna run for the stops prior to what during and prior to lunch"
- **Conflicts:** elsewhere the PM window starts at 13:30; here the MSS comes after 13:00. T9 already lists 13:00 as an option.
- **Rulebook fix:** M7: add the lunch + pre-lunch buy-side ladder.
- **BUILD SPEC (targets_partials):**
  - `pm_ladder_am`: for PM orders, `_targets` adds the lunch high and every untaken AM swing high (09:30-12:00 pivots, `seen_from_created`) as rungs, nearest first, then the SD projection of the MSS leg (`pm_sd_mult`).
  - Params: `pm_ladder_am: bool = False`, `pm_sd_mult: float = 1.5`.
  - Test: `test_pm_ladder_includes_am_highs`.

### 47. M16-sick-sister-ob-open-entry
- **rule_id / kind:** M16 / shortened. Scope: general. judgment = true.
- **Rule:** Condition: the leader (ES) has made the higher high and the laggard (NQ) has not taken its matching high. Entry: buy the laggard at the opening price of its current down-close (OB) candle while that candle is still forming. No return to the OB is required. Target: the laggard's matching old high. No stop is given; the proxy is below the OB candle low. ICT says it also applies to correlated FX pairs.
- **Sources:** 045_DNi9S3_NA44 ~01:41:00.
- **Quote:** "you can trade inside of the range of that candle you don't need it to go away and come back"
- **Conflicts:** 053 requires a deep-discount retrace (OTE + OB + FVG); 045 buys the forming OB candle with no deep-discount condition.
- **Rulebook fix:** M16: add the forming-OB-open entry and the conflict with 053.
- **BUILD SPEC (setups_models):**
  - Builds on `sick_sister` (M16.2, which uses `psides` for the partner index). `sick_entry="ob_open"`: when the partner index has taken its reference high and this one has not, the first down-close bar arms a buy limit at that bar's open. It fills when a later trade comes back to the open. Stop below the bar's low; target the matching high.
  - Params: `sick_entry: str = "discount"` ("ob_open").
  - Test: `test_sick_sister_ob_open`.

### 48. new-lunch-macro-long-nwog
- **rule_id / kind:** new / missing_rule. Scope: index. judgment = true.
- **Rule:** Lunch-macro forecast (046, ~11:54). After a down AM, price may retrace into the zone between the old NWOG CE and the NWOG low (or a down-close OB there), but it must not trade below the NWOG low, and the gap between the NWOG low and the retrace low must stay partly open. From ~12:00, expect large-range candles through the NWOG high into the buy-side and the FVG above it. An entry in that zone with a stop below the NWOG low is our interpretation (ICT did not state or take an entry). Experimental, and in conflict with T8.
- **Sources:** 046_VLis0LcbUaQ ~02:07:16.
- **Quote:** "we don't want to see price trade below the low at 41.37 that's the new week opening Gap"
- **Conflicts:** T8 (no new entries at lunch) vs the 046 lunch macro entry.
- **Rulebook fix:** T7: add the 046 forecast as a research setup; list the T8 conflict.
- **BUILD SPEC (setups_models):**
  - Branch `lunch_nwog_long` (t 700-730). Conditions: the AM net move is down; price is inside [NWOG low, NWOG CE] (`_nwogs`); nothing has traded below the NWOG low.
  - Limit at the NWOG CE or a down-close OB in the zone. Stop at the NWOG low - buffer. Target the buy-side above the NWOG high / the next FVG.
  - This branch alone bypasses the T8 lunch block.
  - Params: `lunch_nwog_long: bool = False`.
  - Test: `test_lunch_nwog_long`.

### 49. A8-symmetry-skip-ifvg-confirmation
- **rule_id / kind:** A8 / missing_condition. Scope: index. judgment = false.
- **Rule:** If ES, NQ and YM are all in agreement (each printing higher highs together; a weakening DXY is context, not required here), a long may be placed inside the opposing FVG directly, without waiting for the A8 inversion. When the indices are not in agreement, require the full A8 IFVG protocol. Bearish = mirror.
- **Sources:** 048_gGxVE8zUIRQ ~00:38:07.
- **Quote:** "I would be going along inside of it not requiring it to go above"
- **Conflicts:** none.
- **[our interpretation]:** with no YM intraday data, "all in agreement" = ES and NQ both made the higher high in the same window (no SMT).
- **Rulebook fix:** A8: add the symmetry exception.
- **BUILD SPEC (setups_models):**
  - `ifvg_symmetry_skip` in `setups.ifvg_filter`: when the partner side in `psides` made the same higher high in the last `smt_window` bars (no SMT), an opposing FVG in the path is accepted as the entry without the inversion steps.
  - Params: `ifvg_symmetry_skip: bool = False`.
  - Test: `test_ifvg_skipped_when_symmetric`.

### 50. A8-ifvg-5m-to-1m-handoff
- **rule_id / kind:** A8 / shortened. Scope: index. judgment = false.
- **Rule:** Reference gap: the 5m SIBI. Ideal case: a 5m candle closes above it and the next 5m candle trades back into it and holds. If a 5m candle trades above it, drop to the 1m and require, in order: a 1m body close above the SIBI, a new 1m candle opening and trading back into it, a hold (no body close back through), then expansion. A 1m spike through and back does not count. Bearish = mirror.
- **Sources:** 048_gGxVE8zUIRQ ~00:21:30.
- **Quote:** "I require it to be above it close it and then start a new candle where it trades down into it"
- **Conflicts:** none.
- **Rulebook fix:** A8: add the 5m-to-1m hand-off.
- **BUILD SPEC (setups_models):**
  - `ifvg_tf=5`: IFVG candidates come from 5m gaps (`sd.zones_tf`). Once a 5m bar trades through, the close / new candle / hold checks (`ifvg_hold`) run on 1m bars.
  - Params: `ifvg_tf: int = 0`.
  - Test: `test_ifvg_5m_ref_1m_confirm`.

### 51. new-hft-laggard-subminute-catchup
- **rule_id / kind:** new / missing_rule. Scope: needs_unavailable_data. judgment = true.
- **Rule:** If the leader index has made a higher high and the laggard has not taken its nearest buy-side: on a 5-15 s chart of the laggard, buy the first BISI after a displacement up. Target: the laggard's nearest buy-side. Stop: below the BISI. Research only.
- **Sources:** 048_gGxVE8zUIRQ ~00:46:00.
- **Quote:** "drop down into like a five second 10 second 15 second chart"
- **Conflicts:** none.
- **Rulebook fix:** M16: add a research note (needs sub-minute data).
- **BUILD SPEC:** none (needs sub-minute bars).

### 52. E5-breakaway-gap-chase
- **rule_id / kind:** E5 / unlisted_contradiction. Scope: index. judgment = true.
- **Rule:** Breakaway-gap variant (experienced, test switch). After a winning first leg with the HTF target not yet met, a new 1m FVG may form in the bias direction during fast displacement and qualify as breakaway (expected to stay partly open, A6). Then place the sell limit at the FVG's near edge (the low of a bearish FVG) instead of its CE, or enter at market if price does not return within N bars. Stop above the FVG high. The default remains E5 (no chase). Long = mirror.
- **Sources:** 049_St9FJHRVdq8 ~00:05:01.
- **Quote:** "I saw this Gap here and I didn't want to miss it"
- **Conflicts:** E5 / M3 evolving SB (better to miss than chase) vs 049's chase entry.
- **Rulebook fix:** E5: list the 049 exception in Section 3.
- **BUILD SPEC (entries_stops_sizing):**
  - `breakaway_chase`: after a closed winner this session with the lock still undelivered, the next same-direction FVG tagged breakaway (existing `breakaway` tag) gets a near-edge limit. If it is unfilled after `breakaway_chase_bars`, place a market order at the next bar's open.
  - Params: `breakaway_chase: bool = False`, `breakaway_chase_bars: int = 3`.
  - Test: `test_breakaway_chase_market_after_n`.

### 53. new-short-top-of-htf-discount-fvg
- **rule_id / kind:** new / missing_rule. Scope: index. judgment = true.
- **Rule:** Bearish day, with the near (upper) edge of an HTF (daily) discount FVG already hit as the first target. If price returns to that edge and a 5m bearish breaker forms there (high, low, higher high, break down), sell inside the breaker. Target: just beyond the nearest short-term low inside the FVG (he used ~1 handle below it). Scale out and be flat by lunch or before the FVG's far edge.
- **Sources:** 050_F509lJRrYIM ~00:51:08.
- **Quote:** "the high end of that discount array or the imbalance on the daily chart"
- **Conflicts:** the rulebook says sell only in premium and treats a discount FVG as support (L9/A5).
- **Rulebook fix:** add a new rule after L9 and list the conflict.
- **BUILD SPEC (setups_models):**
  - `htf_fvg_top_short`. Conditions: bias -1, and a daily bullish FVG top already traded today. A 5m bearish breaker (`levels.breakers` on `htf_bars(df, 5)`) whose zone touches that top arms a limit inside the zone.
  - Target = the nearest swing low inside the daily FVG - 1 pt. Hard exit at 720 (owner #8 path) and before the FVG's far edge.
  - Params: `htf_fvg_top_short: bool = False`.
  - Test: `test_short_top_of_daily_bisi`.

### 54. new-ndog-asian-scalp
- **rule_id / kind:** new / missing_rule. Scope: index. judgment = true.
- **Rule:** Conditions: the 18:00 ET open is below the 17:00 close (gap down), the gap is more than 1 handle, and price has not yet traded up to the NDOG high. Once price trades or consolidates around the NDOG low during the Asian session (18:00 to ~00:00 ET), go long and target the NDOG high. Gap up = mirror. ICT gives no trigger or stop. Our interpretation: enter on a hold of the NDOG low (no body close below it), stop below the post-open low.
- **Sources:** 052_Sh-bDHWNpsk ~00:08:18.
- **Quote:** "would be a very easy bread and butter type scalp"
- **Conflicts:** L6 says the NDOG is confluence only, never a standalone signal.
- **Rulebook fix:** L6: add the 052 exception and list the conflict.
- **BUILD SPEC (setups_models; news_calendar_times owns the session window):**
  - Needs an evening session in `run_day` (18:00-24:00 on ETH bars; the futures data has them).
  - Branch `ndog_scalp`. Conditions: gap > 1 pt and the NDOG high untouched. The first 5m bar that closes back above the NDOG low after trading at it gives a market long. Stop below the post-open low; target the NDOG high - exit_before.
  - Params: `ndog_scalp: bool = False`, `asia_session: bool = False` (adds the 1080-1440 window).
  - Test: `test_ndog_asian_scalp`.

### 55. M16-trending-divergence-continuation
- **rule_id / kind:** M16 / missing_rule. Scope: index. judgment = true.
- **Rule:** Trending days only (the consolidation case is the sick-sister rule in M16, D15). The sister indices made a higher high that the laggard did not, and there is no reason to think price is reversing [our proxy: no MSS against the trend, no HTF premium array reached]. Read the divergence as continuation: expect the market to resume higher without a meaningful retracement. Do not treat it as bearish SMT (B18), and do not wait for a deep-discount pullback before going long. Downtrend = mirror (inferred).
- **Sources:** 053_VSSwM6rDIg0 ~00:08:20.
- **Quote:** "I don't believe it's reversing... I would expect this Market to resume and go higher"
- **Conflicts:** B18 reads the divergence as reversal SMT.
- **Rulebook fix:** B18/M16: add the trending-day exception.
- **BUILD SPEC (setups_models):**
  - `smt_trend_ignore`. A trending day = the bias equals the lock side, the session's first MSS went that way, and no same-side HTF premium array has been reached. On such a day, an SMT tag against the trend does not block or reverse a trade, and `sick_sister` does not require the deep discount.
  - Params: `smt_trend_ignore: bool = False`.
  - Test: `test_smt_ignored_on_trend_day`.

### 56. M16-sick-sister-discount-confluence
- **rule_id / kind:** M16 / shortened. Scope: index. judgment = false.
- **Rule:** Consolidating market only. Go long on the sick sister (the index that took the fewest reference highs). Fib from the swing low to the high it failed to exceed, and wait for price to drop below 0.5 and into 0.62-0.79. Entry zone = where OTE overlaps a bullish OB (consecutive down-close candles) and a bullish FVG. Accumulate the position there with limits (053 filled inside the 09:30-10:00 opening range). No buying while price is above EQ or rallying. Target the buy-side it failed to take; exit at or between the nearer pools. The bearish mirror is only alluded to.
- **Sources:** 053_VSSwM6rDIg0 ~00:05:17, ~00:10:51.
- **Quote:** "inside of the order block below equilibrium inside of optimal trade entry"
- **Conflicts:** 045 buys the forming OB open with no deep-discount condition (item 47).
- **Rulebook fix:** M16: replace "deep discount" with the four-way overlap.
- **BUILD SPEC (setups_models):**
  - Builds on `sick_sister`, which already uses "the day's discount". `sick_entry="ote_stack"`: the entry must sit in `levels.ote_band` of the leg from the swing low to the failed high, and inside both a bullish OB (`order_block_blend`) and a bullish FVG. Spread up to `sick_units` resting limits over the overlap.
  - Params: extend `sick_entry` with "ote_stack"; `sick_units: int = 1`.
  - Test: `test_sick_sister_ote_ob_fvg_overlap`.

### 57. T13-reclaim-0930-open-expansion
- **rule_id / kind:** T13 / missing_rule. Scope: index. judgment = true.
- **Rule:** Bullish bias day: the 09:30 open drops (Judas) into the ORG low (prior close) and/or the CE of a discount HTF FVG and makes the LOD. When price then forms a swing above the 09:30 opening price (more than a wick through it), mark the day as expanding, and hold or add longs toward the premium target. Bearish day = mirror. For the bot this is a tag or a runner confirmation, not an entry signal.
- **Sources:** 055_qiv8pkcNvGk ~00:21:00.
- **Quote:** "as soon as we meaningfully move above the opening price here on this type of day"
- **Conflicts:** none.
- **Rulebook fix:** T13: add the reclaim-the-open expansion confirmation.
- **BUILD SPEC (management_exits):**
  - `open_reclaim_runner` (long case): once a bar closes above the 09:30 open after the session low formed below it, set `pos["expanding"]`. The ladder's last fraction is then kept as a runner to the lock (like `po3_runner`), and BE moves wait for the next rung.
  - Params: `open_reclaim_runner: bool = False`.
  - Test: `test_open_reclaim_keeps_runner`.

### 58. M2-three-drives-conditions
- **rule_id / kind:** M2 / unlisted_contradiction. Scope: index. judgment = true.
- **Rule:** Three drives = three successive pushes in one direction, each taking the previous swing's stops, with fading momentum; the third fails and structure breaks.
  - Take a full reversal entry (2022-model FVG, or the breaker formed by the last swing) only if the HTF draw lies in the reversal direction, or the HTF objective in the original direction has already been delivered.
  - If HTF order flow is still a buy program (daily IOF bullish, B6) or the HTF draw in the original direction is untouched (e.g. a weekly VI above), the counter move is a retracement. Take at most a scalp to the nearest opposing pool/array, keep the HTF bias and look to re-enter in the original direction.
  - Mirror for three drives down.
- **Sources:** 056_NeZlyG8FZLQ ~00:08:47; 074_N4am6Jsp8N8 ~00:33:03; 076_cgsltOB736E ~00:14:51.
- **Quote:** "we're not trying to call Tops"
- **Conflicts:** M2 treats three drives as a reversal trigger vs 056/076.
- **Rulebook fix:** M2: add the HTF-draw condition and the retracement/scalp classification, with the breaker as an entry.
- **BUILD SPEC (setups_models):**
  - Builds on `three_drives` (tag/require). With `three_drives_htf`, a three-drives short counts as a reversal only when the `htf.table` bias is -1 or the up-draw is done (`htf_done`). Otherwise the order becomes a `scalp` (T1 only = the nearest opposing pool).
  - The breaker entry is item 95 (`td_fallback`).
  - Params: `three_drives_htf: bool = False`.
  - Test: `test_three_drives_scalp_when_htf_up`.

### 59. M4-complete-model-breaker-ote-ob
- **rule_id / kind:** M4 / shortened. Scope: index. judgment = true.
- **Rule:** Bearish, on the execution timeframe: identify a breaker from the larger swing (high, low, higher high, then the low breaks). On the retrace, require: (a) price trades up into an FVG below or inside the breaker; (b) it reaches the breaker zone; (c) the zone lies within 62-79% of the down leg; (d) an up-close candle (short-term bearish OB) from before the drop sits inside the zone. Sell limit at the breaker. Target: the nearest old imbalance / sell-side below. Bullish = mirror.
- **Sources:** 056_NeZlyG8FZLQ ~00:12:24.
- **Quote:** "that is a complete model we have a higher structured not this higher time frame but a higher structured breaker"
- **Conflicts:** none.
- **Rulebook fix:** M4: add the "complete model" confluence and the parent-structure breaker.
- **BUILD SPEC (setups_models):**
  - Tag `complete_model` in `finish_gates` on breaker entries when all three hold: the breaker comes from a parent swing (`levels.swing_tiers` tier >= 2), it lies in the leg's `ote_band`, and it contains an opposite-close candle. `complete_model="require"` filters on the tag.
  - Params: `complete_model: str = "off"`.
  - Test: `test_complete_model_tag`.

### 60. M5-lasthour-reversal-into-org
- **rule_id / kind:** M5 / missing_rule. Scope: index. judgment = true.
- **Rule:** Conditions: a gap-down ORG unfilled all day, and the session's downside objective already met (e.g. LOD at 12:00). From 15:00, a bullish MSS with displacement leaves a BISI, plus an OB made of the preceding consecutive down-close candles. Entry: buy the retrace into the BISI. Stop: below the OB (our interpretation). Targets: the ORG near edge, then its CE, then the prior RTH close. Flat by 16:00. Gap-up day = mirror.
- **Sources:** 059_ZfnY2SH3G24 ~00:24:09.
- **Quote:** "There's a shift in market structure here. We have inbounds fair value gap and three consecutive down close candles order block"
- **Conflicts:** none.
- **Rulebook fix:** M5: add the ORG-fill last-hour variant.
- **BUILD SPEC (setups_models + targets_partials):**
  - `lh_org_fill`: in the LH slot, when the ORG is unfilled and the AM/PM lock was delivered (or `htf_done`), allow LH trades toward the ORG with the ladder [ORG near edge, ORG CE, prior close] (from `_org_state`).
  - Params: `lh_org_fill: bool = False`.
  - Test: `test_lh_org_fill_targets`.

### 61. M3-sb-reversal-variant
- **rule_id / kind:** M3 / missing_rule. Scope: index. judgment = false.
- **Rule:** SB reversal variant: within or just before 10:00-11:00 (or 14:00-15:00), price runs a sell-side pool (REL/old low) against the draw, then takes a short-term high (MSS) with displacement that leaves a BISI. Enter long on the retrace into that BISI inside the window. Draw: the buy-side above, with at least 10 handles of room. Bearish = mirror.
- **Sources:** 060_ZtLMTXv-Dr0 ~00:46:43.
- **Quote:** "it isn't always going to be a continuation"
- **Conflicts:** none.
- **Rulebook fix:** M3: add the reversal variant.
- **BUILD SPEC (silver_bullet):**
  - `sb_reversal` in `sb_model._arm`: accept a setup where a pool on the opposite side was swept in [window start - `sb_rev_pre`, window end] and the MSS + FVG point to the new side.
  - The draw then comes from the far side of the swept range, and the 10-handle room check (`sb_room_pts`) applies.
  - Owner #9 lock: the reversal is allowed only if it points at the lock, or if `draw_lock` is off.
  - Params: `sb_reversal: bool = False`, `sb_rev_pre: int = 10`.
  - Test: `test_sb_reversal_after_rel_sweep`.

### 62. D15-one-clean-gap-instrument
- **rule_id / kind:** D15 / missing_rule. Scope: general. judgment = true.
- **Rule:** When correlated instruments offer the same idea, compare the PD array in the same setup area on each one. Prefer the instrument where that array is one clean, obvious FVG. Skip one where the area is "muddy" with several smaller gaps. The source example is FX; applying it to ES/NQ/YM is our extension.
- **Sources:** 061_wWvXWmC_gqU ~01:49:01.
- **Quote:** "it's not as clean and obvious"
- **Conflicts:** none.
- **Rulebook fix:** D15: add the clean-single-gap criterion.
- **BUILD SPEC (setups_models; `backtest.combine`):**
  - Tag `gap_count` = the number of same-side FVGs in the leg between EQ and the leg extreme.
  - `smt_pick="clean"`: in `combine`, when ES and NQ both fill in the same session on the same side, keep the one with gap_count == 1 (else the first).
  - Params: add "clean" to `smt_pick`.
  - Test: `test_combine_prefers_single_gap`.

### 63. M10-ifvg-fvg-signature-full
- **rule_id / kind:** M10 / shortened. Scope: general. judgment = false.
- **Rule:** Bullish: an IFVG has formed with a standard FVG just below it. Trigger: a body closes at the FVG high or its CE; from then on, the lower part of the FVG should not be traded into (invalidate if it is). Entry: IOFED, a limit at the FVG level or just inside it (capping it at the CE is ours). Stop below the FVG (ours). Targets: first partial at the relative equal highs, then the buy-side or inefficiency above the old highs. Bearish = mirror.
- **Sources:** 061_wWvXWmC_gqU ~02:18:22.
- **Quote:** "the algorithm will immediately spool and go the other direction"
- **Conflicts:** none.
- **Rulebook fix:** M10: add the entry, invalidation and targets.
- **BUILD SPEC (setups_models):**
  - Builds on `ifvg_061`, which enters at market on the body close. `ifvg_061_entry="iofed"` replaces that with a limit at the FVG top + 1 tick, no deeper than the CE. Cancel or exit on a trade below the CE. The ladder's first rung = the nearest rel-eq highs.
  - Params: `ifvg_061_entry: str = "market"`.
  - Test: `test_ifvg_061_iofed_limit`.

### 64. new-false-bull-flag-short
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** Flag = a rapid one-sided impulse followed by a consolidation of any length below a short-term high. If the bull flag sits above EQ of the latest significant swing and/or inside a daily/4h bearish OB or premium FVG, it is a false flag: do not buy the breakout.
  - Trigger: price trades slightly above the flag high (BSL taken), then breaks back down through the flag.
  - Entry option (a): sell at the first bearish FVG at or above EQ that the run trades into, ideally in a kill zone.
  - Entry option (b): a sell limit at the open of the last up-close candle before the break, first return only.
  - Stop: above the flag's highest wick ('1 tick' is ours) or above the FVG.
  - Targets: close the void left by the flagpole, then the sell-side below the low where the rally started, then lower pools.
  - Bullish = mirror (fake bear flag). The sources are FX/DXY.
- **Sources:** 061_wWvXWmC_gqU ~01:41:32; cc02_007_cRbPS3uxkj4 ~00:16:23, ~00:16:55, ~00:27:34.
- **Quote:** "make a short slightly short term higher high and then collapse this is the basis of turtle soup"
- **Conflicts:** none.
- **Rulebook fix:** M12: add the false-flag turtle soup.
- **BUILD SPEC (setups_models):**
  - The entry is the normal sweep -> MSS path. New is the context gate `false_flag`, which needs two things:
    - The swept high is the top of a consolidation: at least `flag_min_bars` bars inside a range no wider than `flag_max_frac` of the preceding impulse.
    - The high sits above EQ of the session/daily swing, or inside a same-side HTF array (`_htf_tag`).
  - The first target rung = the flagpole origin low.
  - Params: `false_flag: str = "off"` ("tag" / "require"), `flag_min_bars: int = 5`, `flag_max_frac: float = 0.5`.
  - Test: `test_false_bull_flag_tag`.

### 65. new-reentry-after-breakaway-fill
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = false.
- **Rule:** If a short taken in a breakaway candidate is stopped because the gap fills completely, it was not a breakaway gap. Do not re-enter at once. Wait for price to trade back up to the HTF level / prior FVG. Then require another break lower that leaves a new SIBI, treat it as the new breakaway candidate, and re-enter on the retrace into it (stop above the retrace candle's high). X13 half risk applies. Longs = mirror.
- **Sources:** 062_sfRO5LrTgTA ~00:38:24.
- **Quote:** "break lower again create another fair value and treat that as a potential later Breakaway Gap"
- **Conflicts:** none.
- **Rulebook fix:** X13: add the post-breakaway-fill re-entry sequence.
- **BUILD SPEC (management_exits + setups_models):**
  - Builds on `reentry_half` (`_after_close`). With `reentry_breakaway`, a loss whose entry gap was tagged breakaway and then fully filled arms a re-entry. The re-entry requires (a) price reaching the HTF array / lock-side FVG above, then (b) a new MSS + FVG. Risk x0.5.
  - Params: `reentry_breakaway: bool = False`.
  - Test: `test_reentry_after_breakaway_fill`.

### 66. M9-news-judas-full-sequence
- **rule_id / kind:** M9 / shortened. Scope: index. judgment = false.
- **Rule:** After an 08:30 high-impact release, with SSL/BSL the pre-release pools: if SSL is taken first and then BSL, the bias is long, but do not buy yet. Wait for a pullback into [SSL, BSL] toward its CE and/or the 08:30 open (bodies stop there; wicks may pass). Then require a short-term MSS up with a down-close bullish OB plus an FVG, and buy the OB/FVG. Invalidation: a body break below the OB mean threshold. Targets: the buy-side above / the HTF draw. BSL taken first = mirror.
- **Sources:** 064__YTK5uXBe4o ~01:10:05.
- **Quote:** "You have to wait. What does it want to do? It pulls back inside the range"
- **Conflicts:** none.
- **Rulebook fix:** M9: add the two-pool, range-CE retrace, MSS sequence.
- **BUILD SPEC (setups_models; the news range comes from `_news_ranges`):**
  - `news_two_sided`: on release days, after both news-range extremes are taken, the trade side = the extreme taken second. Arm only after a bar trades back to the range CE or the 08:30 open; then the normal MSS + OB/FVG path. Exit on a body close below the OB MT.
  - Params: `news_two_sided: bool = False`.
  - Test: `test_news_two_sided_waits_for_ce`.

### 67. A12-entry-ob-outside-fvg
- **rule_id / kind:** A12 / missing_rule. Scope: general. judgment = false.
- **Rule:** Bullish entry OB after an MSS: walk back from the displacement. An up-close candle breaks a run of down-close candles (a change in the state of delivery). Ignore down-close candles inside the FVG/shaded zone. The entry OB is the last (lowest) down-close candle outside the FVG; use its range for the entry (bodies should hold it). Use the open where the up-close candle broke the run as the CISD reference (our reading). Bearish = mirror.
- **Sources:** 065_rx15_eN9sxI ~04:04:05.
- **Quote:** "we have to use the out outside of the range"
- **Conflicts:** A12 blends runs and anchors at the first candle.
- **Rulebook fix:** A12: add the outside-the-FVG selection.
- **BUILD SPEC (levels_detectors):**
  - `levels.order_block_blend(..., outside=zone)`: stop the blend at an opposite-close candle, and skip candles whose range lies inside `zone`. Used by `_ob_pre` and `entry_arrays` "ob" when `p.ob_outside_fvg` is on.
  - Params: `ob_outside_fvg: bool = False`.
  - Test: `test_ob_blend_outside_fvg`.

### 68. new-15m-candle-po3-upper-half
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** With bullish 15m order flow (recent 15m candles open, drop, rally and close near their highs, and the BPR/FVG below holds): at a new 15m open, buy the drop after the open while price stays in the upper 50% of the reference 15m candle/range. The reference is ambiguous: the prior up-close candle or the forming candle. Expect the gap below to stay open and the candle to close near its high. Abort on a body close below the BPR equilibrium. Bearish = mirror.
- **Sources:** 065_rx15_eN9sxI ~04:29:00.
- **Quote:** "you can be buying anywhere in the upper 50% of this candle"
- **Conflicts:** none.
- **[our interpretation]:** reference = the prior up-close 15m candle; "bullish flow" = the last 3 closed 15m bars are up-close.
- **Rulebook fix:** B12: add the single-candle PO3 note.
- **BUILD SPEC (setups_models):**
  - Branch `po3_15m`. At each 15m open (minute % 15 == 0), when the last `po3_15m_n` 15m bars closed up and a same-side BPR/FVG below is intact, place a buy limit at the 15m open - 1 tick.
  - The order is valid while price stays above 50% of the prior 15m bar, and is cancelled at the 15m close.
  - Exit on a 1m body close below the BPR EQ. Target = the prior 15m high + range.
  - Params: `po3_15m: bool = False`, `po3_15m_n: int = 3`.
  - Test: `test_po3_15m_upper_half`.

### 69. M12-new-trader-no-turtle-soup
- **rule_id / kind:** M12 / M14, missing_rule. Scope: general. judgment = false.
- **Rule:** ICT calls turtle-soup entries at the raid an experienced-trader technique: buying the sell stops, or selling the buy-side run, including the TGIF sweep of the week high. The new-trader version waits for the run, displacement through the open of the last opposite candle (CISD), a short-term swing taken (MSS) and the FVG (2022 model). Keep turtle soup off by default. Do not override the owner's D10 pre_break default without the owner; flag the tension for owner review.
- **Sources:** 065_rx15_eN9sxI ~03:01:01; 066_wTR-vhOdMgo ~00:31:09.
- **Quote:** "that's a very very difficult thing to do for New Traders"
- **Conflicts:** M12 allows turtle-soup limits with no experience distinction; M14 allows TGIF by any model; owner #11 makes the pre-break OB the default.
- **Rulebook fix:** M12/M14: add the experienced/new label.
- **BUILD SPEC (setups_models):**
  - No new default. Add an `entry_style` tag on `Trade`, so reports can split results by style: "raid" for `turtle_soup` and `ob_entry="pre_break"`, "confirmed" for the post-MSS FVG. The owner question goes in `owner_directives.md` and is for the owner to raise, not part of this build.
  - Params: none.
  - Test: `test_entry_style_tag`.

### 70. M12-turtle-soup-prev-pm-low
- **rule_id / kind:** M12 / missing_rule. Scope: index. judgment = true.
- **Rule:** Weekly draw bullish and price near the previous day's 13:30-16:00 range at 09:30: rest a buy below that range's low (a turtle soup on the Judas run under it). Target: the same range's high. Stop: under the sweep extreme [ours]. Experienced-only switch, default off; the default is the confirmation version. Bearish = mirror at the PM high.
- **Sources:** 067_vuBRMFhFZAY ~00:20:12.
- **Quote:** "wait for the sell side in the previous PM session range if you're bullish that's your buy"
- **Conflicts:** none.
- **Rulebook fix:** M12: add the previous-PM-range turtle soup.
- **BUILD SPEC (setups_models):**
  - Builds on `turtle_soup="cc_limit"` (a resting limit under an old low with a bias). New variant `turtle_soup="prev_pm"`: the level is the previous day's 13:30-16:00 low (high) from `_extra_levels`, the bias is `weekly_bias`, the limit = level - 1 tick at 09:30, and the target = that range's other extreme.
  - Params: add "prev_pm" to `turtle_soup`.
  - Test: `test_turtle_prev_pm_low`.

### 71. M0-target-opposite-extreme-same-range
- **rule_id / kind:** M0 / shortened. Scope: index. judgment = false.
- **Rule:** After price raids one extreme of a session range against the bias (prev PM 13:30-16:00, London 02:00-05:00, lunch 12:00-13:30) and an MSS + FVG forms, T1 = the opposite extreme of that same range. Bullish: the 09:30 drop takes the prev-PM low, so target the prev-PM high. Bearish: the pre-09:30 run takes the London high, then a shift lower, so target the London low; expect to sit through a retracement.
- **Sources:** 067_vuBRMFhFZAY ~00:18:56.
- **Quote:** "why because it's inside the range between 130 and 4:00"
- **Conflicts:** none.
- **Rulebook fix:** M0 step 6: "first target = the other end of the raided range".
- **BUILD SPEC (targets_partials):**
  - `same_range_t1`: in `_targets`, when the sweep pool's name maps to a session range (prev_pm, london, lunch, asia), put that range's opposite extreme first in the ladder, if it is beyond min_rr.
  - Params: `same_range_t1: bool = False`.
  - Test: `test_t1_is_opposite_extreme_of_raided_range`.

### 72. M7-second-dip-into-rejection-block
- **rule_id / kind:** M7 / missing_rule. Scope: index. judgment = false.
- **Rule:** After the lunch low (12:00-13:30) is swept (wick low L), let RB = the lowest close in that swing. If a later dip trades below RB but holds above L, buy on a bullish lowest-timeframe PD array (OB / IFVG / FVG) in discount. Stop below L; if L is taken the idea is stopped (re-enter only if still valid). Target: the lunch high / the ORG buy-side. This needs an exception in X8. Bearish = mirror.
- **Sources:** 067_vuBRMFhFZAY ~01:05:38.
- **Quote:** "I don't need that low to be taken out I don't want to see it"
- **Conflicts:** X8 / the M1 speed check (price must not trade below the swing low's lowest open/close) vs 067.
- **Rulebook fix:** M7: add the second-dip entry; X8: add the exception.
- **BUILD SPEC (setups_models):**
  - `rb_second_dip`: after a PM long sweep of the lunch low, a later bar with RB > low > L arms the `entry_arrays` pick on that dip. `body_low_cancel` (M1.3) is skipped for this setup.
  - Params: `rb_second_dip: bool = False`.
  - Test: `test_second_dip_below_rb_above_low`.

### 73. M10-ifvg-stop-below-whole-ifvg
- **rule_id / kind:** M10 / missing_condition. Scope: index. judgment = false.
- **Rule:** Bullish IFVG (a bearish FVG closed through upward; a new candle trades back in and holds): place buys/adds inside it, preferably where it overlaps a reclaimed bullish OB. Stop: below the IFVG low; do not tighten it inside the IFVG. Trail only after the buy-side is run. The IFVG acts as dynamic support. Bearish = mirror.
- **Sources:** 067_vuBRMFhFZAY ~01:19:07.
- **Quote:** "my stop loss is below the inversion fair value Gap"
- **Conflicts:** M10: stop above the CE + 3-4 ES pts vs 067: stop beyond the whole IFVG.
- **Rulebook fix:** M10: add the far-edge stop variant and the OB-overlap add; list the conflict.
- **BUILD SPEC (entries_stops_sizing):**
  - `ifvg_stop="far"` in `setups.ifvg_stop`: stop = the IFVG's far edge - buffer, instead of the existing CE + pts.
  - With `ifvg_ob_add`, add a unit at the overlap of the IFVG and a reclaimed OB (`levels.reclaimed_obs`).
  - Params: `ifvg_stop: str = "ce"`, `ifvg_ob_add: bool = False`.
  - Test: `test_ifvg_far_edge_stop`.

### 74. M7-pm-short-back-below-lunch-high
- **rule_id / kind:** M7 / shortened. Scope: index. judgment = false.
- **Rule:** Bearish PM (from 13:30): price runs above the lunch high into the ORG. Then price trades back below the lunch high with displacement, leaving a bearish FVG (2022 model). Sell at that FVG and target the lunch-range low. ICT states no stop; use E6. Bullish = mirror.
- **Sources:** 067_vuBRMFhFZAY ~00:49:14.
- **Quote:** "watch and see how it trades back below the New York lunch high if there's a displacement"
- **Conflicts:** none.
- **Rulebook fix:** M7: add "trades back below the lunch high with displacement" to the short mirror.
- **BUILD SPEC:** none; rule_coverage already lists this with the same content. M7 / M7.2 `pm_lunch_target` + `pm_lunch_org` are built, and the displacement back below the lunch high is the MSS that every `_scan_core` trade already needs. Only the rulebook text changes.

### 75. M8-org-repricing-full-conditions
- **rule_id / kind:** M8 / shortened. Scope: index. judgment = false.
- **Rule:** Bearish case (bullish = mirror):
  1. A pre-session forecast HTF target below.
  2. ORG = the prior RTH close (ES 16:15) to the 09:30 open.
  3. After 09:30, a Judas rally away from the ORG trades above the midnight open, runs the London-session buy-side and the prior-day NY-session buy-side, and reaches a premium SIBI.
  4. A 1m MSS down with displacement leaves FVG(s).
  5. Short at the FVG in premium, using Silver Bullet rules (10:00-11:00).
  6. Target the ORG (CE/near edge, then the NWOG low); stop above the CE of the higher of two FVGs.

  The "ORG between price and the HTF draw" filter is ours.
- **Sources:** 069_Sf_uYZBWTrA ~00:14:49.
- **Quote:** "so this is a repricing macro all of this is a Juda swing"
- **Conflicts:** none.
- **Rulebook fix:** M8: replace the one-liner with the stacked conditions.
- **BUILD SPEC (setups_models):**
  - `org_reprice`: an AM order whose target ladder starts at the ORG must meet all of these:
    - the sweep went above the midnight open and took both the London and prior-NY highs (see item 76);
    - a same-side premium array sits at the sweep (`_htf_tag`);
    - the fill comes in 600-660;
    - the ORG lies between the entry and the `htf.table` draw.
  - Stop: `stop_mode="ce2"` (exists).
  - Params: `org_reprice: bool = False`.
  - Test: `test_org_reprice_conditions`.

### 76. M0-all-nearby-pools-run-first
- **rule_id / kind:** M0 / missing_condition. Scope: index. judgment = true.
- **Rule:** Preference / quality filter (one example, 069). Before a counter-Judas entry, note the session pools on the Judas side (the London 02:00-05:00 high, the prior-day NY session high). Prefer to wait until all of them have been run, with price above the midnight open and into a premium array, before taking the MSS entry. An MSS after only the nearer pool is lower quality. Test as a switch. Bullish = mirror.
- **Sources:** 069_Sf_uYZBWTrA ~00:16:49.
- **Quote:** "the reason why I wanted to wait and I didn't take this one here"
- **Conflicts:** none.
- **Rulebook fix:** M0 step 3: add the all-pools preference.
- **BUILD SPEC (setups_models):**
  - `all_pools_first`: in the sweep block, the sweep counts only once every listed pool on that side within `all_pools_pts` of the open is taken. Modes "tag" / "require".
  - Params: `all_pools_first: str = "off"`, `all_pools_names: tuple = ("london", "prev_ny")`, `all_pools_pts: float = 30.0`.
  - Test: `test_wait_for_both_pools`.

### 77. M7-lunch-reprice-org-ce-moc
- **rule_id / kind:** M7 / shortened. Scope: index. judgment = true.
- **Rule:** Bearish day with the forecast HTF target unmet by 12:00: during lunch, expect a quick retrace up to the ORG CE or just above the lunch relative equal highs, then consolidation. The 15:15/15:45 MOC macro then runs the lunch sell-side and delivers the HTF target. A short at the ORG CE / just above the lunch REH is implied, but no stop or management is given, and it conflicts with T8. Research/switch only. Bullish = mirror.
- **Sources:** 069_Sf_uYZBWTrA ~00:20:38.
- **Quote:** "smart money can wait for the algorithm to reprice back up into half of the Shaded area"
- **Conflicts:** T8 (no new entries at lunch).
- **Rulebook fix:** M7/T10: add the lunch-reprice / MOC note.
- **BUILD SPEC (setups_models):**
  - `lunch_org_ce_short` (t 720-810, lock undelivered): a sell limit at max(ORG CE, lunch REH + 1 tick). Stop above the ORG far edge [ours]. Hold to the MOC: exit at 16:00 or at the lock.
  - Params: `lunch_org_ce_short: bool = False`.
  - Test: `test_lunch_org_ce_short`.

### 78. D15-dual-dealing
- **rule_id / kind:** D15 / unlisted_contradiction. Scope: index. judgment = true.
- **Rule:** Option dual_deal: when the same setup triggers on both ES and NQ (same Judas/MSS/FVG entry window), ICT may take both ("dual dealing", 069). The conditions (e.g. no divergence) and the risk allocation (split vs full on each) are not stated; test both variants. This conflicts with Ep 05 "watch one market only" and with D15.
- **Sources:** 069_Sf_uYZBWTrA ~00:19:09.
- **Quote:** "I traded short on NASDAQ and I traded short on ES"
- **Conflicts:** D15 picks one index; Ep 05 says watch one market only.
- **Rulebook fix:** D15: add the option and the conflict.
- **BUILD SPEC (setups_models; `backtest.combine`):**
  - `dual_deal` modes: "split" keeps both same-session, same-side trades at half risk each; "full" keeps both at full risk; "" keeps the current pick.
  - Params: `dual_deal: str = ""`.
  - Test: `test_combine_dual_deal_split`.

### 79. M4-1m-last-upclose-finetune
- **rule_id / kind:** M4 / missing_rule. Scope: index. judgment = false.
- **Rule:** Bullish breaker (bearish = mirror): define the breaker leg/zone on the 5m, then drop to the 1m. Inside that zone, the entry block is the last up-close 1m candle before the run to the lower low. Treat it as an order block with 0/25/50(MT)/75/100% levels. A limit at the MT fills only on a print 1 tick through (E3).
- **Sources:** 070_1HtRfFYiwO0 ~00:55:41.
- **Quote:** "for fine tuning your entry it's the last up close candle prior to the lower run"
- **Conflicts:** A13/D6 use the highest-body up-close candle vs 070's last up-close candle.
- **Rulebook fix:** M4: add the 5m->1m refinement; list the A13/D6 conflict.
- **BUILD SPEC (setups_models):**
  - Build the zone with `breaker_zone(..., tf=5)`. With `breaker_pref="last_1m"`, the entry block = the last up-close 1m bar inside the 5m zone before L2; limit at its MT (fill on 1 tick through).
  - Params: `breaker_tf: int = 0`, `breaker_pref: str = ""` ("last_1m").
  - Test: `test_breaker_5m_zone_1m_last_upclose`.

### 80. M4-two-pool-breaker-near-miss
- **rule_id / kind:** M4 / missing_condition. Scope: index. judgment = true.
- **Rule:** Add to M4 advanced an extra-quality qualifier: before the lower low runs the pre-marked HTF sell-side pool, price first comes close to that pool without taking it, bounces, then drops through it. The two-pool requirement and the turtle-soup buy of the run are already in M4. Bearish = mirror.
- **Sources:** 070_1HtRfFYiwO0 ~00:41:22.
- **Quote:** "it's enticing folks to see that that's a time to go long"
- **Conflicts:** none.
- **Rulebook fix:** M4: add the near-miss qualifier.
- **BUILD SPEC (setups_models):**
  - Tag `near_miss` when, before the sweep bar, a swing low formed within `near_miss_pts` above the swept HTF pool after a bounce at least as large.
  - Params: `near_miss_pts: float = 0.0` (0 = off).
  - Test: `test_near_miss_tag`.

### 81. M4-unfinished-high-keep-ab-leg
- **rule_id / kind:** M4 / missing_rule. Scope: index. judgment = true.
- **Rule:** For breaker SD projections, keep the most recent completed A-B leg. Do not re-anchor on a newer swing high (low) that is expected to be exceeded because the HTF draw beyond it is still untaken.
- **Sources:** 070_1HtRfFYiwO0 ~00:52:42.
- **Quote:** "I don't need to know what that is yet because the A to B leg is already there"
- **Conflicts:** none.
- **Rulebook fix:** M4 advanced: add the anchor rule.
- **BUILD SPEC (setups_models):**
  - In `setups.adv_breaker_order`, keep the A-B leg fixed after the first fill. With `ab_anchor_lock`, a new swing high below an untaken lock target does not reset A/B.
  - Params: `ab_anchor_lock: bool = False`.
  - Test: `test_ab_leg_not_reanchored`.

### 82. E2-iofed-depth-second-gap
- **rule_id / kind:** E2 / missing_condition. Scope: general. judgment = true.
- **Rule:** Bearish retrace into a SIBI (bullish = mirror): if another gap from the same move sits in close proximity above it, expect only an IOFED touch and place the limit at the near edge. If there is no nearby second gap, expect a deeper retrace into the gap (CE as our interpretation). One example (074); test as a switch.
- **Sources:** 074_N4am6Jsp8N8 ~00:36:02.
- **Quote:** "that's what makes this an Institutional referential"
- **Conflicts:** none.
- **Rulebook fix:** E2: add the depth condition.
- **BUILD SPEC (entries_stops_sizing):**
  - `entry="auto2"`: use the near edge (IOFED) when another same-side gap lies within `iofed_gap_bars` bars and `iofed_gap_pts` beyond the picked gap; otherwise use the CE.
  - Params: add "auto2" to `entry`; `iofed_gap_bars: int = 5`, `iofed_gap_pts: float = 3.0`.
  - Test: `test_entry_auto2_depth`.

### 83. M11-cisd-ob-stop-skip-rearm
- **rule_id / kind:** M11 / missing_condition. Scope: general. judgment = false.
- **Rule:** Additions to M11:
  - Context: price has traded into an HTF bullish array (075: a 1h breaker), then a 1m MSS.
  - Draw the OB at the open of the last down-close candle, whatever its shape.
  - Longs: any bullish PD array in the discount of the post-CISD range, stop just below the OB low.
  - If that stop is wider than max risk, skip and wait for an FVG, breaker or IOFED formed after another run higher.
  - If price trades below the OB low, the setup is void; re-arm only on a new MSS plus a new CISD.
  - Bearish = mirror.
- **Sources:** 075_vN2BkfyRWE4 ~01:19:43.
- **Quote:** "that's a little bit too wide for me then don't take the tree wait for another run higher"
- **Conflicts:** none.
- **Rulebook fix:** M11b: add the stop, skip, re-arm and HTF context.
- **BUILD SPEC (setups_models):**
  - Builds on `cisd_ob_entries` (the OB-low cancel exists). New pieces:
    - `cisd_need_htf`: the sweep must be in a same-side HTF array (`_htf_tag`).
    - Stop = OB low - buffer.
    - `max_stop_pts` (item 44) skips the order but keeps the CISD alive.
    - After an OB-low break, clear the setup and re-arm on the next CISD.
  - Params: `cisd_need_htf: bool = False`.
  - Test: `test_cisd_ob_rearm_after_low_break`.

### 84. M10-ifvg-footholds-buy-program
- **rule_id / kind:** M10 / missing_condition. Scope: general. judgment = true.
- **Rule:** After a bullish CISD, the bearish FVGs of the prior down leg are buy-side delivery targets first. A candle closing above one turns it into an IFVG. Do not buy the first touch. Wait for a short-term low to be run (expected near equilibrium of the current range) while bodies respect the IFVG/old FVG CE, with confluence (an OB, a prior candle low, an old gap). Enter on that return into the IFVG. Successive IFVGs are footholds for adds. Stop: E6. Bearish = mirror.
- **Sources:** 075_vN2BkfyRWE4 ~01:29:33.
- **Quote:** "does that mean it's going to trade right here and go higher ... no we have to wait and watch"
- **Conflicts:** none.
- **Rulebook fix:** M10: add the target-then-support order and the stop-hunt requirement.
- **BUILD SPEC (setups_models + targets_partials):**
  - targets_partials: after a bullish CISD, `ifvg_targets` puts the down leg's open SIBIs into the ladder.
  - setups_models: `ifvg_need_hunt` arms an IFVG entry only after a swing low (pivot) below the current price is taken while no body has closed below the IFVG CE.
  - Params: `ifvg_targets: bool = False`, `ifvg_need_hunt: bool = False`.
  - Test: `test_ifvg_needs_stop_hunt`.

### 85. M14-tgif-invalidation-timing
- **rule_id / kind:** M14 / missing_condition. Scope: index. judgment = false.
- **Rule:** Add to M14: the TGIF idea is invalid if price trades above the weekly high after the bearish shift that confirmed it (bullish mirror: below the weekly low). In 075, the pre-14:00 consolidation was treated as time distortion, and the entry came in the 14:00-16:00 PM session after the lunch macro had run the AM low. Treat this as an example of the PM preference, not a hard 14:00 gate.
- **Sources:** 075_vN2BkfyRWE4 ~01:40:30.
- **Quote:** "what happens if it runs up and goes higher then you're wrong"
- **Conflicts:** none.
- **Rulebook fix:** M14: add the invalidation.
- **BUILD SPEC (day_week_context; built inside the TGIF branch of item 90):**
  - Cancel pending TGIF orders, and exit open ones, on a trade above the week high (from the `BT.run` weekly state).
  - Params: `tgif_week_high_exit: bool = True` (active only when `tgif` is on).
  - Test: `test_tgif_invalid_above_week_high`.

### 86. A4-bodies-hold-prev-day-50
- **rule_id / kind:** A4 / missing_condition. Scope: general. judgment = true.
- **Rule:** Long confirmation (one 2023 example, 076, NQ): on a dip into the previous day's range, execution-TF candle bodies hold at or above 50% of the previous day's range, while wicks may pierce it. Enter on the candle that confirms the reaction, inside the IFVG/breaker FVG. Treat a body close below the 50% as a failed confirmation [interpretation]. Bearish = mirror.
- **Sources:** 076_cgsltOB736E ~00:22:29.
- **Quote:** "look at the bodies respecting 50 of the previous day's range"
- **Conflicts:** none.
- **Rulebook fix:** A4: add the previous-day-50% body test.
- **BUILD SPEC (setups_models):**
  - `pd50_bodies`: for longs whose sweep extreme lies inside yesterday's range, require no body close below yesterday's 50% between the sweep and the fill (on 1m bars, or 5m with `pd50_tf=5`). Otherwise drop the order.
  - Params: `pd50_bodies: bool = False`, `pd50_tf: int = 1`.
  - Test: `test_pd50_body_hold`.

### 87. new-overshoot-ltf-fvg-into-htf-level
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** Entry variant (the stop part is already in E6, 078 ~1:22:14): a 60m SIBI formed during a 4h immediate rebalance, with its top just under the low of an older daily SIBI. Sell at the 60m SIBI top, or as price trades just above it (an overshoot into the daily SIBI low). Stop just above the swing high that formed the leg, not above the SIBI or the daily level. Invalid if that swing high is taken. Target the next sell-side pool. Bullish = mirror.
- **Sources:** 078_FQqwmDJOtxk ~01:22:24.
- **Quote:** "as soon as we trade above that I could go short"
- **Conflicts:** none.
- **Rulebook fix:** E2: add the overshoot entry.
- **BUILD SPEC (setups_models):**
  - `htf_overshoot_short`: a 60m bearish FVG (htf arrays) whose top lies within `overshoot_pts` below a daily bearish FVG low arms a sell order at the 60m top + 1 tick, filled when price trades through it. Stop above the leg's swing high.
  - Params: `htf_overshoot_short: bool = False`, `overshoot_pts: float = 3.0`.
  - Test: `test_60m_overshoot_into_daily`.

### 88. new-open-returns-into-bearish-ob
- **rule_id / kind:** new / missing_rule. Scope: index. judgment = true.
- **Rule:** Quality grade (index): displacement breaks below the last up-close candle (bearish OB), then the session open trades straight back up into that OB and price delivers lower at once. Tag this as a top-grade OB short; in the source it was confirmed by SMT at an HTF FVG CE. The source names no stop or body-close condition; use E6. Bullish = mirror.
- **Sources:** 081_0xYpeVRi_qs ~00:11:34.
- **Quote:** "that is one of the strongest signatures you're going to get"
- **Conflicts:** none.
- **Rulebook fix:** A12: add the signature as a quality grade.
- **BUILD SPEC (setups_models):**
  - Tag `open_into_ob` when the entry OB formed before 09:30 (or 13:30) and the fill comes within `open_ob_min` minutes after that open.
  - Params: `open_ob_min: int = 0` (0 = off).
  - Test: `test_open_into_ob_tag`.

### 89. B5-ltf-at-htf-array
- **rule_id / kind:** B5 / missing_condition. Scope: index. judgment = true.
- **Rule:** Carry 15m/60m PD arrays (FVG/BISI/SIBI, OB, their CE) onto the 5m/1m execution chart and use them as the reference for the LTF entry, even where no LTF gap is visible. As a filter, prefer LTF setups whose retrace reaches such an array [interpretation; the source frames it as important, not mandatory].
- **Sources:** 082_JpdNsPE0kWQ ~00:06:22.
- **Quote:** "having this higher time frame PD arrays on your charts are very important"
- **Conflicts:** none.
- **Rulebook fix:** B5: add carrying 15m/60m arrays down to the execution chart.
- **BUILD SPEC (setups_models):**
  - Tag `htf_entry_array` when the fill price lies inside a same-side 15m/60m array (`confluence._zones` / `sd.zones_tf`). `htf_entry_array="require"` filters on it.
  - Add "htf" to `entry_arrays`: when no 1m gap exists, the array's near edge/CE can be the entry.
  - Params: `htf_entry_array: str = "off"`; add "htf" to `entry_arrays`.
  - Test: `test_htf_entry_array_tag`.

### 90. M14-tgif-am-timing
- **rule_id / kind:** M14 / unlisted_contradiction. Scope: index. judgment = true.
- **Rule:** Friday after a trending week. TGIF zone = a 20-30% retrace of the week's range from its extreme.
  - Allow AM execution from 09:30: in 089 the pre-open highs were raided, then an FVG short at the open; in 085 a morning long used TGIF as its target.
  - Window switch: tgif_window = AM from 09:30 | London close 10:00-12:00 | PM.
  - Entry by any model.
  - Keep the HTF-array condition by default (089 had a daily SIBI CE); expose tgif_need_htf_array as a switch.
  - Target the nearer of the TGIF band or the day's opposite pool.
- **Sources:** 085_6-KNSUN-UaU ~00:17:32; 089_h0yOpwSilnE ~00:01:29.
- **Quote:** "because it's Friday and we've had a nice bearish week"
- **Conflicts:** M14 prefers PM / London close with the extreme in by ~13:30 and needs an HTF array; P22 limits entries to 10:00-15:00.
- **Rulebook fix:** M14: add the AM window; list the conflict.
- **BUILD SPEC (day_week_context + targets_partials):**
  - `tgif` applies on Fridays after a trending week, where trending = `weekly_bias` with the week's range > `tgif_min_adr` x ADR5 and the close near an extreme.
  - The 20-30% band from the week's extreme becomes a target rung for orders against the week's direction.
  - Sessions allowed by `tgif_window`. With `tgif_need_htf_array`, the Friday sweep must be at a same-side HTF array.
  - Params: `tgif: bool = False`, `tgif_window: str = "pm"`, `tgif_need_htf_array: bool = True`, `tgif_min_adr: float = 3.0`.
  - Test: `test_tgif_band_target_am`.

### 91. M2-htf-ob-precondition
- **rule_id / kind:** M2 / missing_condition. Scope: index. judgment = false.
- **Rule:** The 2022-model short precondition can be EITHER buy-side taken OR price trading up into an HTF bearish order block in premium, above the daily FVG high (087). Then a displacement breaks the short-term low and leaves a bearish FVG. Sell the retrace using M2's entry and stop. Target the relative equal lows / the sell-side below. Mirror for longs. The daily SIBI alternative is our extension.
- **Sources:** 087_z4GVg3aPnAk ~00:05:51.
- **Quote:** "we trade up into the bearish order block here which is above the daily inefficiencies"
- **Conflicts:** none.
- **Rulebook fix:** M2: add the HTF OB precondition.
- **BUILD SPEC (setups_models):**
  - Covered by item 10's `allow_htf_array_premise` once daily OB rows are included. Add "D" to the `premise_tfs` choices and include daily OBs (`htf._arrays` kind "ob").
  - Test: `test_htf_ob_premise_daily`.

### 92. E1-market-on-touch
- **rule_id / kind:** E1 / missing_rule. Scope: general. judgment = true.
- **Rule:** Switch entry_order = 'limit' | 'market_on_touch'. In market_on_touch mode, enter at market when price first touches the FVG near edge, the OB open (the down-candle body high for longs), or the refined body-gap level. Allow further penetration into the OB, capped at the MT. Stop and targets are unchanged.
- **Sources:** 089_h0yOpwSilnE ~00:04:20; cc04_003_PIYh0CxoY9c ~00:07:43; cc04_012_FgacYSN9QEo ~00:12:51.
- **Quote:** "here's the market trade up into the fair value Gap here I marketed in"
- **Conflicts:** E1 says resting limit only.
- **Rulebook fix:** E1: add market-on-touch as an alternative.
- **BUILD SPEC (entries_stops_sizing):**
  - In the `run_day` pending-fill block, `entry_order="market_on_touch"`: the first bar that touches the level (no 1-tick trade-through needed) fills at the level, or at the next bar's open when `mot_next_open` is on (slippage test).
  - Params: `entry_order: str = "limit"`, `mot_next_open: bool = True`.
  - Test: `test_market_on_touch_fill`.

### 93. B17-M15-madeuce-inside-bisi
- **rule_id / kind:** M15 / unlisted_contradiction. Scope: index. judgment = true.
- **Rule:** B17's inside-BISI no-trade rule applies when price is inside the range AND both sides are arguable: the range has already been partly re-delivered, and price is back around the CE in a range-bound state. Ma Deuce (M15) is allowed inside the range when price sits in the premium half (the discount half for the mirror) of a range not yet re-delivered, and the HTF expectation is a one-sided re-delivery. Apply per index.
- **Sources:** 091_1PkTGkOjoGo ~00:15:17.
- **Quote:** "if we are up in the upper portion of that range ... and we're seeing the market start to break down"
- **Conflicts:** B17 vs M15.
- **Rulebook fix:** B17/M15: add the reconciliation.
- **BUILD SPEC (day_week_context + pre_open.py):**
  - `sloppy_day` "inside_bisi" (exists, opt-in) gets `inside_bisi_redelivered`: it fires only if yesterday's range already traded below the BISI CE and today opens within `bisi_ce_band` of the CE.
  - Ma Deuce (`PO.run_ma_deuce`, `md_blocked`) is exempt when price is in the premium half and the BISI has not yet traded below its CE.
  - Params: `inside_bisi_redelivered: bool = False`, `bisi_ce_band: float = 0.15`.
  - Test: `test_inside_bisi_two_sided_only`.

### 94. M15-bullish-mirror
- **rule_id / kind:** M15 / shortened. Scope: index. judgment = false.
- **Rule:** Bullish Ma Deuce: the HTF expects one big down-close daily candle's SIBI range to be re-delivered higher, and price is in its discount half. After a low, a bearish 1m FVG is broken upward (inverted). After 08:00, buy the retrace down into the IFVG ahead of the 08:30 release. Targets: the range CE, the upper quadrant, the nearby HTF premium array, and in the best case the range high. Pre-market only and research only.
- **Sources:** 091_1PkTGkOjoGo ~00:24:28.
- **Quote:** "everything here is just completely reversed"
- **Conflicts:** none.
- **Rulebook fix:** M15: add the mirror.
- **BUILD SPEC (pre_open.py, alongside setups_models' M15 switches):**
  - `md_sides="both"` in `run_ma_deuce` mirrors every step: daily SIBI, discount half, bearish 1m FVG inverted upward, long into the IFVG, targets CE / quadrant / high.
  - Params: `md_sides: str = "short"`.
  - Test: `test_ma_deuce_bullish_mirror`.

### 95. M2-three-drives-breaker-fallback
- **rule_id / kind:** M2 / missing_condition. Scope: index. judgment = true.
- **Rule:** Three-drives short: price drives above the same buy-side level three times, at a level expected to be sensitive, then an MSS down. Entry 1 = the 2022-model bearish FVG in the displacement. Entry 2, if entry 1 was missed: after price trades lower, short the retrace into the bearish breaker where it overlaps a bearish IFVG. Stop above the breaker/IFVG high [ours]. Target the predefined lower level. Mirror for longs.
- **Sources:** 093_CcNOk_3O5wk ~00:11:14.
- **Quote:** "I wasn't able to catch that so I had to wait for it to trade lower"
- **Conflicts:** none.
- **Rulebook fix:** M2: add the same-level requirement and the breaker + IFVG fallback.
- **BUILD SPEC (setups_models):**
  - `levels.three_drives` gets a same-level option: all three highs within `td_level_pts` of the swept level.
  - With `td_fallback`, when the FVG order expires unfilled, arm a breaker order (`_breaker_order`) on the breaker of the three-drives top, if that breaker overlaps an IFVG (`sd.ifvgs`).
  - Params: `td_same_level: bool = False`, `td_level_pts: float = 2.0`, `td_fallback: bool = False`.
  - Test: `test_three_drives_breaker_fallback`.

### 96. new-opening-price-position-model
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** Position-trader opening-price model (FX context; park it with M17). Weekly bias bullish. Reference = the Asian session opening price (the second reference is unnamed). Wait for price to trade below it first, then buy strength once price trades back above the open. Use a "reasonable" stop; putting it beyond the sub-open low is ours. No lower-timeframe management; hold toward the HTF draw. Expect few setups, frequent small stops and long winners. Mirror for shorts.
- **Sources:** 095_LPmMtq9jLm8 ~00:15:42.
- **Quote:** "you want to see it trade lower first ideally below it and then when it moves higher"
- **Conflicts:** E1 uses limit entries; this model uses a stop entry.
- **Rulebook fix:** M17: list the opening-price position model.
- **BUILD SPEC (bias_htf, research study):**
  - `study.opening_price_model(days, ref="midnight")`: on each day with `weekly_bias` +1, after a trade below the midnight open, place a buy stop at the open. Stop below the sub-open low; exit at the weekly draw or the Friday close. Report the R distribution. No `_scan_core` branch.
  - Test: `test_opening_price_study_smoke`.

### 97. new-15s-breaker-inside-1m
- **rule_id / kind:** new / missing_rule. Scope: needs_unavailable_data. judgment = false.
- **Rule:** If the bullish breaker's L1, H and L2 all sit inside one 1m candle's range, drop to 15-second bars to execute the breaker/immediate-rebalance entry and the adds. Return to 1m management once the position is on.
- **Sources:** 096_tjnir-o4rsQ ~00:01:17.
- **Quote:** "I'm gonna drop down into a 15 second chart"
- **Conflicts:** none.
- **Rulebook fix:** M4: note the 15s execution case (needs sub-minute data).
- **BUILD SPEC:** none (needs sub-minute bars).

### 98. A15-mitigation-block-entry
- **rule_id / kind:** A15 / missing_rule. Scope: general. judgment = true.
- **Rule:** Bearish, with the HTF draw below (098 shows it on the daily). Mitigation block = the last down-close candle of a lower high (its high did not exceed the prior swing high) that price has since traded down through. On a later day, when price trades back up into that candle's range while above that day's opening price (the high part of a bearish PO3), sell inside the candle's range. Put the stop above the candle's MT so that it sits behind 3 PD arrays: the MB candle MT, the bearish OB MT and the high of the adjacent FVG. If all three fail, the trade is wrong. Target the HTF draw. Bullish mirror. Add this as an M0 entry-array option; M4's CC failure-swing retest partly overlaps it.
- **Sources:** 098_PejS-nZTQlE ~00:45:55.
- **Quote:** "you can use a mitigation block which I don't talk very much about but I love them"
- **Conflicts:** A15 (075): weaker than a breaker, used more as a target.
- **Rulebook fix:** A15: add the entry procedure; M0 step 5: list the mitigation block.
- **BUILD SPEC (setups_models):**
  - Add "mitigation" to `entry_arrays`, using `levels.mitigation_blocks` (fixed swing order, review pass) on the execution TF, or on daily bars when `mit_entry_tf="D"`.
  - Entry: a limit inside the block (its low for shorts). Only while price is above that day's opening price (midnight open intraday).
  - Stop: max(block MT, the adjacent FVG top) + buffer.
  - Params: add "mitigation" to `entry_arrays`; `mit_entry_tf: str = ""`.
  - Test: `test_entry_arrays_mitigation_short`.

### 99. A15-stair-step-mitigation
- **rule_id / kind:** A15 / M4, missing_rule. Scope: general. judgment = false.
- **Rule:** While the bearish leg is intact and the HTF target (e.g. a liquidity void's MT) has not been hit: each time price breaks below the latest swing low L_k, the last down-close candle at L_k becomes a new mitigation block. Sell the first retrace into it. The whole candle range is usable, and bodies should not be violated. The limit goes inside the candle, with the near/low edge as the default [our interpretation]. Keep the switch mb_order='limit'|'stop'. Stop above the candle's high. Target a break of the newest low, then the HTF target. Roll the reference to each newer broken low, and stop once the HTF target is reached. Bullish mirror. The example is FX; the concept is general.
- **Sources:** cc04_004_FOUzW0QmsfI ~00:11:52, ~00:13:57.
- **Quote:** "every rally that sees lower prices needs to be mitigated right here so if we trade back up to that low that's a cell"
- **Conflicts:** E1 (cc06_008) puts stop orders on mitigation blocks; cc04_004 uses a limit inside the candle.
- **Rulebook fix:** A15: add the stair-step model and the order-type conflict.
- **BUILD SPEC (setups_models + entries_stops_sizing):**
  - `mit_stair`: after the first fill, each new broken swing low on the trade side arms an add (or, when flat, a new order) at the low of the last down-close candle at that low. Stop above its high. The adds stop once the lock is delivered.
  - `mb_order="stop"` places a sell-stop just below the block low instead of the limit.
  - Params: `mit_stair: bool = False`, `mb_order: str = "limit"`.
  - Test: `test_mitigation_stair_adds`.

### 100. M17-daily-swing-sellstop-midnight
- **rule_id / kind:** M17 / missing_rule. Scope: general. judgment = true.
- **Rule:** Daily TF, bias bearish toward a weekly/daily sell-side target, with price trading up into a daily bearish FVG. Trading begins on the first day whose opening price is still at or near the FVG; skip days that open far below it. After 21:00 ET (Asia in place), place a sell-stop at that day's midnight NY open (the settlement open is acceptable). It fills when price trades below it. Stop above the high of the candle that formed the FVG. Size so that risk is <= 1%. Use multiple units: a first partial at the run below the nearby daily lows, the rest to the larger sell-side target. Mirror for longs. It stays parked under M17 (swing models). Record it as the stop-order exception to E1.
- **Sources:** 098_PejS-nZTQlE ~00:22:11.
- **Quote:** "if it trades below that you're short"
- **Conflicts:** E1: resting limit, never chase.
- **Rulebook fix:** M17: write out the procedure; E1: list the stop-order exception.
- **BUILD SPEC (bias_htf, research study):**
  - `study.daily_fvg_sellstop(days)`: on daily bars with `htf.table` bias -1 and the prior day inside a daily bearish FVG, place a sell-stop at the next midnight open. The stop is the FVG candle high. Exits: the nearest daily low, then the weekly target. Report R. Parked; no live branch.
  - Test: `test_daily_sellstop_study_smoke`.

### 101. new-next-day-or-reh-short
- **rule_id / kind:** new / missing_rule. Scope: index. judgment = false.
- **Rule:** Conditions: the prior day drove down into the low end of an HTF inefficiency (discount), and overnight does not trade below the prior day's low. Mark the 15m single/relative equal highs from the prior day's rally, where the trailed buy stops sit. The next morning (AM session; no specific 09:30-10:00 window), expect a run above them. Optionally take a long setup that runs up into them. After the sweep, require an MSS lower with an FVG and short at that FVG. Stop above the sweep high [ours]. Target the low that formed just before the REH sweep. Cancel the plan if the prior day's low breaks overnight.
- **Sources:** 099_v_iJlBKYmUc ~00:52:08.
- **Quote:** "if they stay like this and we don't break this low overnight I would expect this run here tomorrow morning"
- **Conflicts:** none (the claim's T4 conflict came from a time window ICT did not state).
- **Rulebook fix:** add a next-day plan template under M0/L1.
- **BUILD SPEC (setups_models):**
  - `prev_reh_plan`: at 09:30, if the overnight low > the prior day's low and the prior day's close sits inside a daily bullish FVG's lower half, add the prior day's 15m rel-eq highs (`_eq_levels` on 15m bars) as priority AM pools. The short target = the last swing low before the sweep.
  - Params: `prev_reh_plan: bool = False`.
  - Test: `test_prev_day_reh_plan`.

### 102. M2-skip-filter
- **rule_id / kind:** M2 / missing_condition. Scope: index. judgment = true.
- **Rule:** Add a liquidity filter to M2 (2022 model): skip the entry if an unraided buy-side pool lies just above the entry, inside the stop zone. The typical case is a high probed repeatedly by wicks with no body close above it: the pool is still intact and could be run (a squeeze) before the move. Wait for that pool to be taken first. The news filter (N5, second driver pending) and the Friday filter (2.3) already apply; cross-reference them in M2.
- **Sources:** 100_GJeEU2oIh24 ~01:07:20.
- **Quote:** "I would not take this trade using that logic even if it does deliver"
- **Conflicts:** none.
- **Rulebook fix:** M2: add the stop-zone pool filter and cross-reference N5 / 2.3.
- **BUILD SPEC (setups_models):**
  - `stop_zone_pool`: in `finish_gates`, drop the order if a same-side untaken pool (or a level probed by >= 2 wicks with no body close beyond it) lies between the entry and the stop.
  - Params: `stop_zone_pool: bool = False`.
  - Test: `test_skip_when_pool_inside_stop`.

### 103. A14-unicorn-standalone
- **rule_id / kind:** A14 / missing_condition. Scope: index. judgment = true.
- **Rule:** Bearish unicorn on any TF (the example is 60m ES). Price retraces up into a premium array (e.g. the NWOG's lower quadrant), forming a swing high. It then breaks below the prior swing low, forming a bearish breaker, and a SIBI overlaps the breaker zone. Sell the retrace into that overlap. Target the nearest sell-side swing low. Exit fully there and stop trading the idea ("you're done"). Bullish mirror. Run it as setup 'unicorn_standalone' with no 09:30 requirement, and fix A14's citation of 101.
- **Sources:** 101_VElIka5sk0E ~01:24:37 (caption 84:37).
- **Quote:** "this setup alone is a model in and of itself"
- **Conflicts:** M4: unicorn entry only after a 09:30 sell-side run.
- **Rulebook fix:** A14: make the unicorn a standalone model on any TF; fix the 101 citation.
- **BUILD SPEC (setups_models):**
  - `unicorn_standalone`: unicorn orders on `unicorn_tf` (1, 5, 15 or 60) bars, without needing a pool sweep. The premise is a retrace into a same-side array (item 10 path) or an NWOG quadrant.
  - Single target = the nearest opposite swing; full exit; after that, `done` for the idea.
  - Needs `ob_entry` "post_mss" or "both" (owner #5/#11 note).
  - Params: `unicorn_standalone: bool = False`, `unicorn_tf: int = 1`.
  - Test: `test_unicorn_standalone_60m`.

### 104. M13-max-depth-79
- **rule_id / kind:** M13 / missing_condition. Scope: general. judgment = true.
- **Rule:** After an MSS, do not use an FVG as the entry if reaching it requires a very deep retracement of the displacement leg (harmonic territory, ~80-88%). ICT gives no exact number. A cap at ~79% (the OTE upper bound) is [our interpretation], kept as a switch. Combined with M2's at-or-above-50% rule, valid entry FVGs sit between 50% and the cap.
- **Sources:** 102_uzPM1CuSSx8 ~01:00:33.
- **Quote:** "that's a little too deep of of a retracement I'm not a harmonics Trader"
- **Conflicts:** none.
- **Rulebook fix:** M13/M2: add the depth cap.
- **BUILD SPEC (setups_models):**
  - `max_retrace`: in the gap pick, drop FVGs whose near edge lies beyond `max_retrace` of the leg (measured from the leg extreme).
  - Params: `max_retrace: float = 0.0` (0 = off; test 0.79).
  - Test: `test_fvg_beyond_79_dropped`.

### 105. M10-ifvg-open-dependent
- **rule_id / kind:** M10 / missing_rule. Scope: index. judgment = true.
- **Rule:** Bearish plan with a daily IFVG above.
  - (1) If the session opens with a gap lower, expect a retrace up into the IFVG, possibly through its full range to the top (permitted when the FVG has had only one pass). Short the rejection there. Stop per M10 (above CE + 3-4 ES pts, or above the IFVG top if price trades fully through) [our interpretation]. Target the daily low, then the sell-side. Take partials at the wick CE and candle lows in a high-resistance run.
  - (2) If the open is relatively unchanged, do not pre-place a limit at the IFVG. Require price to trade into it, start lower, and form a 1-5m bearish FVG, then short that FVG toward the sell-side below.
- **Sources:** 102_uzPM1CuSSx8 ~02:21:33.
- **Quote:** "if we open relatively unchanged I'm not going to be so you know fever pitch to to get short of that inversion"
- **Conflicts:** none.
- **Rulebook fix:** M10: add the open-dependent switch.
- **BUILD SPEC (setups_models):**
  - `ifvg_open_mode`: at 09:30 (and for the Sunday open on Mondays), compare the open with the prior close.
    - Gap away from the IFVG > `ifvg_gap_pts`: allow a resting limit at the daily IFVG (`ifvg_depth` controls far-edge vs CE).
    - Otherwise: only the LTF MSS + FVG path after price trades into the IFVG.
  - Params: `ifvg_open_mode: bool = False`, `ifvg_gap_pts: float = 5.0`.
  - Test: `test_ifvg_open_dependent`.

### 106. M0-htf-array-not-reached
- **rule_id / kind:** M0 / missing_rule. Scope: index. judgment = true.
- **Rule:** If the planned HTF entry array (e.g. a 4h IFVG) is not reached and price stalls below it, keep the HTF draw unchanged. Drop to lower TFs (4h -> 1h -> 15m) and enter at the bearish breaker formed below the unreached array, still above the draw. Adds are allowed within the breaker candle. Stop above the breaker high, trailed. An FVG as an alternative entry is [our interpretation]. Mirror for longs.
- **Sources:** 103_IU673ZUGuxI ~00:29:15.
- **Quote:** "I would have liked to seen it trade back up into this inefficiency ... but it was unwilling to get there"
- **Conflicts:** none.
- **Rulebook fix:** M0: add the unreached-array fallback.
- **BUILD SPEC (setups_models):**
  - `array_fallback_breaker`: when the session lock side is set and the planned 4h/1h array above price was not reached, a 15m bearish breaker (`levels.breakers` on `htf_bars(df, 15)`) below it, above the draw, arms a breaker order. The stop goes above the breaker high.
  - Params: `array_fallback_breaker: bool = False`.
  - Test: `test_fallback_15m_breaker`.

### 107. M1-original-consolidation-entry
- **rule_id / kind:** M1 / missing_rule. Scope: general. judgment = false.
- **Rule:** MM buy model: price has left the original consolidation when a candle body closes above its high; wicks do not count. If price later trades back down to that high, go long there (the "original entry"). If it never returns, use the next higher-order entry, i.e. the next PD array in the subsequent stages (per M1's "the next stage becomes your first"). Mirror for the sell model.
- **Sources:** 104_iKsIbUblSWM ~00:32:10.
- **Quote:** "it doesn't have to touch it but if it does that's usually a trade"
- **Conflicts:** none.
- **Rulebook fix:** M1: add the original-consolidation entry.
- **BUILD SPEC (setups_models):**
  - Builds on `mmxm_ctx` (the original consolidation = the parent swing). `mm_oc_entry`: once a body closes above the consolidation high, a limit at that high (first return only). Stop below the consolidation's mid [ours].
  - Params: `mm_oc_entry: bool = False`.
  - Test: `test_mm_original_consolidation_retest`.

### 108. M1-consolidate-at-discount-array
- **rule_id / kind:** M1 / missing_condition. Scope: general. judgment = true.
- **Rule:** After the hourly shift and the retrace into the discount FVG/OB: if price goes sideways inside or at the array, keep the long thesis toward BSL. If price keeps dropping through the array, the leg is not confirmed. [our interpretation] Valid = N bars with a range < X inside the array; invalid = a body close below the array low.
- **Sources:** 104_iKsIbUblSWM ~00:23:42.
- **Quote:** "we would be anticipating some measure of consolidation not dropping lower"
- **Conflicts:** none.
- **Rulebook fix:** M1: add the accumulation-at-the-array condition.
- **BUILD SPEC (setups_models):**
  - `mm_accum_bars`: for MM-model longs, arm only after `mm_accum_bars` consecutive bars inside the array whose total range < `mm_accum_frac` x the array height. Cancel on a body close below the array low.
  - Params: `mm_accum_bars: int = 0`, `mm_accum_frac: float = 1.0`.
  - Test: `test_mm_accumulation_required`.

### 109. M1-accumulation-stages
- **rule_id / kind:** M1 / missing_rule. Scope: general. judgment = false.
- **Rule:** Stages are counted from the trader's own first entry.
  - The return to the original consolidation (if identified) = the original entry.
  - The breaker OB (the down-close candle inside a bullish breaker: low, high, lower low, break above the high) = 1st-stage accumulation, or the 2nd stage if the original entry was taken.
  - A later BISI retraced only to its CE = the next stage (reaccumulation).
  - Each is valid only while the BSL/HTF target above has not been reached.
  - Pyramid from one stage to the next. Mirror for the sell model.
- **Sources:** 104_iKsIbUblSWM ~00:36:46.
- **Quote:** "there's your entry for a first stage accumulation"
- **Conflicts:** none.
- **Rulebook fix:** M1: turn the context-only phases into codeable stage entries.
- **BUILD SPEC (setups_models + entries_stops_sizing):**
  - `mm_stages`: after the first MM fill, arm adds at (a) the down-close candle inside the next bullish breaker (`breaker_zone`), then (b) the CE of the next BISI. Use E12 sizes, and stop once the lock is delivered. When flat, the first of these is the entry.
  - Params: `mm_stages: bool = False`.
  - Test: `test_mm_stage_adds`.

### 110. M1-distribution-stages-lowrisk-short
- **rule_id / kind:** M1 / missing_rule. Scope: general. judgment = false.
- **Rule:** Reversal: price wicks above the 60m SIBI while bodies stay inside it, then breaks lower.
  - (0) Low-risk short: a rally back to the 60m SIBI CE, with the stop just above the reversal highs. If stopped out, re-enter on a later touch of the FVG low, with the stop above the highest high or the CE of the higher wick.
  - (1) Stage 1 distribution: a bearish breaker (high, low, higher high, then the low taken out leaving an FVG). Short the retrace into it once price shows it wants to run away.
  - (2) Stage 2 redistribution: the next rally into a bearish OB (up-close candle), reaching its MT, OR into the body of a bullish OB left on the buy side of the curve. Short or pyramid there. This leg is expected to be the fastest; if it is missed, do not chase.
  - Take ~80% off at the original consolidation. Mirror for the buy model.
- **Sources:** 104_iKsIbUblSWM ~00:45:30, ~00:49:45.
- **Quote:** "that bearish order block is your second stage redistribution"
- **Conflicts:** none.
- **Rulebook fix:** M1: add the sell-side stage entries.
- **BUILD SPEC (setups_models):**
  - `mm_stages` (item 109) for shorts, plus `mm_lowrisk`: a short limit at the CE of a 60m SIBI that was wicked through with bodies inside, armed after an LTF MSS down.
  - Partial of `mm_oc_frac` at the original consolidation (from `mmxm_ctx`).
  - Params: `mm_lowrisk: bool = False`, `mm_oc_frac: float = 0.8`.
  - Test: `test_mm_lowrisk_short_60m_ce`.

### 111. A18-curve-arrays-reverse-ladder
- **rule_id / kind:** A18 / shortened. Scope: general. judgment = true.
- **Rule:** The curve divider is the model's extreme, known once the reversal (breaker/MSS) forms.
  - Buy curve: record each down-close candle on the left (sell-side) leg that was followed by a short-term bounce.
  - Sell curve: record each up-close candle on the left (buy-side) leg that was followed by a short-term decline (cc04_007). Per 104, bullish OBs from the buy-side leg also act as resistance on the sell side when bodies fail to close back above them.
  - On the right leg, each recorded block in turn is the next entry or pyramid add: a limit at the block on a retrace after price has passed it. Use each block once.
  - [our interpretation] A body close back through a block cancels the rest of the ladder.
- **Sources:** 104_iKsIbUblSWM ~00:52:18; cc04_007_X5pQjfkAUCI ~00:04:46.
- **Quote:** "every new buying opportunity is going to be matched up to the previous down candle"
- **Conflicts:** none.
- **Rulebook fix:** A18: add the ladder, the sell-curve mirror and the "only bounced blocks" rule.
- **BUILD SPEC (setups_models):**
  - Builds on `reclaimed_ob` / `levels.reclaimed_obs` (buy curve, one retest). New:
    - `reclaimed_ladder`: every reclaimed block in order is an add level.
    - Sell-side mirror.
    - Filter to blocks followed by a bounce of >= `reclaim_bounce_bars` bars.
  - Params: `reclaimed_ladder: bool = False`, `reclaim_bounce_bars: int = 2`.
  - Test: `test_reclaimed_ladder_sell_curve`.

### 112. M1-one-segment
- **rule_id / kind:** M1 / missing_rule. Scope: general. judgment = false.
- **Rule:** Implement each MM leg as its own setup: the buy-side leg (original entry or stage entries to the HTF target) and the sell-side leg (low-risk short or stage entries to below the original consolidation). Reversing from the long into a short at the target is advanced and off by default.
- **Sources:** 104_iKsIbUblSWM ~00:09:27.
- **Quote:** "they can either trade the long side of the side of the curve or they can sell short on the cell side of the curve"
- **Conflicts:** none.
- **Rulebook fix:** M1: add the one-segment rule.
- **BUILD SPEC (setups_models):**
  - `mm_flip`: after an MM long hits the lock, allow an MM short in the same session only when `mm_flip` is on; by default, `done` for the session side.
  - Params: `mm_flip: bool = False`.
  - Test: `test_mm_no_flip_by_default`.

### 113. M1-short-sell-side-of-buy-curve
- **rule_id / kind:** M1 / missing_rule. Scope: general. judgment = true.
- **Rule:** If an MMBM is anticipated (HTF draw above, untagged HTF support below), a short on the sell side of the curve toward that support is allowed, targeting the support. ICT gives no entry model; use the bot's normal bearish entries. Exit at the support. Switching to longs at the reclaimed blocks after a higher high is a separate setup, and doing both on one curve is advanced and off by default. If the decline has already happened, skip the short and only map the reclaimed blocks.
- **Sources:** cc04_007_X5pQjfkAUCI ~00:01:21.
- **Quote:** "you can anticipate it and watch it go lower and be short"
- **Conflicts:** none (A18 only says don't buy on the way down).
- **Rulebook fix:** A18/M1: allow the counter-curve short to the HTF support.
- **BUILD SPEC (setups_models + targets_partials):**
  - `curve_short`: with the `htf.table` draw up and an untouched HTF discount array below, allow shorts against the bias. The single target = the array's near edge.
  - Params: `curve_short: bool = False`.
  - Test: `test_curve_short_targets_htf_support`.

### 114. A12-ob-at-consolidation-eq-and-eq-retest
- **rule_id / kind:** A12 / missing_rule. Scope: general. judgment = true.
- **Rule:** Consolidation range defined by candle bodies; EQ = 50%.
  - (a) After an impulse out of the range, the bullish OB is the last down-close candle before the impulse. It is preferred when it sits near or at EQ ([our interpretation] within ~25% of the range height). Buy the retrace into it; do not chase.
  - (b) Alternatively, buy a return to the range EQ after the expansion.
  - [our interpretation] Stop below the OB/range low; target beyond the impulse high. No retrace = no trade. Bearish mirror.
- **Sources:** cc01_001_0LhteuLVuDU ~00:11:11, ~00:18:01.
- **Quote:** "the order block that the market makers leave near or at the equilibrium price point"
- **Conflicts:** M13 "never AT 50%" uses a different reference range.
- **Rulebook fix:** A12: add the consolidation-EQ location; N8: note the post-expansion EQ retest.
- **BUILD SPEC (setups_models):**
  - Branch `consol_eq_entry`. Detect a body-defined consolidation (>= `consol_bars` bars, body range <= `consol_max_pts`) followed by a close outside it. Arm a limit at the last opposite-close candle before the impulse, if it lies within 25% of EQ, or at EQ (`consol_eq_mode`).
  - Params: `consol_eq_entry: bool = False`, `consol_bars: int = 20`, `consol_max_pts: float = 8.0`, `consol_eq_mode: str = "ob"`.
  - Test: `test_consolidation_eq_ob_entry`.

### 115. A10-void-retrace-trades
- **rule_id / kind:** A10 / missing_rule. Scope: general. judgment = true.
- **Rule:** After a fast one-sided leg (void) from L to H:
  - (A) Fill trade: on an indication of reversal against the leg ([our interpretation] MSS), trade back into the void toward its origin.
  - (B) Range trade (cc03_001): if no stop run of an old high or low is visible, buy the retrace back into the void of an up-leg, targeting a run of the leg's high only (the known range, no runner). [our interpretation] Stop below L.
  - (C) Continuation: once price retraces into and fills the void, enter in the original leg's direction, expecting the leg to resume. [our interpretation] Stop beyond the void's origin, target past the leg extreme.
  - Do not chase the original leg. Mirrors apply.
- **Sources:** cc01_001_0LhteuLVuDU ~00:15:21; cc03_001_UF5J0nEBc0E ~00:47:58.
- **Quote:** "when that trades back down to that range i'm going to buy it with an expectation it's going to make a new high"
- **Conflicts:** none.
- **Rulebook fix:** A10: add the three void trades.
- **BUILD SPEC (setups_models; voids from `levels.voids`):**
  - `void_trades`: a tuple of "fill", "range", "cont".
    - "fill": an MSS against a void leg targets the void origin.
    - "range": with no pool swept in the last N bars, a limit at the void CE in the leg direction, single target = the leg extreme.
    - "cont": after price trades to the void origin and an MSS back the leg's way, the normal entry, target beyond the extreme.
  - Params: `void_trades: tuple = ()`.
  - Test: `test_void_range_trade`.

### 116. new-retrace-to-origin-ob
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = false.
- **Rule:** Price delivery cycle: consolidation -> expansion -> either a retracement or a reversal. On a retracement, expect price to return to the order block the expansion left behind, then make another leg in the expansion's direction. The entry inside that OB, the MT handling and the reversal test are [our interpretation].
- **Sources:** cc01_002_XwYYWBttWro ~00:18:12.
- **Quote:** "it can retrace come back to the order block it just left behind and then recapitalize that"
- **Conflicts:** none.
- **Rulebook fix:** A12: add the expansion-origin OB as the retracement's destination.
- **BUILD SPEC (setups_models):** covered by item 114 `consol_eq_mode="origin_ob"` (the last opposite candle before the expansion, any location), cancelled on a body close through its MT. Test: `test_origin_ob_retrace`.

### 117. M13-ote-needs-bias-trigger-structure
- **rule_id / kind:** M13 / missing_condition. Scope: general. judgment = false.
- **Rule:** OTE/discount is context, not an entry. A long needs three things: a bullish bias, price at or below EQ (ideally 62-79%), and a separate lower-timeframe entry signal [the signal type is our interpretation; the lesson's examples are a bullish OB and a turtle soup]. With no signal, there is no trade. Read every retracement against the parent range: do not short at 62-79% of a small down leg's retracement when price is in the lower third / below EQ of the parent range, because that is a discount where market makers buy. Mirror for shorts.
- **Sources:** cc01_004_qC0LogyIk2I ~00:17:12; cc01_006_SiVmoeyOWZE ~00:19:45.
- **Quote:** "you just don't go indiscriminately in there trying to buy it just because it goes back to 50 or less that's not enough"
- **Conflicts:** none.
- **Rulebook fix:** M13: add "context, not an entry" and the parent-range exclusion.
- **BUILD SPEC (setups_models):**
  - `ote="limit"` already places a resting limit with no trigger. Add `ote_need_trigger`: the 70.5% limit arms only after an LTF MSS inside the band. Add `ote_parent_pd`: drop shorts whose entry lies below the parent-range EQ (the session/daily dealing range) and longs above it.
  - Params: `ote_need_trigger: bool = False`, `ote_parent_pd: bool = False`.
  - Test: `test_ote_needs_trigger_and_parent_side`.

### 118. M12-ote-failure-turtle-soup
- **rule_id / kind:** M12 / missing_rule. Scope: general. judgment = true.
- **Rule:** Bullish context, discount below EQ: if the OTE long is stopped out (price runs through the fib levels and below a prior low), look for the buy at the low that was just run, a turtle-soup long at a deeper discount. Exit above an old (short-term) high. Stop placement, sizing and the reversal-confirmation test are [our interpretation].
- **Sources:** cc01_004_qC0LogyIk2I ~00:45:27.
- **Quote:** "just find the low that it just blew out and then expect the buy signal there"
- **Conflicts:** none.
- **Rulebook fix:** M12/M13: link an OTE stop-out to a turtle-soup re-entry.
- **BUILD SPEC (management_exits + setups_models):**
  - `ote_fail_ts`: after an OTE-tagged long is stopped below a prior low, `_after_close` arms a `turtle_soup="2023"`-style order at that low (close back above within `ts_back_bars`), with half risk (X13). Target = the nearest old high.
  - Params: `ote_fail_ts: bool = False`.
  - Test: `test_ote_stop_then_turtle_soup`.

### 119. M13-premium-ote-turtle-soup
- **rule_id / kind:** M13 / missing_rule. Scope: general. judgment = false.
- **Rule:** Bearish range (impulse H->L): if price retraces above EQ into or through 62-79% and runs the buy stops above an old high (including the impulse swing high or a short-term high), treat it as a turtle-soup sell in premium. This applies even after an initial OTE short was stopped. Sell the failure back under the high and take profit below the nearest established swing lows, then the next. Stop and priority ranking are [our interpretation]. Mirror for longs in discount below an old low.
- **Sources:** cc01_005_YuefjnUKQdM ~00:07:03.
- **Quote:** "it's going to be a turtle soup sell"
- **Conflicts:** M12 requires an HTF PD array at the level.
- **Rulebook fix:** M13/M12: add the premium-OTE turtle soup as a qualifying context.
- **BUILD SPEC (setups_models):**
  - `ts_ote_ok`: in `_turtle`, the HTF-array requirement (`ts_need_htf`) is also met when the raided high lies in the 62-79% band (or above EQ) of the last impulse leg. Tag `premium_ts`.
  - Params: `ts_ote_ok: bool = False`.
  - Test: `test_turtle_soup_in_ote_band`.

### 120. M13-bodies-stall-62-ob
- **rule_id / kind:** M13 / missing_condition. Scope: general. judgment = true.
- **Rule:** In an OTE short setup, if price reaches 62% and the candle bodies stop at that level (wicks may poke above), the up-close candle there is a bearish OB and a valid short by itself. Take profit below the nearest old swing low. The entry price within the OB and the stop are [our interpretation]. Mirror for longs.
- **Sources:** cc01_005_YuefjnUKQdM ~00:13:59.
- **Quote:** "the bodies of the candle stop perfectly right there you could sell short right there"
- **Conflicts:** none.
- **Rulebook fix:** M13: add the bodies-at-62% OB trigger.
- **BUILD SPEC (setups_models):**
  - Add `ote="ob62"`: when a bar's body top is within 1 tick of the 62% level and its wick is above it, arm a sell limit at that up-close bar's low (open). Stop above the leg high.
  - Params: add "ob62" to `ote`.
  - Test: `test_ote_ob62_entry`.

### 121. M12-quick-rejection-required
- **rule_id / kind:** M12 / missing_condition. Scope: general. judgment = true.
- **Rule:** Turtle-soup validity: after price runs stops beyond an old swing high or low, a genuine turtle soup reverses quickly. If price instead goes sideways and holds around the EQ of the small new range, reject the fade and expect continuation in the run's direction. A single spike back that does not break the range does not count. For a bullish HTF bias after a sweep of lows with a quick rejection: wait for a down-close candle whose high is later traded through (a bullish OB), and buy the return to it. If price never returns, use the next validated down candle. "Quickly" is not quantified [our interpretation]. Mirror for bearish.
- **Sources:** cc01_006_SiVmoeyOWZE ~00:14:24; cc04_002_npL3ZXJ5zOU ~00:25:05.
- **Quote:** "if it's a turtle soup and it wants to go lower after blowing out buy stops it should go lower quickly"
- **Conflicts:** none.
- **Rulebook fix:** M12: add the failure test and the OB entry sequence after the rejection.
- **BUILD SPEC (setups_models):**
  - `ts_back_bars` already enforces a quick close back. New is `ts_cont`: if the turtle soup fails (no close back within `ts_back_bars`, and price ranges around the spike for >= `ts_cont_bars`), allow a continuation entry in the run's direction via the normal MSS path.
  - Also add the `entry_arrays` "ob" CC-validated variant after a quick rejection (exists as "ob").
  - Params: `ts_cont: bool = False`, `ts_cont_bars: int = 10`.
  - Test: `test_failed_turtle_becomes_continuation`.

### 122. L4-lrlr-repeated-buys
- **rule_id / kind:** L4 / missing_rule. Scope: general. judgment = false.
- **Rule:** Bullish LRLR zone: it runs from the break of a short-term high (after a higher low) up to the old low that was violated earlier (the zone ceiling). Inside the zone, each retracement that gives a buy signal targets the short-term high it retraced from (the buy stops above it). Repeat until price reaches the old low, then stop: beyond it is a high-resistance run. Bearish mirror: after a break below a short-term low, sell each retracement, targeting the low it retraced from, until price reaches the level where the prior short-term high broke.
- **Sources:** cc01_007_22XkhpJR5eA ~00:14:10.
- **Quote:** "that buy signal will have very little resistance to get through the old high that it retraced from"
- **Conflicts:** none.
- **Rulebook fix:** L4: add the zone bounds and the repeated-entry rule.
- **BUILD SPEC (targets_partials + setups_models):**
  - `lrlr_zone`: compute the zone (the latest broken short-term high up to the nearest earlier violated low above). Inside it, the T1 of each new long = the swing high the retrace started from. No new longs once price is at the ceiling.
  - Params: `lrlr_zone: bool = False`.
  - Test: `test_lrlr_zone_repeat_targets`.

### 123. M12-cc-daily-ob-turtle-soup
- **rule_id / kind:** M12 / missing_condition. Scope: general. judgment = false.
- **Rule:** Daily bullish OB = the open..high of the last down candle before the daily up move. On 1h (refinable to 15m/5m), price sweeps a prior swing low and reaches the daily OB. C = the last down-close candle before the bounce. Arm only after a later candle trades above C.high. Buy limit at C.open + spread (FX 5 pips; on 5m, the daily OB level + spread). Stop at C's MT, or below the sweep low/OB. Map the buy-stop pools before entry.
  - Exit switch A (cc02_001, 1h): half at 1R, BE after 2R, runner to the pools (~5R).
  - Exit switch B (cc02_003, 5m refined): half at 3R, runner to the 15m pool, then the 1h pool (9R-15R). The 3R minimum applies only to switch B.
- **Sources:** cc02_001_mjVHmE1gVMg ~00:18:50; cc02_003_pctqB3UD6dk ~00:01:21.
- **Quote:** "not just simply as it hits that level we're gonna wait for something to give us confirmation"
- **Conflicts:** cc02_001 (half at 1R, BE after 2R, runner 5R) vs cc02_003 (half at 3R, runner 9-15R).
- **Rulebook fix:** M12 CC line: add the trade-through trigger, the spread and the second exit variant.
- **BUILD SPEC (setups_models):**
  - Builds on `turtle_soup="cc_1h_ob"` (1R / BE 2R / 5R exists). New:
    - `cc_ob_validate`: the order arms only after a later bar's high > C.high.
    - `cc_ob_tf` (60 / 15 / 5).
    - `ts_r_mults` preset "cc02_003" = (3, 9, 15) with BE after 3R.
    - The spread comes from `entry_offset_ticks` (item 125).
  - Params: `cc_ob_validate: bool = False`, `cc_ob_tf: int = 60`.
  - Test: `test_cc_1h_ob_waits_trade_through`.

### 124. E3-entry-spread-offset
- **rule_id / kind:** E3 / missing_rule. Scope: general. judgment = false.
- **Rule:** Long limit = level + entry_buffer; short limit = level - entry_buffer. The level is the OB open/high or the HTF PD-array level. In FX, ICT uses about 5 pips explicitly so that the spread fills the order [CC, fx]. For the index this is a test switch only, entry_offset_ticks in {0, 1, 2} [our interpretation: futures charts print trades, not the bid, so the spread rationale is weaker]. With a positive offset, a touch fills (bar low <= level + buffer). This conflicts with E3's 2023 1-tick-through rule.
- **Sources:** cc02_001_mjVHmE1gVMg ~00:21:13; cc02_002_Zsg8IeBtfu0 ~00:07:55; cc03_003_t2VNzJZ4hK4 ~00:32:55; cc04_003_PIYh0CxoY9c ~00:07:30.
- **Quote:** "if you have a limit order you're going to add a few pips and preferably it's about five pips"
- **Conflicts:** E3: a limit fills only on a 1-tick print through.
- **Rulebook fix:** E3: add the CC offset as an alternative.
- **BUILD SPEC (entries_stops_sizing):**
  - `entry_offset_ticks` moves every limit price toward the market by N ticks (in `_finish_order`, before `_round_px`). The fill test stays strict, so with N >= 1 a touch of the original level fills.
  - Params: `entry_offset_ticks: int = 0`.
  - Test: `test_entry_offset_fills_on_touch`.

### 125. B5-topdown-entry-refinement
- **rule_id / kind:** B5 / missing_rule. Scope: general. judgment = true.
- **Rule:** With price at an HTF (M/W/D) PD array in the bias direction, step down timeframes (1h -> 15m -> 5m in cc02_002). On each one, find the last down-close candle (bullish) at or inside the HTF level that a later candle trades above. Its open/high (+ spread) becomes the refined entry. The stop stays at the same structural point (below the sweep low or the HTF level), so it shrinks in pips. Use the lowest TF that gives such an OB, and never use one without the HTF level in play. Targets: first the execution TF's pool (3R in cc02_002), then the HTF pools. The mitigation-block pairing is analogous. Mirror for shorts.
- **Sources:** cc02_002_Zsg8IeBtfu0 ~00:02:27; cc02_003_pctqB3UD6dk ~00:01:34; cc04_003_PIYh0CxoY9c ~00:33:37; cc04_004_FOUzW0QmsfI ~00:11:12.
- **Quote:** "transposing the higher time frame levels to lower time frame charts is important"
- **Conflicts:** none.
- **Rulebook fix:** B5: add the refinement procedure.
- **BUILD SPEC (setups_models):**
  - `cc_ob_tf` (item 123) generalised: `refine_tfs=(60, 15, 5)`. For the cc_1h_ob path, search each TF from the lowest up for a validated down-close candle inside the daily OB; use the lowest found. The stop stays below the sweep low.
  - Params: `refine_tfs: tuple = ()`.
  - Test: `test_refine_to_5m_ob`.

### 126. L15-min-3R-prefer-5R
- **rule_id / kind:** L15 / missing_rule. Scope: general. judgment = false.
- **Rule:** RR_final = (planned final target / first opposing HTF draw minus the exit buffer - entry) / (entry - stop). Filter switch min_rr_final in {1, 3, 5}: reject setups below the floor, and tag/rank rr5 setups higher. It applies to the final draw, not to the first partial (cc02_001 still banks half at 1R). Sources: cc02_004 (general money management: 3:1 foundation, 5:1 preferred) and cc06_002/cc06_006 (swing: "nothing less than 3:1", 5-10:1 common). The intraday index application is our interpretation, and it conflicts with L15's handle-based room and cc02_001's 1:1 examples.
- **Sources:** cc02_004_pFdW8wdR9sQ ~00:01:51; cc06_002_Xs1i0aIeTME ~00:12:38; cc06_006_JAjL7rUX2Iw ~00:07:03.
- **Quote:** "use nothing less than three to one reward the risk ratios"
- **Conflicts:** bot `min_rr=1` on T1 and L15's 5-handle minimum room vs ICT's 3R minimum.
- **Rulebook fix:** L15: add the R:R floor on the final draw.
- **BUILD SPEC (targets_partials):**
  - `min_rr_final`: in `_finish_order`, after the ladder is built, drop the order if (last rung - entry) / risk < `min_rr_final`. Tag `rr5` when >= 5.
  - Params: `min_rr_final: float = 0.0`.
  - Test: `test_min_rr_final_filter`.

### 127. A12-secondary-ob
- **rule_id / kind:** A12 / missing_rule. Scope: general. judgment = true.
- **Rule:** While price retraces into a primary bullish OB (high..open), a down-close candle formed inside that retrace is a secondary bullish OB [our interpretation of which candle]. Go long on it (the entry price is not specified; use its open/high per A12, with the MT as a test variant). It is invalid on a body close below its MT. The example stop is a fixed 20 pips (FX), below that MT; "below its low" is our interpretation. Target the old high / buy stops at >= 3R. Bearish mirror. A single example (cc02_004 ~3:14).
- **Sources:** cc02_004_pFdW8wdR9sQ ~00:03:14.
- **Quote:** "a hypothetical long entry on the secondary bullish order block"
- **Conflicts:** none.
- **Rulebook fix:** A12: add the nested OB entry.
- **BUILD SPEC (setups_models):**
  - Add "ob_secondary" to `entry_arrays`: when the retrace enters the primary OB zone (`_ob_pre`), the first down-close bar inside it arms a limit at its open (or its MT with `ob_entry_px="mt"`). Cancel on a body close below its MT.
  - Params: add "ob_secondary" to `entry_arrays`.
  - Test: `test_secondary_ob_entry`.

### 128. X13-reentry-mechanics
- **rule_id / kind:** X13 / missing_rule. Scope: general. judgment = false.
- **Rule:** After a stop-out, with the draw still untouched and the idea not unraveled, wait for a new down-close candle C, then arm when a later candle trades above high[C]. Buy limit at high[C] (variant: open[C]); either fills on the return. Stop below low[C] (below the whole OB, not its MT), which gives a wider stop than the first try. Risk = half the losing trade's risk %. Mirror for shorts.
- **Sources:** cc02_005_vWDElb65YHg ~00:04:02.
- **Quote:** "that authorizes any new return to this down candle as a buying opportunity"
- **Conflicts:** none.
- **Rulebook fix:** X13: add the entry and stop mechanics.
- **BUILD SPEC (management_exits):**
  - Builds on `reentry_half`. `reentry_mode="cc_ob"`: the re-entry order is the next CC-validated down-close candle (a later high > its high). Limit at its high (or open), stop below its low, risk x0.5.
  - Params: `reentry_mode: str = ""`.
  - Test: `test_reentry_cc_ob_mechanics`.

### 129. new-seven-factor-context
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = false.
- **Rule:** high_reward = >= 2 big-picture factors + >= 2 intermediate-term factors + 1 from each of the 3 short-term factors, all agreeing in direction (7 in total; ICT's "four things" at ~53:58 is a slip). It is a context/grade label only. No order is placed until a model entry trigger fires. The factor list must come from the cc02_006 slide, which is not in the captions, so the encoding is our interpretation.
- **Sources:** cc02_006_bftKgceXqYo ~00:54:23.
- **Quote:** "this is not execution this is not entry it just gives you the framework"
- **Conflicts:** none.
- **Rulebook fix:** B4: add the seven-factor grade (context only).
- **BUILD SPEC (bias_htf):**
  - Tag `factors7` = a count of agreeing factors from what the bot has: big picture (monthly/weekly bias from `htf.table`), intermediate (daily bias, daily IOF `flip`), short term (time-of-day window, SMT tag, 4h/1h array). Report only.
  - Params: `factor_tag: bool = False`.
  - Test: `test_factor_count_tag`.

### 130. new-false-bear-flag-long
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = false.
- **Rule:** Context: a 1h bear flag (up-sloping consolidation after a drop) forms where the daily chart has run below the lows of prior daily candle bodies (HTF discount / stop run). Do not buy the first rally. Wait for a swing high [3-bar pivot, our interpretation] to form and then be traded through. On the first retrace, buy limit at the last down-close candle before the break. Stop below the flag low. Targets in order: the last up candle's body, equal highs, bearish OBs, then the older equal highs / long-term objective. Bearish mirror (false bull flag in an HTF premium).
- **Sources:** cc02_007_cRbPS3uxkj4 ~00:22:28.
- **Quote:** "we want to wait for a swing high to be created and violated on the upside"
- **Conflicts:** none.
- **Rulebook fix:** add a new rule next to the false-bull-flag item (64).
- **BUILD SPEC (setups_models):** the mirror of item 64's `false_flag` gate (a flag consolidation at an HTF discount after a daily run below body lows), with `entry_arrays` "ob" CC-validated. Test: `test_false_bear_flag_long`.

### 131. M12-setup-selection-order
- **rule_id / kind:** M12 / missing_condition. Scope: general. judgment = true.
- **Rule:** Three disciplines exist on all TFs (cc03_001):
  - (a) Turtle soup: selling a run above an old high when bearish.
  - (b) OB return: selling the previous bearish OB when a stop run above is judged unnecessary.
  - (c) Range/void trade: trading back into the range or liquidity void when no violation of an old high/low is in view.

  ICT gives no fixed priority ("no preference"; the selection criteria are deferred to later lessons). He also says a trader may specialise in one discipline. Encode as entry_discipline in {turtle_soup, ob_return, range_void, any}, tested separately. Any fixed ordering is our interpretation. Bullish mirror.
- **Sources:** cc03_001_UF5J0nEBc0E ~00:45:51; cc04_002_npL3ZXJ5zOU ~00:22:09.
- **Quote:** "you're going to see either Turtle soups ... or you're going to be looking for a return back to fair value"
- **Conflicts:** none.
- **Rulebook fix:** M12: add the three disciplines and the "pick one" note.
- **BUILD SPEC (setups_models):**
  - `entry_discipline` is a preset that switches the other paths on/off: turtle_soup -> `turtle_soup="cc_limit"` only; ob_return -> `ob_entry="pre_break"` only; range_void -> `void_trades=("range",)` only; any -> current.
  - Params: `entry_discipline: str = "any"`.
  - Test: `test_entry_discipline_presets`.

### 132. M12-contrarian-pmh
- **rule_id / kind:** M12 / missing_rule. Scope: general. judgment = true.
- **Rule:** [CC, parked with swing models per M17] Contrarian short-term idea: when the daily trades above the previous month's high (or blows off into a significant HTF level after an extended run), a reversal pattern there can be sold short for a limited move ("not forever"). ICT gives no specific trigger, stop or target here. Any failure confirmation or target choice is our interpretation. Mirror below the PML.
- **Sources:** cc03_001_UF5J0nEBc0E ~00:16:57.
- **Quote:** "that may be a really good selling scenario to sell short but not forever"
- **Conflicts:** none.
- **Rulebook fix:** M17: list the PMH/PML contrarian idea.
- **BUILD SPEC (setups_models):**
  - Intraday proxy: PMH/PML are already pools (L3, `ipda_pools`). `pmh_contrarian` lets a sweep of the PMH arm the normal short path even against the daily bias, with the single target = the session's opposite pool.
  - Params: `pmh_contrarian: bool = False`.
  - Test: `test_pmh_sweep_contrarian_short`.

### 133. new-htf-regime-trigger-and-entry
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** [CC, demonstrated on FX, HTF/swing scope (see M17)] Monthly range = the most recent down-close candle D and the most recent up-close candle U.
  - Bullish: when a later candle trades above high[D], D is a bullish OB. Wait for a return into D and buy at or below its level, refining to the daily or weekly down candle inside it. Wicks through are acceptable while the refined candle's MT holds. Target U and the old or equal highs above it.
  - Daily alternative: at a monthly bullish OB, wait for a break above a daily short-term high, then buy the return into the OB or the latest daily down candle.
  - Bearish: at a monthly or weekly bearish OB, the move is confirmed when price trades below the low of the last up-close candle. Then sell the return into a breaker or the bearish OB, or a stop run above an old high. Target the sell stops below the candle bodies, then the HTF bullish OB.
- **Sources:** cc03_002_PQkcFbr61FI ~00:14:23, ~00:22:50; cc03_004_9kabTfUEVKg ~00:08:22, ~00:09:54.
- **Quote:** "if you get the market trade above a down candle you wait for a return back to that down candle"
- **Conflicts:** none.
- **Rulebook fix:** B10/M17: add the HTF activation -> return -> target sequence.
- **BUILD SPEC (bias_htf):**
  - `htf.table` column `mob` (+1/-1/0): +1 once a monthly bar trades above the last down-close monthly candle's high (the activation); stays set until price trades below that candle's low. Mirror -1.
  - Used as a bias source with `bias_src="mob"` (research), and in `study.monthly_ob_study` for the daily-entry statistics.
  - Params: `bias_src` gains "mob".
  - Test: `test_monthly_ob_activation_column`.

### 134. B12-ob-below-midnight-open
- **rule_id / kind:** B12 / missing_condition. Scope: general. judgment = false.
- **Rule:** [CC] Bullish daily bias. Candidate OB = a down-close candle formed at or below today's NY midnight (00:00) open, in today's London or NY session or, when needed, the previous day's session. It is validated when a later candle trades above its high. Buy-limit at the OB on its return (CC adds a few pips/ticks), only while price is below the midnight open. Mirror for shorts above the open.
- **Sources:** cc03_003_t2VNzJZ4hK4 ~00:33:28.
- **Quote:** "it has to be below the opening price"
- **Conflicts:** none.
- **Rulebook fix:** B12: add the OB entry under the open.
- **BUILD SPEC (setups_models):**
  - `ob_below_open`: for `ob_entry` / `entry_arrays` "ob" longs, require the OB candle's body to sit at or below the midnight open, and the fill to happen while price is below it. Mirror for shorts.
  - Params: `ob_below_open: bool = False`.
  - Test: `test_ob_below_midnight_open`.

### 135. new-eq-wait-fresh-ob
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** [CC] When price trades at the equilibrium (about 50%) of the current intraday range, ignore small OBs that formed there earlier. Wait for a new down-close candle that a later candle then trades above (a validated bullish OB), and buy its return. This is shown inside the B12 setup below the midnight open. Mirror for shorts.
- **Sources:** cc03_003_t2VNzJZ4hK4 ~00:34:10.
- **Quote:** "when we're at equilibrium price points like that we want to see price give us an order block"
- **Conflicts:** none.
- **Rulebook fix:** A12: add the fresh-OB-at-EQ rule.
- **BUILD SPEC (setups_models):**
  - `eq_fresh_ob`: when the fill price would lie within `eq_tol_pts` of the day's range EQ, only OBs formed after price first reached EQ are allowed.
  - Params: `eq_fresh_ob: bool = False`.
  - Test: `test_eq_needs_fresh_ob`.

### 136. M12-counter-run-in-confirmed-trend
- **rule_id / kind:** M12 / missing_rule. Scope: general. judgment = false.
- **Rule:** [CC, taught on DXY vs FX; the index mapping is our interpretation] If the latest swing extreme is confirmed symmetrically by the correlated market (ES/NQ/YM all make the lower low, i.e. no SMT), do not stalk reversals. A retrace above the latest short-term high (bearish swing) or below the latest short-term low (bullish swing) is treated as a stop run: look for a turtle soup or MSS back in the swing direction, targeting beyond the confirmed extreme. If the swing was NOT symmetrical (SMT present), reversal patterns become high probability instead (B18).
- **Sources:** cc03_005_GuycI8XubgE ~00:03:27.
- **Quote:** "that short-term high is going to be just a run on buy stops"
- **Conflicts:** none.
- **Rulebook fix:** B18/M12: add the symmetric-swing continuation reading.
- **BUILD SPEC (setups_models):**
  - `sym_swing_ts`: when the session's last swing extreme was made by both ES and NQ (`psides`, no SMT tag), counter-trend sweeps of short-term highs/lows arm only in the swing's direction (turtle-soup/MSS back with the trend). Reversal trades need an SMT tag.
  - Params: `sym_swing_ts: bool = False`.
  - Test: `test_symmetric_swing_fades_counter_run`.

### 137. new-trendline-trap
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** Up-trendline with the HTF not bullish (price at a daily bearish array with a draw below). Pivot lows L1 < L2, touch 3 = L3, and H23 = the high between L2 and L3. When price rallies back toward H23, either (a) sell the bearish OB just below H23, (b) sell an LTF bearish breaker, or (c) sell the failure after a small poke above H23 (turtle soup). Stop above the run high; target below L2, then the daily draw. Down-trendline mirror with the HTF bullish: buy at L23 via the OB (price dips into the old low but not through it) or via a turtle soup below L23; target the buy stops above H2. [our interpretation] 3-candle pivots, a touch tolerance of a few ticks, a poke <= 1-2 ES pts.
- **Sources:** cc03_007_o8NfSK-pUlE ~00:08:18, ~00:10:46.
- **Quote:** "I'm looking for a bullish order block at that low in between the two points"
- **Conflicts:** none.
- **Rulebook fix:** add a new rule (trendline trap) after M12.
- **BUILD SPEC (levels_detectors + setups_models):**
  - levels_detectors: `levels.trendline_touches(lows, tol)` returns three-touch rising lines (pivots L1 < L2 < L3 within `tl_tol_ticks` of a line), with H23.
  - setups_models: with `trendline_trap` and the `htf.table` bias against the line, H23 counts as a priority pool (turtle soup within `ts_max_pts`), and the ladder starts below L2.
  - Params: `trendline_trap: bool = False`, `tl_tol_ticks: int = 4`.
  - Tests: `test_trendline_touches`, `test_trendline_trap_short`.

### 138. new-hs-fade
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = false.
- **Rule:** HTF bullish (price in the body of a daily bullish OB). On the hourly (index: our interpretation, 15m-1h), find S1 < head H > S2 with relatively equal lows between them (the neckline). When price trades below the neckline lows, buy the sell stops there with a resting limit at or just below the lows. Partial at the right shoulder S2; main objective = the buy stops above H. [our interpretation] Stop beyond the sweep extreme, wide enough to survive repeated runs of the lows (ICT's example ran them 4 more times). Inverse H&S in a bearish HTF (daily bearish breaker or OB): sell above the neckline highs, using either the wick high or the highest body. Partial at S2; objective = the sell stops below the head. Re-sell if price runs the level again.
- **Sources:** cc03_008_w8lbrvZXUVY ~00:06:30, ~00:07:11.
- **Quote:** "i see that as a turtle soup long that took out two previous lows"
- **Conflicts:** none.
- **Rulebook fix:** add a new rule (H&S fade) under M12.
- **BUILD SPEC (levels_detectors + setups_models):**
  - levels_detectors: `levels.head_shoulders(h, l, n, tol)` on 15m/60m bars returns (S1, H, S2, neckline lows/highs).
  - setups_models: with `hs_fade` and a same-side HTF array, the neckline rel-eq lows are a `turtle_soup="cc_limit"` level. Ladder [S2, H + buffer]. `hs_stop_pts` gives a wide fixed stop.
  - Params: `hs_fade: bool = False`, `hs_tf: int = 60`, `hs_stop_pts: float = 0.0`.
  - Tests: `test_head_shoulders_detector`, `test_hs_fade_long`.

### 139. E2-body-extreme-entry
- **rule_id / kind:** E2 / missing_condition. Scope: general. judgment = true.
- **Rule:** A turtle-soup/H&S fade level has two options. Option A: the wick extreme. Option B: the highest body, max(open, close), among the swing highs for a short (the lowest body for a long). Rest a limit at the chosen level so it fills as soon as price trades beyond it. Switch ts_entry='body'|'wick'. "No retest needed" follows from using a resting limit [our interpretation]; it is not an ICT statement.
- **Sources:** cc03_008_w8lbrvZXUVY ~00:15:43.
- **Quote:** "you can use the bodies of the candles like i teach where the most volume is"
- **Conflicts:** none.
- **Rulebook fix:** M12: add the body/wick level choice.
- **BUILD SPEC (setups_models):**
  - `ts_entry="body"` in the cc_limit / htf_stab / prev_pm turtle variants: the level = the extreme body of the swing candles instead of the wick.
  - Params: `ts_entry: str = "wick"`.
  - Test: `test_turtle_body_level`.

### 140. new-tf-matches-objective
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** Fix one setup TF per strategy configuration that fits the profit objective, and do not take setups on every timeframe. ICT's FX mapping: ~40 pips -> 15m; 50+ pips -> 30m-60m; 75-100 pips -> 1h-4h ("100 pips a week = 4h or 1h, nothing less"); ~250 pips over two weeks -> 4h-daily. [our interpretation] Index bot: 1m/5m setups for 5-10 handle objectives; larger objectives need higher-TF setups.
- **Sources:** cc04_002_npL3ZXJ5zOU ~00:37:27.
- **Quote:** "you got to pick a time frame that fits what your model is"
- **Conflicts:** none.
- **Rulebook fix:** B5: add the TF-objective match.
- **BUILD SPEC (targets_partials):**
  - `tf_target_cap`: cap the final ladder rung at `tf_cap_pts[tf]` (e.g. {1: 10, 5: 20, 15: 40}) for the run's tf; orders with T1 beyond the cap need a higher tf. Research switch for comparing runs.
  - Params: `tf_target_cap: bool = False`, `tf_cap_pts: tuple = ((1, 10.0), (5, 20.0), (15, 40.0))`.
  - Test: `test_tf_target_cap`.

### 141. A12-same-candle-retrace
- **rule_id / kind:** A12 / missing_rule. Scope: general. judgment = false.
- **Rule:** Once a candle trades above the bullish OB's high (validation), arm the buy limit at the OB high immediately, effective from that same bar. In body mode, the OB high is the body top, which for a down-close candle is its open. A retrace fill inside the validating candle itself counts; on lower-TF data, a fill after the trade-through within the same HTF candle counts. Bearish mirror at the OB low.
- **Sources:** cc04_003_PIYh0CxoY9c ~00:04:04.
- **Quote:** "even in the very candle that broke that down candle's high"
- **Conflicts:** none.
- **Rulebook fix:** A12: add the same-candle retrace rule.
- **BUILD SPEC (entries_stops_sizing):**
  - CC-validated OB orders (`ob_arm`, `cc_1h_ob`, `entry_arrays` "ob") on HTF candles: arm from the 1m bar after the 1m trade-through inside the validating HTF candle, not from the HTF candle close. `ob_arm="touch"` exists for the 1m case; add `ob_arm="intrabar_htf"`.
  - Params: add "intrabar_htf" to `ob_arm`.
  - Test: `test_htf_ob_armed_inside_validating_candle`.

### 142. A13-breaker-reentries-and-wait
- **rule_id / kind:** A13 / missing_condition. Scope: general. judgment = true.
- **Rule:** After the sweep of L1, keep the setup armed while price trades around L1. Do not enter on an early reclaim of / flirt with L1, and do not cancel on a rejection there; wait for a significant move that breaks the in-between swing high H (MSS; close vs wick per D3). After the break, the first return to the breaker is the primary entry, and every later retracement is also a valid entry in the same direction. Existing per-session trade limits apply. Bearish mirror. [our interpretation] Cancel if a new low below L2 prints before H breaks, if the session ends, or once price closes beyond the stop-run extreme; new PD arrays formed after the break are secondary entries.
- **Sources:** cc04_005_UrS-mtGHtAA ~00:04:51, ~00:01:08.
- **Quote:** "all future retracements will be viewed as new selling opportunities especially once it trades back up to the low"
- **Conflicts:** A13: "first touch is valid"; M4: "buy the first return to the bullish breaker".
- **Rulebook fix:** A13/M4: add the later-retracement entries and the wait.
- **BUILD SPEC (setups_models):**
  - `breaker_retests`: number of retests of the same breaker that may create orders (default 1 = current). Each new retest after price has left the zone by >= `breaker_leave_pts` re-arms, subject to `max_trades_session`.
  - Params: `breaker_retests: int = 1`, `breaker_leave_pts: float = 3.0`.
  - Test: `test_breaker_second_retest_entry`.

### 143. A17-rejection-block-entries
- **rule_id / kind:** A17 / missing_rule. Scope: general. judgment = true.
- **Rule:** Bearish RB: the trigger is the block low = the highest open/close in the swing.
  - Aggressive: sell limit at the trigger, with a "significant" stop above (above the highest wick + buffer [our interpretation]).
  - Conservative: after price trades above the trigger without making a new wick high, place a sell-stop just below the trigger. Cancel on a new wick high.
  - Bullish mirror: the trigger is the lowest open/close. Buy limit just below it, or, after a small trade-through, a buy-stop just above it.
  - [our interpretation] Trade-through >= 1 tick.
- **Sources:** cc04_006_oALYX0HCSYw ~00:10:39, ~00:11:19.
- **Quote:** "you could be a seller on a stop below that level"
- **Conflicts:** E1 (cc06_008) lists limits on rejection blocks.
- **Rulebook fix:** A17: add both entries.
- **BUILD SPEC (setups_models + entries_stops_sizing):**
  - With `rb_pools` (item 41), the intraday RB (`levels.rejection_blocks` on the execution TF) is also an entry: `rb_entry="limit"` at the body extreme; `rb_entry="stop"` arms a sell-stop 1 tick below the trigger after a trade-through without a new wick high, cancelled on a new wick high. Stop above the wick high.
  - Params: `rb_entry: str = ""`.
  - Test: `test_rb_conservative_sell_stop`.

### 144. A16-propulsion-entries
- **rule_id / kind:** A16 / missing_rule. Scope: general. judgment = false.
- **Rule:** Bullish: buy limit at the propulsion candle's high, expecting at most ~1-2 ticks below it (FX: "a pip or two"). The deepest acceptable fill is its MT (50% of the body), and losing the MT = the idea is wrong (tight stop just beyond the MT). Bearish propulsion = an up-close candle that trades up into a prior bearish OB. Entry 1: sell at its low or MT, stop above the MT. Entry 2: after a candle breaks below its low, sell the next return up to that low (the body need not be reached). Mirror for bullish.
- **Sources:** cc04_008_glu98jAH8vE ~00:01:49, ~00:06:53.
- **Quote:** "it may go pip or two below the high"
- **Conflicts:** none.
- **Rulebook fix:** A16: add the bearish mirror, the depth tolerance and the second entry.
- **BUILD SPEC (setups_models):**
  - Add "propulsion" to `entry_arrays` (uses `sd.propulsions`, both sides): limit at the block's high (low for shorts), stop beyond its MT. `prop_second`: after a break of the block's far extreme, arm a limit at that extreme on the next return.
  - Params: add "propulsion" to `entry_arrays`; `prop_second: bool = False`.
  - Test: `test_propulsion_entry_and_second`.

### 145. L8-vacuum-block-entries
- **rule_id / kind:** L8 / missing_rule. Scope: index. judgment = true.
- **Rule:** Bullish VB.
  - Partial fill (preferred when the gap forms late, 10:00-11:00): buy limit at the top of the highest down candle in the pre-gap run, stop below that run's lowest low. It requires an immediate reaction (a timeout of 1-3 candles = [our interpretation]).
  - Full fill (preferred when the gap forms early NY/08:30): buy limit at VB_low = the close of the last pre-gap up candle, stop below the lowest low.
  - Precondition: the buy-side liquidity above the gap candle's high is untaken.
  - Management: after the rally, a trade back below VB_low = take partials or exit. Size = equity x risk% / distance.
  - Bearish: after a gap down, wait for up-close candles to fill it, then short at the bearish OB inside the gap or at VB_high, with a stop above the pre-gap up-run high and the target sell-side below.
- **Sources:** cc04_009_shPGUz9pU-A ~00:07:24, ~00:10:12, ~00:14:37.
- **Quote:** "the bullish order block would begin at the higher of the two down candles prior to the gap up"
- **Conflicts:** none.
- **Rulebook fix:** L8: add the two entries and the time-of-day choice.
- **BUILD SPEC (setups_models):**
  - Builds on `vacuum_blocks` (`levels.vacuum_block`, event-anchored, built). `vb_entry`:
    - "partial" = a limit at the top of the highest down candle of the pre-gap run, with a `vb_react_bars` timeout exit.
    - "full" = a limit at the VB low.
    - "auto" = full before 10:00, partial after.
  - Stop below the run low. Precondition: the high above the gap candle is untaken.
  - Params: `vb_entry: str = ""`, `vb_react_bars: int = 3`.
  - Test: `test_vacuum_block_partial_vs_full`.

### 146. new-post-void-fill-gap-sell
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** A bearish void with top L is filled when price trades back up to L, preferably on the second touch. If two bearish candles print immediately afterwards, with the second opening below the first's close (a common gap between bodies), sell-limit inside that gap (a few pips/ticks under L). Targets: the equal lows formed before the fill, then the next sell-side pool. [our interpretation] Stop above the fill high; "immediately" = within 1-2 candles. Bullish mirror.
- **Sources:** cc04_010_HTQgH11W37o ~00:12:41.
- **Quote:** "we can put an order in here the cell with a limit order at 104.70"
- **Conflicts:** none.
- **Rulebook fix:** A10: add the post-fill body-gap sell.
- **BUILD SPEC (setups_models):**
  - Add "void_fill_gap" to `void_trades` (item 115): after a void top is touched, a VI between two same-direction bars within 2 bars arms a limit inside the VI. Stop above the fill high; the ladder = the rel-eq lows before the fill.
  - Test: `test_void_fill_body_gap_sell`.

### 147. new-sellstop-run-before-void-fill
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** With an unfilled bearish liquidity void above and short-term/equal lows below, the run of the sell stops under those lows is the buying opportunity. The void top is the target. If price fails short of the top and runs the same lows again, that second raid is a valid re-entry. [our interpretation] Entry mechanism = a turtle-soup limit at/below the lows, or M0 (MSS + FVG); stop below the raid low. Mirror for bullish voids.
- **Sources:** cc04_010_HTQgH11W37o ~00:08:07.
- **Quote:** "that run on those cell stops what was necessary for them to facilitate new logs"
- **Conflicts:** none.
- **Rulebook fix:** A10/L4: link the sell-stop raid to the void-fill draw.
- **BUILD SPEC (targets_partials + management_exits):**
  - `void_draw`: an unfilled opposing void (`levels.voids`) within reach becomes the lock-side target for longs after a sell-side sweep.
  - `void_rearm`: a second sweep of the same lows after a stop-out re-arms once.
  - Params: `void_draw: bool = False`, `void_rearm: bool = False`.
  - Test: `test_void_draw_and_second_raid`.

### 148. new-last-buyside-offered-level
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** L = the low of the last up-close candle (the last point where buy-side was delivered) before the one-sided down-close delivery begins. Once price has broken below L, the move from L down is one-sided sell-side, and the first return to L is a sell zone. Ladder sell limits at L and slightly below (ICT: 104.55 / 104.50, ~5 pips; on ES ~1 pt). Price may tag it twice. Target the sell stops below the nearest old lows. ICT gives no stop; the bot default = beyond the high of the retest swing [our interpretation]. Candle selection is discretionary (judgment). Mirror for longs.
- **Sources:** cc04_012_FgacYSN9QEo ~00:15:37.
- **Quote:** "that's where the last point at which the low had traded up to the close so buy side liquidity has been delivered"
- **Conflicts:** none.
- **Rulebook fix:** A10: add the last-buy-side-offered level as an entry.
- **BUILD SPEC (setups_models):**
  - Add "last_offer" to `entry_arrays`: L = the low of the last up-close bar before >= `offer_run` consecutive down-close bars. Limits at L and L - `offer_step_pts` (E12 split).
  - Params: add "last_offer"; `offer_run: int = 3`, `offer_step_pts: float = 1.0`.
  - Test: `test_last_offer_level_sell`.

### 149. M4-two-chance-aggressive-vs-mss-retest
- **rule_id / kind:** M4 / missing_rule. Scope: general. judgment = false.
- **Rule:** Bearish (bullish mirror): pre-draw the key level K above old high H1.
  - Chance 1 (switch, default off; ICT says it needs conviction and should be practised in demo): sell at/above H1 into K while the candle running H1 is still open, without waiting for a wick or rejection. Stop above the run extreme H2.
  - Chance 2 (default): whether or not chance 1 was taken or filled, keep the setup armed. Once price breaks below the in-between short-term low L (MSS), sell the return to L, stop just above H2. If chance 1 filled, chance 2 is an add (E12).
  - Cancel per E5 if the target trades first or the order expires.
  - A strong move away from H2 raises confidence that H2 will not be revisited, but ICT does not make it a hard filter. The source context is the daily timeframe; applying it intraday is our interpretation.
- **Sources:** cc05_005_xRjKtUEKkSE ~00:17:52, ~00:15:36.
- **Quote:** "it's like a two-chance setup"
- **Conflicts:** none.
- **Rulebook fix:** M4: add the two-chance sequence.
- **BUILD SPEC (setups_models):**
  - Builds on `ts_breaker_pyramid` (a turtle-soup fill plus an add at the breaker) and `cc_swings="breaker"` (the retest of the breaking point). New: `two_chance` keeps the `cc_swings` breaking-point order alive whether or not the turtle order filled; it is an add if the turtle filled, else a new order.
  - Params: `two_chance: bool = False`.
  - Test: `test_two_chance_retest_after_missed_soup`.

### 150. M4-retest-nearer-ob-or-none
- **rule_id / kind:** M4 / missing_rule. Scope: general. judgment = true.
- **Rule:** After the MSS, place limits at the nearest OB formed in the break leg (the last opposite-colour candle before the leg's continuation) and at the breaking point L. Fill whichever is reached first, and cancel the other. If neither is reached before the target trades or before pending-order expiry, cancel. Never enter at market.
- **Sources:** cc05_005_xRjKtUEKkSE ~00:16:56.
- **Quote:** "you may never get that return"
- **Conflicts:** none.
- **Rulebook fix:** M4: add the nearer-OB alternative.
- **BUILD SPEC (setups_models):**
  - In `cc_breaker_order`, `cc_near_ob`: also place an OCO limit at the last opposite-close bar of the break leg; the first fill cancels the other.
  - Params: `cc_near_ob: bool = False`.
  - Test: `test_cc_breaker_oco_near_ob`.

### 151. M4-only-two-reversal-entry-locations
- **rule_id / kind:** M4 / missing_rule. Scope: general. judgment = false.
- **Rule:** Conceptual frame [CC]: a reversal is entered only (a) at/beyond the old high/low at a pre-drawn HTF key level (breaker swing / turtle soup, the preferred, deepest-discount / highest-premium entry), or (b) on the retracement back to the structure break. Option (b) covers both the breaker swing and the failure swing; the PD array at that retrace, e.g. an FVG/OB, is the entry. Prefer the breaker swing; use the failure-swing retest when no new extreme came. Classical chart patterns (H&S, flags) and candlestick patterns are never entry reasons.
- **Sources:** cc05_005_xRjKtUEKkSE ~00:31:28.
- **Quote:** "you're going to be selling it at ohi or you're going to be selling it on a retracement back to a break in market structure that's it"
- **Conflicts:** none.
- **Rulebook fix:** M4: add the two-locations frame and the exclusion of pattern-based entries.
- **BUILD SPEC:** none; text only (the bot already enters reversals only at a raided extreme or on the post-MSS retrace, and has no pattern-based entries).

### 152. M4-gray-area-no-entry
- **rule_id / kind:** M4 / missing_rule. Scope: general. judgment = false.
- **Rule:** Bearish: after H1 and the pullback to L, while L is unbroken and H1 is not exceeded, place no new reversal entry (except the optional at-level limit at K above H1). Arm the retest entry only when L breaks, whether or not H2 > H1 formed. Bullish mirror.
- **Sources:** cc05_005_xRjKtUEKkSE ~00:23:38.
- **Quote:** "this is a gray area we don't know for certain if this is going to stop here or if it's going to continue up"
- **Conflicts:** none.
- **Rulebook fix:** M4: add the no-entry gray area.
- **BUILD SPEC:** none; already in rule_coverage with the same content (M4.5 `cc_swings` arms only on the break of the in-between swing, and no other branch enters between the first reaction and that break). Rulebook text only.

### 153. A15-mitigation-block-sell-entry
- **rule_id / kind:** A15 / unlisted_contradiction. Scope: general. judgment = true.
- **Rule:** Bearish [CC]: old high H (HTF resistance), swing low S, lower high B < H (failure swing), then a break below S. When price retraces back up to S (zone = the last down-close candle in the S swing low), sell there. It is the first array above EQ to check: mitigation block, then bearish breaker, then void/FVG, then bearish OB. Target the liquidity below the recent low / the second impulse swing, then the old support; expect another retrace and a resell before support is reached. Stop above B [our interpretation]. Bullish mirror. Add a D-decision: A15 target-only (075 ~21:40) vs cc05_014 entry use (and E1's CC stop-order use).
- **Sources:** cc05_014_pwO-E-OOH5k ~00:07:47.
- **Quote:** "this would be another selling opportunity"
- **Conflicts:** A15 (075 ~21:40): weaker than a breaker, used as a target, bot tag-only; cc05_014 uses it as a sell entry.
- **Rulebook fix:** A15 + Section 3 decision.
- **BUILD SPEC (setups_models):** covered by item 98 (`entry_arrays` "mitigation"); add `entry_arrays_order` so that "mitigation" is checked before "breaker" when both exist (cc05_014 order). Params: `entry_arrays_order: tuple = ()`. Test: `test_mitigation_before_breaker_order`.

### 154. new-rate-differential-htf-checklist
- **rule_id / kind:** new / missing_rule. Scope: fx_only. judgment = false.
- **Rule:** Long (buy the strong-yield currency): 1) pair selected by rate differential; 2) price trades into strong HTF support (old low or a daily/weekly bullish PD array); 3) a smart-money clue that it is being bought; 4) at least one of: seasonal bullish for the period, or a sharp drop in futures OI into the support; 5) DXY direction favours the trade (H/USD pairs: DXY weak, or a DXY higher high while the pair fails to make a lower low). All are required. Short mirror: weak-yield currency into HTF resistance, with the sold clue, seasonal/OI confirmation and DXY confirmation.
- **Sources:** cc05_008_w6VlX-rsTUs ~00:06:40.
- **Quote:** "us dollar index directional confirmation that qualifies the setup"
- **Conflicts:** none.
- **Rulebook fix:** M17 out-of-scope list: add the rate-differential checklist [fx-only].
- **BUILD SPEC:** none (fx_only).

### 155. M17-daily-stop-entry-at-open-with-roll
- **rule_id / kind:** M17 / missing_rule. Scope: general. judgment = false.
- **Rule:** Long [CC, swing/position, parked under M17]:
  1. A monthly and/or weekly (preferably both) PD array above price is the draw.
  2. Wait for a daily candle that CLOSES down; ignore it while forming.
  3. After the close, place a BUY STOP at that candle's OPEN.
  4. If not filled, each new down-close daily candle moves the stop to its open; repeat until the HTF array is reached.

  Prefer setups at or below EQ of the monthly/weekly range; the signals weaken near HTF premium. After partials, the same size may be re-added on a return to the entry open. The stop is deferred to trade management. Short mirror (up-close candle, sell stop at its open, HTF draw below).
- **Sources:** cc05_016_vb_Yc-gCBfU ~00:00:36, ~00:03:05.
- **Quote:** "if it doesn't trade back above the opening price you don't get a fill you just got to wait for another new down candle"
- **Conflicts:** E1 (cc10_011 ~15:32) index buy stop above a down-close candle's HIGH vs this daily model's stop at the candle's OPEN.
- **Rulebook fix:** M17: write out the daily stop-entry model.
- **BUILD SPEC (bias_htf, research study):**
  - `study.daily_candle_entries(days, mode="stop_open")`: on daily bars with the `htf.table` weekly/monthly draw up, buy stop at the open of the latest down-close day, rolled daily until filled or the draw is hit. Exit at the draw. Report R. Shared with item 156.
  - Test: `test_daily_stop_open_roll`.

### 156. M17-daily-limit-at-close
- **rule_id / kind:** M17 / missing_rule. Scope: general. judgment = false.
- **Rule:** Long [CC, swing/position, parked under M17]: (1) a monthly/weekly PD array above price is the draw, preferably after a daily structure break higher is already underway. (2) A daily candle CLOSES down (ignore it while forming). (3) After the close, place a buy limit at that candle's close. (4) It fills when a later bar trades below the close (E3: at least 1 tick through). Short mirror: up-close daily candle, sell limit at its close, HTF draw below. The stop is deferred to the trade-management lesson. The order lifetime is unstated [our interpretation: replace it with each new qualifying candle's close].
- **Sources:** cc05_017_WDattjFvNBc ~00:00:41.
- **Quote:** "the buy limit is going to be placed at the bearish candles close"
- **Conflicts:** none.
- **Rulebook fix:** M17: add the limit-at-close companion.
- **BUILD SPEC (bias_htf, research study):** `study.daily_candle_entries(mode="limit_close")` (item 155). Test: `test_daily_limit_close`.

### 157. M17-daily-candle-entry-needs-daily-pd-array
- **rule_id / kind:** M17 / missing_condition. Scope: general. judgment = true.
- **Rule:** Arm a daily-candle entry (limit at the close of the opposite-coloured candle, or stop at its open) only when (a) the monthly/weekly PD array draws price in the trade direction and (b) the daily move against it trades into a daily PD array. For shorts that is a bearish OB, a gap/FVG traded into, a filled liquidity void, a run above a recent daily high, or an old daily low retested as resistance. Longs mirror. Once the HTF move is underway, follow-on down-close (up-close) candles in the trend toward the HTF array are also valid. A bare candle with no PD-array or HTF context is not a setup.
- **Sources:** cc05_017_WDattjFvNBc ~00:04:48.
- **Quote:** "we're not just indiscriminately going out and finding up candles and dam candles"
- **Conflicts:** none.
- **Rulebook fix:** M17: add the PD-array condition.
- **BUILD SPEC (bias_htf, research study):** `daily_candle_entries(need_array=True)`: the first entry needs the daily bar to touch an `htf._arrays` daily row of the trade side; later entries in the trend do not. Test: `test_daily_entry_needs_array`.

### 158. M17-daily-limit-after-mss
- **rule_id / kind:** M17 / missing_condition. Scope: general. judgment = true.
- **Rule:** Preferred precondition for daily buy-limit entries (at a down-close candle's close): the market has already shown a market structure break higher on the daily and is underway toward the monthly/weekly premium draw. These are continuation entries in the middle of the move, not turning-point picks. Shorts mirror. The source states a preference, not a hard filter; the exact MSS definition is our interpretation.
- **Sources:** cc05_017_WDattjFvNBc ~00:01:25.
- **Quote:** "when the market's already shown the willingness to have a market structure break"
- **Conflicts:** none.
- **Rulebook fix:** M17: add the preference.
- **BUILD SPEC (bias_htf, research study):** `daily_candle_entries(need_mss=True)`: require a daily close above the last daily swing high (`htf` daily pivots) since the HTF array touch. Test: `test_daily_limit_after_mss`.

### 159. E1-stop-vs-limit-ob-tradeoff
- **rule_id / kind:** E1 / missing_condition. Scope: general. judgment = true.
- **Rule:** Position trades (daily execution framed by a daily PD array): either a stop or a limit entry is acceptable, as a matter of preference. A limit demands a specific price and may miss the move or the fill; a stop fills more often but leaves a larger gap between entry and stop loss. Size from the resulting stop distance, with risk no more than 1%. This conflicts with the per-array preference in E1 (cc06_008: limits on OBs, rejection blocks and old highs/lows; stops on breakers, mitigation blocks, FVGs and voids), which is the swing-trading guidance.
- **Sources:** cc05_018_okN5p701T7Y ~00:04:48.
- **Quote:** "buy stop generally you're going to end up getting filled more"
- **Conflicts:** E1 (cc06_008 ~14:20) per-array order types.
- **Rulebook fix:** E1: add the position-trade trade-off.
- **BUILD SPEC (bias_htf, research study):** `daily_candle_entries` reports both order types side by side (fill rate, R). Test: covered by item 155's test.

### 160. M17-position-trade-checklist
- **rule_id / kind:** M17 / missing_rule. Scope: general. judgment = false.
- **Rule:** Position trade, bullish (bearish mirror):
  1. A bullish seasonal tendency for the next 3-4 months (a road map only, B23).
  2. Intermarket confirmation from at least 3 of 4 asset classes (stocks, rates, commodities, currencies).
  3. Interest-rate yields confirm (rising yields support the currency; divergence warns of a pause).
  4. Monthly and weekly PD arrays define where institutional order flow will seek to trade; arrays on the path are mapped as speed bumps or rocket fuel.
  5. On the daily, expect a quarterly shift / intermediate swing and aim for the meat, not the extreme.
  6. Daily PD arrays (OB, void, gap, rejection block, old high/low) frame the entry.
  7. Choose a stop or limit entry, risk no more than 1%.
  8. Trail the stop below the lowest low of the last 40 trading days, tightening to the 20-day low once price covers 50% of the expected HTF range.

  A seasonal without technical alignment is not traded.
- **Sources:** cc05_018_okN5p701T7Y ~00:02:49.
- **Quote:** "once this occurs we go into a higher time frame monthly and weekly chart for PDA"
- **Conflicts:** none.
- **Rulebook fix:** M17: add the ordered checklist.
- **BUILD SPEC (bias_htf, research study):** `study.position_checklist(day)` returns which steps hold using the data we have (seasonal from history, `INTERMARKET` daily DXY/TNX, `htf.table` M/W/D arrays, the 40/20-day trail). Report only. Test: `test_position_checklist_smoke`.

### 161. B10-swing-entry-location-mwd-discount
- **rule_id / kind:** B10 / missing_rule. Scope: general. judgment = true.
- **Rule:** Swing long: in a monthly/weekly uptrend, wait for a retracement to a discount level that reaches a monthly, weekly or daily discount array from the top-down map, transposed to the 4H. Monthly and weekly arrays offer the best odds of an explosive rally. Use the dealing range (the discount half) and nearby sell stops below recent lows as context [the threshold and the sweep requirement are our interpretation]. FX/metals only: confirm with DXY weakness or DXY SMT divergence while price trades at the discount array. The order type is per array (E1, cc06_008). Short mirror at premium arrays with DXY strength. In the cc06_001 examples such retracements recurred about every 3 months (3-4).
- **Sources:** cc06_001_0juYnbKays0 ~00:17:36; cc06_008_VL4YLTRerHY ~00:13:43.
- **Quote:** "the best odds are seen with these levels offering an explosive rally"
- **Conflicts:** none.
- **Rulebook fix:** B10: add the location priority and the discount requirement.
- **BUILD SPEC (bias_htf, research study):** `study.swing_entries(tf="4h")`: 4h bars, entries only when price is inside an `htf.table` monthly/weekly/daily discount array and below the daily dealing-range EQ. Rank by array TF. Test: `test_swing_entry_location`.

### 162. M12-no-turtle-soup-inside-consolidation-swing
- **rule_id / kind:** M12 / missing_condition. Scope: general. judgment = false.
- **Rule:** Swing mode: do not take range-bound trades, such as turtle soups that only keep price inside a monthly/weekly consolidation. Take only strong directional setups in markets that are trending or breaking out of consolidation. A turtle soup at a discount array in the direction of the HTF trend is still a valid swing entry.
- **Sources:** cc06_001_0juYnbKays0 ~00:19:14.
- **Quote:** "we're not looking for turtle soups to stay inside of a consolidation"
- **Conflicts:** the intraday CC lessons (cc09_003, cc09_004) do fade consolidation edges; this exclusion applies to swings only.
- **Rulebook fix:** M12/M17: add the swing-only exclusion.
- **BUILD SPEC (bias_htf, research study):** in `study.swing_entries`, skip turtle-soup entries when the weekly `drange` (bias_htf B17 column) is 0. Test: `test_swing_no_range_turtle`.

### 163. new-clarity-filter-pass-if-arguing
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** Require a clearly defined entry PD array on the support side, and a clearly defined opposing array or old high/low as the target, each detected by exactly one primary classification. If the entry level qualifies only marginally (at threshold edges), or the path to the target is dominated by overlapping candles (high resistance), skip [our interpretation].
- **Sources:** cc06_002_Xs1i0aIeTME ~00:09:20.
- **Quote:** "if you're having to convince yourself chances are it's probably not a good trait pass on it"
- **Conflicts:** none.
- **Rulebook fix:** add a general clarity rule next to B18's obviousness rule.
- **BUILD SPEC (setups_models):**
  - `clarity`: drop orders whose entry gap is within 10% of a size threshold (`min_gap`, `disp_mult`), or whose path from entry to T1 has an overlap ratio (sum of bar ranges / path length) above `clarity_overlap`. Tag when `clarity="tag"`.
  - Params: `clarity: str = "off"`, `clarity_overlap: float = 4.0`.
  - Test: `test_clarity_filter_marginal_gap`.

### 164. M17-swing-sequence-condition-impulse-retrace
- **rule_id / kind:** M17 / missing_rule. Scope: general. judgment = true.
- **Rule:** Swing long:
  1. Condition: HTF bullish (B10 plus macro/intermarket agreement).
  2. Impulse: the market rallies with displacement away from a point of origin; no entry during the impulse.
  3. Stage: note the premium arrays where the rally may top, and wait for the retracement without trying to time it.
  4. Enter during the retracement at discount arrays (transposed M/W/D/4H) within the impulse leg.
  5. Profit from the expansion toward HTF premium arrays.

  Short mirror.
- **Sources:** cc06_003_g--tikwaupk ~00:14:18.
- **Quote:** "there is a condition first then there's the stage portion of taking the trade and then there's the execution"
- **Conflicts:** none.
- **Rulebook fix:** M17: add the swing order of operations.
- **BUILD SPEC (bias_htf, research study):** `study.swing_entries` gains a state machine (condition -> impulse leg detected by `disp_mult` on 4h -> entries only in the retrace into that leg's discount). Test: `test_swing_sequence_states`.

### 165. new-4h-bounce-must-make-higher-high
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = false.
- **Rule:** Swing long off a 4h bullish OB (inside a bullish MWD sequential). If the bounce breaks the prior 4h swing high, buying is confirmed, and the next buy level is the last down-close 4h candle before the broken high, ideally also a daily OB. If the bounce fails to make a higher high, treat the 4h level as weak and wait for price to reach the next daily bullish OB (its high/open) below. A 4h OB that gets traded through does not cancel the idea while the daily OB holds. Bearish mirror.
- **Sources:** cc06_004_osRUnIpGIJ0 ~00:21:34.
- **Quote:** "it rallies does it create a new high no actually fails so now we have to wait"
- **Conflicts:** none.
- **Rulebook fix:** B10: add the 4h confirmation/failure rule.
- **BUILD SPEC (bias_htf, research study):** in `study.swing_entries`, after a 4h OB fill, if no higher 4h swing high forms within N bars, the next entry must be at a daily OB. Test: `test_4h_bounce_fail_waits_daily`.

### 166. B10-swing-requires-sequential
- **rule_id / kind:** B10 / missing_condition. Scope: general. judgment = false.
- **Rule:** Swing long only when the monthly-weekly-daily sequential is bullish (B10 cases): price is reacting from discount arrays, down-close OBs hold and up-close OBs get run through, and no bearish breaker has formed on the governing timeframe. Otherwise a touch of an OB, or a run below an old low, is not a swing entry. Short mirror.
- **Sources:** cc06_004_osRUnIpGIJ0 ~00:38:37.
- **Quote:** "you can't just go in here and take an order block or buy a old low once it's been traded below it and assumed it's going to be a swing trade"
- **Conflicts:** none.
- **Rulebook fix:** B10: state that the sequential is mandatory for swings.
- **BUILD SPEC (bias_htf, research study):** `study.swing_entries(need_mwd=True)` uses the B10 `mwd` cases (rule_coverage) as a hard gate. Test: `test_swing_needs_mwd`.

### 167. M17-swing-framework-mw-map-4h-execution
- **rule_id / kind:** M17 / missing_rule. Scope: general. judgment = false.
- **Rule:** Swing short:
  - Mark monthly bearish arrays over ~18 months of monthly data and weekly bearish arrays (OB low/open/MT, voids, FVGs, OTE, old highs, rejection blocks); add daily arrays; carry all of them to the 4h.
  - Short only when price trades into a monthly/weekly premium array that fits the MWD sequential (B10) and sits above EQ of the swing range.
  - Enter with a 4h pattern: a limit at the 4h OB open/MT, or the position-trade stop entries. Stop 1 pip/tick beyond the 4h setup candle's extreme.
  - Target the first opposing monthly/weekly discount array. Minimum reward:risk 3:1 (often 5-10:1).
  - No execution charts below the 4h. Setups often complete near the daily close, so orders can be framed the day or night before.
  - Long mirror.
- **Sources:** cc06_005_soY9zX3gt2U ~00:11:01; cc06_006_JAjL7rUX2Iw ~00:00:58.
- **Quote:** "our executable time frame is the four hour"
- **Conflicts:** none.
- **Rulebook fix:** M17: write out the swing framework.
- **BUILD SPEC (bias_htf, research study):** `study.swing_entries` defaults: 4h execution, `htf._arrays` on M/W/D with an 18-month lookback, 4h OB limit, stop beyond the 4h candle extreme, target = the first opposing M/W array, `min_rr_final=3` (item 126). Test: `test_swing_framework_defaults`.

### 168. A21-swing-short-premium-of-major-range
- **rule_id / kind:** A21 / missing_condition. Scope: general. judgment = false.
- **Rule:** 4h swing short: dealing range = the highest swing high before the current decline down to the lowest low since; short only above its 50%. Long mirror: major swing low to the subsequent high, buy only below 50%.
- **Sources:** cc06_005_soY9zX3gt2U ~00:11:36.
- **Quote:** "we are in a premium area here above equilibrium so we are in a selling side of the marketplace"
- **Conflicts:** none.
- **Rulebook fix:** A21: name the dealing range for 4h swing entries.
- **BUILD SPEC (bias_htf, research study):** the `study.swing_entries` premium/discount gate uses this range. Test: `test_swing_dealing_range_eq`.

### 169. new-htf-ob-mt-entry-4h-ob-confirm
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** Short: monthly bearish OB = the last up-close monthly candle before the down move; MT = 50%. When price returns to the MT, watch the 4h: a 4h up-close candle runs above the MT and the next 4h candle(s) turn down (a 4h bearish OB). Sell limit at that 4h OB candle's open (at/near the monthly MT). Stop = the 4h candle high + 1 pip/tick (70 pips in the example). Target = the first monthly discount array (585 pips, ~8R). Require >= 3R. Long mirror.
- **Sources:** cc06_006_JAjL7rUX2Iw ~00:23:25.
- **Quote:** "we're using the mean threshold on the monthly candle and it's also the opening of that bullish candle that makes the high"
- **Conflicts:** none.
- **Rulebook fix:** M17/A12: add the monthly-MT + 4h-OB entry.
- **BUILD SPEC (bias_htf, research study):** a `study.swing_entries` entry type "mt_4h_ob": the monthly OB MT from `htf._arrays` "M", confirmed by a 4h up-close bar through the MT followed by a down bar. Test: `test_monthly_mt_4h_ob_entry`.

### 170. new-eight-hallmark-swing-checklist
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** Hallmarks of an explosive swing (cc06_007), checked per candidate market and direction:
  1. Trending profile: at least two of the four asset classes trending, one of stocks/commodities and one of currencies/interest rates.
  2. Intermarket confluence supports the direction.
  3. COT commercial hedging aligns.
  4. OI change confirms (e.g. OI falling while commercials cut shorts = bullish).
  5. Seasonal tendency aligns.
  6. Volatility contraction (an inside bar / the smallest range of recent candles) = imminent expansion, no direction.
  7. News headlines against the trade = fuel.
  8. Williams %R (15-period) retail sentiment.

  More aligned hallmarks = a higher probability of an explosive move. ICT states no ordering, gating or minimum count; treat any threshold as our interpretation.
- **Sources:** cc06_007_Hoo_wTMgdcY ~00:20:56.
- **Quote:** "we now have five things in our favor suggesting there's going to be an explosive price action"
- **Conflicts:** none.
- **Rulebook fix:** B20/M17: add the hallmark list.
- **BUILD SPEC (bias_htf, research study):** `study.hallmarks(day)` scores what the data allows (trend of ES/TNX/DXY from `INTERMARKET`, seasonal from history, daily volatility contraction, %R on daily bars); COT/OI/headlines are marked missing. Report only. Test: `test_hallmarks_smoke`.

### 171. M17-osok-short-term-trade-definition
- **rule_id / kind:** M17 / missing_rule. Scope: general. judgment = false.
- **Rule:** Short-term (One Shot One Kill) trade: held from a few days up to one week. Setups are framed on the monthly and weekly charts. Trade in the direction of the current or next week's probable range; the weekly range is the backbone. Trending and range-bound weeks both qualify. Take only clear, obvious setups; otherwise sit out (they form every week).
- **Sources:** cc07_001_mQA8jCem9d0 ~00:01:14.
- **Quote:** "it's the practice of trading a duration of one week or a few days"
- **Conflicts:** none.
- **Rulebook fix:** M17: define OSOK.
- **BUILD SPEC (bias_htf, research study):** `study.osok(weeks)` framework (see items 172-174): weekly holding, flat by the Friday close [our interpretation], monthly/weekly framing. Test: `test_osok_smoke`.

### 172. M17-osok-execution-chain-1h-minimum
- **rule_id / kind:** M17 / missing_rule. Scope: general. judgment = false.
- **Rule:** Bearish monthly frame: scan the weekly, daily and 4h for premium arrays above price (levels plotted on the 4h). When price trades into one, refine on the 1h (a 1h array inside the HTF array; breakers/mitigation blocks are not visible on the 4h; a second entry if the 4h array was missed) and sell. Target the weekly discount array. No entries below 1h (below 60m = day trading/scalping). 1h arrays alone may be executed inside a kill zone, Mon-Wed (cc07_001 ~31:20). Bullish mirror.
- **Sources:** cc07_001_mQA8jCem9d0 ~00:16:17; cc07_006_O69iFqP1j7o ~00:20:04.
- **Quote:** "our one hour chart is our executable time frame for one shot one kills"
- **Conflicts:** none.
- **Rulebook fix:** M17: add the OSOK execution chain.
- **BUILD SPEC (bias_htf, research study):** `study.osok` executes on 1h bars (`htf_bars(df, 60)`), entries at 1h arrays inside W/D/4h arrays, Mon-Wed entries only. Test: `test_osok_1h_execution`.

### 173. new-missed-monthly-array-use-lower-tf
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = false.
- **Rule:** If price has left the monthly origin array: keep the monthly direction, wait for a retrace into a weekly, daily or 4h array of the origin type (premium for shorts), execute on 1h, and target the weekly opposing array.
- **Sources:** cc07_001_mQA8jCem9d0 ~00:17:35.
- **Quote:** "it's already moved away from it you can't really use that to trade off of you just know that it's moving lower"
- **Conflicts:** none.
- **Rulebook fix:** M17: add the missed-monthly fallback.
- **BUILD SPEC (bias_htf, research study):** in `study.osok`, the monthly array sets the direction only; entries use W/D/4h arrays. Test: covered by `test_osok_1h_execution`.

### 174. M17-osok-weekly-to-daily
- **rule_id / kind:** M17 / missing_rule. Scope: general. judgment = false.
- **Rule:** OSOK short: origin = a weekly premium array; objective = an opposing daily discount array (the source does not say "nearest"). List every premium PD array on the weekly, daily and 4h. Wait for price to trade up into one, then sell on the 1h execution chart and aim for the daily discount array. Long is the mirror: weekly discount origin, daily premium objective. ICT expects a tradeable instance most weeks, and applies it to all asset classes.
- **Sources:** cc07_001_mQA8jCem9d0 ~00:22:41.
- **Quote:** "this my friends is the one shot one kill setup"
- **Conflicts:** none.
- **Rulebook fix:** M17: write out the OSOK setup.
- **BUILD SPEC (bias_htf, research study):** `study.osok` target = the nearest untouched daily opposing array (the "nearest" pick is ours). Test: `test_osok_weekly_to_daily_target`.

### 175. new-wednesday-news-weekly-reversal
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** Bullish: an old weekly/monthly low or retail support exists. A high/medium-impact release (Wednesday) drives price below it into a monthly/weekly/daily discount array, then the market discounts the news and reverses. To locate the low, take the swing from the old-low rally to Tuesday's high and project its 1.27/1.68 extension downward. Target = a 1.27/1.68 extension from the swing projection fulcrum that overlaps a weekly/daily premium array. Bearish mirror: an old high/resistance run on news into a M/W/D premium array, then a 1.27/1.68 extension down into a weekly/daily discount array. Entry trigger not stated [our interpretation: buy once price reclaims the old low].
- **Sources:** cc07_003_hbE8S5FSdtQ ~00:36:11.
- **Quote:** "once it dries down below that the Market discounts that news and reverses"
- **Conflicts:** none.
- **Rulebook fix:** M17: add the Wednesday news reversal template.
- **BUILD SPEC (day_week_context, weekly study):** `study.wed_news_reversal(weeks)`: Wednesdays with a calendar.py release that run an old weekly/monthly low into an `htf.table` discount array, then reclaim it; measure the 1.27/1.68 projections against the realised week extremes. Report only. Test: `test_wed_news_reversal_study_smoke`.

### 176. new-array-count-not-quality-filter
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = false.
- **Rule:** PD arrays are used only where they exist. When a type is absent (no breaker, no void, etc.), setup validity is unchanged; there are simply fewer entry and target candidates. Do not score or filter setups by how many array types are present. (Nearest-first and skip-exhausted are already in A22.)
- **Sources:** cc07_004_YV4fEF4d2wA ~00:06:04.
- **Quote:** "if there's an absence of any one of them it doesn't negate or increase or lessen the validity"
- **Conflicts:** none.
- **Rulebook fix:** A22: add the no-count-scoring note.
- **BUILD SPEC:** none; text only (the bot scores nothing by array count; A22's nearest-first is already in rule_coverage).

### 177. new-after-of-shift-sell-any-premium-array
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** After a weekly bias flip (e.g. Tuesday fails to make a new high and breaks down), look for shorts in the premium range. Sell a retrace into a premium PD array (a 4h mitigation block, breaker, OB, institutional/round level) above current price, even though it is below the week's high. Target a discount array (e.g. a liquidity void) on a timeframe lower than the premium array (4h/1h). Order type and stop not stated [our interpretation: stop above the array]. Bullish mirror.
- **Sources:** cc07_004_YV4fEF4d2wA ~00:12:50.
- **Quote:** "while we're not necessarily needing the actual high of the week we can still take participation in the market move"
- **Conflicts:** none.
- **Rulebook fix:** B8/M17: add post-flip participation entries.
- **BUILD SPEC (bias_htf):** with `weekly_flip_follow`, once the `htf.table` `flip` column (B8) turns -1 mid-week, intraday shorts may use 4h premium arrays below the week high as the sweep "array" (item 10 path with `premise_tfs` containing 240). Params: `weekly_flip_follow: bool = False`. Test: `test_post_flip_4h_array_short`.

### 178. A21-longs-above-eq-subrange-discount
- **rule_id / kind:** A21 / unlisted_contradiction. Scope: general. judgment = true.
- **Rule:** A long above the overall consolidation EQ (daily range, drawn on bodies) is allowed only if price is in the discount half of its current sub-range (quadrant/eighth), at a bullish PD array (e.g. a daily bullish OB MT), with a higher premium array remaining as a target. Take first profit at a 4h/1h premium array. Probability: the overall discount range is best. Near the top of the overall range, buy setups fall off sharply (skip or minimum size). Short mirror.
- **Sources:** cc07_005_y0lVKWLsZeM ~00:11:58.
- **Quote:** "even though we're above it and technically in a overall premium Market we can still take Longs"
- **Conflicts:** A21: buy below EQ, sell above, no exception.
- **Rulebook fix:** A21 + Decision 12: add the sub-range exception.
- **BUILD SPEC (bias_htf):**
  - `htf.table` column `range_q` = the quadrant (1-4) of the prior close in the 60-day body range.
  - `pd_subrange`: when the existing daily premium/discount gate would block a long in quadrants 3-4, allow it if the entry is in the lower half of that quadrant at a daily array. Block quadrant 4's upper half (`pd_top_skip`).
  - Params: `pd_subrange: bool = False`, `pd_top_skip: bool = True`.
  - Test: `test_long_above_eq_in_subrange_discount`.

### 179. B6-intraweek-reversal-1h-confirmation
- **rule_id / kind:** B6 / missing_rule. Scope: general. judgment = true.
- **Rule:** Intraweek reversal confirmation (1h): after the candidate reversal low at a HTF array (Tue/Wed), require a break of the latest short-term swing high. Then mark each new bullish OB (a down candle or a series of down candles) and extend it forward. Each retrace into one that holds, with price quickly surging away, is institutional sponsorship; each can be bought, with a premium array (e.g. an FVG) as the target. [Our interpretation: "holds" = no body close below the OB MT, and a failed OB weakens the reversal idea.] Bearish mirror.
- **Sources:** cc07_007_jvc105qaCJs ~00:17:24.
- **Quote:** "we start seeing evidences of institutional sponsorship on every bullish order block"
- **Conflicts:** none.
- **Rulebook fix:** B6: add the 1h sponsorship check.
- **BUILD SPEC (bias_htf):** `htf.table` 1h column `h1_sponsor`: +1 after a 1h short-term high breaks following a weekly-low candidate at an HTF array, kept while every later 1h bullish OB holds on a body-close basis at its MT. Used as a bias source for Wed-Fri (`bias_src="h1_sponsor"`). Test: `test_h1_sponsorship_column`.

### 180. M17-weekly-judas-po3
- **rule_id / kind:** M17 / missing_rule. Scope: general. judgment = false.
- **Rule:** Bearish week (HTF bias plus intermarket aligned): an early-week rally above the weekly open (often after a Sunday gap up) into a weekly premium array is the weekly Judas / weekly PO3 manipulation. Expect the week high Mon-Wed. Scale in (small size Monday, more if Tue/Wed make a higher high), then expect distribution down to the opposing discount array (here a 4h liquidity void in the weekly range's discount half). Bullish mirror.
- **Sources:** cc07_008_LBlK6JB0QS0 ~00:31:31.
- **Quote:** "engineered price higher built in a premium so they can sell it"
- **Conflicts:** none.
- **Rulebook fix:** T13: add the weekly PO3.
- **BUILD SPEC (day_week_context):** `weekly_po3`: with the weekly bias -1, intraday shorts Mon-Wed are allowed only when price is above the weekly open (the Sunday 18:00 open), and longs are blocked; tag `weekly_judas` when the week high so far is inside a weekly premium array. Params: `weekly_po3: bool = False`. Test: `test_weekly_po3_gate`.

### 181. new-bullish-week-daily-routine-london-ny
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** Bullish weekly bias: price trading above the Sunday/weekly open, a daily discount array met, no opposing daily array hit.
  - London: wait for the open, then a decline; buy the low at a discount PD array on the hourly or lower chart. If London does not open-and-decline and instead rallies: no trade, no chase.
  - NY: R = London low to the high formed before 08:20 (08:30). After the 08:20 CME open, buy a retracement into R and target expansion above it [our interpretation: at a PD array in R's lower half].
  - If London was skipped, a later NY decline into discount can still be bought.
  - Bearish mirror.
- **Sources:** cc08_001_-cXnnHjy9s0 ~00:42:40, ~00:44:50.
- **Quote:** "in New York we're looking for retracement into the range that was created from London's low to the high formed prior to 8 20 8 30 a.m"
- **Conflicts:** none.
- **Rulebook fix:** B13: add the daily routine.
- **BUILD SPEC (setups_models):**
  - NY part only: `ny_london_range`. With the weekly bias +1, AM longs require the entry inside R = [London low (02:00-05:00), the high from the London low to 08:20], below its EQ.
  - The London part uses the existing London SB session.
  - Params: `ny_london_range: bool = False`.
  - Test: `test_ny_retrace_into_london_range`.

### 182. M17-normal-protraction-profile
- **rule_id / kind:** M17 / missing_rule. Scope: fx_only. judgment = true.
- **Rule:** FX only. Sell (buy mirror): bearish daily bias. CBDR < 40 pips, or > 40 only if the Asian range (20:00-00:00) then holds 20-30 pips; Asian range 20-30 pips. After 00:00 NY, price must rally (a small modest dip first is allowed) and keep rising into 02:00. By 01:00-01:30 it should exceed the Asian/CBDR high. Judas extent = 1-2 CBDR standard deviations. The entry can come from 01:00-01:30 into that extreme. HOD expected 02:00-04:00. Buy: a decline from 00:00 making lower lows past 01:00-01:30; the LOD may form just before 02:00. No such move by 02:00 means it is not this profile; check the delayed profile.
- **Sources:** cc08_005_eU8WcUftUtY ~00:02:53, ~00:06:11, ~00:13:19.
- **Quote:** "if it does not start trading up into 2 o'clock in the morning New York time that is not this profile"
- **Conflicts:** T3 London kill zone 02:00-05:00 vs entries from 01:00 (T3 already notes 01:00-05:00).
- **Rulebook fix:** M17 [fx-only]: add the normal protraction profile.
- **BUILD SPEC:** none (fx_only).

### 183. M17-delayed-protraction-profile
- **rule_id / kind:** M17 / missing_rule. Scope: fx_only. judgment = false.
- **Rule:** FX only. Sell: bearish daily bias, CBDR any size, no rally from 00:00 into 02:00 (price drifts lower). Mark 02:00 on the 15m and wait for a retracement rally starting at or just after 02:00 that stays below the day's high. Short at a 15m premium PD array (bearish OB, FVG, liquidity void). Buy: bullish bias, CBDR any size, a small Asian range is a plus but optional. Wait for a retracement lower at or shortly after 02:00 into an intraday discount PD array (OTE, bullish OB, FVG, liquidity void) and buy there [our interpretation: no new day low, mirroring the sell side].
- **Sources:** cc08_005_eU8WcUftUtY ~00:09:59, ~00:16:39.
- **Quote:** "draw a vertical line at 2 a.m. wait for a retracement higher"
- **Conflicts:** none.
- **Rulebook fix:** M17 [fx-only]: add the delayed protraction profile.
- **BUILD SPEC:** none (fx_only).

### 184. M17-london-open-nine-buy-setups
- **rule_id / kind:** M17 / missing_rule. Scope: fx_only. judgment = false.
- **Rule:** Prerequisites: HTF bullish; the daily has reacted from a discount PD array; a clear path to an opposing premium array; ideally Mon-Wed; CBDR < 40 pips and Asian range <= 20 pips. Long setups (short mirror), each in the London open KZ and overlapping CBDR/Asian SDs and a discount array:
  1. Asian low - 5 pips (spread).
  2. An FVG below a short-term low from the prior NY session.
  3. A bullish OB below a short-term low (prior day or intraday).
  4. When very bullish, 1 SD below CBDR/Asian plus a discount array.
  5. During the 00:00-02:00 protraction lower (Judas), at a discount array.
  6. A liquidity void fill that completes under a short-term low.
  7. A straight rally from 00:00 with no protraction, then the first retrace into a 15m/5m bullish OB in 02:00-04:00.
  8. 1-2 SD of the Asian range plus a discount array.
  9. Turtle soup: a short-term low taken twice with no prior upside protraction.

  Stops (~14:29-16:22): CBDR overlap 30 pips; run under the Asian low 40 pips; sell-stop raid 30 pips under the low; first-retrace OB 10 pips under the day low; second-run turtle soup 30 pips; other setups = the Asian low - 0.5 x ADR5.
- **Sources:** cc08_007_5Z_3NbclMSY ~00:08:44.
- **Quote:** "it has to overlap with other things Central Bank dealers range Asian range"
- **Conflicts:** none.
- **Rulebook fix:** M17 [fx-only]: list the nine setups.
- **BUILD SPEC:** none (fx_only).

### 185. new-judas-protraction-and-london-open-scalp
- **rule_id / kind:** new / missing_rule. Scope: fx_only. judgment = false.
- **Rule:** FX only.
  - Bullish day: after 00:00 NY, if price protracts lower below the midnight open (00:00-02:00) and reaches a discount PD array, buy there.
  - Bearish day: the 0 GMT / 00:00 open can see a protraction higher, which can be scalped from the open or just below it before 01:00. The direction is not stated; most likely it is a long scalp of the protraction, then a short of the Judas top.
  - Short the London Judas swing higher into a premium array. If that entry is missed, short a 5m retrace (FVG/bearish OB) and hold to 05:00.
  - In the 05:00-07:00 London-lunch retrace, short once a premium array is hit.
  - An index analog at 09:30 is our interpretation only.
- **Sources:** cc08_007_5Z_3NbclMSY ~00:09:39; cc09_007_-oMtfDvc18Y ~00:06:42.
- **Quote:** "I'm going to be looking to go long during that Judah swing"
- **Conflicts:** none.
- **Rulebook fix:** M17 [fx-only]: add the protraction entries and London scalps.
- **BUILD SPEC:** none (fx_only).

### 186. new-no-protraction-first-retrace-ob
- **rule_id / kind:** new / missing_rule. Scope: fx_only. judgment = false.
- **Rule:** FX only (London KZ). If price rallies from 00:00 NY with no protraction into discount, then in 02:00-04:00 buy the first retracement into a 15m or 5m bullish OB, with a stop 10 pips below the day's low so far. Short mirror.
- **Sources:** cc08_007_5Z_3NbclMSY ~00:10:28.
- **Quote:** "buy the first retracement into a 15 and or five minute bullish order block"
- **Conflicts:** none.
- **Rulebook fix:** M17 [fx-only].
- **BUILD SPEC:** none (fx_only).

### 187. M17-0gmt-htf-entry-model
- **rule_id / kind:** M17 / missing_rule. Scope: fx_only. judgment = true.
- **Rule:** FX only. Long: D-1's daily bar traded into a daily discount PD array (e.g. a bullish OB) and rallied away from it, with HTF order flow bullish (Mon-Wed, the quarterly shift and the seasonal add odds). On D, buy at the 0 GMT open (19:00 EST / 20:00 EDT) or with a 10-20 pip offset limit below it. Stop = entry - ADR5. Hold to the next HTF premium array, or close the same day if used as a day trade. Short: D-1 respected a daily premium array (a bearish OB or a turtle soup of an old high) and sold off; on D, sell at the 0 GMT open or with an offset limit above it; stop = entry + ADR5; target the HTF discount. No D-1 reaction = no trade.
- **Sources:** cc08_008_1MnfiqKx5Uo ~00:11:26, ~00:15:48.
- **Quote:** "and then the very next trading day you're looking at zero GMT opening price"
- **Conflicts:** none.
- **Rulebook fix:** M17 [fx-only].
- **BUILD SPEC:** none (fx_only).

### 188. M17-0gmt-open-offset-limit
- **rule_id / kind:** M17 / missing_rule. Scope: fx_only. judgment = false.
- **Rule:** FX only. Short: sell at the 0 GMT open (market), or a sell limit at the open + 10-20 pips (example +20); stop = the limit entry + ADR5. Long mirror: buy limit at the open - 10-20 pips; stop = entry - ADR5. To avoid missing a move that never pulls back, split the size: half at the 0 GMT open, half at the +/-20 limit. If the limit is not filled, that portion is missed.
- **Sources:** cc08_008_1MnfiqKx5Uo ~00:19:15.
- **Quote:** "take the sell at zero GMT or add 10 to 20 Pips above the opening price for your sell"
- **Conflicts:** none.
- **Rulebook fix:** M17 [fx-only].
- **BUILD SPEC:** none (fx_only).

### 189. M0-judas-ends-in-15m-array
- **rule_id / kind:** M0 / missing_rule. Scope: general. judgment = true.
- **Rule:** FX source (cc09_001 London buy setup): price declines under the NY midnight open and the Asian range low, ideally into a logical 15m discount array (bullish OB/FVG/old low). Price should leave that array sharply; if it hovers there, odds drop and the setup is downgraded or skipped. Shorts mirror. Index use (a Judas sweep into a 15m array under M0) is our interpretation only, as a preference, not a requirement.
- **Sources:** cc09_001__TNhWRPa6GA ~00:05:11.
- **Quote:** "ideally the decline under the Asian range low will be to a logical discount array on a 15-minute time frame"
- **Conflicts:** none.
- **Rulebook fix:** M0 step 3: note the 15m-array preference and the immediacy test.
- **BUILD SPEC (setups_models):**
  - Tag `sweep_15m_array` when the sweep extreme lies in a same-side 15m array (`sd.zones_tf(..., 15)`, `_ts_arrays` with tfs=(15,)).
  - `sweep_leave_bars`: drop the sweep if price stays within `sweep_leave_pts` of the extreme for more than N bars.
  - Params: `sweep_15m_array: str = "off"`, `sweep_leave_bars: int = 0`, `sweep_leave_pts: float = 2.0`.
  - Test: `test_sweep_15m_array_tag_and_hover`.

### 190. B20-15m-williams-r-entry
- **rule_id / kind:** B20 / missing_rule. Scope: general. judgment = true.
- **Rule:** Williams %R(10) on the 15m as a sentiment confluence (FX London setup cc09_001; index use is interpretation). For longs, %R should read at its most bearish (at or near its swing low) at the entry; shorts mirror. Do not use fixed overbought/oversold thresholds or crossings. Price is primary; %R only raises odds and never triggers an entry.
- **Sources:** cc09_001__TNhWRPa6GA ~00:05:55.
- **Quote:** "I use a 10 period Williams percent R and I plot that on my 15-minute time frame"
- **Conflicts:** none.
- **Rulebook fix:** B20: add the 15m %R confluence.
- **BUILD SPEC (bias_htf):**
  - Tag `wr15_extreme` when the 15m %R(10) at the fill bar is the lowest (longs) of its last `wr_lookback` 15m values. Report only.
  - Params: `wr15_tag: bool = False`, `wr_lookback: int = 20`.
  - Test: `test_wr15_extreme_tag`.

### 191. M12-turtle-soup-entry-depth
- **rule_id / kind:** M12 / shortened. Scope: general. judgment = true.
- **Rule:** Source context: the FX Asian-session turtle-soup scalp (cc09_003). Sell limit at the short-term high + 5 pips (preferred), or + 1-2 pips (aggressive); long mirror below the low. If the limit is not reached (E3 fill rule), the trade is missed; do not chase at market. Applying a depth to M12 index turtle soup (e.g. ~1-2 ES pts) is our interpretation.
- **Sources:** cc09_003_km0haQkTalc ~00:09:08.
- **Quote:** "if I can't get it then I miss it"
- **Conflicts:** none.
- **Rulebook fix:** M12: add the depth and the miss rule.
- **BUILD SPEC (setups_models):** `ts_cc_below_pts` (exists for cc_limit) is the depth; add a test for the 1 / 1.25 / 2 pt settings and that an unfilled limit is not converted to market. Test: `test_turtle_depth_miss`.

### 192. new-asian-range-fade-no-htf
- **rule_id / kind:** new / missing_rule. Scope: fx_only. judgment = true.
- **Rule:** FX only (JPY/AUD/NZD crosses). Mark the 5m short-term highs/lows formed late in the NY session, before the Asian session starts. From 20:00 to 00:00 NY, when price trades above a late-NY short-term high, sell with a limit 5 pips above it (1-2 aggressive; unfilled = missed). Stop 20 pips, target 20 pips fixed. Long mirror below short-term lows. No HTF array or order-flow requirement inside this consolidation window; fading against the HTF direction is acceptable and often better. Outside this window, M12's HTF requirement stands.
- **Sources:** cc09_003_km0haQkTalc ~00:04:39, ~00:10:03.
- **Quote:** "all we're looking for is that initial whip above a short-term high"
- **Conflicts:** M12 needs an HTF PD array and HTF order flow; cc09_003 fades the first Asian whip regardless.
- **Rulebook fix:** M17 [fx-only]; M12: list the window exception.
- **BUILD SPEC:** none (fx_only).

### 193. new-consolidation-outer-edge-fade
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** Bias comes from daily/4H order flow. Take a clearly definable 1H/15m range RH/RL with EQ = the midpoint. Bullish: when price trades below RL, buy (a limit just below RL, or on the reversal back inside). Bearish: mirror above RH. Never take the breakout against the HTF bias. Target EQ only; ICT says not to hold for the opposite end. The swept short-term low/high may be the Asian session low/high or the prior day's low/high (cc09_004 ~19:25). Stop unstated [our interpretation: beyond the sweep extreme]. This conflicts with N8 "Consolidation = no trade" (cc09_003); the two need reconciling.
- **Sources:** cc09_004_g7jchu4g31c ~00:12:08.
- **Quote:** "we're buying up those sell stops"
- **Conflicts:** N8 (consolidation = no trade); cc06_001 ~19:14 excludes it for swings only.
- **Rulebook fix:** N8: add the edge-fade exception; list it in Section 3.
- **BUILD SPEC (setups_models):**
  - `consol_fade`: detect a 15m/60m range (>= `consol_bars` bars of the TF, width <= `consol_width_adr` x ADR5). A sweep of its edge in the `htf.table` bias direction arms the normal entry (or `turtle_soup="2023"`), with a single target at the range EQ.
  - Params: `consol_fade: bool = False`, `consol_tf: int = 60`, `consol_width_adr: float = 0.5`.
  - Test: `test_consolidation_edge_fade_to_eq`.

### 194. new-inside-range-expansion-fade
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = false.
- **Rule:** Bearish daily/4H bias, inside a 1H/15m range: find a short-term high just above EQ (the 3-candle pivot definition is ours). When price rallies away from EQ and trades above it, sell. Target the opposite extreme of the range and the stops just outside it. Do not treat the break as an MSS. Bullish mirror: a short-term low just below EQ broken on an expansion away from EQ is a buy (~8:41, ~17:58, ~20:24).
- **Sources:** cc09_004_g7jchu4g31c ~00:15:37.
- **Quote:** "look for short-term Highs are just above equilibrium and then a rally above that"
- **Conflicts:** N8 (consolidation = no trade).
- **Rulebook fix:** N8: add the inside-range fade.
- **BUILD SPEC (setups_models):**
  - Add the mode `consol_fade="inner"` to item 193. Inside the detected range, a sweep of a pivot high within `consol_eq_band` of EQ (above it) arms a short with the target at the range low - buffer.
  - Params: `consol_eq_band: float = 0.15`.
  - Test: `test_inner_range_eq_high_fade`.

### 195. new-eight-reversal-catalogue
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = false.
- **Rule:** Setup tags share the M0 skeleton (raid of a pool -> entry at a PD array), each with its own pool and context filter:
  1. PDH raid short.
  2. PDL raid long.
  3. Intra-week high raid short.
  4. Intra-week low raid long.
  5. Intermediate-term high raid short.
  6. Intermediate-term low raid long.
  7. NY session reversal: only when the NY open trades into an HTF PD array that has not yet been met; otherwise NY continues London.
  8. London close (10:00-12:00) reversal: same HTF-array condition, plus the separate large-range-day scalp.

  (5)/(6), intermediate-term highs/lows (previous week or older), need a storyline: an HTF PD array beyond them, or a long prolonged trend. None of the eight is taken on the raid alone.
- **Sources:** cc09_005_KrGTimL3YRQ ~00:00:29.
- **Quote:** "I'm going to cover the eight reversals that I think that can be effectively traded with consistency"
- **Conflicts:** none.
- **Rulebook fix:** M12/L2: add the reversal catalogue.
- **BUILD SPEC (setups_models):**
  - Tag `reversal_type` on every swept-pool trade (pdh/pdl, week_hi/lo from `BT.run` weekly state, iterm_hi/lo = the prior weeks' swing extremes, ny_rev, lc_rev).
  - `reversal_need_htf` requires a same-side HTF array at the sweep for types 3-8 (`_htf_tag`).
  - Params: `reversal_need_htf: bool = False`.
  - Test: `test_reversal_type_tags`.

### 196. L2-pdh-pdl-fade-only-in-expansion-retrace
- **rule_id / kind:** L2 / missing_condition. Scope: general. judgment = false.
- **Rule:** Long: weekly/daily/4h IOF bullish and a larger up expansion; the current day(s) are a normal retracement; price trades below the PDL AND into a discount array (e.g. a daily bullish FVG) -> buy intraday. Short mirror: the retracement up has already filled the FVG/premium array before price trades above the PDH -> sell just above the PDH. Otherwise do not fade PDH/PDL. The intermediate-term section (~22:46) also allows fading old highs/lows in range-bound conditions, as a separate setup.
- **Sources:** cc09_005_KrGTimL3YRQ ~00:15:56.
- **Quote:** "during a normal retracement lower into a fair value Gap price finds buyers under the previous day's low"
- **Conflicts:** none.
- **Rulebook fix:** L2: add the expansion-retracement condition.
- **BUILD SPEC (setups_models):**
  - Builds on `daily_level_needs_array` / `_flow` (L2, built). New `pdl_expansion`: PDL/PDH fades also need the `htf.table` weekly bias and daily flip to agree with the fade direction, and the prior 1-3 days to be counter-moves (closes against the weekly bias).
  - Params: `pdl_expansion: bool = False`.
  - Test: `test_pdl_fade_needs_expansion_retrace`.

### 197. new-intra-week-extreme-raid
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = false.
- **Rule:** Short: the market is trending up and an HTF premium array above has not yet been reached. On Tue/Wed/Thu, price trades above the intra-week high (the highest of the week so far; relative equal highs preferred) AND into that array -> sell intraday at London or NY with a PD-array entry; expect the high of the week. Long mirror: price trades below the intra-week low (Mon-Thu; it may blend with the prior Friday/previous-week lows when the raid is Mon/Tue) into an unmet HTF discount array; expect the low of the week, or at minimum a tradable bounce. Exceeding the level alone is not a signal. ICT hedges the weekdays, so treat Tue-Thu as a preference for highs. Equal highs alone can be a target for a longer move, so the HTF array confluence is required.
- **Sources:** cc09_005_KrGTimL3YRQ ~00:04:07, ~00:06:08.
- **Quote:** "coupled with the running out of a previous intra week low"
- **Conflicts:** none.
- **Rulebook fix:** L1/M12: add the intra-week raid reversal.
- **BUILD SPEC (levels_detectors + setups_models):**
  - levels_detectors: the intra-week high/low so far (from `BT.run` weekly state, or computed from `hist` since the Sunday open) as pools `week_hi` / `week_lo`.
  - setups_models: sweeps of them need a same-side HTF array (`reversal_need_htf`, item 195); day-of-week preference via `week_raid_days`.
  - Params: `week_pools: bool = False`, `week_raid_days: tuple = (1, 2, 3)`.
  - Test: `test_intraweek_high_raid_short`.

### 198. new-overlapping-reversal-score
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** Score = the number of reversal types satisfied together (PDH/PDL raid, intra-week extreme raid, intermediate-term raid, NY reversal timing, London close timing). Prefer / size up a score >= 2; tag and report. The count and the size-up are [our interpretation]. ICT gives only the qualitative claim that an overlap is stronger, with no threshold and no size rule. Start with tag and report only.
- **Sources:** cc09_005_KrGTimL3YRQ ~00:20:57.
- **Quote:** "when you see an overlap of these types of reversal Concepts it makes it even stronger"
- **Conflicts:** none.
- **Rulebook fix:** M12: add the overlap note.
- **BUILD SPEC (setups_models):** tag `reversal_score` = the count of `reversal_type` labels (item 195) satisfied by the same sweep. Report only. Test: `test_reversal_score_count`.

### 199. new-london-close-second-swipe-reentry
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = false.
- **Rule:** After a bullish NY reversal at an HTF discount array (NY low L), if price trades below L back into the same array during 10:00-12:00, re-enter long below L. The stop "beyond the sweep wick" is [our interpretation]; ICT gives no stop. Bearish mirror: sell above the NY high.
- **Sources:** cc09_005_KrGTimL3YRQ ~00:34:08.
- **Quote:** "step right in there again and buy it below the New York uh low"
- **Conflicts:** none (the rulebook otherwise recommends no re-entry).
- **Rulebook fix:** X13: add the London-close second-swipe re-entry.
- **BUILD SPEC (management_exits + setups_models):**
  - `lc_second_swipe`: after an AM long (stopped or still open) whose sweep extreme sat in an HTF array, a second sweep of the AM low within 600-720 into the same array arms one more long via the normal path. Risk x0.5 if the first trade lost.
  - Params: `lc_second_swipe: bool = False`.
  - Test: `test_london_close_second_swipe`.

### 200. T3-london-close-counter-trend-scalp
- **rule_id / kind:** T3 / missing_rule. Scope: general. judgment = true.
- **Rule:** Bullish day (bearish mirror). Conditions: London (00:00-05:00) and NY (07:00-10:00) moved the same direction, the day range >= ADR5 (prefer >= 1.25x), and the time is 10:30-13:00 NY. On the 5m, wait for a high, a pullback, and a lower/equal rally (failure swing); sell at the last up-close 5m candle (bearish OB). Stop = HOD + buffer (FX 10 pips; index not given). Target = HOD - 0.20-0.30 x the day range, ~1R max (the "<= 20 pips" is the target cap). ICT says he no longer trades it because it often fails, and that it suits the S&P better. The index stop/target in points is unspecified.
- **Sources:** cc09_006_OVfn-gDk2dE ~00:23:58; cc09_007_-oMtfDvc18Y ~00:09:29.
- **Quote:** "you're going to Target 20 to 30 percent of the total daily range in a retracement lower"
- **Conflicts:** T3 London close 10:00-12:00 vs the setup window 10:30-13:00.
- **Rulebook fix:** T3: add the counter-trend scalp and the window conflict.
- **BUILD SPEC (setups_models):**
  - Branch `lc_scalp` (t 630-780). Conditions: the overnight and AM moves are the same direction, the day range >= `lc_adr_mult` x `adr5()`, and a 5m failure swing at the HOD.
  - Short limit at the last up-close 5m bar's open. Stop HOD + `lc_stop_pts`. Single target = HOD - `lc_retrace` x the day range.
  - Params: `lc_scalp: bool = False`, `lc_adr_mult: float = 1.0`, `lc_stop_pts: float = 2.0`, `lc_retrace: float = 0.25`.
  - Test: `test_london_close_scalp`.

### 201. M17-london-close-asia-only-reversal-profile
- **rule_id / kind:** M17 / missing_condition. Scope: general. judgment = true.
- **Rule:** Skip London close and Asia trades by default. Take a London close reversal (10:00-12:00) only when price trades into an HTF PD array not yet met at that time (the reversal-profile condition, the same as the NY session reversal). The London close retracement scalp has its own ADR5-exceeded condition (item 200). Take an Asia long only if NY ended just above an unmitigated HTF discount array without touching it [fx-only for Asia; the index analogue at midnight is our interpretation].
- **Sources:** cc09_006_OVfn-gDk2dE ~00:29:41.
- **Quote:** "if it's going to be a reversal Market profile then I'm all over London close"
- **Conflicts:** none.
- **Rulebook fix:** T3/M17: add the reversal-profile condition.
- **BUILD SPEC (setups_models):**
  - `lc_rev_need_htf`: AM-session sweeps whose extreme falls in 600-720 need a same-side, not-yet-met HTF array at the sweep (`_htf_tag`).
  - Params: `lc_rev_need_htf: bool = False`.
  - Test: `test_london_close_reversal_needs_htf`.

### 202. E5-missed-entry-5m-retrace
- **rule_id / kind:** E5 / missing_condition. Scope: general. judgment = true.
- **Rule:** Exception to E5: if the bias is intact and the ideal entry (the Judas extreme / at-below the open) was missed, a later entry is allowed as a 5m scalp. Buy a 5m retrace into a discount array (FVG/OB/liquidity void) formed by the move, inside a kill zone (NY; London lunch 05:00-07:00 only when London was quiet early, then active late), even above the opening price. Target the ADR5 high or the next 4h/60m premium array; if the ADR5 extreme is hit before 10:00, take 80% and leave a runner. Mirror for shorts. The number of re-entries is not specified.
- **Sources:** cc09_006_OVfn-gDk2dE ~00:17:03; cc09_007_-oMtfDvc18Y ~00:21:11.
- **Quote:** "we use scalps to fill in slow periods or enter trades that may have already started"
- **Conflicts:** E5: if price leaves without retracing, let it go.
- **Rulebook fix:** E5: add the 5m-retrace exception.
- **BUILD SPEC (setups_models):**
  - `missed_5m`: when the session's sweep/MSS fired but no order filled and price left (> `missed_leave_pts`), allow one more order on the first 5m same-side FVG/OB formed by the move (`sd.zones_tf(..., 5)`), ignoring `po3_inclusive` / the open-side gate. Target the ADR5 extreme or a 60m premium array.
  - Params: `missed_5m: bool = False`, `missed_leave_pts: float = 5.0`.
  - Test: `test_missed_entry_5m_retrace`.

### 203. new-asian-open-scalp
- **rule_id / kind:** new / missing_rule. Scope: fx_only. judgment = false.
- **Rule:** [fx-only, M17] Asian open scalp: when the market is bearish, sell at or just above the 0 GMT open (shown as 20:00 NY in the example). Target 15-20 pips as the Asian range forms. Exit 100%, no runner, no second leg. ICT describes only the short side; a bullish mirror is our interpretation.
- **Sources:** cc09_007_-oMtfDvc18Y ~00:11:35.
- **Quote:** "always aim for 15 to 20 Pips in this session"
- **Conflicts:** none.
- **Rulebook fix:** M17 [fx-only].
- **BUILD SPEC:** none (fx_only).

### 204. B12-dip-below-open-into-converging-15m-array
- **rule_id / kind:** B12 / missing_condition. Scope: general. judgment = true.
- **Rule:** Bullish day: after the 00:00 NY open, look for price to trade below the open, ideally to an SD projection of the Asian/CBDR/Flout range (FX; an index analogue is our interpretation), into a 15m discount PD array; buy there. Extra confidence (optional, not required) comes when that 15m array converges with a daily/4h/60m discount array. Use the midnight open rather than 0 GMT to avoid trading twice and overtrading. Bearish mirror.
- **Sources:** cc09_008_cqf8nH54bb8 ~00:46:17.
- **Quote:** "to a discount PD array that I can see on a 15 minute time frame"
- **Conflicts:** none.
- **Rulebook fix:** B12: add the 15m array and the HTF convergence.
- **BUILD SPEC (setups_models):** covered by item 189 (`sweep_15m_array`) together with `po3_ideal` (item 13). Add the tag `htf_converge` when the 15m array overlaps a 60m/4h/daily same-side array. Test: `test_htf_converge_tag`.

### 205. new-stopout-at-planned-array-next-day-flip
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = false.
- **Rule:** If price breaks through the planned HTF support array A (with or without our long being stopped), on the next trading day trade toward the next lower daily array T. After the 00:00 NY (or 0 GMT, FX) open, wait for a rally above the open into a premium array (FVG/bearish OB) on the 15m/5m, sell there, and target T. At T, expect the daily bullish IOF to resume and look for longs again. The HTF bias is unchanged (B9); this is not a same-session reversal (X13 holds).
- **Sources:** cc09_008_cqf8nH54bb8 ~00:54:35.
- **Quote:** "if we lose this level here the next trading day I'm going to look at the opening price"
- **Conflicts:** none.
- **Rulebook fix:** B9/X13: add the next-day counter move.
- **BUILD SPEC (bias_htf):**
  - `htf.table` column `array_lost` (+1/-1): yesterday closed through the daily discount (premium) array that was the planned support (resistance).
  - With `array_lost_flip`, the next day allows shorts against the daily bias, with the target = the next lower daily array; longs again once that array is touched.
  - Params: `array_lost_flip: bool = False`.
  - Test: `test_array_lost_next_day_short`.

### 206. new-leader-entry-vs-reference-extreme
- **rule_id / kind:** new / missing_rule. Scope: needs_unavailable_data. judgment = true.
- **Rule:** [commodities, swing/daily; needs DXY + commodity daily data] Accumulation read: while DXY makes higher highs, the commodity fails to make lower lows (a higher low, short-term highs broken). Buy when DXY forms an intermediate-term high (often at a premium array / void fill) and the commodity simultaneously trades down into a prior bullish OB (a discount array). The exit/target is not specified (the examples ran parabolic). Applying it to indices (leader vs reference) is our interpretation.
- **Sources:** cc10_002_ygtvWKyOzHQ ~00:21:20.
- **Quote:** "we're blending PD arrays discount with the context"
- **Conflicts:** none.
- **Rulebook fix:** M17/B19: add the commodity leader entry [needs data].
- **BUILD SPEC:** none (needs commodity data).

### 207. new-spread-divergence-buy
- **rule_id / kind:** new / missing_rule. Scope: needs_unavailable_data. judgment = true.
- **Rule:** Daily nearby contract. Long when all hold: the market is at a premium (nearby priced above the next month out, spread > 0); price makes lower lows while the spread makes higher lows (bullish divergence); price is in the discount half of the recent range; and it trades into a discount array (bullish OB, FVG, liquidity void, or below equal/old lows), ideally OTE. Divergence size unspecified. Inverse: a price higher high with a lower spread peak = trail the stop / take partial profits and wait for a new buy signal.
- **Sources:** cc10_004_WsolkBzpDOQ ~00:15:41.
- **Quote:** "if you ever see that when a market has a premium and it's underlying bullishness"
- **Conflicts:** none.
- **Rulebook fix:** M17: add the spread-divergence model [needs data].
- **BUILD SPEC:** none (needs contract-spread data).

### 208. new-bond-or-stop-run-volume-divergence
- **rule_id / kind:** new / missing_rule. Scope: bonds_only. judgment = true.
- **Rule:** [bonds-only; needs ZB 15m + volume] OR = 08:00-09:00 NY (the highest volume of the day). After 09:00, price trades below the OR low on a lower 15m volume bar than the OR's peak volume = a stop run / volume divergence and a potential reversal. Expect a rally that finds support at the opening range and continues higher later in the day. The entry trigger and stop are not stated (our interpretation: buy the reclaim of the OR low, stop below the run low). Short mirror.
- **Sources:** cc10_006_CGbSpa_9Z9Y ~00:05:06.
- **Quote:** "price trades down below the low that was formed between 8 AM and 9 A.M this is a stop run and a potential reversal"
- **Conflicts:** none.
- **Rulebook fix:** M17 [bonds-only].
- **BUILD SPEC:** none (bonds_only).

### 209. new-bond-or-ob-first-second-test
- **rule_id / kind:** new / missing_rule. Scope: bonds_only. judgment = false.
- **Rule:** [bonds-only] The last down-close 15m candle(s) inside the 08:00-09:00 OR = a bullish OB. Buy on the first retest; a second retest later is equally valid. Target above the OR high / prior highs. A new high made on lower volume = weakness (take profit or expect a retrace back into the OR). Short mirror (the last up-close candles = a bearish OB).
- **Sources:** cc10_006_CGbSpa_9Z9Y ~00:08:53.
- **Quote:** "inside the opening range the last down closed candle is a bullish order block"
- **Conflicts:** none.
- **Rulebook fix:** M17 [bonds-only].
- **BUILD SPEC:** none (bonds_only).

### 210. T4-bond-large-or-retracements
- **rule_id / kind:** T4 / missing_rule. Scope: bonds_only. judgment = true.
- **Rule:** [bonds-only] OR 08:00-09:00 NY. When the OR is large (threshold unstated), look for retracement / fair value entries (OB, FVG) rather than the range itself. In the example, after the OR runs one side's liquidity (the London high) and then the other (the London/early lows = Judas), buy the retrace into the OB/FVG formed by the run. Take partials at the nearby FVG fill and run the rest to the opposite OR extreme. Mirror for shorts.
- **Sources:** cc10_007_JpV-J31mxhg ~00:13:32.
- **Quote:** "when there's a large opening range we want to start looking for retracement ideas or fair value ideas"
- **Conflicts:** none.
- **Rulebook fix:** T4 [bonds-only]; merge with item 211.
- **BUILD SPEC:** none (bonds_only).

### 211. M12-bond-or-turtle-soup-pm-ob
- **rule_id / kind:** M12 / missing_rule. Scope: bonds_only. judgment = false.
- **Rule:** [bonds-only] If 08:00-09:00 runs the London high and then the London / 06:00-07:00 lows (turtle soup), the last down-close candle of that run = a bullish OB. Entries: (a) a turtle-soup buy below those lows; (b) an AM buy limit at the FVG/OB before 10:00; (c) better: the PM retest of the OB after price has traded back above the swept low. Take profit at the FVG fill above (the 08:00-hour last up-close candle gap), with a runner to the OR high. Stop not stated (our interpretation: below the soup low).
- **Sources:** cc10_007_JpV-J31mxhg ~00:14:07.
- **Quote:** "it creates a turtle soup which is a move below the 154 02 level in the opening range"
- **Conflicts:** none.
- **Rulebook fix:** M12 [bonds-only].
- **BUILD SPEC:** none (bonds_only).

### 212. N8-small-or-am-scalp-threshold
- **rule_id / kind:** N8 / missing_condition. Scope: bonds_only. judgment = true.
- **Rule:** Consolidation day (bonds): OR <= 12 ticks -> expect a volatility squeeze, then an expansion that may run the overnight high/low, in the IOF direction. AM scalp target 5-10 ticks (ICT also suggests a limit exit beyond the target, e.g. 16 ticks against an 8-tick objective, as a bonus). Do the trading in the AM, before noon. The index scaling of the 12-tick threshold is our interpretation. That a wider OR means no scalp is implied, not stated.
- **Sources:** cc10_008_RgpxhuVp5Xg ~00:09:44.
- **Quote:** "if the opening range is 12 ticks or less generally you'll have an expansion move of some kind"
- **Conflicts:** none.
- **Rulebook fix:** N8: add the 12-tick threshold [bonds-only].
- **BUILD SPEC:** none (bonds_only).

### 213. new-or-reference-arrays-reused
- **rule_id / kind:** new / missing_rule. Scope: index. judgment = true.
- **Rule:** Index OR60 (09:30-10:30) reference arrays: the bearish OB just before 09:30 (the last up-close candle before the drop); the rejection block = the last up-close candle inside the OR (shorts) or the lowest-close down-close candle (longs); and the bullish OB = the last down-close candle inside the OR. After the OR, use returns to these arrays for entries in the bias direction. The same array can be reused later in the day (ICT's NQ example: a second, larger short later the same day). Stop, target and invalidation are our interpretation (e.g. stop beyond the OR extreme, target the opposite OR end / next pool). ICT also notes that a weaker-volume retest that fails to exceed the OR low supports the rejection.
- **Sources:** cc10_010_ORbtHOUzAIM ~00:07:38.
- **Quote:** "that same reference point is used later on in the day for a dramatic sell-off."
- **Conflicts:** none.
- **Rulebook fix:** L3/T4: add the OR reference arrays.
- **BUILD SPEC (setups_models):**
  - Add "or_ref" to `entry_arrays`. At 10:30, record the OR60 arrays (`order_block` on 570-630 bars plus the last opposite bar before 570).
  - After 10:30, a return to one in the bias direction arms a limit at its body edge. It is reusable until a body closes through (`or_ref_reuse`).
  - Params: add "or_ref" to `entry_arrays`; `or_ref_reuse: int = 2`.
  - Test: `test_or_reference_array_reuse`.

### 214. new-am-trend-definition-and-start
- **rule_id / kind:** new / missing_rule. Scope: index. judgment = true.
- **Rule:** AM trend (index): between 09:30 and 12:00, expect one main swing. The day's high/low tends to form 09:30-10:30; the swing may end 10:30-11:00 or run to noon; it may continue or reverse the overnight move. Bullish template: at/after 09:30, price trades down into a prior bullish array (the last down-close candle OB, or a London FVG), then expands up. Buy at the array; the stop below it and the buy-side target by noon are [our interpretation]. Bearish mirror (price trades up into a bearish OB, as in ICT's first example).
- **Sources:** cc10_011_wWCKTEhVp2o ~00:01:08, ~00:03:48.
- **Quote:** "between the open at 9 30 a.m and noon New York time there is typically a trend or Price swing daily"
- **Conflicts:** none.
- **Rulebook fix:** T5: add the AM-trend concept.
- **BUILD SPEC (setups_models):**
  - `am_array_open`: from 09:30 to 10:30, a first touch of a pre-09:30 same-side array (London FVG, last opposite-close OB) in the bias direction arms a limit at its near edge without an MSS (the item 12 path with 1m/5m arrays). Single AM trade.
  - Params: `am_array_open: bool = False`.
  - Test: `test_am_open_into_london_fvg`.

### 215. new-london-breaker-precursor
- **rule_id / kind:** new / missing_rule. Scope: index. judgment = false.
- **Rule:** Index AM precursor: if, during London, price runs sell stops below a swing low and forms a bullish breaker (the last up-close candles before the run), with bullish IOF, anticipate a 09:30 expansion higher. Bearish mirror. This is a bias/anticipation cue. The entry (e.g. on a return to the breaker or via the AM-trend template) and the target (the buy-side above the London/overnight highs) are our interpretation.
- **Sources:** cc10_011_wWCKTEhVp2o ~00:06:34.
- **Quote:** "the fact that during London we had a breaker"
- **Conflicts:** none.
- **Rulebook fix:** B12/T5: add the London breaker cue.
- **BUILD SPEC (bias_htf):**
  - Session bias input `london_breaker` (+1/-1/0): a `levels.breakers` zone formed 02:00-05:00 after a London sweep. With `bias_src` including "london_breaker", it sets the AM side when the daily bias is 0 or agrees.
  - Params: `london_breaker_bias: bool = False`.
  - Test: `test_london_breaker_sets_am_side`.

### 216. T9-pm-reversal-turtle-soup-am-high
- **rule_id / kind:** T9 / missing_rule. Scope: index. judgment = false.
- **Rule:** T9 add: a PM reversal (13:00-16:00) may take the form of a rejection / turtle soup of a previous high (bearish) or low (bullish), e.g. the AM extreme. Trade it with the M12 turtle-soup mechanics. The entry, stop and targets are our interpretation (not in cc10_012).
- **Sources:** cc10_012_qZg_5bac518 ~00:06:19.
- **Quote:** "so the afternoon session can create a reversal"
- **Conflicts:** M6 (2023) requires an IFVG for the PM reversal; the CC version is a turtle soup.
- **Rulebook fix:** T9: add the turtle-soup form; list the M6 difference.
- **BUILD SPEC (setups_models):** `turtle_soup="2023"` with the AM high/low as a PM pool (`pm_am_stops`, item 28) already gives it; add `ts_sessions` so the turtle soup can be limited to the PM. Params: `ts_sessions: tuple = ()`. Test: `test_pm_turtle_soup_am_high`.

### 217. T13-two-session-close-profile
- **rule_id / kind:** T13 / missing_rule. Scope: index. judgment = false.
- **Rule:**
  - Bullish AM: at a discount array, ES/NQ/YM lows from London -> 09:30 show SMT -> buy ES; hold to 10:30-11:00; target a 15m/60m premium array.
  - Lunch 12:00-13:00 consolidates (it may dip into a lunch FVG/OB).
  - PM: SMT between the lunch low and the low right after 13:00 -> buy ES; hold toward the close; target a 15m/60m premium array.
  - Bearish mirror: from 13:00, hunt the ES short-term high (a bearish OB/FVG/void, or a run above the lunch high) with SMT on the lunch high vs the post-13:00 high; hold at least to 15:00, ideally 16:00.
  - The PM leg may come in two stages (early profit-taking short of the 15/60m array, then a last-hour ramp into it), and any of the three indices can be the divergent one for an ES trade.
- **Sources:** cc10_014_yWBxZsbmK1U ~00:01:09, ~00:06:51.
- **Quote:** "from one o'clock in the afternoon New York time we're immediately going to be hunting and stalking the e-mini S P's short-term High"
- **Conflicts:** none.
- **Rulebook fix:** T13: add the two-session profile.
- **BUILD SPEC (setups_models + management_exits):**
  - Builds on `profile_tags` and `smt_entry`. `profile_two_session`: when the AM trade's side has an SMT tag and is delivered, the PM session requires the same side with SMT on the lunch-low vs post-13:00-low pair (`smt_windows` ((720, 810),)).
  - The PM exit is held to 16:00 (shorts: >= 15:00), with no 14:00 time exit.
  - Params: `profile_two_session: bool = False`.
  - Test: `test_two_session_profile_pm_smt`.

### 218. T13-am-move-pm-reversal-htf-nesting
- **rule_id / kind:** T13 / missing_rule. Scope: index. judgment = false.
- **Rule:**
  - AM rally / PM reversal: buy ES on bullish SMT (London -> 09:30) at an AM discount array; hold to ~11:00; expect a lunch retrace.
  - If the AM high formed below a 15/60m premium array, expect a post-13:00 rally into it. A 15/60m array nested in a 4h/daily premium array is the catalyst for the PM short [requiring SMT highs = our addition].
  - Target: if the AM discount array was also HTF, expect only a bounce/consolidation there (cover). If not, hold for a break of the intraday low. Hold toward 15:00-16:00.
  - AM decline / PM reversal: mirror. Short on SMT highs; hold >= 10:30, ideally ~11:00. The PM may first run the daily/lunch low into a 15/60m discount array, and a nested 4h/daily array is the reversal catalyst. Hold toward 15:00. The intraday high is taken only if the AM premium array was not HTF.
- **Sources:** cc10_014_yWBxZsbmK1U ~00:09:52, ~00:12:23.
- **Quote:** "if the daily am session discount array is not a higher time frame discount array we'll look for continuational downside"
- **Conflicts:** none.
- **Rulebook fix:** T13: add the AM-move / PM-reversal profile and the nesting test.
- **BUILD SPEC (setups_models + targets_partials):**
  - `pm_nest_reversal`: PM counter-AM trades need the PM sweep extreme in a 15m/60m array nested in a 4h/daily same-side array (`nest_tfs`, Ep01.15, reused with ("D", "4h", "1h")).
  - Target: if the AM entry array was HTF, the single target = that array; else the ladder extends past the AM extreme.
  - Params: `pm_nest_reversal: bool = False`.
  - Test: `test_pm_reversal_needs_nested_array`.

### 219. T13-consolidation-profiles
- **rule_id / kind:** T13 / missing_rule. Scope: index. judgment = false.
- **Rule:**
  - AM decline / PM rally: sell ES on bearish SMT at a premium array; hold 10:30-11:00. PM: buy on SMT at the PM lows. If the AM low was at a 15/60m array nested in a 4h/daily array, the PM low runs only the lunch low; otherwise it first runs the AM low.
  - The PM extreme typically forms around 14:00 at a 15/60m array; exit there. Afterwards expect a drift back to the day's equilibrium. Never hold to 16:00.
  - AM rally / PM decline: mirror, with SMT on the lunch high vs the post-lunch high. If the AM high was at a 4h/daily premium array, the PM rally runs only the lunch high; otherwise it takes the intraday high into a 4h/daily array before the short. Hold the short to ~14:00 minimum; it targets the short-term lows.
- **Sources:** cc10_014_yWBxZsbmK1U ~00:14:28, ~00:17:47.
- **Quote:** "generally around two o'clock in the afternoon"
- **Conflicts:** none.
- **Rulebook fix:** T13: add the consolidation profiles (X11 has only the ~14:00 exit).
- **BUILD SPEC (setups_models + management_exits):**
  - `profile_consol`: when the AM and PM trades are on opposite sides (consolidation profile), the PM trade exits at 14:00 + `consol_exit_min` (X11 path) with a target at the 15/60m array.
  - The PM pool choice follows the nesting test: the lunch extreme only if the AM extreme was at a nested HTF array, else the AM extreme first.
  - Params: `profile_consol: bool = False`, `consol_exit_min: int = 15`.
  - Test: `test_consolidation_profile_pm_exit_1400`.

### 220. M17-stock-jan-fvg-refill-entry
- **rule_id / kind:** M17 / missing_rule. Scope: stocks. judgment = false.
- **Rule:** Stocks, buy watchlist (Feb-May window): after a January stock-vs-Dow SMT (the Dow makes a lower low, the stock a higher low), a January up-day gap or liquidity void on the stock's daily chart is a discount array. Its refill in early February (Boeing on the 2nd trading day, Home Depot) was where the rally began. This is shown in examples, not stated as a mandatory entry rule. Prefer stocks sitting near weekly old highs, which are poised for a breakout ("low resistance liquidity run"). Drop stocks that are too extended or far below their old highs. Express the trade with affordable call options and narrow the list to 2-4 names.
- **Sources:** cc10_016_rcO8-nb3S0Q ~00:07:07.
- **Quote:** "that Gap was closed in the second trading day of February discount array"
- **Conflicts:** none.
- **Rulebook fix:** M17: add the stock watchlist entry.
- **BUILD SPEC (bias_htf, stock research study):**
  - New `mentorship/stocks_watch.py` (a new file, not built in this step) using daily bars from `alpaca_data.py` for the Dow 30 and DIA.
  - `jan_smt(year)`: stocks with a higher January low while DIA made a lower low.
  - `gap_refill(stock)`: January up-gaps/voids refilled in Feb; report the forward 1-3 month returns.
  - Test: `test_stock_jan_smt_synthetic`.

### 221. M17-stock-sell-watchlist-smt
- **rule_id / kind:** M17 / missing_rule. Scope: stocks. judgment = false.
- **Rule:** Universe: the Dow 30 (homework: the Nasdaq 100). The index must be poised to decline (index SMT at a premium, weekly bearish). In January or May 1-Aug 1, select stocks whose weekly chart makes a lower high at a premium array while the Dow makes a higher high, with weekly order flow already bearish; exclude defensives (VZ, GE, KO). The signal holds until an index itself fails to make a higher high. Narrow to 2-4 names; trade via puts. The "index poised to decline" filter is shown by index SMT at highs, e.g. the Nasdaq higher high while the Dow/SPX fail in May-Jul 2015.
- **Sources:** cc10_017_dH381VCOVl0 ~00:01:40, ~00:02:40.
- **Quote:** "Leadership stocks that are aggressively sold by institutions will be found to fail to Rally higher during bearish months"
- **Conflicts:** none.
- **Rulebook fix:** M17: add the stock sell watchlist.
- **BUILD SPEC (bias_htf, stock research study):** `stocks_watch.sell_list(date)`: weekly lower high vs a DIA higher high in Jan / May-Jul, weekly bias -1 (`weekly_bias` on stock weeks), defensives excluded; forward returns reported. Test: `test_stock_sell_smt_synthetic`.

### 222. new-stock-short-prefer-rally-into-premium
- **rule_id / kind:** new / missing_rule. Scope: stocks. judgment = true.
- **Rule:** For stock short candidates, prefer stocks that make a counter-trend rally (Judas-like) into a premium array or lower high during the bearish window. Exclude stocks that only drift lower steadily without such a rally (the WMT example), even if they later decline.
- **Sources:** cc10_017_dH381VCOVl0 ~00:09:43.
- **Quote:** "you really want to find an area where a price wants to Rally away kind of like a Juda swing"
- **Conflicts:** none.
- **Rulebook fix:** M17: add the rally-into-premium preference.
- **BUILD SPEC (bias_htf, stock research study):** in `stocks_watch.sell_list`, require a weekly up-close bar into a weekly premium array within the window. Test: `test_stock_short_needs_rally`.

### 223. M17-fx-mega-trade
- **rule_id / kind:** M17 / missing_rule. Scope: fx_only. judgment = true.
- **Rule:** FX mega trade (fx-only, out of scope for the bot). The context is the quarterly shift plus the seasonal tendency (a road map, not a must). Using the 7 majors' futures (6E/6B/6A/6N/6S/6C/6J), classify each by institutional order flow and relative strength: strong currencies break premium arrays and hold higher lows; weak ones break discount arrays and make lower highs. A qualified trade requires DXY confirmation, and among correlated pairs you keep the stronger (e.g. drop NZD for AUD). Pair the strongest with the weakest in a cross, or trade the futures/calls. The horizon is between swing and position. Entries are deferred to the August PDFs.
- **Sources:** cc11_002_CxwFON8MLB0 ~00:11:23.
- **Quote:** "you look for strong and weak currency Futures ... you're also going to be confirming with the dollar Index"
- **Conflicts:** none.
- **Rulebook fix:** M17 out-of-scope list: add the FX mega trade.
- **BUILD SPEC:** none (fx_only).

### 224. new-stock-mega-trade-process-and-filters
- **rule_id / kind:** new / missing_rule. Scope: stocks. judgment = false.
- **Rule:** Process:
  1. Anticipate new earnings leaders at the quarterly shift.
  2. Seasonal window (early year or Sep-Nov).
  3. Indices up or poised up.
  4. Fundamental screen.
  5. RS leader filter; weekend watchlist, checked daily.
  6. Wait for a three-index daily SMT where one average fails to make a lower low while the others do (in the example the Dow and SPX made a lower low and the NASDAQ held a higher low).
  7. Qualify only stocks whose swing low in the same window is HIGHER than the prior one (a lower low = reject), basing and not gapped away.
  8. Express with calls chosen by Greeks/strike.

  Preferences: IBD 50 / sector-leader lists, a SmartSelect composite of 98 or more, a share price above about $20-25.
- **Sources:** cc11_003_kny8Kpisvoc ~00:28:37, ~00:31:14.
- **Quote:** "we want to find stocks that make that higher lower"
- **Conflicts:** none.
- **Rulebook fix:** M17: add the stock mega-trade process.
- **BUILD SPEC (bias_htf, stock research study):** `stocks_watch.mega(date)`: the steps the data allows (index SMT on daily DIA/SPY/QQQ, stock higher low in the same window, base/no-gap filter from item 225, price > $20). Fundamentals/IBD are marked unavailable. Test: `test_stock_mega_higher_low_filter`.

### 225. new-stock-no-gapped-away-or-overextended
- **rule_id / kind:** new / missing_rule. Scope: stocks. judgment = true.
- **Rule:** Reject a stock if, at the SMT date, price sits above an unfilled daily gap that opened above its latest consolidation and has extended well beyond it, or if the trend into the window has no multi-week base and is extended (turtle-soup risk). Accept it if it is inside or just breaking out of a base; a small gap followed by sideways movement is fine.
- **Sources:** cc11_003_kny8Kpisvoc ~00:32:27, ~00:43:37.
- **Quote:** "the fact that we had all this extension no real consolidations in here that makes it uh suspect to me"
- **Conflicts:** none.
- **Rulebook fix:** M17: add the gap/extension filter.
- **BUILD SPEC (bias_htf, stock research study):** `stocks_watch.base_ok(stock, date)`: a base = >= 15 daily bars with range <= 15% within the last 60 bars; reject an unfilled up-gap above the base with price > base high x 1.10 [thresholds ours]. Test: `test_stock_base_filter`.

### 226. new-bond-mega-trade
- **rule_id / kind:** new / missing_rule. Scope: bonds_only. judgment = true.
- **Rule:** 1) May-June window; 2) daily/weekly IOF bullish; 3) price below EQ of the HTF range; 4) a daily scan of the 5y/10y/30y for rate SMT at the low; 5) long ZB when price ran sell stops below a short-term low into a bullish OB/FVG (the next unmitigated discount array if nearer ones were traded through), with SMT at that array; 6) hold toward the Sep-Oct highs; 7) no bond overtrading outside this setup. Additions: Sep-Nov gives secondary short-term rallies, not the mega trade; a move under about $10k per ZB contract does not qualify; the SMT can be checked on 2h intraday line charts over about one month around the low; the signal can come late (e.g. July 2011); some years fail (2012-2013), so don't force it.
- **Sources:** cc11_004_At43V93rnDQ ~00:05:40, ~00:19:09.
- **Quote:** "the first thing you're looking for is a seasonal tendency ... performing a daily scan for the interest rate smt"
- **Conflicts:** none.
- **Rulebook fix:** M17 [bonds-only]: add the bond mega trade.
- **BUILD SPEC:** none (bonds_only).

### 227. B4-prefer-calendar-driven-manipulation
- **rule_id / kind:** B4 / missing_condition. Scope: general. judgment = true.
- **Rule:** Bullish bias: execute only when price trades into a discount array at a specific time of day (a kill zone). It is preferred, but not required, that the run into the array is a news/economic-calendar-driven manipulation. Bearish mirror at premium arrays. ICT gives no size or priority boost; treat it as a preference or a tag only.
- **Sources:** cc12_003_3B7Reg2Yiqs ~00:25:39.
- **Quote:** "it has to do this many times with the manipulation aspect by the economic calendar"
- **Conflicts:** none.
- **Rulebook fix:** B4: add the calendar-manipulation preference.
- **BUILD SPEC (news_calendar_times):** tag `news_sweep` when the sweep extreme falls within `news_sweep_min` minutes after a `calendar.py` release time that day. Report only. Params: `news_sweep_min: int = 0` (0 = off). Test: `test_news_sweep_tag`.

### 228. M13-pattern1-full-sequence-ote-fvg
- **rule_id / kind:** M13 / missing_condition. Scope: general. judgment = false.
- **Rule:** Long sequence:
  1. HTF bullish; price bounces off an HTF discount array (a bullish OB) at swing low L.
  2. The impulse to H leaves an FVG near L.
  3. A short-term low S then forms, and price fails to rally after equal highs or a higher high.
  4. Price drops into the FVG and below S (a sell-stop raid).
  5. Buy at the OTE (62-79%, sweet spot 70.5% of L->H) where it overlaps the FVG. The live example allowed 70.5% or about 79% (the gap close).

  Stop: in the live example, below the next discount array beneath the entry. Target the external range liquidity above H. Without S, the setup is lower probability. Short mirror. Conflict with E2/D11 as noted.
- **Sources:** cc12_004_Oec_0NM_OeY ~00:26:47, ~00:57:31.
- **Quote:** "this is the actual entry with the overlap of 70.5 because it could spread just past the the gap"
- **Conflicts:** E2/D11 default entry at the FVG near edge vs the 70.5% OTE overlap here.
- **Rulebook fix:** M13: add the sequence order, the overlap entry and the no-S downgrade.
- **BUILD SPEC (setups_models):**
  - Builds on `ote="limit"` (70.5%) and `ote_stack_tag`. New `ote_fvg_overlap`: the limit is placed at 70.5% only if that price lies inside an FVG of the L->H leg; otherwise it goes at the FVG edge nearest 70.5% within the band.
  - `ote_need_s`: requires a swing low S inside the leg that was taken before the fill.
  - Params: `ote_fvg_overlap: bool = False`, `ote_need_s: bool = False`.
  - Test: `test_ote_fvg_overlap_with_s_raid`.

### 229. M4-pattern3-breaker-half-size-add-ltf
- **rule_id / kind:** M4 / missing_condition. Scope: general. judgment = false.
- **Rule:** After a turtle-soup low L2 (stops under L1 taken) and a rally through the short-term high H, H becomes a bullish breaker. On the first retrace to the breaker, either enter new (if the soup was missed) or, if already long from L2, add about half the initial size (examples 2 -> +1, 20 -> +10). Do not expect price to go back to the OB/OTE below the breaker, because the stop run has done its work. Refine on a lower timeframe: the entry is the LTF OTE/FVG/OB in the leg's upper portion that overlaps the breaker. The pattern applies on every timeframe. Stop placement and the short mirror are not stated here; a short mirror is our assumption.
- **Sources:** cc12_004_Oec_0NM_OeY ~00:36:02.
- **Quote:** "I can add 10 now at that higher buy level off the bullish breaker"
- **Conflicts:** none.
- **Rulebook fix:** M4 "Pyramid": add the half-size add, the missed-soup entry and the LTF refinement.
- **BUILD SPEC (setups_models + entries_stops_sizing):**
  - Builds on `ts_breaker_pyramid` (one add at the breaker). New pieces:
    - `ts_breaker_add_mult` = 0.5 of the initial units.
    - When the soup was missed, the breaker retest is a new order (shares `two_chance`, item 149).
    - `ts_breaker_ltf`: the add limit is the 1m FVG/OB inside the breaker zone nearest its top.
  - Params: `ts_breaker_add_mult: float = 0.5`, `ts_breaker_ltf: bool = False`.
  - Test: `test_ts_breaker_half_add_ltf`.
