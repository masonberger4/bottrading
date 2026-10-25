# Rulebook gaps: session, day and week stops, and trade frequency

Topic `session_day_week_stops_frequency`. Every item below is a verified gap between ICT's captions and `mentorship_rules.md`. When the checker gave a corrected rule, that corrected rule is the one written here; when it gave none, the claim's full rule is used. "[our interpretation]" marks thresholds or readings that ICT does not state.

Conventions:
- Times are New York. Prices in ES points unless stated; the engine converts with `p.es_pt` (SPY ~ ES/10).
- New Params switches default off (rule_coverage.md section 3). Each work package adds its fields in its own commented block at the end of `Params` (strategy.py ~65-705) and validates string switches in `__post_init__` (~705).
- Code anchors (current `mentorship` branch):
  - Session state: `run_day` (strategy.py ~2490). `done = {"AM", "PM", "PRE7", "PRE9", "NEWS"}` (~2566), `state = {"reentered", "day_pts"}` (~2574), `lost_side` (~2577, set from `_after_close`'s return at ~2715 / ~2801-2810, never cleared). SB keys `SB_AM` / `SB_PM` (~2847-2851), last-hour key `LH` (~2852-2855), `skip_main` (~2857).
  - Side gates: the `for sd in sides` loop (~2902-2916): `reverse_after_loss` (default True, ~171, so `lost_side` only blocks when it is set False), `weekly_bias`, `want`, `tgif`, `year_end`, draw lock, `stop_flip`.
  - `_after_close` (~1858): `no_pm_after_am_win`, `reentry_half` (one re-entry per session, half risk via `state["reentered"]`), `day_target_pts`.
  - Position loop (~2590-2716): adds, `pd3_exit` (~2676), `am_exit` (~2693).
  - Day context: `blocked()` (~842), `day_context()` (~1902, `tgif_long|short`), `adr5()` (~828), `MACROS` (~58), `sloppy_day` / `Chop` / `sloppy_mode` (~2545-2590).
  - Week state: `backtest.run` (backtest.py ~269-310) holds the only cross-day state (`max_trades_week`, truncation of `day_trades`). `run_day` gets no week state today.
  - Silver Bullet: `sb_model.run_sb` (~31), `_arm` (~213).
  - Intermarket: `backtest.INTERMARKET()` (~321) gives a daily DXY trend tag only (close vs 20-day mean).
- Work packages are the names in `rule_coverage.md` section 3. Session stops, re-entry permissions and done flags go to **management_exits**; day/week/month state, weekday and calendar rules to **day_week_context**; new entry branches (re-entry triggers, reversal variants) to **setups_models**; macro and session-window gates to **news_calendar_times**; swing / position / HTF studies to **bias_htf**; the SB window priority to **silver_bullet**.
- Tests: `tests/test_management_exits.py`, `tests/test_day_week_context.py`, `tests/test_news_calendar.py`, `tests/test_bias_htf.py` (new files), or `tests/test_setups_models.py` where named. Each spec names its test function. Every new switch also joins the "all off = identical trades" regression in its package's test file.
- Items scoped `fx_only` or `needs_unavailable_data` get the rulebook fix only, with no build spec.
- Swing, position and OSOK models are parked under M17. Their `general`-scope build specs are research studies on daily / 4h bars (`study.py`, `htf.py`), not live `run_day` branches.

Summary: 41 items, 35 new build specs. Items without a build spec:
- 1 fx_only: new-no-chase-missed-london-profile.
- 2 that need data we do not have: B17-dxy-weekly-objective-ends-week (needs a DXY objective map on intraday/daily arrays; only a daily trend tag exists), new-multi-asset-regime-aggressiveness (four asset classes).
- 2 already listed in rule_coverage.md with the same content:
  - X10-skip-pm-am-range-vs-adr5: section 3 day_week_context X10d "`am_range_skip_pm` (AM range >= k x ADR5 -> done PM and SB_PM)" is the same rule. Rulebook text fix only.
  - X15-all-conditions-days-only: section 3 day_week_context N8.2 "trend_recipe tag/only/side (small ranges, react into an array, 08:30 news)" is the same gate; its "only" mode is this filter. Rulebook text fix only (bond trigger needs data; FX checklist excluded).
- 1 covered by existing switches (preset only, no new code): X15-frequency-scaling-graduation (`max_trades_week` + bar timeframe `tf`).

Several items extend a section 3 entry instead of duplicating it; each says which (X13a, X13b, D18, X7c, X14b, X14d, N8.3, N9.5, N10, N10.3, M14.1, M14.3, N7.6, B17.1).

Shared pieces this topic adds (build first):
- **`week` state (day_week_context).** `backtest.run` builds one dict per ISO week and passes it to `run_day` as a new kwarg `week` (via `day_kwargs`): `n` (trades so far), `net` (closed P&L, $ and % of start-of-week equity), `pts` (net ES pts), `done` (bool) + `done_reason`, `draw` / `draw_hit` (the weekly objective from `htf.table` / X15d `week_done_on_draw`), `carry` (unmet draw from the prior week), `month_n`, `month_big` (count of >= `big_rr` winners this month). `run_day` writes back on each close. Items 19, 21, 22, 23, 28-31, 33, 38 use it. Replaces the truncation in backtest.py ~301 (entry-time order fix, X15 in section 3).
- **`state["idea"]` (management_exits).** Per session: `{"side", "draw", "failed", "fail_reason", "last_close": {"kind": win/loss/trail_win/runner_stop, "side", "i", "risk"}}`. Set at the session's first scan (expected direction = `want` / lock side / `cur_bias`) and updated in `_after_close`. Items 1-5, 7-9, 14 use it.
- **`setups.reentry_ok(ctx, sd, i, p, idea, mode)` (setups_models).** One gate for every re-entry kind: draw untouched (no 1-tick trade through `idea["draw"]`), no opposing MSS since the close, no body close beyond the defended structure, and a NEW PD array (FVG / OB / breaker / IFVG / NWOG edge) formed after the close bar, armed as a limit only (no market chase). Returns the array or None. Items 2-5 use it.
- **`state["day_net"]` (management_exits).** Always track realized day P&L after costs (today only when `day_target_pts` is on, ~1876). Items 16, 17, 31 use it.

---

## A. Re-entry and reversal after a closed trade (X13, X14, D18)

### 1. X13-am-fail-no-reverse-pm-reset
- **rule_id / kind:** X13 / unlisted_contradiction. Scope: index. judgment = true.
- **Rule:** Set the expected direction before the AM. The AM idea fails on an AM loss, or (our interpretation) when price runs against the expected direction before any fill. Once it fails: no reversal for the rest of the AM. At the PM session (14:00 per 001; 13:30 variant) clear the lost-side block. PM setups in either direction are allowed, and ICT expects the reversed-direction PM setup to be cleaner. The no-reversal rule is strict for new and funded traders; experienced traders may sometimes reverse (001 ~47:30).
- **Sources:** 001_XN8tuO4QIRw ~00:48:43, ~00:48:51.
- **Quotes:** "it starts to go down don't don't reverse wait" (001); "you're probably gonna have something really nice in the PM session" (001).
- **Conflicts:** bot `lost_side` blocks the opposite side after a loss with no PM reset vs 001 ~48:51 expecting the reversed-direction PM trade.
- **[our interpretation]:** the no-fill failure test (opposite pool run with displacement before any fill).
- **Rulebook fix:** X13: "The no-reverse rule applies when the AM idea fails, by a loss OR by price running the opposite pool before any fill (001 ~48:43). It lasts for the AM only: at the PM session the block clears and either direction is allowed; ICT expects the reversed PM setup to be cleaner (001 ~48:51). Strict for new/funded traders; experienced traders may reverse (001 ~47:30)."
- **BUILD SPEC (management_exits; extends section 3 X13a / D18 "lost_side reset at the PM"):**
  - Where: `run_day` ~2577: replace the day-scoped `lost_side` with `state["idea"]["AM"]["failed"]`; at the first PM bar (`t >= p.pm[0]`, or 840 when `pm_reset_t=840`) clear `lost_side` when `lost_side_scope="session"`. No-fill failure: in the bar loop before any AM fill, if `idea["side"]` is set and the bar trades 1 tick through the AM session / pre-market extreme on the opposite side with a displacement candle (the existing `M1.2` displacement test, `displacement_mult`), set `failed=True, fail_reason="no_fill_run"`, set `done["AM"]=True` and cancel `pending` if it is an AM order.
  - Params: `lost_side_scope: str = "day"` ("day" = today; "session"), `am_idea_fail: bool = False`, `pm_reset_t: int = 810` (810 = 13:30; test 840).
  - Test: `test_am_fail_pm_reset`. Synthetic day with `reverse_after_loss=False`: an AM long loses; with "day" the PM short is skipped, with "session" it arms. Second case: no AM fill, sell-side run with displacement at 09:50 -> `done["AM"]` set, a PM short allowed.

### 2. X14-reentry-after-winning-exit
- **rule_id / kind:** X14 / unlisted_contradiction. Scope: index. judgment = true.
- **Rule:** Switch `reentry_after_win` (default off = X14; test on). After a winning exit short of the session/HTF draw, allow another SAME-direction entry when the draw is still untouched and price returns into a new or untested PD array in the bias direction (OB, breaker, FVG, NWOG edge), optionally with the sister index already delivered (049). Same target. Size rebuilt per E12 (6/3/1). Evidence: 049, 050 (050 multiple re-entries, framed as experienced-only). Do not cite 019, 086 or cc09_003 as direct evidence. Cap: new-trader mode 1 trade; test 2 per session.
- **Sources:** 049_St9FJHRVdq8 ~00:02:38; 050_F509lJRrYIM ~00:49:44 (019, 086, cc09_003 rejected as direct evidence).
- **Quotes:** "I took a small Profit just to show my son ... but then I noticed that we were likely to continue" (049); "as soon as we went back up to new week opening gap ... I sold short again" (050).
- **Conflicts:** X14 "no re-entry after a winner" (095 ~47:08), X15/M3 one AM trade, bot one trade per session vs 049, 050. 050 frames many re-entries as experienced-only.
- **[our interpretation]:** the sister-index condition as an optional filter; the cap of 2 per session.
- **Rulebook fix:** X14: "No re-entry after a winner is the new-trader rule (095). Experienced: after a winning exit short of the draw, one more same-direction entry at a new PD array formed after the exit, same target, size rebuilt (049 ~2:38; 050 ~49:44)." Add 049 and 050 to D19's conflict list.
- **BUILD SPEC (setups_models gate + management_exits done flags):**
  - Where: `_after_close` ~1871: when `lost is None` and `reentry_after_win` and the trade's final exit was below its draw (`tr.exits[-1]` price short of `idea["draw"]`) and `state["win_reentries"][session] < reentry_win_max`, set `done[session]=False`, record `idea["last_close"]={"kind": "win", ...}`. In the side loop (~2902) skip the opposite side while `last_close.kind=="win"`. `_scan` only arms through `setups.reentry_ok(..., mode="win")` (new array after the exit bar; limit order). Sister option: `reentry_need_sister` requires the partner frame (`pa`) to have traded through the same draw kind (e.g. its own session low) before the re-entry bar. Risk multiplier 1.0 (fresh E12 ladder via `add_size_fracs` from stops_sizing_scaling_in).
  - Params: `reentry_after_win: bool = False`, `reentry_win_max: int = 1` (test 1/2), `reentry_need_sister: bool = False`.
  - Test: `test_reentry_after_win`. Synthetic short: TP at an intermediate low, draw below untouched, a new bearish FVG forms after the exit -> a second short arms at the FVG; no long arms; with the draw already traded no re-entry; `reentry_win_max=1` blocks a third.

### 3. X13-reentry-after-trail-stop-in-profit
- **rule_id / kind:** X13 / wrong. Scope: index. judgment = true.
- **Rule:** Switch `reentry_after_trail_win`. If a trade's trailed stop is hit at better than breakeven, the target pool is untouched, and the defended structure (IFVG/breaker low for longs) has not been broken, and the day is not a high-resistance day (022): allow a same-direction re-entry in the same session. Entry is a limit at the IFVG CE (085), or the first retest of the breaker/last up-close candle after price trades above it (022). Stop: below the IFVG low/wick CE (085) or at the CE of the FVG beneath (022). Target = the original pool. No size reduction is stated (085 added contracts). Exact size is not verifiable from the captions. Observed max: 2 AM re-entries (056). Half risk applies only after a losing stop. Fix X13's citation: 085 ~27:21 is a profitable stop-out with no half-risk statement.
- **Sources:** 085_6-KNSUN-UaU ~00:27:16; 056_NeZlyG8FZLQ ~00:11:39; 022_ALMsQytQ1fg ~02:41:56 (083 chart-only, unverifiable).
- **Quotes:** "getting stopped out now returning back into the inversion fair value Gap" (085); "come back down and touch it as support, I would use that as a entry technique" (022).
- **Conflicts:** X13 cites 085 ~27:21 for half-risk re-entry; X14 "no re-entry after a winner" (095) vs 056/085.
- **[our interpretation]:** "high-resistance day" proxy (below); full size.
- **Rulebook fix:** X13: remove 085 ~27:21 from the half-risk citation. Add X13c: "Stopped out in profit on a trail with the target untouched and the IFVG/breaker intact: re-enter at the IFVG CE (085) or the breaker retest (022), full size, same target; up to 2 AM re-entries (056)."
- **BUILD SPEC (setups_models + management_exits):**
  - Where: `_after_close`: when the last exit kind is `stop` / `trail` and the exit price is beyond entry in profit, set `last_close.kind="trail_win"` and, under the switch, `done[session]=False` (counter `state["trail_reentries"][session] < 2`). `setups.reentry_ok(mode="trail_win")`: defended structure = the IFVG / breaker the trade's stop was trailed under (`pos` keeps `trail_ref` low/high; add the field where the trail moves the stop); any 1m body close beyond it voids. Entry branch: limit at that IFVG's CE (`ifvg_entry` geometry from setups.py) or, `trail_reentry_entry="breaker"`, the first retest of the last up-close (down-close) candle above (below) which price traded. Stop: IFVG low - pad, or the CE of the FVG beneath the breaker. Target: `idea["draw"]`. Risk mult 1.0. High-resistance proxy [our interpretation]: skip when `ctx.cur_sloppy` is non-empty or `chop.on`.
  - Params: `reentry_after_trail_win: bool = False`, `trail_reentry_entry: str = "ifvg_ce"` ("ifvg_ce" / "breaker"), `trail_reentry_max: int = 2`.
  - Test: `test_reentry_after_trail_win`. Long trailed under an IFVG, stopped +3 pts, draw above untouched -> limit at IFVG CE armed at full size; a body close below the IFVG low first -> nothing armed; a losing stop-out does not use this path (half risk via `reentry_half`).

### 4. X13-reentry-after-loss-conditions
- **rule_id / kind:** X13 / shortened. Scope: general. judgment = true.
- **Rule:** After a losing stop-out, the idea is intact if: (a) the draw/target liquidity is still untouched; (b) no opposing MSS has formed and price has not closed beyond the swing that started the leg / the lower FVG under the setup [our interpretation]; (c) a NEW PD array (FVG/OB) forms after the stop-out. Then allow a same-direction re-entry by limit at that new array only (no market chase). Short example (104): after the stop, wait for price to trade below the HTF SIBI low, then short its return to the SIBI bottom edge; stop above the highest high formed, or above the CE of a new higher wick. Size: half the previous risk per X13 (070/cc02_005/cc06_003); 060 and 104 give no size cut, so test half vs same.
- **Sources:** 060_ZtLMTXv-Dr0 ~01:22:23; cc02_005_vWDElb65YHg ~00:03:34; 104_iKsIbUblSWM ~00:45:43.
- **Quotes:** "if I get stopped out and the criteria still existing ... I will re-enter" (060); "it doesn't mean the trades completely no longer viable" (cc02_005).
- **Conflicts:** X13 half risk (070; cc02_005; cc06_003) vs 060 and 104 with no size reduction.
- **[our interpretation]:** condition (b).
- **Rulebook fix:** X13b: "Idea intact = draw untouched, no opposing MSS, no close beyond the leg's origin swing; a sweep of the MT stop is not unraveling (cc02_005 ~3:34). Re-enter only on the next new signal, by limit at a PD array formed after the stop; never chase (060 ~1:22). Size half (070; cc02_005) or same (060; 104): test both."
- **BUILD SPEC (setups_models; refines section 3 X13b "gated reentry_half"):**
  - Where: replace X13b's "restored sweep with fvg after the stop" trigger with `setups.reentry_ok(mode="loss")` (the three conditions above; (b) uses the trade's `swept`/leg-origin swing stored on `Trade`). Variant `reentry_trigger="sibi_return"` (104): after the stop, wait for a 1-tick trade beyond the entry array's far edge, then a limit at that edge on the return; stop above the highest high since the stop (or the CE of a new wick when `reentry_stop="wick_ce"`, using `wick_ce` from stops_sizing_scaling_in). Size: `reentry_risk_mult` replaces the hard 0.5 at ~2876 / ~2923.
  - Params: `reentry_trigger: str = "new_array"` ("new_array" / "sibi_return"), `reentry_risk_mult: float = 0.5` (test 1.0), `reentry_stop: str = "array"` ("array" / "wick_ce").
  - Test: `test_reentry_after_loss_gate`. Long stopped at the MT; (i) draw untouched + new bullish FVG -> limit armed at 0.5 risk; (ii) opposing MSS before the FVG -> none; (iii) `reentry_risk_mult=1.0` -> full risk; (iv) no market entry is ever armed.

### 5. D18-reentry-count-max-2
- **rule_id / kind:** D18 / unlisted_contradiction. Scope: general. judgment = true.
- **Rule:** Allow up to `reentry_max` same-direction re-entries while the idea is intact (X13 conditions), each at half the previous attempt's risk (2% -> 1% -> 0.5%), each on a new or retested order block after the prior stop, with the stop below the whole OB rather than its mean threshold. `reentry_max` = 2 (cc02_005 demo: three total attempts); test vs 1.
- **Sources:** cc02_005_vWDElb65YHg ~00:13:41.
- **Quote:** "when it comes back down into this order block here that would be another opportunity" (cc02_005).
- **Conflicts:** D18 recommends a single re-entry vs cc02_005 ~13:41 showing two.
- **Rulebook fix:** D18: "ICT demonstrates up to two re-entries, each at half the prior risk (2% -> 1% -> 0.5%), stop under the whole OB (cc02_005 ~12:30-14:30). Test reentry_max 1 vs 2."
- **BUILD SPEC (management_exits):**
  - Where: `_after_close` ~1873: `state["reentered"][session]` becomes a count; re-open the session while `count < p.reentry_max`; the risk multiplier passed to `_scan` / `pm_reversal` (~2876, ~2923) becomes `p.reentry_risk_mult ** count`. Each re-entry needs `reentry_ok(mode="loss")` with an OB formed or retested after the last stop; with `reentry_ob_stop="full"` the stop goes below the OB's low (not its MT).
  - Params: `reentry_max: int = 1` (test 2), `reentry_ob_stop: str = "mt"` ("mt" / "full").
  - Test: `test_reentry_count`. Two consecutive losing stops: `reentry_max=1` arms one re-entry at 0.5; `=2` arms a third at 0.25; risk of attempt 3 computed from the OB low when "full".

### 6. X13-swing-reentry-next-htf-array
- **rule_id / kind:** X13 / missing_condition. Scope: general. judgment = true.
- **Rule:** [swing, parked per M17] On a swing stop-out (long; mirror for short): re-check the original reasons (HTF bias and gates). If they are still valid, do not re-use the failed array. Arm the next entry at the next lower untested 4H discount array; if the 4H has none, use the nearest daily, then weekly, then monthly discount array (cc06_003; cc06_008 "new M/W/D array"). Size = 50% of the trade that just failed (cc06_003). Never size up to win it all back; recovery may take several trades. Keep the HTF idea while the layered M/W array holds; price trading into its MT or low is tolerated (cc06_005). The invalidation threshold is our interpretation. ICT states no count limit either way, so it is a test parameter.
- **Sources:** cc06_003_g--tikwaupk ~00:23:43; cc06_005_soY9zX3gt2U ~00:30:49; cc06_008_VL4YLTRerHY ~00:17:34.
- **Quotes:** "you're going to refer to the Daily the weekly and the monthly discount arrays" (cc06_003); "re-enter at a new monthly weekly or daily discount array" (cc06_008).
- **Conflicts:** none real (cc06_005/008 are silent on size).
- **[our interpretation]:** the invalidation threshold; the count limit as a parameter.
- **Rulebook fix:** X13/E10 (swing note, parked): "Swing stop-out: re-check the reasons; re-enter only at a NEW, lower 4H discount array, else daily/weekly/monthly; 50% of the failed size; M/W array may be traded into its MT/low (cc06_003; cc06_005; cc06_008)."
- **BUILD SPEC (bias_htf, research study):**
  - Where: `study.py` new `swing_reentry_study(daily, h4)`: simulate a swing long at a 4H discount array (`htf._arrays` on 4h bars) under a bullish M/W bias; on a stop, pick the next lower untested 4H array, else D/W/M (`htf._arrays` per tf, `known_of` respected); size 0.5x per consecutive failure; void when a M/W array body-closes beyond its far edge [our interpretation]. Report hit rates and recovery fraction by attempt number.
  - Params (study args): `swing_reentry_max` (1/2/3/none), `swing_void="mw_far_edge"`.
  - Test: `test_swing_reentry_cascade` (tests/test_bias_htf.py). Synthetic daily/4h frames: a failed 4H array long picks the next lower 4H array, and with none falls to the daily array; the failed array is never reused.

### 7. X13-reverse-after-failure-switch
- **rule_id / kind:** X13 / unlisted_contradiction. Scope: general. judgment = true.
- **Rule:** Default: no reversal after a loss (X13). Experienced test switch `reverse_after_failure` (D18 option B, extended): at most one opposite trade per session, reduced size (102: "half the leverage"). Variants: (a) 094: the position is clearly offside and moving aggressively against the entry before the stop is hit -> close, and use the stop price as the opposite-direction entry. Trigger thresholds are ours to define and test. (b) 102: after a breaker/mitigation block/FVG fails, trade its inversion when price returns and the inversion holds (per A8 validity). (c) cc04_008: a propulsion-block entry loses its MT -> stand aside or look for a reversal short (needs MSS + FVG, our wording). (d) 045: after a small aborted loss, the opposite trade in the sick-sister index (M16). Add 045, 102 and cc04_008 to D18 B; 094 is already listed.
- **Sources:** 045_DNi9S3_NA44 ~02:51:00; 094_2AC4IKTj2ug ~00:03:05; 102_uzPM1CuSSx8 ~01:47:19; cc04_008_glu98jAH8vE ~00:05:36.
- **Quotes:** "I closed the position and used the stop loss order as my entry" (094); "if I use a mitigation block and it fails ... I can trade it inverse" (102).
- **Conflicts:** X13 "lose in the AM -> do not reverse" (Ep 01; 001) and bot `lost_side` vs 045, 094, 102, cc04_008.
- **[our interpretation]:** variant (a) offside thresholds; variant (c) MSS + FVG requirement.
- **Rulebook fix:** D18 option B: add 045 (sick sister after an aborted loss), 102 (inversion of a failed breaker/mitigation block, half leverage) and cc04_008 (failed propulsion block -> sidelines or reversal). Keep "experienced only; max one per session".
- **BUILD SPEC (setups_models; extends section 3 X13a `reverse_in_session`):**
  - Where: `_after_close` sets `idea["last_close"]` with the failed array (`tr.entry_kind`, array bounds). In the side loop (~2904), when `reverse_after_failure != "off"` and `state["reversed"][session]` is unset, allow the opposite side only through `setups.reverse_entry(ctx, sd, i, p, idea, variant)`:
    - "inversion" (102): the failed array becomes an IFVG/inverted breaker; limit at its near edge on the return, stop beyond its CE + `stop_pad`, A8 validity check.
    - "at_stop" (094): in the position loop, if the open trade is offside by >= `offside_frac` x (entry->stop) with bodies closing beyond the entry FVG [our interpretation], close at market (`exit kind "offside"`) and arm a stop order at the old stop price in the opposite direction; stop beyond the adverse leg extreme; target the nearest opposite pool.
    - "prop_fail" (cc04_008): the trade's entry kind is a propulsion block and a body closes through its MT -> stand aside, or with MSS + FVG against it, one reverse.
    - "sick_sister" (045): delegate to the built `sick_sister` branch (setups.py, M16) with the partner frame, after a loss <= 0.5R.
  - Risk mult `reverse_risk_mult=0.5`; `state["reversed"][session]=True` after arming.
  - Params: `reverse_after_failure: str = "off"` ("off" / "inversion" / "at_stop" / "prop_fail" / "sick_sister" / "all"), `reverse_risk_mult: float = 0.5`, `offside_frac: float = 0.5`.
  - Test: `test_reverse_after_failure` (tests/test_setups_models.py). A breaker long fails (body close below), price returns to it -> short limit at the inverted breaker at 0.5 risk; a second reversal in the same session is refused; "off" leaves trades identical.

### 8. X14-opposite-second-trade-after-win
- **rule_id / kind:** X14 / unlisted_contradiction. Scope: general. judgment = true.
- **Rule:** Switch `allow_opposite_after_target` (default off). (a) 093 (index): with a bullish daily bias and a predefined low-of-day level below price, a short toward that level is allowed (partials at intermediate lows, exit just above the level). Once it is reached, flat, then look for a long toward the daily draw. At most one short + one long per AM. 093 shows the plan; only the short was taken. (b) cc10_007 (T-bond split-session profile, not index-specific): a PM trade opposite the AM trend after a noon reversal profile is allowed ONLY if the AM did not deliver the bulk of the day's expected range. If it did, skip the PM (cc10_007 ~9:05). Test against `no_pm_after_am_win`.
- **Sources:** 093_CcNOk_3O5wk ~00:14:52; cc10_007_JpV-J31mxhg ~00:12:21.
- **Quotes:** "sell short here ride all the way down ... and then look for the move in here where I can go long" (093); "the split session rules ... both offering opportunities one for buy and one for a sell" (cc10_007).
- **Conflicts:** X14 "no re-entry after a winner" (095), "AM wins -> skip PM" (065B), D19 one AM + one PM vs 093 and cc10_007.
- **[our interpretation]:** the low-of-day level definition (daily wick CE confluent with an intraday discount array).
- **Rulebook fix:** X14: "Exception (experienced, 093): a counter-bias short into a predefined low-of-day level, then a long from that level toward the daily draw; one of each per AM. Split session (cc10_007): PM opposite the AM only if the AM did not deliver the bulk of ADR (else skip PM, cc10_007 ~9:05)."
- **BUILD SPEC (setups_models + management_exits):**
  - Where: (a) new `setups.lod_level(ctx, p)` = the daily wick CE (`wick_days` levels, built) that has an intraday discount array (C rows) within `lod_conf_pts`; under the switch, a counter-bias short is allowed only when its final target is that level (target capped at level + 1 tick); `_after_close` on reaching it sets `done[session]=False` once and forces the next side to `want` (bias side). (b) PM: allow the side opposite the AM trade only when `idea["AM"]` closed at target and `am_range < skip_pm_adr_k x adr5` (reuses X10d `am_range_skip_pm` helper) and a PM MSS against the AM direction formed after 12:00.
  - Params: `allow_opposite_after_target: str = "off"` ("off" / "lod" / "split" / "both"), `lod_conf_pts: float = 2.0`.
  - Test: `test_opposite_after_target`. Bullish bias, wick-CE level below: short to the level closes at +X, a long then arms at the level; a third trade is refused. Split: AM range 0.9 x ADR5 -> no PM short.

### 9. N3-021-citation-misread
- **rule_id / kind:** N3 / wrong. Scope: general. judgment = false.
- **Rule:** Remove 021 ~43:56 as the source of an FOMC re-entry ban in N3, X13 and D18. The FOMC rule rests on N3's 14:00-14:45 observation-only rule and the bot's FOMC-PM block; 021 shows an AM trade taken that day. Add a general rule (021 ~44:00, normal day): when a winner is mostly closed near its target and the small remainder sits on a very tight stop, a stop-out of that remainder ends the trading for that move (no re-entry). If the final target is reached, close the charts for the session.
- **Sources:** 021_DVxC7UAHzwk ~00:44:08.
- **Quote:** "if this was any other day and I was in it trading it I'd have just about everything off the position" (021).
- **Conflicts:** N3/X13/D18 citation of 021 vs what 021 says.
- **Rulebook fix:** N3, X13, D18: delete "(021 ~43:56)" from "Don't re-enter if stopped on FOMC"; the FOMC no-re-entry stays as an N3.5 design choice resting on the FOMC PM block. Add X14e: "Runner stopped on a tight stop after the bulk was banked near the target: no re-entry for that move; final target hit: done for the session (021 ~44:00)."
- **BUILD SPEC (management_exits):**
  - Where: `_after_close`: when the trade had partials totalling >= `runner_frac_done` of size and its last exit is the stop, tag `last_close.kind="runner_stop"`; the re-entry switches of items 2-3 refuse that kind. When the final rung (T-last) filled, `done[session]=True` and the SB key for that session too. News package: change the comment / source of `fomc_no_reentry` (section 3 N3.5) to "design choice, no source" (default stays as section 3 sets it).
  - Params: `runner_frac_done: float = 0.75`.
  - Test: `test_runner_stop_no_reentry`. With `reentry_after_trail_win=True`, a trade with 80% closed at partials and the rest stopped -> no re-entry armed; with 30% closed -> re-entry path allowed.

---

## B. Session stops and in-day frequency (X7, X14, X15, L15, N9)

### 10. L15-chop-micro-scalps
- **rule_id / kind:** L15 / unlisted_contradiction. Scope: index. judgment = true.
- **Rule:** Unlisted contradiction: L15 minimum room is 5 pts (10 for new traders) vs 010 ~1:16:00, ~2.5-handle micro scalps (sell a retrace into a 1m FVG, target the nearest short-term low, about two per day for ~5 handles). In the same passage ICT prefers a 10-handle range before engaging. New traders study chop and do not trade it; seasoned traders turn charts off. Optional experienced test switch `chop_scalp` (default off): min room 2.5 pts, max 2 scalps/day, stop after ~5 pts total.
- **Sources:** 010_cWekmMLqiNM ~01:15:51.
- **Quote:** "that's a very very small little micro range but that's two and a half handles" (010).
- **Conflicts:** L15 room (010 ~1:15:16 "give me 10 handles") vs the 2.5-handle chop scalps in the same video.
- **Rulebook fix:** L15: add "010 ~1:15-1:17: ICT can take ~2.5-handle micro scalps in chop (1m FVG retrace -> short-term low, two for ~5 handles) but prefers a 10-handle range; new traders study chop, seasoned traders turn charts off."
- **BUILD SPEC (management_exits; extends `sloppy_mode="scalp"`, strategy.py ~4237):**
  - Where: the scalp branch ~4237 currently exits at min(+5, T1). Add `chop_scalp_pts`: when > 0, the scalp's only exit is the nearest short-term pool within `chop_scalp_pts` (min room = that value instead of `min_draw_pts`), entries only at a 1m FVG retrace; `state["chop_scalps"]` counts; stop the day after `chop_scalp_max` scalps or `chop_scalp_day_pts` net.
  - Params: `chop_scalp_pts: float = 0.0` (test 2.5), `chop_scalp_max: int = 2`, `chop_scalp_day_pts: float = 5.0`.
  - Test: `test_chop_scalp_cap`. Chop day with `sloppy_mode="scalp"`, `chop_scalp_pts=2.5`: two scalps of +2.5 then nothing more; normal days unaffected.

### 11. N9-pm-narrative-from-am-chop
- **rule_id / kind:** N9 / missing_rule. Scope: general. judgment = true.
- **Rule:** If the AM is chop: at 13:30 check (a) a large opening gap still unfilled on the opposite side of price, (b) SMT at the AM extreme (e.g. ES lower low not confirmed by NQ), (c) repeated AM runs of the nearby lows/highs without expansion. If all hold, the PM bias is toward the unfilled gap; target the gap's level (022: 4121-4123). If that level already printed before 13:30, cancel the PM idea. If the PM attempt fails, accept the loss (no fix-up trades).
- **Sources:** 022_ALMsQytQ1fg ~02:26:36.
- **Quote:** "What what happens if you come back at 1:30 and it has already done that? Then it's over." (022)
- **Conflicts:** none.
- **[our interpretation]:** "large" gap size and "repeated runs" counts (below).
- **Rulebook fix:** N9: add N9.7 "Chop AM -> PM narrative (022 ~2:25-2:27): unfilled opening gap + SMT at the AM extreme + repeated AM raids without expansion -> PM bias toward the gap; void if the gap level printed before 13:30; one attempt only. ICT: not an invitation for new traders."
- **BUILD SPEC (day_week_context):**
  - Where: `run_day` at the first PM bar: `pm_narrative(ctx, p, i)` -> side or None. (a) ORG (`ctx` opening-gap levels, L7) with unfilled part on the opposite side and size >= `pm_narr_gap_pts`; (b) the built `_smt` check at the AM extreme vs the partner frame; (c) >= 2 AM 1-tick runs of AM swing lows (highs) with no bar range > `displacement_mult` x average. Requires the AM flagged chop (`chop.on` during the AM or no AM fill). If the gap level traded between 12:00 and 13:30 -> None. Result sets the PM `want` to that side and the PM draw lock to the gap level; `done["PM"]` after one PM trade regardless of outcome.
  - Params: `pm_narrative: bool = False`, `pm_narr_gap_pts: float = 5.0`.
  - Test: `test_pm_narrative_chop` (tests/test_day_week_context.py). Synthetic ES/NQ pair: gap above unfilled, ES lower low not confirmed by NQ, chop AM -> PM want = long, target = gap level; same frames with the gap filled at 13:00 -> no PM trade.

### 12. new-am-search-timebox-60min
- **rule_id / kind:** new / missing_rule. Scope: index. judgment = true.
- **Rule:** AM search time box (test parameter `am_search_minutes`, default off): about one hour of looking ("an hour or so", 042 ~6:20), then cancel pending orders and stop for the session. The anchor (session start vs 09:30) is our interpretation. Test 60 and 90 min from 09:30 vs off, and keep SB-window entries (10:00-11:00) exempt or test the conflict explicitly.
- **Sources:** 042_hQ379EuyNKQ ~00:05:55.
- **Quote:** "usually I do about an hour or so and then I cut bait" (042).
- **Conflicts:** Silver Bullet 10:00-11:00 (M3) extends past a 60-minute box from 09:30.
- **[our interpretation]:** the 09:30 anchor.
- **Rulebook fix:** T4/T5: add "ICT usually looks for about an hour, then cuts bait (042 ~6:20; stayed longer that day for teaching)."
- **BUILD SPEC (news_calendar_times):**
  - Where: `run_day` bar loop before `skip_main` (~2857): if `am_search_minutes` and session == "AM" and no AM fill yet and `t >= 570 + am_search_minutes`: cancel a pending AM order, `done["AM"]=True`; `SB_AM` stays open unless `am_search_sb="include"` (then also `done["SB_AM"]=True` and `run_sb` skips the AM window).
  - Params: `am_search_minutes: int = 0` (test 60 / 90), `am_search_sb: str = "exempt"` ("exempt" / "include").
  - Test: `test_am_search_timebox` (tests/test_news_calendar.py). A setup that would fill at 10:40: with 60 it is skipped and its pending cancelled at 10:30; an SB fill at 10:20 still happens with "exempt", not with "include".

### 13. X7-three-failures-flatten-open-trade
- **rule_id / kind:** X7 / missing_condition. Scope: index. judgment = true.
- **Rule:** When the 3rd PD array in the session fails (price does not respect it, bodies close through it): close any open position at market whatever its P/L, cancel pending orders, no new AM entries. PM per 044: study from 13:45; if nothing qualifies by 14:30, done for the day.
- **Sources:** 044_LN1nfYp4dBw ~01:54:41.
- **Quote:** "if you have a trade you get out of it regardless of wherever it is" (044).
- **Conflicts:** none.
- **Rulebook fix:** X7c: "Three failed arrays -> cut bait: flatten any open trade at market regardless of P/L, cancel orders, done for the AM; PM from 13:45, done if nothing by 14:30 (044 ~1:54)."
- **BUILD SPEC (management_exits; extends section 3 X7c `session_stop_after_fails`):**
  - Where: X7c's session array-fail counter (arrays mode). On the 3rd fail: if `pos` open, exit at the bar close (`exit kind "pd3_session"`), `pending=None`, `done[session]=True` and `done["SB_"+session]=True`. When session == "AM" and `pd3_pm_window` on: the PM entry window becomes 825-870 (13:45-14:30) for that day.
  - Params: `session_fail_flatten: bool = False`, `pd3_pm_window: bool = False`.
  - Test: `test_three_fails_flatten`. Open long while a third bullish array fails -> closed at that bar's close at a loss, no further AM entries; PM entries only between 13:45 and 14:30.

### 14. X15-one-am-trade-is-sb-priority
- **rule_id / kind:** X15 / wrong. Scope: index. judgment = false.
- **Rule:** Replace "one AM SB trade a day (047 ~8:00)" in M3, X15 and D19 with: if limited to one AM trade, choose the 10:00-11:00 Silver Bullet (047 ~8:00). Parameter: when max AM trades = 1, only the SB setup is eligible in the AM. Any one-SB-per-day cap is a separate tested parameter without 047 as its source.
- **Sources:** 047_441vklRYYR4 ~00:08:02.
- **Quote:** "if I was only going to trade one time a day in the morning where would I focus between 10 o'clock and 11 o'clock" (047).
- **Conflicts:** none.
- **Rulebook fix:** M3, X15b, D19: as the rule above.
- **BUILD SPEC (silver_bullet):**
  - Where: `run_day` ~2849: when `one_am_trade_mode="sb_only"`, skip the main AM scan entirely (`skip_main=True` for session "AM" outside `_in_sb`) and let only `run_sb`'s AM window (or the `SB_AM` key) trade; after any AM fill set `done["AM"]=done["SB_AM"]=True`.
  - Params: `one_am_trade_mode: str = "off"` ("off" / "sb_only").
  - Test: `test_one_am_trade_sb_only`. A day with a 09:45 main-model setup and a 10:20 SB setup: "sb_only" trades only the SB; "off" unchanged.

### 15. X14-new-trader-stop-when-day-positive
- **rule_id / kind:** X14 / missing_condition. Scope: index. judgment = true.
- **Rule:** New-trader mode: stop for the day once realized day P&L after commissions is > 0 (102 ~1:52). Trade the AM (08:30-11:00) or the PM, not both by default, and no PM after an AM win (065 ~4:15, new students only). PM/last-hour recovery of a losing AM is experienced-only (102 ~2:01:30). Experienced-mode switch `pm_after_am_win`: a PM entry is allowed after AM trades while the HTF draw is still unreached (056 ~8:19: AM P&L not stated, so "after an AM win" is our inference). Test both.
- **Sources:** 065_rx15_eN9sxI ~04:16:00; 102_uzPM1CuSSx8 ~01:51:30 (and ~2:01:30); 056_NeZlyG8FZLQ ~00:08:19.
- **Quotes:** "if you make money in the morning don't trade the afternoon as a new student" (065); "do you have more money today than you had at the start of the day if you do stop" (102).
- **Conflicts:** X14 "AM wins -> skip PM" (065B ~4:12) vs 056 ~8:19 trading the PM SB after AM trades.
- **[our interpretation]:** "after a net-positive AM" for 056.
- **Rulebook fix:** X14c: add "as a new student (065 ~4:15); that doesn't mean everybody stops". Add: "New trader: stop once the day is net positive after commissions (102 ~1:52); AM or PM, not both; recovering a losing AM in the PM is experienced-only (102 ~2:01). Experienced: PM after AM trades while the HTF draw is unreached (056 ~8:19)."
- **BUILD SPEC (management_exits; extends section 3 X14d):**
  - Where: `_after_close`: with `trader_mode="new"`: `state["day_net"] > 0` -> all done keys True (same loop as `day_target_pts`, ~1880); any AM trade -> `done["PM"]=True` (AM or PM, not both) unless the AM net < 0 and `pm_recover_loss` (experienced only, forced False in "new"). With `pm_after_am_win="draw_open"`: after an AM win, keep `done["PM"]` False only while `htf.table` draw for the day (`ctx` draw / lock) is untouched; else done.
  - Params: `trader_mode: str = "off"` ("off" / "new" / "experienced"), `pm_after_am_win: str = "off"` ("off" / "draw_open"), `pm_recover_loss: bool = False`.
  - Test: `test_trader_mode_day_positive`. "new": an AM +0.5R closes -> no further trade incl. SB_PM; AM loss -> no PM either (recovery off). "experienced" + "draw_open": AM win with the draw untouched -> PM trade allowed; draw hit -> PM done.

### 16. X14-beginner-template-numbers
- **rule_id / kind:** X14 / shortened. Scope: index. judgment = false.
- **Rule:** New-trader mode (095 ~47:08, his son's micro-contract example): 1 contract, one setup, target 10-15 ES/NQ handles, stop ~12 handles. On hitting the target, flat and done (no re-entry). Progression as skill grows: 20-25, then 30-50, then ~100-handle targets with far fewer trades.
- **Sources:** 095_LPmMtq9jLm8 ~00:47:08.
- **Quote:** "one contract doing one setup trying to get 10 handles or 10 to 15. risking 12 handles" (095).
- **Conflicts:** X14 bread-and-butter 5 handles (044; 046) vs 095 10-15 handles.
- **Rulebook fix:** X14: "Beginner template (095 ~47:08): 1 contract, one setup, 10-15 handle target, ~12 handle stop, stop after the target; progression 20-25 -> 30-50 -> ~100 handles with fewer trades (095 ~49:00)."
- **BUILD SPEC (management_exits; preset over existing fields):**
  - Where: `Params.__post_init__` preset `beginner_template=True` sets: fixed lot 1 (`lot=1`, risk-% sizing off via `size_mode="fixed"` if present, else `risk_pct` override computed per trade), single exit at `t1_fixed_pts=beginner_target_pts` with `t1_fixed_all=True` (built, Ep03.24), max stop `max_stop_pts=12` (skip setups whose stop > 12), `trader_mode="new"` (item 15). Progression = study grid over `beginner_target_pts` (10, 15, 25, 40, 100).
  - Params: `beginner_template: bool = False`, `beginner_target_pts: float = 12.5`, `max_stop_pts: float = 0.0` (0 = off).
  - Test: `test_beginner_template`. A setup with a 14-pt stop is skipped; one with 8 pts trades 1 unit, exits at +12.5, then no more trades that day.

### 17. X14-conflicted-htf-one-entry
- **rule_id / kind:** X14 / shortened. Scope: index. judgment = false.
- **Rule:** If the HTF narrative is conflicted (both sides valid, price inside an unresolved daily imbalance): prefer no trade until price leaves the range. If trading, take at most one entry and stop after it wins (091 ~8:30-10:50). Additional 1m scalps only in experienced mode.
- **Sources:** 091_1PkTGkOjoGo ~00:10:44.
- **Quote:** "forces your hand to be a intraday scalper ... you get really one entry and that's it" (091).
- **Conflicts:** none.
- **Rulebook fix:** X14b: "Also when the HTF narrative is conflicted (both sides valid, inside a daily BISI/SIBI): prefer no trade; at most one entry, stop after a win; more 1m scalps only for experienced traders (091 ~8:30-10:50)."
- **BUILD SPEC (management_exits; extends section 3 X14b `chop_one_win`, reuses B17.1 detector):**
  - Where: day flag `conflicted` = B17.1 `neutral_5050` both-sides test (bias_htf) OR the `inside_bisi` sloppy test (built, B17.4). Under `conflicted_mode`: "skip" -> return [] in `run_day` like `sloppy_mode`; "one" -> after the first fill all done keys True for the day (win or loss); "one_win" -> done after the first win only.
  - Params: `conflicted_mode: str = "off"` ("off" / "skip" / "one" / "one_win").
  - Test: `test_conflicted_one_entry`. Day tagged inside_bisi: "one" yields at most 1 trade; "skip" yields 0; untagged day unchanged.

### 18. X15-monthly-cap
- **rule_id / kind:** X15 / missing_rule. Scope: general. judgment = true.
- **Rule:** Parameter `max_trades_month`: test 3 (student, 095 ~49:31) vs ~10 (cc02_004 ~17:05, return-math illustration at 5:1 RR) vs uncapped. No requirement to trade every session or every month. Optional `skip_months` switch; the months come from our own mapping (B23 Mar/Jun/Aug, N7 August), not from cc02_004.
- **Sources:** 095_LPmMtq9jLm8 ~00:49:31; cc02_004_pFdW8wdR9sQ ~00:17:05.
- **Quotes:** "you can make a lot of money doing three trades a month" (095); "you don't have to trade every single month" (cc02_004).
- **Conflicts:** 095 ~3/month vs cc02_004 ~10/month; both below X15's ~3/week (099).
- **[our interpretation]:** the skip_months mapping.
- **Rulebook fix:** X15: add X15e "Month: a student needs ~3 trades a month (095 ~49:31); 10/month appears only as return math (cc02_004 ~17:05); some months need not be traded (unnamed)."
- **BUILD SPEC (day_week_context):**
  - Where: `backtest.run` (~293): month counter beside the weekly one; skip the day when `month_n >= max_trades_month`; truncate `day_trades` in entry-time order. Also pass `week["month_n"]` into `run_day` so the in-day loop stops arming once the cap is reached (fixes the truncation-order issue for this cap). `skip_months`: tuple of month numbers -> `blocked()` returns "month".
  - Params: `max_trades_month: int = 0`, `skip_months: tuple = ()`.
  - Test: `test_month_cap` (tests/test_day_week_context.py). Synthetic month with 6 trade days: cap 3 -> exactly the first 3 trades by entry time; `skip_months=(8,)` -> no August trades.

### 19. X15-frequency-scaling-graduation
- **rule_id / kind:** X15 / missing_rule. Scope: general. judgment = true.
- **Rule:** New-trader mode: one market, one condition, target one good setup per week (064), at most ~2 per week (cc01_001). Accept no-trade days; do not add markets to trade daily (cc01_001: four FX pairs with one condition gives ~1/day, deferred until experienced). Experienced mode: the same model on a lower timeframe for more occurrences per week (064 ~1:38), daily caps still apply.
- **Sources:** 064__YTK5uXBe4o ~01:37:56; cc01_001_0LhteuLVuDU ~00:19:44.
- **Quotes:** "you can take that and reduce it to a smaller time frame and you can find more of that same model" (064); "you're not going to get a trade every single day but you can get a couple of them every single week" (cc01_001).
- **Conflicts:** none.
- **Rulebook fix:** X15: add "Frequency scales with markets x conditions: one condition on one market ~1-2 a week (064; cc01_001); more comes from the same model on a lower timeframe with experience, not from adding markets."
- **No new build spec:** covered by existing switches. New-trader preset = one symbol per run, one setup family, `max_trades_week=2`; graduation = rerun with a lower `tf` (5 -> 1). Add the preset row to `trader_mode="new"` (item 15) as `max_trades_week=2` when that field is 0.

### 20. X15-three-per-week-htf-quality
- **rule_id / kind:** X15 / missing_condition. Scope: general. judgment = false.
- **Rule:** Max ~3 trades per week (099 ~47:36). Eligible only if the setup forms on the 4h or 1h chart and targets a weekly or daily array/liquidity pool.
- **Sources:** 099_v_iJlBKYmUc ~00:47:36.
- **Quote:** "you really limit it down to the very best of the best setups from a four hour an hourly chart" (099).
- **Conflicts:** none.
- **Rulebook fix:** X15a: "~3 a week (099 ~47:36), only setups formed on the 4h/1h chart toward a weekly or daily objective."
- **BUILD SPEC (day_week_context + bias_htf gate):**
  - Where: `_scan` final gate (setups_models-owned bias block ~1138-1170 in section 3 terms; current `_scan_core` target merge): when `htf_quality_only`, require (a) the trade's final target level kind in {daily/weekly array, PDH/PDL, PWH/PWL, NWOG} (`pos["level_kinds"]`, built) and (b) a 1h or 4h structure tag: the sweep or the MSS reference swing is a 1h/4h swing (`levels.swing_tiers`, built, with `mss_ref_tf` in {"60","240"}). Combine with `max_trades_week=3`.
  - Params: `htf_quality_only: bool = False`.
  - Test: `test_htf_quality_only`. Two setups, one targeting a 1m swing high, one targeting PDH with a 1h MSS reference: only the second trades.

### 21. X15-weekly-goal-stop
- **rule_id / kind:** X15 / missing_rule. Scope: general. judgment = true.
- **Rule:** Starter mode: risk 1.5% per trade; `weekly_target_pct` = 1.5 (6%/month; 20 pips/week at 1:1, cc02_001 ~14:36-22:57). Once realized weekly P&L >= target, `stop_week_on_goal`: no new trades until next week. ICT's own weekly goal: 50-75 pips, with nothing above it (cc02_001 ~14:36); a 100-pip weekly range is an occasional aim (cc02_003). Up to 2-3 trades toward the goal, never forced (cc02_003 ~13:56). All sources are FX; the index point equivalent is our interpretation. Test against `max_trades_week` alone.
- **Sources:** cc02_001_mjVHmE1gVMg ~00:22:57, ~00:14:36; cc02_003_pctqB3UD6dk ~00:13:56.
- **Quotes:** "you're over in a couple hours you're done for the week" (cc02_001); "it may require you to do a second trade or a third trade" (cc02_003).
- **Conflicts:** goal size 1.5% vs 50-75 pips vs ~100 pips; X15 cites cc02_003 ~12:03 for one setup/week while ~13:56 allows 2-3.
- **[our interpretation]:** index points equivalent (`weekly_cap_pts`).
- **Rulebook fix:** X15: add X15f "Weekly goal (cc02_001; cc02_003, FX): starter 1.5%/week at 1.5% risk 1:1; ICT 50-75 pips/week; up to 2-3 trades toward it, never forced; done for the week once met." Fix the cc02_003 citation: it allows 2-3 trades.
- **BUILD SPEC (day_week_context):**
  - Where: `backtest.run`: after each day, `week["net"]` in % of start-of-week equity (`account_equity` + closed P&L) and `week["pts"]`; when `>= weekly_target_pct` (or `>= weekly_cap_pts` ES pts) set `week["done"]=True, done_reason="goal"`; skip later days of the week. Inside `run_day`, `_after_close` updates `week` and sets all done keys when the goal is reached intraday. Never adds trades (cap still `max_trades_week`).
  - Params: `weekly_target_pct: float = 0.0` (test 1.5), `weekly_cap_pts: float = 0.0` (test 10-15 [our interpretation]).
  - Test: `test_weekly_goal_stop`. Week where Monday nets +1.6% -> Tue-Fri skipped; nets +1.0% -> Tuesday trades.

### 22. new-rr-month-gate
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** Optional switch `rr_month_gate`: until 1-2 big-RR winners (big_rr = 5 [our interpretation]; test 3) have closed this calendar month, require final-draw RR >= big_rr. After that, setups with RR 2-3 are allowed. Default off; compare against fixed min RR.
- **Sources:** cc02_001_mjVHmE1gVMg ~00:12:11.
- **Quote:** "once you get one or two of them in your month ... you can now start lowering your risk to reward ratio" (cc02_001).
- **Conflicts:** none.
- **[our interpretation]:** big_rr = 5.
- **Rulebook fix:** E/X section: add "After one or two big-payout winners in the month, 2:1-3:1 setups are acceptable if you want to stay busy (cc02_001 ~12:11)."
- **BUILD SPEC (targets_partials gate, state from day_week_context):**
  - Where: `backtest.run` counts trades this month with realized R >= `rr_big` into `week["month_big"]`. In the `_scan_core` target merge (the min-RR / `min_draw_pts` check), required final-draw RR = `rr_big` while `month_big < rr_n_big`, else `rr_relaxed`.
  - Params: `rr_month_gate: bool = False`, `rr_big: float = 5.0`, `rr_n_big: int = 1`, `rr_relaxed: float = 2.0`.
  - Test: `test_rr_month_gate`. A 3R setup early in the month is skipped; after a 5R winner closes, an identical 3R setup trades; the counter resets on the 1st.

### 23. X15-all-conditions-days-only
- **rule_id / kind:** X15 / missing_rule. Scope: general. judgment = true.
- **Rule:** Filter `trending_day_only` (switch vs every-day baseline): allow entries only when the full N8 recipe holds: small/contracting prior ranges, price at a daily discount/premium array, high/medium 08:30 news, and the treasury bond divergence/expansion trigger where data exists (cc10_009). No daily quota and no fallback trade (cc09_001 ~10:17; 102 ~2:01). Do not import the cc09_001 London/Asian-range checklist (FX, M17).
- **Sources:** cc09_001__TNhWRPa6GA ~00:10:17; cc10_009_S0ouOvtjV2I ~00:11:05.
- **Quotes:** "day trading is not everyday trading" (cc09_001); "keep your opportunities few and far between and high highly selected cherry picking situations" (cc10_009).
- **Conflicts:** none.
- **Rulebook fix:** N8.2: "Use the recipe as a gate, not only a tag: trade only days where all of it holds; no daily quota, no fallback trade (cc09_001 ~10:17; cc10_009 ~11:05)."
- **Already listed:** section 3 day_week_context N8.2 "trend_recipe tag/only/side" is this gate ("only" mode). No new build spec; the bond trigger needs data.

### 24. X15-position-trade-frequency
- **rule_id / kind:** X15 / missing_rule. Scope: general. judgment = true.
- **Rule:** HTF position model (parked module): expect about 2 good setups per calendar year, 3 if conditions are very symmetrical, rarely 4 (at most one per quarterly shift). Take only very clear, high-odds setups.
- **Sources:** cc05_013_crPpMwgwa7k ~00:24:19.
- **Quote:** "i look personally for two and if i'm lucky three good position trade setups a year" (cc05_013).
- **Conflicts:** none.
- **Rulebook fix:** X15 (position note, parked M17): "Position trades: ~2 a year, 3 if lucky, rarely 4 (one per quarterly shift) (cc05_013 ~24:19)."
- **BUILD SPEC (bias_htf, research study):**
  - Where: any future position-model study in `study.py` reports signals per calendar year and per quarter and flags parameter sets producing > 4/yr or > 1 per quarter as over-firing.
  - Params (study args): `pos_max_per_quarter=1`, `pos_flag_per_year=4`.
  - Test: `test_position_freq_flag` (tests/test_bias_htf.py). A synthetic signal list with 2 in one quarter keeps only the first and raises the flag at 5/yr.

### 25. X15-swing-frequency
- **rule_id / kind:** X15 / missing_rule. Scope: general. judgment = true.
- **Rule:** Swing module (parked): expect about 1 (occasionally 2) swing setups per 4-6 weeks, limited to seasonally poised markets. Target about 6 choice swings a year and skip any that does not look right. Swing trading is the alternative for traders who cannot day trade or short-term trade. Thresholds such as min R or a max-signals/yr flag are [our interpretation].
- **Sources:** cc06_006_JAjL7rUX2Iw ~00:14:25; cc06_008_VL4YLTRerHY ~00:33:59.
- **Quotes:** "there's typically one to two swing trades per every four to six weeks" (cc06_006); "swing trades again they only set up around 4 to 6 weeks" (cc06_008).
- **Conflicts:** none.
- **[our interpretation]:** min R and the over-firing flag.
- **Rulebook fix:** X15 (swing note, parked M17): "Swings: ~1 (sometimes 2) per 4-6 weeks per seasonally poised market, ~6 choice swings a year; skip any that doesn't look right (cc06_006; cc06_008)."
- **BUILD SPEC (bias_htf, research study):**
  - Where: swing study in `study.py`: one open swing per market; report signals per 4-6 week block and per year; flag > 12/yr [our interpretation]; run as a separate book from intraday results.
  - Params (study args): `swing_one_open=True`, `swing_flag_per_year=12`.
  - Test: `test_swing_one_open` (tests/test_bias_htf.py). Overlapping swing signals: the second is dropped while the first is open.

### 26. new-frequency-by-origin-tf
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** Short-term (OSOK) framing: a monthly/weekly-origin PD array can yield several sequential short-term setups toward the opposing weekly array while the target is unmet. A 4h-origin frame yields fewer (not a hard cap of one), but they are still high probability.
- **Sources:** cc07_001_mQA8jCem9d0 ~00:18:29.
- **Quote:** "if it's a weekly or it's a monthly level we could potentially see multiple short-term trades form" (cc07_001).
- **Conflicts:** none.
- **Rulebook fix:** M17 (OSOK statistics): "Monthly/weekly-origin frames can give several sequential short-term trades toward the target; 4h-origin frames fewer (cc07_001 ~18:29)."
- **BUILD SPEC (bias_htf, research study; OSOK stays statistics-only per M17):**
  - Where: `study.py` OSOK study: tag each short-term signal with its origin array tf (`htf._arrays` tf of the array the leg started from) and count sequential signals per frame until the target is hit. Report the distribution by origin tf.
  - Params (study args): `osok_origin_tfs=("M","W","D","4h")`.
  - Test: `test_osok_origin_tag` (tests/test_bias_htf.py). A synthetic weekly-origin leg with two signals before the target counts 2 for "W".

---

## C. Day-of-week and week-level stops (N10, M14, N7, N8, N9, X10, X13, B17)

### 27. N10-unmet-target-carries-to-monday
- **rule_id / kind:** N10 / missing_rule. Scope: general. judgment = false.
- **Rule:** If the weekly draw is not reached by the Friday close (late in the week), keep the bias and the target for Monday and/or Tuesday of the next week. Stay with the bias (no counter-bias trades) until the target is hit, then go neutral or sidelined. Weekend holds remain banned for the bot.
- **Sources:** 061_wWvXWmC_gqU ~02:32:51.
- **Quote:** "they're going to leave that portion open and trade it in Monday" (061).
- **Conflicts:** none.
- **Rulebook fix:** N10: add N10.6 "Weekly draw unmet at Friday's close -> carry bias and target into Mon/Tue; no counter-bias trades until it hits, then neutral (061 ~2:32)."
- **BUILD SPEC (day_week_context):**
  - Where: `backtest.run`: at week end, if `week["draw"]` exists and not hit, store `carry = {"side", "level", "until": next Tuesday}` into the next week's dict. `run_day` (Mon/Tue, `d <= carry["until"]`): `want = carry["side"]` when `want` is 0/None or under `carry_override`, add the level to the draw pool list (as a `carry_draw` kind); once traded through, clear `carry` and set that day's `want=0` for the rest of the week (neutral) when `carry_neutral_after`.
  - Params: `carry_weekly_draw: bool = False`, `carry_neutral_after: bool = True`.
  - Test: `test_carry_weekly_draw`. Week ends with the weekly high draw untouched: Monday only longs arm, target includes the level; after it trades Monday, Tuesday is neutral.

### 28. N10-thursday-reversal-after-targets-met
- **rule_id / kind:** N10 / missing_condition. Scope: general. judgment = true.
- **Rule:** If the week's HTF (long-term/intermediate) targets were met Mon-Wed, expect Thursday may form the opposite end of the weekly range. Don't press with-trend entries or fight the retracement, but treat it as a retracement and keep the HTF bias until close-based flips (B8). Base rate: a Wed/Thu intraweek reversal forms about once a month per market. The trigger details and test are [our interpretation].
- **Sources:** 099_v_iJlBKYmUc ~01:02:20; 100_GJeEU2oIh24 ~00:08:24; cc07_007_jvc105qaCJs ~00:22:51.
- **Quotes:** "it's likely that Thursday can create the low of the week" (099); "Wednesday or Thursday reversals generally form every month" (cc07_007).
- **Conflicts:** none.
- **[our interpretation]:** the mechanical trigger (Wednesday-extreme break then MSS) and the monthly-count test.
- **Rulebook fix:** N10.3: "Thursday reversal applies after the week's HTF targets were met Mon-Wed (099 ~1:02; 100 ~8:24): treat it as a retracement, don't press with-trend, keep the HTF bias until B8 flips. Base rate ~1 Wed/Thu reversal week a month (cc07_007 ~22:51)."
- **BUILD SPEC (day_week_context; extends section 3 N10 / N10.3 thu_reversal tag):**
  - Where: `day_context` (Thursday, and Friday): if `week["draw_hit"]` happened Mon-Wed, tag `thu_after_targets`; under `thu_targets_met_block`, `block_side["thu_targets"] = (week_trend_sign,)` (with-trend side blocked Thu/Fri); counter-trend trades use the nearest opposing pool as the only target (no ladder extension). Study: `study.py` counts weeks with a Wed/Thu turn (weekly extreme set Wed/Thu after Mon/Tue range > ADR5) per month.
  - Params: `thu_targets_met_block: bool = False`.
  - Test: `test_thu_after_targets_block`. Week with the weekly low draw hit Tuesday: Thursday shorts are blocked, a long to the nearest pool is allowed; same Thursday without a hit draw is unchanged.

### 29. N10-friday-skip-profitable-week
- **rule_id / kind:** N10 / missing_condition. Scope: general. judgment = true.
- **Rule:** Friday: if week-to-date P&L > 0 (or weekly targets are met), don't trade Friday; protect the week's profit. Weekly objective delivered -> done for the week (already X15).
- **Sources:** 100_GJeEU2oIh24 ~00:07:18.
- **Quote:** "it's Friday if you have profits on the week the worst thing you could possibly do is offer them up on the altar" (100).
- **Conflicts:** none.
- **Rulebook fix:** N10.4: "Skip Friday when the week is profitable, not only when the weekly targets are met (100 ~7:18)."
- **BUILD SPEC (day_week_context; extends section 3 N10 `friday_week_done`):**
  - Where: `backtest.run` before calling `run_day` on a Friday: if `skip_fri_if_week_up` and `week["net"] > 0` -> skip the day (`skips` row "fri_week_up").
  - Params: `skip_fri_if_week_up: bool = False`.
  - Test: `test_skip_friday_week_up`. Week net +0.3R by Thursday -> no Friday trades; net -0.2R -> Friday trades.

### 30. new-late-week-close-flat
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** After a losing trade, if a re-entry's open profit brings the week (or session) back to >= 0 and it is Thu/Fri or late in the session: close it and move to the sidelines (close the week flat). The "late in session" cutoff (e.g. after 15:00) is [our interpretation]. Otherwise trail the stop so the recovered loss is locked in.
- **Sources:** cc02_005_vWDElb65YHg ~00:08:05.
- **Quote:** "take it off close the week flat do not go into the weekend with a net loss" (cc02_005).
- **Conflicts:** none.
- **[our interpretation]:** the 15:00 cutoff.
- **Rulebook fix:** X13: add "Late in the week (Thu/Fri) or late in the session, close a recovery re-entry once it brings the week back to flat; otherwise trail to lock the recovery (cc02_005 ~8:05)."
- **BUILD SPEC (management_exits, week state from day_week_context):**
  - Where: position loop (~2590): for a trade that is a re-entry after a loss (`state["reentered"]` set for its session), compute `week["net"] + day closed + open P&L` each bar; if >= 0 and (weekday in Thu/Fri or `t >= late_flat_t`): close all at the bar close (`exit kind "flat_week"`), set all done keys (Thu/Fri: also `week["done"]`). Otherwise, under `recover_trail`, move the stop to the price where week P&L = 0 once that is beyond the current stop.
  - Params: `late_week_flat: bool = False`, `late_flat_t: int = 900`, `recover_trail: bool = False`.
  - Test: `test_late_week_close_flat`. Thursday: a loss of 1R, then a half-size re-entry reaches +2R open (week back to 0) -> closed there, no more trades that week; same on Tuesday morning -> not closed, stop trailed to the break-even-week price with `recover_trail`.

### 31. N10-mon-wed-extreme-trending-week
- **rule_id / kind:** N10 / missing_condition. Scope: general. judgment = true.
- **Rule:** In a trending week with bullish bias, look for the weekly low Mon-Wed, formed at an HTF discount PD array (FVG, OB, breaker, old low, 20/40/60-day range levels). Bearish: weekly high Mon-Wed at a premium array. The trending-week classifier is [our interpretation]. Tag the weekday of the weekly extreme for testing.
- **Sources:** cc07_006_O69iFqP1j7o ~00:21:27.
- **Quote:** "in trending environments we look for the Monday Tuesday or Wednesday low to form" (cc07_006).
- **Conflicts:** none.
- **[our interpretation]:** the trending classifier.
- **Rulebook fix:** N10.3: "~70% Mon-Wed extreme applies to trending weeks and forms at an HTF discount (premium) array, incl. 20/40/60-day range levels (cc07_006 ~21:27)."
- **BUILD SPEC (day_week_context; extends section 3 N10 `mon_wed_extreme` / N10.3 `pool_mon_wed`):**
  - Where: `day_context` Mon-Wed: `week_trending` = prior week's range >= `adr5 x 5 x trend_k` and closed in its outer quarter in the bias direction [our interpretation], or the B14 NWOG regime tag where built. Under `mw_extreme_need_array`, the Mon-Wed weekly-low long requires the sweep/entry to sit inside a daily/weekly discount array (`htf._arrays` D/W) or within `ipda_pools` 20/40/60-day levels (built, B21). Thu/Fri tag `wk_extreme_dow` for the study.
  - Params: `mw_extreme_need_array: bool = False`, `trend_k: float = 0.8`.
  - Test: `test_mw_extreme_array`. Trending week, Tuesday sweep not at a D/W array -> no long; same sweep inside a daily FVG -> long arms.

### 32. N10-missed-mon-wed-no-chase
- **rule_id / kind:** N10 / missing_rule. Scope: general. judgment = true.
- **Rule:** If the weekly bias move has visibly started Mon-Wed (e.g. the expected weekly low/high is in and price has expanded away from it by Wed London close, 30-50% of the expected range done, per T14) and the bot holds no position from it (missed or stopped out): on Thu/Fri take no trades targeting a large weekly extension; only nearest-pool targets or skip. Expect only modest Thu follow-through and a Friday retrace or flat close. No conflict with T14: cc07_006 itself gives the 30-50% by Wednesday figure.
- **Sources:** cc07_006_O69iFqP1j7o ~00:24:29, ~00:25:09.
- **Quotes:** "it's important not to get PIP drunk" (cc07_006); "don't expect a massive move higher or lower in in the last two days of the trading week" (cc07_006).
- **Conflicts:** none (the claimed T14 conflict was rejected).
- **[our interpretation]:** "visibly started" test (below).
- **Rulebook fix:** N10.4: add "Missed the Mon-Wed move (no position from it): no big targets Thu/Fri, nearest pool or skip; expect small Thursday follow-through and a Friday retrace (cc07_006 ~24:29-25:33)."
- **BUILD SPEC (day_week_context):**
  - Where: `day_context` Thu/Fri: `week_started` = the week's low (high for bear bias) set Mon-Wed and Wed 05:00 close >= 30% of `5 x adr5` away from it [our interpretation]; `week["n_with_trend"] == 0` (no with-trend trade this week, or only losses). Under `missed_week_mode`: "nearest" -> `_targets` keeps only the first rung (single exit); "skip" -> `blocked()` returns "missed_week".
  - Params: `missed_week_mode: str = "off"` ("off" / "nearest" / "skip").
  - Test: `test_missed_week_nearest`. Week expanded from Monday's low with no bot trade: Thursday long exits fully at the nearest pool; with a winning Tuesday long the rule does not apply.

### 33. M14-tgif-timing-and-precondition
- **rule_id / kind:** M14 / missing_condition. Scope: index. judgment = true.
- **Rule:** TGIF (down week; mirror for up): retrace 20-30% of the weekly range, measured up from the lowest low so far. Timing: it can start Thursday into Friday; if Friday makes a new weekly low, expect it later Friday, starting around the London close 10:00-12:00 NY, or in the PM if 10:00-12:00 consolidates. Precondition switch: strict (066: the week reached an HTF array in trend direction) vs loose (084: a one-directional, large-range week where price ran sell-side but fell short of the weekly FVG). After a large down week with Friday's low, don't target the remaining relative equal lows; expect the retrace.
- **Sources:** 084_VdGihxSuSRk ~00:15:56, ~00:15:36.
- **Quotes:** "retrace 20 to 30 percent of the weekly range on Thursday into Friday" (084); "fell short of reaching that there and then we had a nice retracement off the low formed on Friday which is TGIF" (084).
- **Conflicts:** M14/066 require the week to reach an HTF array vs 084 calling TGIF after ES fell short of the weekly FVG.
- **Rulebook fix:** M14: "Can start Thursday into Friday; a new Friday low pushes it later Friday; London close 10:00-12:00 first, PM only if 10:00-12:00 consolidates (084 ~15:56). 084 called TGIF with the weekly FVG not reached (precondition loose vs 066 strict). After a big down week with Friday's low, don't target remaining REL (084 ~18:42)."
- **BUILD SPEC (day_week_context; extends section 3 M14.1 `tgif_htf_array` and M14.3 `tgif_timing`):**
  - Where: `day_context` (~1902, the tgif block ~1945): (1) `tgif_htf_array` gets a mode: "strict" = M14.1, "loose" = Mon-Thu range >= 1.5x average and closed in the outer quarter, no array needed. (2) Thursday start: when `tgif_thu` and Thursday holds the week's low after 10:00 with Wednesday's low taken earlier, apply the `tgif` side block on Thursday PM too. (3) Friday sequencing: if Friday's AM prints a new weekly low, the TGIF entry window is 600-720; if the 10:00-12:00 range < `tgif_consol_frac x adr5`, move the window to 810-900. (4) `tgif_no_rel`: drop sell-side REL targets on TGIF Fridays (`_targets` filter).
  - Params: `tgif_precond: str = "strict"` ("strict" / "loose"), `tgif_thu: bool = False`, `tgif_seq: bool = False`, `tgif_consol_frac: float = 0.25`, `tgif_no_rel: bool = False`.
  - Test: `test_tgif_seq_loose`. Large down week that missed the weekly FVG: "strict" gives no TGIF tag, "loose" does; Friday new low at 09:45 + 10:00-12:00 consolidation -> TGIF long only from 13:30.

### 34. N9-macro-failure-any-macro
- **rule_id / kind:** N9 / shortened. Scope: index. judgment = true.
- **Rule:** For any macro window in use (AM 09:50-10:10, 10:50-11:10; lunch 11:50-12:10; PM 13:30-~13:35, 14:50-15:10, 15:15-15:45; London macros FX/out of scope): if price shows no reach toward the pre-identified liquidity or inefficiency during the window (ICT: "doesn't budge"; our proxy: no new extreme toward the draw and no displacement candle), cancel pending orders and take no new entries for the rest of that session. Default = the next session is still allowed; switch `macro_fail_scope=day` per "maybe even that trading day".
- **Sources:** 073_fXVJnBVizYY ~00:35:33 (and ~00:30:51).
- **Quote:** "it's probably indicative of a bailout and don't do anything with that session or maybe even that trading day" (073).
- **Conflicts:** none.
- **[our interpretation]:** the no-move proxy.
- **Rulebook fix:** N9.5: "Applies to every macro in use, not only the two AM ones; failure = the market doesn't budge toward the draw; ends the session, maybe the day (073 ~30:51, ~35:33)."
- **BUILD SPEC (news_calendar_times; extends section 3 N9.5 `macro_no_move` / `macro_no_move_pm`):**
  - Where: `run_day` at each macro end bar (`MACROS`, ~58; add `(810, 815)` for 13:30-13:35 per T7's 13:39 note): if the session's draw is set and within the window there was no new extreme toward it and no displacement bar (`displacement_mult`), then cancel pending for that session and `done[session]=done["SB_"+session]=True`; with `macro_fail_scope="day"` all keys. `macro_fail_windows` picks which macros are checked.
  - Params: `macro_fail_windows: str = "am"` ("am" = N9.5 / "all"), `macro_fail_scope: str = "session"` ("session" / "day").
  - Test: `test_macro_fail_scope` (tests/test_news_calendar.py). Flat 14:50-15:10 with a PM draw above: PM done, no last-hour trade; "day" on the 09:50 macro also blocks the PM.

### 35. N8-consolidation-pm-full-exit-at-pool
- **rule_id / kind:** N8 / shortened. Scope: general. judgment = false.
- **Rule:** Consolidation day: if the AM (before 12:00) has run a liquidity pool, no PM trade. Otherwise at most one PM scalp toward the nearest untapped pool (overnight H/L, session H/L, PDH/PDL); exit all of it when that pool is taken (no runner), then stop for the day. Treat the PM chance as uncommon: the default on consolidation days is AM-only (scalp size, 5-10 ticks in bonds).
- **Sources:** cc10_008_RgpxhuVp5Xg ~00:10:24.
- **Quote:** "once it takes those stops don't be greedy just run the stops with the professionals and take your profits" (cc10_008).
- **Conflicts:** none.
- **Rulebook fix:** N8.3: "PM on a consolidation day: only if the AM left a pool untapped; target that pool, 100% out there, no runner, then done; uncommon, default AM-only (cc10_008 ~10:16-11:07)."
- **BUILD SPEC (day_week_context; extends section 3 N8.3 `consol_day_rules`):**
  - Where: on a day tagged consolidation (N8.1 / `chop` / sloppy "chop"), the PM: `_targets` keeps only the nearest untapped pool from {ONH/ONL, AM H/L, PDH/PDL}, single exit (no ladder, no runner, no adds); `_after_close` sets all done keys after that trade; if any of those pools was run before 12:00, `done["PM"]=True`.
  - Params: `consol_pm_pool_exit: bool = False`.
  - Test: `test_consol_pm_pool_exit`. Consolidation day, ONH untapped: one PM long, 100% exit at ONH, nothing after; ONH taken at 10:30 -> no PM trade.

### 36. X10-skip-pm-am-range-vs-adr5
- **rule_id / kind:** X10 / missing_condition. Scope: general. judgment = true.
- **Rule:** X10 addition: at 11:00-12:00, if today's range since the AM start (08:00 per cc10_007's bond session; 09:30 or 08:30 for index [our choice]) >= `skip_pm_if_am_range_pct_adr5` x ADR5 (L16; ICT says only "a large degree" / "lion's portion", threshold to test e.g. 0.7-0.8): flatten before NY lunch and take no PM entries.
- **Sources:** cc10_007_JpV-J31mxhg ~00:09:00.
- **Quote:** "if there's a large degree of the average daily range ... seen in the AM session that means that the PM session will be rather abbreviated" (cc10_007).
- **Conflicts:** none.
- **Rulebook fix:** X10d: "'Delivered the day's range' is measured against average daily range: a large share of ADR5 in the AM -> flat before lunch, no PM (cc10_007 ~9:05)."
- **Already listed:** section 3 day_week_context X10d "`am_range_skip_pm` (AM range >= k x ADR5 -> done PM and SB_PM)" is the same rule. No new build spec; build X10d with k tested at 0.7 / 0.8.

### 37. N7-august-drawdown-restart
- **rule_id / kind:** N7 / missing_rule. Scope: general. judgment = false.
- **Rule:** Extend N7 August: if a drawdown occurs or a challenge is failed during August, stop live trading for the rest of August (review/journal only) and resume no earlier than the first trading day of September.
- **Sources:** 079__NWG_eJRBpU ~00:25:46.
- **Quote:** "if you have blown your account challenge ... don't be in a rush to start back up wait until September" (079).
- **Conflicts:** none.
- **Rulebook fix:** N7.6: add "Drawdown or a failed challenge in August -> stop until September (079 ~25:46)."
- **BUILD SPEC (day_week_context; extends section 3 N7.6):**
  - Where: `backtest.run`: track equity peak; in August, once drawdown from the peak >= `aug_dd_pct` (or the month's net <= -`aug_dd_pct`), skip all remaining August days (`skips` row "august_dd").
  - Params: `aug_dd_stop_pct: float = 0.0` (test 2.0-3.0, our threshold).
  - Test: `test_august_dd_stop`. August with a -3% drop by Aug 10 -> no trades Aug 11-31, trades resume Sep 1.

### 38. X13-two-failed-trend-signals
- **rule_id / kind:** X13 / missing_rule. Scope: general. judgment = true.
- **Rule:** Swing mode only (parked per M17): after a stopped-out with-trend daily/4h signal under a monthly/weekly trend, take the next with-trend signal. If that one also stops out, set a "trend tiring" flag on the monthly/weekly profile (ICT: possible intermediate/long-term shift). Any pause in new with-trend entries until the profile is re-classified is our interpretation, a switch to test, not ICT's rule.
- **Sources:** cc06_001_0juYnbKays0 ~00:09:01.
- **Quote:** "it's probably near a longer term or intermediate term shift" (cc06_001).
- **Conflicts:** cc06_005 keeps taking the next setup while the HTF idea holds.
- **[our interpretation]:** the pause.
- **Rulebook fix:** X13 (swing note, parked): "Two consecutive failed with-trend swing signals = the M/W trend may be tiring, a possible intermediate/long-term shift (cc06_001 ~9:01)."
- **BUILD SPEC (bias_htf, research study):**
  - Where: swing study in `study.py`: after two consecutive with-trend stop-outs set `trend_tired`; report the forward 20/40-day return in the trend direction vs baseline; variant `tired_pause` skips with-trend signals until the `htf.table` `flip` column changes.
  - Params (study args): `tired_n=2`, `tired_pause=False`.
  - Test: `test_trend_tired_flag` (tests/test_bias_htf.py). Signal list win, loss, loss -> flag set after the second loss; a win in between resets the count.

### 39. B17-dxy-weekly-objective-ends-week
- **rule_id / kind:** B17 / missing_condition. Scope: needs_unavailable_data. judgment = true.
- **Rule:** Extend B17/X15: the weekly objective may be defined on DXY (inverse to ES/NQ). If DXY reaches its weekly objective (038: a volume imbalance above relative equal highs), set week_done for index trading: no new entries for the rest of the week, expect consolidation. Same-week confounders in 038: Fed testimony and NFP week. Needs DXY data.
- **Sources:** 038_4H74nXabvL0 ~00:06:08.
- **Quote:** "that right there cools the jets for me for the week" (038).
- **Conflicts:** none.
- **Rulebook fix:** B17.3 / X15d: "The weekly objective may be a DXY objective (038 ~6:08: DXY into a VI above REH -> done for the week on ES); confounders that week: Fed testimony, NFP week."
- **No build spec:** needs DXY bars to map its PD arrays and REH/REL; `INTERMARKET()` has only a daily trend tag.

### 40. new-no-chase-missed-london-profile
- **rule_id / kind:** new / missing_rule. Scope: fx_only. judgment = false.
- **Rule:** FX-only London model (out of scope per M17): bias from the daily chart; valid entries only from (a) the classic London protraction/Judas swing after 00:00 NY into 02:00, or (b) the delayed protraction/Judas swing 02:00-03:00 NY. If neither occurs by ~03:00 NY, take no London trade that day regardless of how far price runs.
- **Sources:** cc08_005_eU8WcUftUtY ~00:20:30.
- **Quote:** "it'll probably be a 90 pip day ... and you aren't getting in" (cc08_005).
- **Conflicts:** none.
- **Rulebook fix:** M17 (London model note): "No London profile (normal 00:00-02:00 or delayed 02:00-03:00) -> no London trade that day, however far it runs (cc08_005 ~20:30)."
- **No build spec:** fx_only.

### 41. new-multi-asset-regime-aggressiveness
- **rule_id / kind:** new / missing_rule. Scope: needs_unavailable_data. judgment = true.
- **Rule:** Needs cross-asset data (FX/DXY, commodities, bonds, equities). Once a day before the session, score sync_count = number of the four asset classes behaving as expected (seasonal/directional). 4/4, or 3/4 with the third just joining = harmony: normal aggressiveness, pyramiding allowed, targets at large HTF moves. <= 2/4 = decoupled: dial back (ICT gives no numbers; half size / no pyramiding / take most at the first pool are our parameters). No clear smart-money tracks or no clear draw = no trade.
- **Sources:** cc10_019_gs3KMgz84yc ~00:17:01 (and ~21:10, ~22:19, ~25:14).
- **Quote:** "when it's not like it you need to dial it back" (cc10_019).
- **Conflicts:** none.
- **[our interpretation]:** the size / pyramiding / target mapping.
- **Rulebook fix:** B17.5 / E9: "Four-asset harmony (currencies, commodities, bonds, stocks) sets aggressiveness; 2 of 4 = not symmetrical, dial back; no clear tracks = hands in pockets (cc10_019 ~17:01-25:31)."
- **No build spec:** needs data for four asset classes.
