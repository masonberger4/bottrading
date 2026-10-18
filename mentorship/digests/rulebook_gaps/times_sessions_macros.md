# Rulebook gaps: times, sessions and macros

Topic `times_sessions_macros`. Every item below is a verified gap between ICT's captions and `mentorship_rules.md`. Where the checker gave a corrected rule, that is the rule written here. Where it gave none, the claim's full rule is used. "[our interpretation]" marks thresholds or readings that ICT does not state.

Conventions:
- Times are New York. Minutes-of-day are used in Params (09:30 = 570, 10:00 = 600, 12:00 = 720, 13:30 = 810, 14:00 = 840, 15:00 = 900, 15:50 = 950). Prices are in ES points unless stated; the engine converts them with `p.es_pt` (SPY ~ ES/10).
- New Params switches default off (rule_coverage.md section 3). Each work package adds its fields in its own commented block at the end of `Params` (strategy.py ~65-705) and validates string switches in `__post_init__` (~705).
- Code anchors (current `mentorship` branch):
  - Windows: `MACROS` (strategy.py ~58: 08:50-09:10, 09:50-10:10, 10:50-11:10, 11:50-12:10, 13:10-13:40, 14:50-15:10, 15:15-15:45); Params `am=(570,660)`, `pm=(810,950)`, `last_hour=(900,950)`, `last_hour_sweet=(915,945)`, `macro=(590,610)`, `am_exit=720`, `or_minutes=30`, `sb_windows=((600,660),(840,900))`, the pre-open switches `pre_0700` / `pre_0900` / `post_news` (~202-208).
  - Session selection: `run_day` (~2490). `am_start` (~2541), `pre_windows` (~2567-2573), `done` (~2565), the session pick (~2821-2832), the news gate (~2833-2843), the last-hour slot (~2845-2856), `skip_main` (~2857), `blocked()` (~2864).
  - Session pools: `DayCtx.__init__` `self.sess` (~1159-1180): London 02:00-05:00 (complete 05:00), `prev_pm` 13:30-16:00, lunch 12:00-13:30 (complete 13:30); OR high/low `or_end` / `or_hl` (~1203); `ctx.or60` (~2558).
  - Trade tags: `_scan_core` order build (~4248-4296): `macro`, `macro_win`, `lh_sweet`, setup names `pm_last_hour` / `pm_sb` / `pm`.
  - Last hour / MOC: `setups.moc_run` (~708), `setups.htf_done` (~631), `lh_on` (~30); Params `moc_run`, `moc_cap_pts`, `moc_pool_exit`, `lh_htf_done_skip`, `pm_last_hour_model` (~594-607).
  - Lunch / PM draws: `pm_off_lunch` (~340), `pm_lunch_target` / `pm_lunch_org` (~612-614), `pm_reversal` (~609), `_lock_times` / `_lock_step` (~2205-2290).
  - Day context: `day_context()` (~1902), `sloppy_day()` (~1964), `Chop` (~2040), `adr5()` (~828), `_news_gate()` (~2192). HTF: `htf.table` (~95), `htf._arrays` (~66). SB: `sb_model.run_sb` (~31), `_arm` (~213).
- Work packages are the names in `rule_coverage.md` section 3. Session windows, macro gates, OR and news timing go to **news_calendar_times**. Day / week tags and studies go to **day_week_context**. New entry branches (lunch macro, 10:50 macro, last-hour OB, London-close scalp) go to **setups_models**. Draw / target changes go to **targets_partials**. Holding and exits go to **management_exits**. HTF regime tags go to **bias_htf**. SB window changes go to **silver_bullet**.
- Tests live in `C:\Users\mason\bottrading\tests\`: `test_news_calendar.py`, `test_day_week_context.py`, `test_management_exits.py`, `test_targets_partials.py`, `test_bias_htf.py` (new files), and `test_setups_models.py` / `test_levels_detectors.py` (existing). Each spec names its test function. Every new switch also joins the "all off = identical trades" regression in its package's test file.
- Items scoped `fx_only` or `bonds_only` get the rulebook fix only, with no build spec (no FX or ZB intraday data in the engine; M17 parks FX day-trade models).

Summary: 66 items, 42 new build specs. Items without a build spec:
- 10 fx_only: new-protraction-windows, B12-midnight-judas-timing, T2-0820-cme-open, T1-pdh-0gmt-boundary (the index part already exists as L2 `pd_hl_session`), T2-0gmt-open-condition, new-cbdr-asian-range-filter, T3-london-news-manipulation, T14-tuesday-london-70 (the index weekly-extreme study is T14 in section 3), T13-mm-sell-model-times, T3-1400-caps-extreme. new-overnight-trend-from-2000 is also fx-only per the checker (11 in all).
- 6 bonds_only: bonds-session-clock, bonds-signal-0800-0830, bonds-london-reference, bonds-am-volume-swing, bonds-pm-three-outcomes, bonds-po3-template.
- 3 already listed in rule_coverage.md with the same content:
  - T3-london-kz-window: section 3 news_calendar_times **Ep06.1** "`london_kz` (a LON window, futures only), `london_kz_start` and `ny_kz_futures`" is the same window switch. The conditional 02:00-04:00 stat is FX. Rulebook text fix only.
  - T3-ny-kz-0700-1000: same **Ep06.1** entry (`ny_kz_futures`). Rulebook text fix only.
  - L8-time-decides-fill: section 3 levels_detectors **L8** "`vacuum_block()` at releases (08:30 near/MT/far; 10:00+ near/MT)" is built (`levels.vacuum_block`, `vacuum_blocks`; section 4). Rulebook text fix only.
- 2 with no engine window to act on: T8-london-lunch (no engine entries 05:00-07:00) and T3-asia (no engine entries 18:00-00:00). Rulebook text fix only.
- 1 folded into another spec: T3-london-close-window (the `london_close` window Param is defined in item 54's spec).
- 1 parked with the swing idea: new-swing-check-before-kz.

Several items extend a section 3 entry instead of duplicating it. Each says which one (T7, T8, T9, T10, T4, T5, L3, M9.2, M14.3, N8.3, T14, N9.3, Ep06.1).

Shared pieces this topic adds (build first, news_calendar_times):
- **`macro_of(t)` helper** (strategy.py, next to `MACROS`): returns the macro key ("0950", "1050", "1150", "1330", "1450", "1515") for a minute, or "". Replaces the inline generator in `_scan_core` (~4272). Items 1-3, 6, 10, 12 use it.
- **`ctx.am_dir` and `ctx.am_leg`** (set in `run_day` at 11:50 = 710, no look-ahead): AM direction = sign(close at 11:49 - open at 09:30), plus the AM leg origin (the AM low for an up AM) and extreme with their bar indices. Items 11, 12, 15, 19 use it.
- **`trend_day(ctx, i)` tag** (day_week_context): the N8.2 trend recipe when built, else the test definition "no retrace to the session EQ (50% of the 09:30-now range) after 10:00" [our interpretation]. Items 5, 16 use it.

---

## A. Macros (T7)

### 1. T7-macro-start-only-all
- **rule_id / kind:** T7 / shortened. Scope: index. judgment = false.
- **Rule:** For the 09:50-10:10, 10:50-11:10 and 11:50-12:10 macros (044; 046), a valid macro run is one that begins inside the window. It does not have to complete inside it. For the 15:15-15:45 MOC macro, the run toward unengaged liquidity may print its target after the window, before 16:00 (014: high at 15:54). Do not require the target to print inside the window. Apply the same start-only test to the 13:30 and 14:50-15:10 windows only as an untested extension.
- **Sources:** 044_LN1nfYp4dBw ~00:56:58; 046_VLis0LcbUaQ ~02:37:56; 014_g8bhZReDK-Q ~00:04:29.
- **Quotes:** "there's two macros that start in those two" (044); "it doesn't mean it completes in that 20 minute period it just means it begins" (046).
- **Conflicts:** none.
- **Rulebook fix:** T7: replace "the run must start in 09:50-10:10" with "Every macro is a start-only test: the run begins in the window and may finish later (09:50, 10:50, 11:50 per 044 / 046; the MOC target may print up to 16:00, 014 high at 15:54). The 13:30 and 14:50 windows: same test, untested extension."
- **BUILD SPEC (news_calendar_times; extends section 3 T7 `macro_gate` and Ep07.8 "macro_only 0950/all (start-or-arm test)"):**
  - Where: `run_day` session block after `skip_main` (~2857). With `macro_gate` on, a setup arms only when its sweep extreme bar or its MSS bar (the run's launch) falls inside a macro window from `macro_gate_set`. The fill and the target are not time-checked. Pending orders armed in a macro keep `pending_minutes`. MOC trades keep their target order to 15:59 and flatten at the session close (existing `flatten`).
  - Params: `macro_gate: str = "off"` ("off" / "start" = launch bar in the window / "arm" = arm bar in the window); `macro_gate_set: tuple = ("0950", "1050", "1150", "1515")` (add "1330" and "1450" for the extension test).
  - Test: `test_news_calendar.py::test_macro_gate_start_only`. Synthetic day: sweep at 10:05, MSS at 10:08, fill at 10:14, target at 10:40. With "start" the trade is taken and its target counts; with "arm" and a 10:12 MSS it is skipped.

### 2. T7-0950-reversal-or-continuation
- **rule_id / kind:** T7 / missing_condition. Scope: index. judgment = true.
- **Rule:** 09:50-10:10 also frames the first 20-40 min after 09:30. It can be (A) a reversal point: the run from 09:30 completes inside the window by taking a pool (043 buy-side; 073 buy-side plus a premium FVG rebalanced), and the window's extreme becomes the swing extreme, with the draw flipping to the opposite pool when the day's narrative supports it (e.g. the NFP profile). (B) A continuation re-accumulation: price consolidates and leaves an FVG in the bias direction, which is bought or sold on the retrace toward the next draw (015). (C) The start of a run (existing T7).
- **Sources:** 043_NkwqJBzgQwo ~00:05:31; 073_fXVJnBVizYY ~00:25:56; 015_QKvjPltjsqU ~00:27:13.
- **Quotes:** "stop deading its tracks at the macro at 950" (043); "for the algorithm to seek another setup either to reverse or continue" (015).
- **Conflicts:** none.
- **[our interpretation]:** "premium" = above 50% of the 09:30-now range; "rebalanced" = at least one body closes inside the FVG and the next bar leaves it.
- **Rulebook fix:** T7: add "09:50-10:10 branches: (A) reversal when the 09:30 run takes a pool (and rebalances a premium/discount FVG) inside the window, its extreme = swing extreme, draw flips to the opposite pool if the narrative supports it (043; 073 NFP); (B) continuation: consolidation leaves a bias-direction FVG, buy/sell its retrace (015); (C) start of a run."
- **BUILD SPEC (setups_models):**
  - Where: `setups.py` new `macro_0950(ctx, sd, i, p, session)` called from `_scan_core` when `t` is in 590-610. Branch A: a pool from `ctx.sess` / OR20 / `_eq_levels` on the side opposite `sd` was traded 1 tick through inside 590-610, and an opposing FVG above 50% of the 09:30-now range was rebalanced. Then set `ctx.m0950 = {"kind": "rev", "ext": price, "i": bar}` and allow a `sd` setup toward the opposite pool only if `sd` agrees with `want` or `nfp` is in the day tags. Branch B: no opposing pool taken, an FVG in the `want` direction formed in 590-610. Arm a limit at its near edge as a continuation entry (add if a position is open, per the entries_stops_sizing add block). Tag `m0950` = rev / cont / start on every AM trade.
  - Params: `m0950_branch: str = "off"` ("tag" / "rev" / "cont" / "both").
  - Test: `test_setups_models.py::test_m0950_branches`. Day 1: buy-side over OR20 taken at 09:55 plus premium FVG rebalanced, then MSS down: with "rev" a short arms toward the 09:30-09:50 low. Day 2: inside bar consolidation with a bullish FVG at 10:02: with "cont" a long limit arms at its near edge.

### 3. T7-1050-macro-setup
- **rule_id / kind:** T7 / missing_rule. Scope: general. judgment = false.
- **Rule:** 10:50-11:10 on any day type (consolidation, reversal, or continuation into lunch): identify the untapped pool (BSL/SSL). Long case: price sweeps a short-term low, then breaks the short-term high (MSS) inside the window; enter on the first trade back into the resulting VI/FVG as close as possible (no breaker required). Target the untapped BSL. Mirror for shorts. Tag the macro extreme as a likely protected level for the day. Stop placement and a no-fill cutoff are our additions, to be tested.
- **Sources:** 022_ALMsQytQ1fg ~03:09:01, ~03:10:40.
- **Quotes:** "It's going to run for the liquidity that has not been tapped yet." (022).
- **Conflicts:** none.
- **[our interpretation]:** stop below the sweep low (or OB MT); no fill by 11:10 -> cancel.
- **Rulebook fix:** T7: add "10:50-11:10 model (022 ~3:07-3:12): any day type; short-term sweep, MSS inside the window, enter close inside the VI/FVG (no breaker needed), target the untapped pool; the macro extreme is often a protected level for the day."
- **BUILD SPEC (setups_models):**
  - Where: `setups.py` new `macro_1050(ctx, sd, i, p, session)`, called from `_scan_core` when `650 <= t < 670`. Uses the existing short-term swing sweep (A1 `swing_tiers` short tier) instead of a session pool, MSS through the short-term high inside 650-670, entry = near edge of the first VI/FVG of the break (`vi_arrays` + FVG list), stop = sweep extreme minus `stop_buffer` (or `ob_mt` when `stop_mode="ob_mt"`), target = the nearest untapped pool from `_targets` (AM session pools, OR, prior PM). Order `cut` = 670 when `m1050_cut` is on. Its own done key `M1050` so it does not consume the AM trade. Store `ctx.protected[sd.sign] = sweep extreme` (used as a stop anchor for later trades when `protect_macro_ext` is on).
  - Params: `m1050: bool = False`, `m1050_cut: bool = True`, `protect_macro_ext: bool = False`.
  - Test: `test_setups_models.py::test_macro_1050`. Sweep of a 10:40 swing low at 10:52, MSS at 10:56 with an FVG, retrace fill at 10:59: trade armed with `entry_kind="m1050"`, target = AM high. Same pattern at 11:15: no trade.

### 4. T7-1500-at-least-one
- **rule_id / kind:** T7 / shortened. Scope: general. judgment = false.
- **Rule:** 15:00-16:00 holds three macros. Not all occur every day: usually two do, and at least one always does (022 ~3:16:44). Treat this as a stat to test, and list the conflict with T7's "MOC does nothing if the HTF target already hit" (Ep 01; 030).
- **Sources:** 022_ALMsQytQ1fg ~03:16:44.
- **Quotes:** "Usually two, but always one of them." (022).
- **Conflicts:** T7 "MOC does nothing if the HTF target already hit" (Ep 01; 030) vs "always one". 059 (item 9) supports "always one".
- **Rulebook fix:** T7: "15:00-16:00 has three macros; usually two occur, at least one always does (022 ~3:16:44) [stat to test]. Conflict: MOC does nothing when the HTF target is already hit (Ep 01; 030)."
- **BUILD SPEC (day_week_context, study):**
  - Where: new `study.py` function `macro_runs_study(days)`. For each day and each window (14:50-15:10, 15:15-15:45, and 15:45-16:00), mark a "run" when a leg starts in the window (start-only test from item 1) and travels >= `macro_run_pts` ES points. Report the count of windows with a run per day, split by `htf_done` at 15:00. No engine change.
  - Params: none in `Params`; study argument `macro_run_pts=5.0` [our interpretation].
  - Test: `test_day_week_context.py::test_macro_runs_study_counts`. Two synthetic days, one with runs in two windows and one with none: counts 2 and 0.

### 5. T7-no-macro-trending
- **rule_id / kind:** T7 / missing_condition. Scope: general. judgment = true.
- **Rule:** On a one-sided trending day the macro windows show no signature. Disregard macro tags/setups for that session (025 ~59:10). Classify the trend with N8's trending-day recipe and/or a test definition (e.g. no retrace to the session EQ after the open). ICT notes such days are infrequent.
- **Sources:** 025_7RiUUCqQ3SY ~00:59:10.
- **Quotes:** "trending days you're not going to see a macro" (025).
- **Conflicts:** none.
- **[our interpretation]:** the "no retrace to the session EQ" trend definition.
- **Rulebook fix:** T7: add "On trending days macros show no signature; ignore macro tags/setups (025 ~59:10). Such days are uncommon."
- **BUILD SPEC (news_calendar_times; uses the shared `trend_day` tag):**
  - Where: in `run_day` before the macro gate (item 1) and before the macro setups (items 2, 3, 12): if `macro_trend_off` is on and `trend_day(ctx, i)` is true, skip the macro gate (normal AM/PM rules apply) and skip the macro-only setups. Tag `trend_day=1` on trades.
  - Params: `macro_trend_off: bool = False`.
  - Test: `test_news_calendar.py::test_macro_off_on_trend_day`. A day that rises from 09:30 without touching its running 50% after 10:00: with `macro_gate="start"` and `macro_trend_off=True` a 10:30 setup outside a macro is allowed; with `macro_trend_off=False` it is not.

### 6. T7-1450-targets
- **rule_id / kind:** T7 / shortened. Scope: index. judgment = true.
- **Rule:** At 14:50-15:10, if price has made a high in premium (above the 50% of the day's dealing range; ideally above the midnight open), expect a down swing to begin. First target: the swing low just below the equilibrium of the PM up-leg (leg low to macro high). Further targets: untaken lows of the 07:00 session, the 08:30 low and the 09:30-11:00 low, nearest first. On Friday (TGIF), also the 20% retracement of the weekly range. Then sell the retrace into the bearish breaker / OB high (institutional order flow entry drill) for the last-hour run toward the REL / ORG. Bullish mirror with highs.
- **Sources:** 043_NkwqJBzgQwo ~00:15:49; 075_vN2BkfyRWE4 ~01:45:16.
- **Quotes:** "it's up in a premium it's gonna seek what discount" (043); "the 7 A.M New York session time the 830 lows the 9 30 to 11 lows" (075).
- **Conflicts:** none.
- **[our interpretation]:** "the 07:00 session low" = low of 07:00-08:30; "08:30 low" = low of 08:30-09:30.
- **Rulebook fix:** T7: replace "from premium it seeks discount (043; 075)" with the rule above, citing 043 ~15:49 (EQ of the PM leg, breaker entry) and 075 ~1:45 (07:00 / 08:30 / 09:30-11:00 lows; TGIF 20% on Fridays).
- **BUILD SPEC (targets_partials + setups_models):**
  - Where: `DayCtx.__init__` adds session pools `s0700` (420-510), `s0830` (510-570) and uses `am_hl` for 09:30-11:00 (pools complete at 510 / 570 / 660). In `_targets` (~1318), when `session == "PM"` and the arm time is in 890-910 and `m1450_targets` is on: first rung = the first swing low below the EQ of the PM leg (lowest low since 13:30 to the macro high), then untaken `s0700`, `s0830`, AM lows by distance; on Fridays add the TGIF 20% level (the M14.2 `tgif_zone` helper when built). Premium gate: the macro high must be above 50% of the 00:00-now range (and above the midnight open when `m1450_mid_open` is on), else no short from this branch. Entry uses the existing breaker path (`breaker_zone`, `ob_entry`).
  - Params: `m1450_targets: bool = False`, `m1450_mid_open: bool = True`.
  - Test: `test_targets_partials.py::test_m1450_ladder`. PM rally 13:40-14:55 into premium, untaken 08:30 low and 09:30-11:00 low below: target ladder = [leg-EQ swing low, 08:30 low, AM low]; with the macro high below the 50% line no short arms.

---

## B. Last hour and MOC (T7, T10)

### 7. T10-lasthour-ob-pullback
- **rule_id / kind:** T7 / shortened. Scope: index. judgment = true.
- **Rule:** With bullish order flow (and the HTF draw still above), in the last hour 15:00-15:50 (T10 entry cutoff): after a pullback into the last down-close OB, the one traders read as "the high is in", buy the OB (open to high). Target untaken buy-side or the daily-chart level. ES exits may run to the T11 16:15 flatten. Bearish mirror. Single example (012); tag it, don't treat it as a core rule.
- **Sources:** 012_HkiPAi1Mdu8 ~00:14:52.
- **Quotes:** "that last hour trading the macro runs from three o'clock to four o'clock" (012).
- **Conflicts:** T7 places the MOC macro at 15:15-15:45; 012 says 15:00-16:00.
- **Rulebook fix:** T10: add "Last-hour OB pullback (012 ~14:52, single example): in bullish order flow with the HTF draw above, buy the pullback into the last down-close OB in 15:00-15:50; target untaken buy-side / the daily level; ES exit to 16:15. Note 012 calls the whole 15:00-16:00 'the macro'."
- **BUILD SPEC (setups_models):**
  - Where: `setups.py` new `lh_ob_pullback(ctx, sd, i, p, session)`, called from `_scan_core` when `lh_slot` / `p.last_hour[0] <= t < p.last_hour[1]`. Conditions: `sd` agrees with `want`, `htf_done(ctx, sd, i)` is false, the last down-close candle before the PM high (bull case) is the OB; limit at its open, stop below its low; target = the nearest untaken buy-side from `_targets` or the daily draw (`htf` draw). No sweep required (unlike M5). `entry_kind="lh_ob"`.
  - Params: `lh_ob_pullback: bool = False`.
  - Test: `test_setups_models.py::test_lh_ob_pullback`. Bull PM, HTF draw above, a 15:12 dip into the last down-close OB: long armed at the OB open, target = the untaken PDH. Same day with `htf_done`: no trade.

### 8. T10-1550-pool-timing
- **rule_id / kind:** T10 / missing_condition. Scope: index. judgment = true.
- **Rule:** Last hour with a targeted pool: if price starts running the pool at/after ~15:50 ("10 of 4"), expect an aggressive run through it into layered stops just beyond (027: ~3 ES pts above the old high, possibly more); hold the runner toward that until the close. If the pool is taken before 15:50, expect only a small flurry and then a pull back into the range: take nearly everything off and keep at most 1 contract. If the 15:15-15:45 MOC has already reached the day's HTF target, expect only a 5-10 handle sputter 15:45-16:00 and no new expansion trades (T11: no adds in the last ~15 min). An up day rarely closes on its high unless it is a trending day.
- **Sources:** 027_STEGBblm4dI ~00:49:36; 056_NeZlyG8FZLQ ~00:19:28.
- **Quotes:** "right when we got to 10 of 4... we would have seen that blistering big run up" (027); "some kind of little sputter move which is maybe it's good for you know five or eight maybe ten handles" (056).
- **Conflicts:** none.
- **[our interpretation]:** "aggressive run" extension = `lh_late_ext_pts` beyond the pool.
- **Rulebook fix:** T10: add the 15:50 branch (aggressive run through the pool, runner to the close), the early-take management (take nearly all off, keep at most 1 unit) and 056's 5-10 handle sputter after the MOC delivered the HTF target.
- **BUILD SPEC (management_exits; extends section 3 T10 `moc_pool_exit`):**
  - Where: `run_day` position loop (~2590-2716) for trades with `setup` in ("pm_last_hour", "moc_run", "lh_ob"). When the pool rung is hit: if `t < 950`, exit `1 - lh_keep_frac` of the position (default keep 0.1, at least 1 unit only if lot allows) and move the stop to breakeven; if `t >= 950`, keep the runner with a target `lh_late_ext_pts` beyond the pool until the flatten. When the MOC target was hit before 15:45 (`htf_done` true at 945), set `done["LH"] = True` and cap any 15:45-16:00 trade target at `moc_cap_pts` (already 10).
  - Params: `lh_pool_timing: bool = False`, `lh_keep_frac: float = 0.1`, `lh_late_ext_pts: float = 3.0` [027 example].
  - Test: `test_management_exits.py::test_lh_pool_timing`. Pool hit at 15:46: 90% exits, runner stop at BE. Pool hit at 15:52: runner held to the extension. HTF target hit at 15:40: no new LH entries after 15:45.

### 9. T7-lasthour-after-target
- **rule_id / kind:** T7 / unlisted_contradiction. Scope: index. judgment = true.
- **Rule:** After the day's objective is hit (e.g. at noon) and an MSS against the morning move forms after 12:00, if an opposite-side unfilled inefficiency remains (ORG first, or an FVG), expect consolidation and then a 15:00-16:00 run into it; trade it only via the last-hour model (MSS/FVG/OB). Expect no last-hour move only when no unengaged liquidity or inefficiency remains that day. List as a conflict with T7 "does nothing if HTF target already hit" and N9 (015).
- **Sources:** 059_ZfnY2SH3G24 ~00:23:13.
- **Quotes:** "It's going to consolidate until the last hour of the day" (059).
- **Conflicts:** T7 MOC "does nothing if the HTF target already hit" (Ep 01; 014; 030; 032; 056); N9 "daily objective done before lunch: skip the rest of the day" (015).
- **Rulebook fix:** T7 and N9: add the 059 exception and list the conflict in the D-decisions.
- **BUILD SPEC (setups_models; touches `lh_htf_done_skip`, section 3 N9.3):**
  - Where: `setups.py` where `htf_done` gates the last hour (~918) and in the N9.3 `objective_done_skip` gate when built. With `lh_after_target` on: if the day's objective was delivered before 12:00 (`ctx.lock` delivered flag) AND a PM MSS against the AM direction (`ctx.am_dir`) formed after 720 AND today's ORG (or an FVG) opposite the AM move is still unfilled, then do not skip the LH slot; the LH draw = that ORG level (`org_draw` / L7 levels) for setups in the reversal direction only.
  - Params: `lh_after_target: bool = False`.
  - Test: `test_setups_models.py::test_lh_after_target_org`. AM sell to target at 11:55, bullish MSS at 12:30, ORG above unfilled: with the switch on a 15:10 long setup is taken toward the ORG; off, `lh_htf_done_skip` skips it.

### 10. T7-lasthour-consolidation-direction
- **rule_id / kind:** T7 / missing_rule. Scope: index. judgment = true.
- **Rule:** If the daily context is range-bound and intraday price has tried repeatedly to break one boundary without a sustained break (trapping traders on that side), the 15:15-15:45 MOC macro direction is toward the opposite boundary (e.g. buy-side above range highs/REH when the lows held). Use the 2022 model toward it; with no clear setup, wait until 15:40-15:45 for a 5-8 (max ~10) handle run. On a big bull day that has already printed its HOD (not a trending day), expect the close near but off the high: no new longs into the close.
- **Sources:** 032_SSWN6YSVyFY ~00:59:56.
- **Quotes:** "the Market's going to start probing outside those boundaries" (032).
- **Conflicts:** none (027: a trending day can close on its high, kept as the exception).
- **[our interpretation]:** "tried repeatedly" = 2+ tests of the boundary within `eq_tol_pts` x 2 without a body close beyond; "big bull day" = day range >= ADR5 and close in the top quarter.
- **Rulebook fix:** T10: add the range-day MOC direction rule (032 ~59:56-1:01:00) and the big-bull-day "no new longs into the close" note.
- **BUILD SPEC (setups_models; extends section 3 T10 `moc_run`):**
  - Where: `setups.moc_run` (~708) and the `_scan_core` side loop for the LH slot. When `moc_range_dir` is on and the day is range-bound (`sloppy_day` big_prev / chop tag or `inside_day` tag), count boundary tests since 09:30; the MOC side = away from the side tested 2+ times. Block the other side in 900-960. `moc_run` keeps its 15:40 start and `moc_cap_pts`. Big-bull-day block: if day range >= `adr5` and the HOD printed before 15:00 and `trend_day` is false, block new longs (shorts mirror) from 900.
  - Params: `moc_range_dir: bool = False`, `moc_no_chase_hod: bool = False`.
  - Test: `test_setups_models.py::test_moc_range_direction`. Range day, lows tested 3 times: only longs arm in 15:15-15:45. Big bull day with HOD at 14:10: no LH long.

---

## C. Lunch (T7, T8)

### 11. T8-lunch-raid-target
- **rule_id / kind:** T8 / shortened. Scope: index. judgment = false.
- **Rule:** At 11:50, compute the AM direction. Bullish AM: candidate lunch pool L = (a) the most recent swing low (trailed-stop level) formed before 12:00, ignoring swings formed at/after noon; (b) the low formed before 11:00/12:00; (c) on 08:30-news days, the first swing low after the release. Direction = against those profitable all morning (064). Expect a run beginning 11:50-12:10 (046; optionally after repricing into the nearest opposing FVG, 075) that trades through L between 12:00 and 13:30 (064). If it has not happened in the lunch hour, expect it in the first 30-45 min after lunch, around 13:30-13:45 (026); take no PM entry before it. Don't trail stops just beyond L; treat L as a sweep pool for the PM. Bearish AM: mirror with highs. Test which candidate is hit most on 1m data.
- **Sources:** 025_7RiUUCqQ3SY ~01:01:51; 064__YTK5uXBe4o ~01:46:02; 075_vN2BkfyRWE4 ~01:10:44; 046_VLis0LcbUaQ ~02:37:56; 026_GFdWahZUNOw ~01:26:19.
- **Quotes:** "I'm not saying the highest high I'm saying the most recent High" (025); "if they don't run them in the lunch hour you anticipate that occurring at noon to 1 30 to 1 45" (026).
- **Conflicts:** 025 "most recent high, not the highest" vs 064 "the low of the day formed prior to 11/noon" vs 075 "first swing low after the news". Kept as three candidates to test.
- **Rulebook fix:** T8 / X5: name the lunch raid level (three candidates, sources above), the timing (start 11:50-12:10, through L by 13:30, fallback 13:30-13:45) and the consequences (no PM entry before it; no trailing stops just beyond L).
- **BUILD SPEC (news_calendar_times + management_exits; extends section 3 T8 `lunch` session):**
  - Where: `run_day` at bar 710 computes `ctx.lunch_L` for the chosen candidate (a: last confirmed short-term swing opposite `ctx.am_dir` with index < 720; b: AM extreme opposite the move up to 660 / 720; c: first swing after 510 on `NEWS_0830` days). (1) PM gate: with `lunch_raid_wait` on, no PM entry until `lunch_L` has traded 1 tick through or `t >= lunch_raid_by` (825 = 13:45). (2) Trailing: in the position loop, a trailed stop for an AM trade may not sit within `eq_tol_pts` beyond `lunch_L` (move it beyond the next swing). (3) `lunch_L` joins `ctx.sess` as `lunch_raid` pool for PM sweeps. Study output: which candidate is taken first per day (`study.py lunch_raid_study`).
  - Params: `lunch_raid: str = "off"` ("recent" / "am_low" / "post_news" / "first_of"), `lunch_raid_wait: bool = False`, `lunch_raid_by: int = 825`, `lunch_trail_guard: bool = False`.
  - Test: `test_news_calendar.py::test_lunch_raid_pool_and_wait`. Bull AM with swing lows at 10:40 and 11:35; a 12:05 swing low is ignored; L = 11:35 low with "recent". With `lunch_raid_wait` a 13:31 PM long is skipped until L trades at 13:38.

### 12. T7-lunch-macro-htf-program
- **rule_id / kind:** T7 / missing_condition. Scope: index. judgment = false.
- **Rule:** At 11:50-12:10, if a late-AM pullback has taken a nearby sell-side (or repriced into an FVG) with buy-side/REH resting above, expect the lunch macro to run that buy-side. If the HTF program is bullish, buy in the macro: first partial just above the REH, runner toward the HTF draw. If the HTF program is bearish, treat the run into buy-side as a raid and look to sell after it. Mirror for sell-side. Single example (070); judgment.
- **Sources:** 070_1HtRfFYiwO0 ~00:31:06.
- **Quotes:** "we're in a higher time frame bullish buy program" (070).
- **Conflicts:** none.
- **Rulebook fix:** T7 lunch line: add the HTF-program condition (070 ~31:06, single example).
- **BUILD SPEC (setups_models; requires item 13's `lunch_macro_entry`):**
  - Where: inside the `lunch_macro_entry` branch (item 13). Before arming, read `want` (HTF bias). If the late-AM pullback took a sell-side pool between 660 and 710 and REH/buy-side rests above: `want > 0` -> long setup in 710-730, first rung = REH + `exit_before_pts`, runner to the HTF draw (`htf` draw level); `want < 0` -> no long; arm a short only after the REH trades 1 tick through and an MSS down forms (the normal model, side = -1). Mirror.
  - Params: `lunch_htf_program: bool = False`.
  - Test: `test_setups_models.py::test_lunch_macro_htf_program`. Same intraday path with `want=+1` -> long armed at 11:52 with rungs [REH, HTF draw]; with `want=-1` -> short armed after the REH raid.

### 13. T8-lunch-entries-switch
- **rule_id / kind:** T8 / unlisted_contradiction. Scope: index. judgment = true.
- **Rule:** Default (new-trader/bot): no entries 12:00-13:30 (bot 11:00-13:30). Test switch `lunch_macro_entry`: during 11:50-12:10 (extended to ~12:30), bearish case: price retraces up into a 5m/15m SIBI inside/under a bearish breaker or OB -> sell at the SIBI near edge, stop above the SIBI (beyond any overshoot wick), target the nearest sell-side protecting the AM move. Bullish case (AM draw unfinished, buy-side still above): price runs sell-side under late-AM lows/REL into the low of a 15m BISI with an untraded inefficiency -> buy there, stop below it, target AM buy-side/REH and the PM draw. Reduced target.
- **Sources:** 046_VLis0LcbUaQ ~00:32:10; 065_rx15_eN9sxI ~04:16:00; 080_XODINFwpeaw ~00:12:39; 081_0xYpeVRi_qs ~00:15:28.
- **Quotes:** "are you a lunchtime Trader yes you can trade lunch ... but as a new Trader you shouldn't" (065); "that would be a wonderful short for the lunchtime macro" (081).
- **Conflicts:** 065B ~4:12 "no new entries at lunch" vs 046, 080, 081 lunch-macro trades; 065 ~4:16 reconciles it as a new-trader rule.
- **[our interpretation]:** the 12:30 extension; "reduced target" = first rung only, no runner.
- **Rulebook fix:** T8: "No new entries at lunch (065B ~4:12) is the new-trader rule; experienced traders may trade the lunch macro (065 ~4:16; 046 ~32:10; 080 ~12:39; 081 ~15:28). List in the D-decisions."
- **BUILD SPEC (news_calendar_times + setups_models):**
  - Where: `run_day` session pick (~2827): add a `LUNCH` session for `lunch_macro_win` (710-750) with its own done key, active only when `lunch_macro_entry` is on. `_scan_core` in `LUNCH` uses only 5m/15m arrays (`entry_tf="5m"` path with `setup_minutes` 5 or 15): short = retrace into a SIBI under a bearish breaker/OB (`breaker_zone`), limit at the near edge, stop above the SIBI high and any overshoot wick; long = sell-side sweep under late-AM lows into a 15m BISI low, limit at the BISI low, stop below it. Target = the first rung only (`lunch_first_rung_only`). `blocked()` still applies.
  - Params: `lunch_macro_entry: bool = False`, `lunch_macro_win: tuple = (710, 750)`, `lunch_first_rung_only: bool = True`.
  - Test: `test_news_calendar.py::test_lunch_macro_session`. Off: no trade between 12:00 and 13:30. On: a retrace into a 5m SIBI at 11:58 arms a short with one target = the AM sell-side pool.

### 14. T8-lunch-three-behaviours-reversal
- **rule_id / kind:** T8 / shortened. Scope: index. judgment = true.
- **Rule:** Going into lunch, classify the expected behaviour: (1) AM draw delivered -> consolidation/retrace, no new entries; (2) AM draw not yet reached and opposite pool already taken -> run for the remaining liquidity (may start in 10:50-11:10); (3) day's draw or the far edge of the HTF PD array (high of a 60m SIBI for an up move; low of a 60m BISI for a down move) reached between ~11:50 and ~12:15 -> tag that extreme as a likely HOD/LOD; an MSS against the morning move after 12:00 = lunch reversal: stop/flatten with-trend positions and allow a PM setup (MSS + FVG) toward the opposite side (e.g. unfilled ORG, sell-side below the morning range) by the last hour. Record the reversal level as the array's far edge, not its CE.
- **Sources:** 073_fXVJnBVizYY ~00:29:35; 059_ZfnY2SH3G24 ~00:15:28; 007_bGtQOXrrK9c ~00:09:44.
- **Quotes:** "it'll run for liquidity or it can reverse okay so there's three primary functions" (073); "once it gets to the top of the hourly Fair Day Gap at noon time lunch has a market reversal" (007).
- **Conflicts:** Appendix A Ep 05 "[corrected] reversed off the hourly FVG's CE" vs 007 ~9:44 "top of the hourly fair value gap".
- **[our interpretation]:** the 11:50-12:15 band for "at noon".
- **Rulebook fix:** T8: replace "lunch = consolidation/retrace" with the three functions (073 ~29:35) and the noon reversal (059 ~15:28; 007 ~9:44). Appendix A Ep 05: correct "reversed off the hourly FVG's CE" to "reversed at the top (far edge) of the hourly FVG; the CE was the AM limit level".
- **BUILD SPEC (day_week_context tag + management_exits + setups_models):**
  - Where: at bar 710 set `ctx.lunch_kind` = "consol" (lock delivered), "run" (lock undelivered and the opposite pool taken), else "open". In 710-735, if price trades into the far edge of a 1h FVG from `htf` arrays (`htf_targets` "1h") on the AM side, or the day's lock, set `ctx.noon_ext`. A PM MSS against `ctx.am_dir` after 720 with `noon_ext` set -> `lunch_kind="reversal"`: (a) with `noon_rev_flat` on, flatten any open AM-direction position at that bar (exit reason `noon_rev`); (b) unlock the PM side opposite the AM (draw = ORG / AM-range opposite pool). Tag `lunch_kind` on all PM trades.
  - Params: `lunch_kind_tag: bool = True` (tag only, no behaviour change), `noon_rev_flat: bool = False`, `noon_rev_pm: bool = False`.
  - Test: `test_management_exits.py::test_noon_reversal`. AM rally into the top of a 1h SIBI at 12:03, MSS down at 12:20: open long flattened with `noon_rev`; PM short toward the ORG allowed with `noon_rev_pm`.

### 15. T8-lunch-length-am-speed
- **rule_id / kind:** T8 / missing_condition. Scope: index. judgment = true.
- **Rule:** Default lunch 12:00-13:00. Fast AM -> expect only a short or shallow lunch pause. Lethargic AM -> lunch may run 11:00-13:00 or to 14:00 (stated as uncommon). The thresholds for "fast" and "lethargic" are our interpretation.
- **Sources:** cc10_012_qZg_5bac518 ~00:02:56.
- **Quotes:** "if there's a fast Market in the morning Traders are going to want to probably work through lunch" (cc10_012).
- **Conflicts:** none.
- **[our interpretation]:** fast = 09:30-11:00 range >= 0.6 x ADR5; lethargic = < 0.3 x ADR5.
- **Rulebook fix:** T8: add "Lunch length depends on the AM (cc10_012 ~2:56): fast AM -> short pause; lethargic AM -> 11:00-13:00, rarely to 14:00."
- **BUILD SPEC (news_calendar_times):**
  - Where: `run_day` at bar 660 computes `am_speed = am_range / adr5(hist)`. With `lunch_by_speed` on: fast -> PM window starts at `lunch_fast_pm` (780 = 13:00) instead of `p.pm[0]`; lethargic -> `am_exit` effectively 660 for new entries (no AM entries after 11:00) and PM start `lunch_slow_pm` (840). Tag `am_speed` on trades.
  - Params: `lunch_by_speed: bool = False`, `am_fast_k: float = 0.6`, `am_slow_k: float = 0.3`, `lunch_fast_pm: int = 780`, `lunch_slow_pm: int = 840`.
  - Test: `test_news_calendar.py::test_lunch_length_by_am_speed`. Fast-AM day: a 13:05 PM setup arms. Slow-AM day: it does not; a 14:02 setup does.

### 16. T8-lunch-trending-days
- **rule_id / kind:** T8 / missing_condition. Scope: index. judgment = true.
- **Rule:** If the day profile is a two-session up/down close (trending) day, do not expect lunch consolidation or retrace; lunch can stay active in the trend direction, depending on the catalyst behind the move. On other profiles, lunch = consolidation with shallow retracements.
- **Sources:** cc10_013_P5pyzmgZA1s ~00:16:58.
- **Quotes:** "the only time that the lunch hour is different is when we see the trending days" (cc10_013).
- **Conflicts:** none.
- **Rulebook fix:** T8 / T13: add the trending-day exception (cc10_013 ~16:58).
- **BUILD SPEC (management_exits):**
  - Where: the `am_exit` block (~2693). With `am_exit_trend_hold` on and `trend_day(ctx, i)` true at 720 with the open position in the trend direction, skip the 12:00 `am_exit` and keep the trade's ladder/trail to the session close. The lunch gates from items 11 and 13 are skipped on such days.
  - Params: `am_exit_trend_hold: bool = False`.
  - Test: `test_management_exits.py::test_am_exit_trend_hold`. Trend day long open at 11:59: with the switch it is still open at 12:30; without it, it exits at 12:00 with `am_exit`.

---

## D. PM session (T8, T9)

### 17. T9-pm-start-time
- **rule_id / kind:** T9 / shortened. Scope: index. judgment = true.
- **Rule:** PM start: arrays and reactions before ~13:20 are too early; expect the PM move 13:20-13:30, with 14:00 preferred. Chop between the lunch macro and 14:00 is time distortion (no signal). From 14:00, require displacement in the bias direction. CC: one PM swing daily 13:00-16:00, typically starting ~14:00 (cc10_012), and cc10_014 starts it right after the 12-13 lunch. Param pm_start in {13:00, 13:20, 13:30, 14:00}. The "origin 14:00 +/- 15 min" window is our interpretation.
- **Sources:** 019_ZrZJmwrMxFY ~00:20:37; 075_vN2BkfyRWE4 ~01:40:05; cc10_012_qZg_5bac518 ~00:01:52; cc10_014_yWBxZsbmK1U ~00:19:07.
- **Quotes:** "115. it's a little too early for my liking" (019); "all of this consolidation is time Distortion" (075).
- **Conflicts:** cc10_012 / cc10_014 open the PM at 13:00 vs 019 "too early" at 13:15 vs 075 / Ep 01 14:00 vs bot 13:30. Add cc10_014 to D7.
- **Rulebook fix:** T9: add the 13:20 cutoff (019 ~20:37), 14:00 preferred, the 075 time-distortion rule, cc10_014 in D7.
- **BUILD SPEC (news_calendar_times; extends section 3 T9):**
  - Where: `Params.pm[0]` already sets the PM start (810). Add `pm_array_from`: in `_scan_core` for `session == "PM"`, the entry array (FVG/OB/breaker) must be created at or after `pm_array_from`, so arrays from the lunch chop are not triggers. With `pm_1400_disp` on, PM setups between 810 and 840 are skipped, and from 840 the MSS leg must pass the displacement test (M1.2 `displacement_mult`); its first FVG is tagged `pm_1400`.
  - Params: `pm_array_from: int = 0` (0 = off; test 800 / 810 / 840), `pm_1400_disp: bool = False`. Preset grid: `pm[0]` in {780, 800, 810, 840}.
  - Test: `test_news_calendar.py::test_pm_array_from`. An FVG formed at 13:05 retested at 13:40: skipped with `pm_array_from=810`, taken with 0.

### 18. T9-pm-faster-measured-move
- **rule_id / kind:** T9 / missing_rule. Scope: index. judgment = true.
- **Rule:** Index PM measured moves tend to be faster than the AM's (cc10_012). Open-outcry profiles (067): (1) lunch reverses the AM; (2) trending: AM low -> lunch high -> run into 15:00-16:00; (3) AM move, 12-13 consolidation, then the PM repeats the AM's size 14:00-16:00 in about half the time; (4) AM move, then consolidation for the rest of the day. Which profile applies comes from the calendar and the weekly draw (the mapping is our interpretation). cc10_007 (bonds): a large share of ADR in the AM -> abbreviated PM. Test as statistics first.
- **Sources:** 067_vuBRMFhFZAY ~00:39:22; cc10_007_JpV-J31mxhg ~00:08:46; cc10_012_qZg_5bac518 ~00:01:52.
- **Quotes:** "it would do it in half the time" (067); "measured moves in the afternoon tend to be faster" (cc10_012).
- **Conflicts:** none.
- **Rulebook fix:** T9 / T13: add the four open-outcry profiles (067 ~39:22) and "PM measured moves are faster" (cc10_012 ~1:52); cite cc10_007 as the bond lesson.
- **BUILD SPEC (day_week_context, study first):**
  - Where: `study.py` new `pm_profile_study(days)`: per day, AM leg size S and duration (09:30-12:00 extreme to extreme), PM leg size and duration (14:00-16:00), and a profile label 1-4 (reversal / trending / measured / consolidation; thresholds: PM leg >= 0.7 S = "measured", PM range < 0.3 S = "consolidation" [our interpretation]). Report the ratio PM duration / AM duration. Only if profile 3 holds: engine switch `pm_mm_target` adds a target rung at AM extreme + S (in the AM direction) for PM continuation trades in `_targets`.
  - Params: `pm_mm_target: bool = False`.
  - Test: `test_day_week_context.py::test_pm_profile_study_labels`. Synthetic measured-move day: label 3, PM/AM duration ratio 0.5.

### 19. T8-pm-carry-condition
- **rule_id / kind:** T8 / missing_condition. Scope: index. judgment = true.
- **Rule:** The draw carries to the PM/last hour only if it is still untouched AND the AM move has not been fully erased (retraced). Skip candidate targets that price has already traded through both ways (balanced); target only the next remaining inefficiency or pool. Template (015): the AM reaches the nearer levels, lunch consolidates, the PM runs to the farther one, though the market may do it all before lunch. Measuring "erased" as a retrace to the AM leg origin is our interpretation.
- **Sources:** 015_QKvjPltjsqU ~00:06:21; 029_dwJcsi3ddFg ~01:30:37.
- **Quotes:** "consolidate during lunch, and then run up into that level here during the PM session" (015); "we haven't really fully erased everything that we put in this morning" (029).
- **Conflicts:** none.
- **Rulebook fix:** T8 carry rule (029 ~1:29:48): add "only if the AM move is not erased; skip balanced zones (029 ~1:30:37)".
- **BUILD SPEC (targets_partials; extends section 3 T8 `pm_carry_draw`):**
  - Where: the PM lock in `_lock_step` / `_lock_times` (~2205-2290). With `pm_carry_erase` on, the AM draw carries to the PM only if price has not traded back to `ctx.am_leg` origin (1 tick through) between the AM extreme and 13:30. In `_targets`, with `skip_balanced` on, drop a candidate level when, since it formed, price has traded through it in both directions (a close above and a close below it).
  - Params: `pm_carry_erase: bool = False`, `skip_balanced: bool = False`.
  - Test: `test_targets_partials.py::test_pm_carry_not_erased`. AM rally from 4000 to 4020, untouched draw 4030: lunch dips to 4010 -> PM draw stays 4030; lunch dips to 3998 -> no carried draw. A level crossed both ways is not in the ladder.

---

## E. AM session and opening range (T4, T5, L3)

### 20. T5-am-session-to-noon
- **rule_id / kind:** T5 / shortened. Scope: index. judgment = false.
- **Rule:** Index AM session 08:30-11:00, which can extend to 12:00 (044; 073 says 08:30-12:00), nesting 09:50-10:10, the 10:00-11:00 SB and 10:50-11:10. The AM trend usually ends 10:30-11:00 (cc09_006); lunch 11:00-13:00 per cc09_006. Hold open AM positions to 12:00 at the latest (X10/D16). Add an am_session=(08:30,12:00) variant.
- **Sources:** 044_LN1nfYp4dBw ~00:55:47; 073_fXVJnBVizYY ~00:14:36; cc09_006_OVfn-gDk2dE ~00:22:27.
- **Quotes:** "it can go as far as noon the beginning of New York lunch hour" (044); "the end of the morning session or the am trend" (cc09_006).
- **Conflicts:** cc09_006 lunch 11:00-13:00 vs T8 12:00-13:00/13:30.
- **Rulebook fix:** T5: add 073's 08:30-12:00, the "can extend to noon" clause (044) and cc09_006's AM-trend end 10:30-11:00.
- **BUILD SPEC (news_calendar_times; extends section 3 T5 / Ep01.10 `am_from_0830`):**
  - Where: Params `am` already sets the AM window and `am_exit=720` already closes leftovers at 12:00 (built). Add the preset `am_session="0830_1200"` resolved in `__post_init__` to `am=(510, 720)` (with Ep01.10's 510 snapshot so the overnight pools are complete at 08:30) and `am_trend_end`: no new AM entries after `am_trend_end` (660) while positions may run to `am_exit`.
  - Params: `am_session: str = "default"` ("default" = `am` as set / "0830_1200"), `am_trend_end: int = 0` (0 = off; test 630 / 660).
  - Test: `test_news_calendar.py::test_am_session_variant`. With "0830_1200" a setup at 11:30 arms; with `am_trend_end=660` it does not, while a position opened at 10:40 is still open at 11:45.

### 21. T4-or-length
- **rule_id / kind:** T4 / unlisted_contradiction. Scope: index. judgment = true.
- **Rule:** Compute OR20 (09:30-09:50), OR30 (09:30-10:00) and OR60 (09:30-10:30) highs/lows. 073: the OR can be used after 20 min; liquidity taken outside OR20 informs the 09:50-10:10 macro's next draw. 2023 "don't trade the OR" uses OR30; CC index rules use OR60. Add a decision item with param or_minutes in {20, 30, 60}.
- **Sources:** 073_fXVJnBVizYY ~00:25:03; cc10_010_ORbtHOUzAIM ~00:11:09.
- **Quotes:** "it can form in 20 minutes" (073); "the full spectrum is a 60-minute opening range" (cc10_010).
- **Conflicts:** T4 2023 "OR = 09:30-10:00 always" vs 073 OR usable after 20 min vs cc10_010 60-min OR.
- **Rulebook fix:** T4: add OR20 (073 ~25:03) and a D-decision "or_minutes in {20, 30, 60}".
- **BUILD SPEC (levels_detectors):**
  - Where: `Params.or_minutes` (~191) already accepts 30 / 60; `DayCtx` (~1203) builds the OR from it. Allow 20 (validate in `__post_init__` to {0, 20, 30, 60}). Store `ctx.or20` alongside `ctx.or60` (~2558) so item 2's macro branch can read OR20 regardless of `or_minutes`. `or_extra` (L3) keeps adding the other OR.
  - Params: `or_minutes` accepts 20 (no new field).
  - Test: `test_levels_detectors.py::test_or20_pool`. With `or_minutes=20` the OR high is a pool usable from 09:50 (`or_end = 590`) and `ctx.or20` matches the 09:30-09:49 high/low.

### 22. L3-or-refs-expire-1100
- **rule_id / kind:** L3 / shortened. Scope: index. judgment = false.
- **Rule:** At 10:00, record the OR30 (09:30-10:00) high/low and the FVGs formed inside it. Use them as sweep/target pools and entry arrays for 10:00-11:00 (including the SB). Stop treating them as OR references after 11:00. The expiry rule comes from a single source (090).
- **Sources:** 090_bhYcXBI3z9U ~00:49:21.
- **Quotes:** "the opening range and whatever liquidity is established at that point we use that going forward into 11 o'clock" (090).
- **Conflicts:** none.
- **Rulebook fix:** L3 / P2: "OR pools and OR FVGs are AM references until 11:00 (090 ~49:21)."
- **BUILD SPEC (levels_detectors; extends section 3 L3):**
  - Where: `DayCtx` OR block (~1203) also stores `ctx.or_fvgs` (FVGs created between 570 and `or_end`). In `_targets` and the sweep pool list, drop the `opening_range` kind when `t >= or_expire` (660). In `_scan_core` entry-array selection, `or_fvg_entries` lets an OR FVG be the entry array for setups armed in 600-660 (SB included via `sb_model._arm`'s array list).
  - Params: `or_expire: int = 0` (0 = never; test 660), `or_fvg_entries: bool = False`.
  - Test: `test_levels_detectors.py::test_or_refs_expire`. OR high untaken at 11:05: not a pool/target with `or_expire=660`, still one with 0. An OR FVG retested at 10:20 is the entry array with `or_fvg_entries`.

### 23. N5-pre0930-entries
- **rule_id / kind:** N5 / unlisted_contradiction. Scope: index. judgment = true.
- **Rule:** Test switch `pre_open_entries` (default off): on index futures, allow the normal model (sweep -> MSS/breaker -> FVG/OB toward a defined draw) 07:00-09:29 when the setup is obvious (022 ~2:14; 096 ~8:29; 018 ~8:25). On 08:30-news days a post-release fade is allowed: the spike into an HTF OB plus an LTF VI consolidates, then a short follows (050 ~34:08-48:14; exact entry minute not stated). If the draw is delivered before 09:30, take no AM entries and trade the PM (N9). Treat this as an addition to T4's "earlier setup only if obvious". N5's "wait for 09:30" covers only no-08:30-news days, so this does not contradict it.
- **Sources:** 022_ALMsQytQ1fg ~02:14:11; 018_eTMS36H7HA0 ~00:08:25; 096_tjnir-o4rsQ ~00:08:29; 050_F509lJRrYIM ~00:34:08.
- **Quotes:** "There's nothing saying you can't trade 7:00 to 9:00 in the morning." (022); "it's almost eight o'clock" (096).
- **Conflicts:** N5 (Ep 05; 007; 019) "wait for 09:30" applies to no-news days only; N5's news-range wait vs 050's entry after the release.
- **Rulebook fix:** T4 / N5: add "Pre-09:30 entries on the normal model when obvious (022 ~2:14; 096; 018) - switch, off by default; 08:30-news post-release fade into HTF OB + LTF VI (050)".
- **BUILD SPEC (news_calendar_times; the base windows are already built):**
  - Already in code: `pre_0700` (07:00-08:30, `pre_flat_0830`), `pre_0900` (09:00-09:29), `post_news` (08:30-day 09:00-09:29 off the 08:30-09:00 range) (strategy.py ~202-208; `pre_open_entries.md`). Section 3 T5 `pre_0820` covers 08:20. Only two pieces are new:
  - Where: (1) `post_news_fade`: in the `NEWS` pre-window, a short (long) only after the release spike trades into an htf OB (`htf_targets` "15m"/"1h") overlapping a 1m/5m VI (`vi_arrays`) and the next 3+ bars fail to make a new extreme; entry = VI near edge, stop = VI far edge + 1 tick. (2) `pre_draw_done_am`: when a pre-window trade reaches the session lock draw before 570, set `done["AM"] = True` (PM untouched).
  - Params: `post_news_fade: bool = False`, `pre_draw_done_am: bool = False`.
  - Test: `test_news_calendar.py::test_post_news_fade_and_draw_done`. CPI day: spike at 08:31 into a 15m OB with a 1m VI, stall to 08:40: short armed. A PRE9 long reaching the draw at 09:20: no AM scan with `pre_draw_done_am`.

### 24. new-premarket-difficult-days
- **rule_id / kind:** new / missing_rule. Scope: index. judgment = true.
- **Rule:** If the day is expected to be hard to read because of a high-impact driver later today (e.g. FOMC at 14:00) or tomorrow, and there is a medium/high-impact 08:30 release today: allow entries 07:00-08:29 on the normal model when the structure is clear. Hold through 08:30, letting the release deliver price toward the pool target. (Not stated by ICT, our addition: no AM/PM trades after the target fills.) Off on other days.
- **Sources:** 032_SSWN6YSVyFY ~00:06:00.
- **Quotes:** "I will adopt the seven o'clock to 8 30 time window" (032).
- **Conflicts:** `pre_flat_0830=True` (bot flattens pre-open trades before an 08:30 release) vs 032 holding through the release.
- **[our interpretation]:** stop for the day after the target fills.
- **Rulebook fix:** T6 / N5: add "On days with FOMC later or a high-impact driver tomorrow, plus an 08:30 release today, ICT uses 07:00-08:30 and holds through the release (032 ~6:00)."
- **BUILD SPEC (news_calendar_times):**
  - Where: `run_day` pre-window setup (~2567). With `pre_0700_hard_days` on: add `PRE7` only when `news(day) == "0830"` AND (`fomc` in today's tags OR `next_trading_day(day)` has a high-impact event from `calendar.py`); on those days skip `pre_flat_0830` (hold through the release). With `hard_day_one_trade` on, a PRE7 target fill sets `done` for AM and PM.
  - Params: `pre_0700_hard_days: bool = False`, `hard_day_one_trade: bool = False`.
  - Test: `test_news_calendar.py::test_pre0700_hard_days`. CPI day with FOMC: a 07:40 long survives 08:30; CPI day without FOMC/next-day event: no PRE7 window.

### 25. new-hold-pre0930-through-open
- **rule_id / kind:** new / missing_rule. Scope: index. judgment = true.
- **Rule:** If a pre-09:30 position is funded (partials booked) and its target is untaken, it may be held through 09:30 with the stop behind the HTF array/bodies. Expect delivery at the open. If price drifts lower into the open (long case; short mirror), flag `risk_0930_sweep`: the open may run the low and the stop first. ICT's mitigation is being funded with partials already taken, not reducing size. Do not hold an unfunded pre-open position through 09:30 under this flag (our interpretation).
- **Sources:** 105_A97shZGPE2I ~00:39:20, ~00:44:52.
- **Quotes:** "at 9:30 we're really going to rip up into this area here if it doesn't do before" (105); "the more likely that they'll want to take the 930 run rip that low" (105).
- **Conflicts:** T4 "don't trade the OR".
- **[our interpretation]:** drift = the last 20 min (550-570) of 5m closes in the lower third of the post-entry range.
- **Rulebook fix:** new rule under T4: "Holding a funded pre-09:30 position through the open (105 ~39:20, ~44:52); drift into the open raises the 09:30 sweep risk."
- **BUILD SPEC (management_exits):**
  - Where: position loop (~2590-2716) at bar 569 for trades with `session` in PRE7 / PRE9 / NEWS. Compute `risk_0930_sweep` (drift test). With `pre_hold_open` on: funded (a partial taken) -> hold, tag the flag; unfunded and flagged -> exit at 09:29 close (reason `pre_open_unfunded`); unfunded and not flagged -> hold.
  - Params: `pre_hold_open: bool = False`.
  - Test: `test_management_exits.py::test_pre_hold_open`. Funded PRE9 long with drift: held past 09:30, tag set. Unfunded with drift: closed at 09:29.

### 26. T4-no-early-entry-conditions
- **rule_id / kind:** T4 / missing_condition. Scope: index. judgment = false.
- **Rule:** Disallow early entries (pre/at 09:30) when a second scheduled driver is still pending (e.g. 10:00 news on an 08:30 day, which is consistent with N5) or when untaken liquidity pools sit close on both sides of price, especially beyond the stop. The Friday/targets-met-week condition is not stated in 100 ~1:26:48; drop it, or source it separately (N10 cites 100 ~7:05).
- **Sources:** 100_GJeEU2oIh24 ~01:26:48.
- **Quotes:** "this is one of those instances where I wouldn't do it" (100).
- **Conflicts:** none.
- **[our interpretation]:** "close" = within the trade's risk distance.
- **Rulebook fix:** T4 early-entry exception: add the two disable conditions (100 ~1:26:48).
- **BUILD SPEC (news_calendar_times):**
  - Where: `run_day` pre-window loop (~2821): with `pre_entry_guard` on, skip PRE7 / PRE9 / NEWS / `or_deep` sessions when `release_times(day)` has a release at or after 600 that day, and in `_scan_core` reject a pre-open order when an untaken pool (from `ctx.sess` / `_eq_levels`) lies beyond the stop within one risk distance.
  - Params: `pre_entry_guard: bool = False`.
  - Test: `test_news_calendar.py::test_pre_entry_guard`. CPI day with ISM at 10:00: no PRE9 trade. No 10:00 release but an untaken low 1 pt under the stop: rejected.

### 27. M9-fomc-1430
- **rule_id / kind:** M9 / wrong. Scope: index. judgment = false.
- **Rule:** FOMC is a two-stage event: the 14:00 statement move is usually false (a "red herring"), and the real move comes at/after 14:30 (021 ~2:46, ~6:28, ~18:38; 065B ~5:33). Observe only until ~14:45 (021 ~6:00). Drop "14:25" unless a source is found. The minute-level sequence inside 14:30-14:45 is unverified from the transcripts.
- **Sources:** 021_DVxC7UAHzwk ~00:02:40.
- **Quotes:** "at 2 30 the real move comes in" (021).
- **Conflicts:** none in the sources: the rulebook's "14:25" has no source.
- **Rulebook fix:** N3 / M9: replace "14:25-14:30 (021)" with "14:30 (021 ~2:46, ~6:28, ~18:38; 065B ~5:33); observe until ~14:45".
- **BUILD SPEC (news_calendar_times; corrects section 3 M9.2):**
  - Where: section 3 M9.2 specifies `fomc_judas` with "a 14:00-14:25 range, fomc_pm_from 865". Change that spec to a 14:00-14:30 range (stage 2 from 870) and keep `fomc_pm_from` default 885 (14:45, ~172, already the observe-until time). No other change.
  - Params: `fomc_stage2_from: int = 870` (used by `fomc_judas` when built).
  - Test: `test_news_calendar.py::test_fomc_stage2_time`. FOMC day: the stage-1 range is 14:00-14:29; no FOMC-day PM entries before 14:45 with the default.

---

## F. Waiting and time distortion

### 28. new-10min-wait-choppy
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** Judgment/research: when price is lethargic and choppy before any setup, wait ~10 minutes (10 one-minute bars) before acting; then take only a normal-model setup (displacement + FVG toward the draw). This is a single anecdote from a Fed-speaker day (027 ~25:03), not a stated rule.
- **Sources:** 027_STEGBblm4dI ~00:25:03.
- **Quotes:** "I'm gonna give it 10 minutes and see what it does" (027).
- **Conflicts:** none.
- **[our interpretation]:** "choppy" = the existing `Chop` detector (~2040) is on.
- **Rulebook fix:** add a research note under X9: "027 ~25:03: a 10-minute wait when price is lethargic and choppy (single anecdote)."
- **BUILD SPEC (news_calendar_times):**
  - Where: `run_day` after `chop.update(i)` (~2817). With `chop_wait_bars > 0`: when `chop.on` turns true and no position/pending exists, set `wait_until = i + chop_wait_bars`; skip scans until then; after it, require the M1.2 displacement test on the MSS leg.
  - Params: `chop_wait_bars: int = 0` (test 10 on 1m).
  - Test: `test_news_calendar.py::test_chop_wait`. Chop detected at 10:05: a 10:09 setup is skipped, a 10:16 setup with displacement is taken.

### 29. new-time-distortion
- **rule_id / kind:** new / missing_rule. Scope: index. judgment = true.
- **Rule:** Treat as time distortion (no swing points, MSS, breaker or FVG signals; no direction inferred): (a) after the session extreme is set, bodies staying inside an FVG for several bars during 10:00-12:00 (wicks may poke out) -> expect continuation toward the original draw, the FVG stays a valid entry; (b) sub-5m consolidation in the minutes before a scheduled high-impact release; (c) bars after 16:00; (d) chop between the lunch macro and 14:00. Liquidity seeking resumes in market hours/macros.
- **Sources:** 060_ZtLMTXv-Dr0 ~00:24:12; 100_GJeEU2oIh24 ~00:42:21; 075_vN2BkfyRWE4 ~01:40:05.
- **Quotes:** "the Wicks will go just outside that fair value Gap but that's okay" (060); "it's being held for a news event ... being held for a session close" (100).
- **Conflicts:** none.
- **[our interpretation]:** "several bars" = 5+; "minutes before a release" = 15 min.
- **Rulebook fix:** A13: generalize "time distortion" with the four cases above (060 ~24:12; 100 ~42:21; 075 ~1:40).
- **BUILD SPEC (levels_detectors + news_calendar_times):**
  - Where: new `levels.time_distortion_mask(t, releases, p)` returning True for bars in (b) 15 min before each `release_times(day)` entry, (c) >= 960, (d) 730-840 when `td_lunch` is on. In `_scan_core`, swings/MSS/FVGs whose defining bars fall under the mask are not triggers (filter the swing list and the FVG list by creation bar). Case (a): with `td_fvg_hold` on, an FVG whose wicks are pierced while bodies stay inside during 600-720 keeps `valid=True` (not invalidated by the wick test).
  - Params: `time_distortion: bool = False`, `td_lunch: bool = True`, `td_fvg_hold: bool = False`.
  - Test: `test_levels_detectors.py::test_time_distortion_mask`. A 13:15 swing low is not an MSS reference with the switch; an FVG wicked through at 10:40 with bodies inside stays valid with `td_fvg_hold`.

---

## G. London and the overnight sessions (T3, T13)

### 30. T3-london-extreme-consolidation
- **rule_id / kind:** T3 / missing_condition. Scope: index. judgment = true.
- **Rule:** If the market has been chopping inside a range since at least the prior session (010: since the previous morning), do not assume the London 02:00-05:00 extreme is the day's high/low; let NY confirm. Otherwise expect it in London (bearish HOD / bullish LOD).
- **Sources:** 010_cWekmMLqiNM ~00:39:18.
- **Quotes:** "the largest portion of the day can many times form overnight in London unless we are in consolidations" (010).
- **Conflicts:** none.
- **[our interpretation]:** "chopping inside a range since the prior session" = the prior RTH range < 0.6 x ADR5 and overnight stays inside it.
- **Rulebook fix:** T3: add the consolidation exception (010 ~39:18).
- **BUILD SPEC (day_week_context):**
  - Where: `day_context()` (~1902) adds tag `consol_overnight` when the test holds. Wherever the London pool is treated as the day's protected extreme (`session_priority`, `_lock_times` candidates), with `london_ext_consol` on, the London high/low is not the protected extreme on `consol_overnight` days (it remains a pool).
  - Params: `london_ext_consol: bool = False`.
  - Test: `test_day_week_context.py::test_consol_overnight_tag`. Narrow prior day with an inside overnight: tag set; trending prior day: not set.

### 31. new-ny-runs-london-extreme-news
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** Bearish day, London (02:00-05:00) made the high and broke down: with no medium/high-impact release, treat the NY retrace as a continuation sell with the London high as invalidation; expect NY to run above the London high only on a news day. Bullish mirror.
- **Sources:** 065_rx15_eN9sxI ~03:07:01.
- **Quotes:** "those are always on the heels of a higher medium impact news driver" (065).
- **Conflicts:** none.
- **Rulebook fix:** T3: add "NY runs out the London extreme and reverses only on medium/high-impact news days (065 ~3:07)."
- **BUILD SPEC (setups_models):**
  - Where: `_scan_core` side gate. With `london_ext_guard` on, on days with no release in `release_times(day)` and a London extreme that held (London high = overnight high for a down London leg), an AM long setup whose target is above the London high is dropped, and an AM short uses the London high as its maximum stop (stop = min(model stop, London high + `stop_buffer`)). On news days nothing changes.
  - Params: `london_ext_guard: bool = False`.
  - Test: `test_setups_models.py::test_london_ext_guard`. No-news bearish London day: a long toward the London high is rejected; the same day tagged CPI: it arms.

### 32. new-london-confirm-after-daily-signal
- **rule_id / kind:** new / missing_rule. Scope: index. judgment = true.
- **Rule:** After a bearish daily signal (down-close outside day into a daily inefficiency low), require London (02:00-05:00) to confirm before taking NY shorts. London should trade below the inefficiency low, then retrace into it or the day's lower wick and reject with displacement lower. Then sell a 1m/5m FVG or short-term premium; targets are the relatively equal lows, then the daily lower-wick CE. Invalidation: trading above the outside day's high. If London only consolidates, deprioritise the NY short. ICT said this in August, so it carries extra caution. Bullish mirror is our extension.
- **Sources:** 081_0xYpeVRi_qs ~00:09:24.
- **Quotes:** "I'd like to see the London session really support the idea" (081).
- **Conflicts:** none.
- **[our interpretation]:** "London only consolidates" = the 02:00-05:00 range < 0.3 x ADR5 or no trade below the inefficiency low.
- **Rulebook fix:** B-section outside-day rule (line 255, 081 ~1:31): add the London-confirmation condition (081 ~4:30-9:24).
- **BUILD SPEC (bias_htf):**
  - Where: `htf.table` already flags the outside day (B11b `outside_day_rule` in section 3). In `run_day`, at 300 (London complete), with `london_confirm` on and yesterday a down-close outside day into a daily BISI low: London confirmed = traded below the BISI low AND a 5m close back below it after a retrace into it. Not confirmed -> AM shorts blocked (or `risk_mult` 0.5 with `london_confirm="half"`). Invalidation: AM shorts blocked once price trades above the outside day's high.
  - Params: `london_confirm: str = "off"` ("block" / "half").
  - Test: `test_bias_htf.py::test_london_confirm`. Outside-day setup, London trades below the BISI low and rejects: AM short allowed. London inside: blocked.

### 33. T13-fx-daily-session-template
- **rule_id / kind:** T13 / missing_rule. Scope: general (sources FX). judgment = true.
- **Rule:** FX, bearish HTF day (bullish mirrors), NY time: open (00:00 / 0 GMT) at or near the eventual HOD, a small move above the open allowed (small Asian counter-move ignored). HOD forms 02:00-05:00 with ~70% probability only when the HTF narrative/array supports it (065 ~2:11). London leg = 40-60% of the day's range by 05:00 (tag london_share). 05:00-07:00 London lunch: small retracement/consolidation. NY 07:00-10:00: second leg (possible 08:00-08:30 retrace) toward the ADR5 low; if ADR5 is hit before 10:00 take ~80% off. LOD normally forms in London close 10:00-12:00 at/beyond the ADR5 projection, then price retraces/consolidates and closes off the low; on explosive days the extreme can extend to the 15:00 bond close (not a 13:00 cap). Generally done by noon (cc08_001). Tags/stats only; for index futures keep T12 (opposite extreme 15:00-16:00) and test the 10:00-12:00 variant on trending days.
- **Sources:** 065_rx15_eN9sxI ~02:10:04; cc01_002_XwYYWBttWro ~00:16:14; cc08_002__2nUKLAD9ig ~00:09:24; cc09_006_OVfn-gDk2dE ~00:10:28; cc09_007_-oMtfDvc18Y ~00:05:13; 008_cxdjcXec3eA ~00:05:29.
- **Quotes:** "usually does about anywhere between 40 and 60 of the daily range before we get to 5 a.m New York time" (cc09_006); "between 5 a.m and 7 A.M New York time this is the London lunch" (cc09_006).
- **Conflicts:** 008 (Ep 06) opposite extreme 10:00-12:00 vs T12 index 15:00-16:00 (cc10_011; cc10_012); cc01_002 London close 10:00-11:00 vs 10:00-12:00.
- **Rulebook fix:** T13: add the FX template above with its clock anchors and figures, marked FX; note the index T12 conflict.
- **BUILD SPEC (day_week_context, study only on ES all-hours data):**
  - Where: `study.py` new `session_template_study(days)` on Databento ES 1m all-hours: per day, `london_share` = (London 02:00-05:00 leg) / day range (00:00-16:00), the minute of HOD and LOD binned by session (Asia, London, London lunch, NY 07:00-10:00, London close 10:00-12:00, PM, last hour), split by daily direction and by `trend_day`. No engine change.
  - Params: none.
  - Test: `test_day_week_context.py::test_session_template_bins`. Synthetic day with HOD at 03:10 and LOD at 11:20: bins "london" / "london_close", `london_share` computed.

### 34. T3-london-close-window
- **rule_id / kind:** T3 / unlisted_contradiction. Scope: general. judgment = false.
- **Rule:** london_close KZ = 10:00-12:00 NY (cc08_002 "definitive"); variant (10:00,11:00) per cc01_002. Separate filter for the London-close counter-trend scalp (cc09_006/007): only if London and NY moved in the same direction, the ADR5 high/low has been reached (ideally exceeded) and time >= 10:30; entry 10:30-13:00 on a 5m failure swing + OB, stop 10 pips beyond the day's extreme, target 20-30% of the day's range. Drop cc08_001 (its 14:00-15:00 window is the New York close/bond close, not London close).
- **Sources:** cc01_002_XwYYWBttWro ~00:16:34; cc09_006_OVfn-gDk2dE ~00:23:14; cc08_001_-cXnnHjy9s0 ~00:16:11.
- **Quotes:** "going up into 10:00 or 11:00 in the morning New York time where it will have a reversal again that's London close" (cc01_002).
- **Conflicts:** cc01_002 10:00-11:00; Ep 06 / cc08_002 10:00-12:00; cc09_006 10:30-13:00 (setup filter).
- **Rulebook fix:** T3: "London close 10:00-12:00 (cc08_002); variant 10:00-11:00 (cc01_002). cc09_006's 10:30-13:00 is the scalp filter, not the kill zone. cc08_001's 14:00-15:00 is the NY close."
- **BUILD SPEC:** none of its own. The `london_close` window Param is defined in item 54 (the only engine user).

### 35. T3-london-kz-window
- **rule_id / kind:** T3 / unlisted_contradiction. Scope: general. judgment = false.
- **Rule:** london_kz = 01:00-05:00 NY per cc08_002 "definitive" (02:00-05:00 as a switch); compute the London pool over the chosen window. HOD (bearish)/LOD (bullish) 02:00-04:00 is a conditional stat, expected only under the London normal-protraction profile (CBDR<40 pips or Asian range 20-30 pips, protraction right after 00:00 into ~02:00 reaching 1-2 SD of CBDR/Asian range); delayed-protraction profile: Judas at/after 02:00. FX day-trade entries 02:00-04:00 at 1-2 SD + PD array on 15m/5m remain fx-only (M17).
- **Sources:** cc08_002__2nUKLAD9ig ~00:08:30; cc08_005_eU8WcUftUtY ~00:07:15; cc08_007_5Z_3NbclMSY ~00:07:39.
- **Quotes:** "the time window begins at 1am it ends at 5am" (cc08_002).
- **Conflicts:** cc08_002 01:00-05:00 "definitive" vs Ep 06 / T3 02:00-05:00 vs cc08_005 / cc08_007 02:00-04:00.
- **Rulebook fix:** T3: "London KZ 01:00-05:00 (cc08_002 definitive), 02:00-05:00 as a switch; HOD/LOD 02:00-04:00 is conditional on the normal-protraction profile (cc08_005), FX."
- **BUILD SPEC:** already listed in rule_coverage.md section 3 news_calendar_times **Ep06.1** ("`london_kz` (a LON window, futures only), `london_kz_start` and `ny_kz_futures`"), same content: `london_kz_start` in {60, 120} also sets the `ctx.sess["london"]` window start (~1172). No new spec.

### 36. T3-ny-kz-0700-1000
- **rule_id / kind:** T3 / unlisted_contradiction. Scope: general. judgment = false.
- **Rule:** ny_kz = 07:00-10:00 NY (cc08_002 definitive); 07:00-09:00 (Ep 06, FX) as a variant. Futures/index window (08:20/08:30-11:00, T5) stays a separate parameter.
- **Sources:** cc08_002__2nUKLAD9ig ~00:04:05.
- **Quotes:** "every day at 7 A.M Eastern Standard Time New York Begins the New York Kill Zone" (cc08_002).
- **Conflicts:** Ep 06 07:00-09:00 (FX) vs cc08_002 07:00-10:00.
- **Rulebook fix:** T3: "NY KZ 07:00-10:00 (cc08_002 definitive); 07:00-09:00 (Ep 06, FX) variant; the futures window is separate (T5)."
- **BUILD SPEC:** already listed in section 3 **Ep06.1** (`ny_kz_futures`), same content. No new spec.

### 37. T8-london-lunch
- **rule_id / kind:** T8 / missing_rule. Scope: general. judgment = true.
- **Rule:** london_lunch = 05:00-07:00 NY. Expect quiet: consolidation, a small retracement, or continuation of London's direction; it prepares the next leg (continuation or, less often, reversal, cc08_001). Kill-zone scalps should not fill here (cc09_006); FX exception (cc09_007): a retrace into a premium (discount) array during 05:00-07:00 may be scalped in London's direction. No 05:30 bleed rule (unsourced).
- **Sources:** cc08_002__2nUKLAD9ig ~00:07:48; cc09_006_OVfn-gDk2dE ~00:06:28; cc09_007_-oMtfDvc18Y ~00:05:13.
- **Quotes:** "this is London lunch this is generally when we're not looking for any major significant price moves" (cc08_002).
- **Conflicts:** none.
- **Rulebook fix:** T8: add "London lunch 05:00-07:00 (cc08_002 ~7:48; cc09_006 ~6:28): quiet, continuation or small retrace; FX-only scalp exception (cc09_007)."
- **BUILD SPEC:** none. The engine has no entry window in 05:00-07:00 (`sb_london` ends 04:00, `pre_0700` starts 07:00), so there is nothing to gate.

### 38. T3-asia
- **rule_id / kind:** T3 / unlisted_contradiction. Scope: general. judgment = false.
- **Rule:** Asian range (reference, 20:00-00:00 NY) is a level/range definition, not an entry window. Default: no entries in Asia in any instrument (095). FX-only switch: AUD/NZD/JPY pairs may use the Asian KZ 18:00-21:00 NY (to 22:00 at most, cc07_001) or an Asian-currency news release. Trading day begins 00:00 NY (095; cc08_002).
- **Sources:** 095_LPmMtq9jLm8 ~00:20:23; cc07_001_mQA8jCem9d0 ~00:30:43.
- **Quotes:** "I just don't think that you should be trying to trade the Asian system" (095).
- **Conflicts:** T3 "20:00-00:00 FX session" vs 095 no Asia trading vs cc07_001 18:00-21:00/22:00.
- **Rulebook fix:** T3: replace "Asia 20:00-00:00 is FX only (095)" with the rule above.
- **BUILD SPEC:** none. The engine has no Asia entry window.

### 39. new-protraction-windows
- **rule_id / kind:** new / missing_rule. Scope: fx_only. judgment = true.
- **Rule:** For t in {0 GMT (20:00 NY summer / 19:00 winter), 00:00 NY, 07:00 NY}: the first small impulse swing after t is the protraction (Judas) leg, counter to the main move that follows; do not trade with it; its extreme is the raid before the real move. 0 GMT: one small move away then reversal (tag only). 07:00: if London moved lower, the first rally after 07:00 into short-term highs/premium is the NY protraction to sell (mirror if London moved higher). FX-only (cc01_008); thresholds for "small" and london_dir are ours. For index futures test whether 08:30/09:30 Judas supersedes 07:00.
- **Sources:** cc01_008_K4LtfujVpJs ~00:11:32, ~00:03:27, ~00:04:54.
- **Quotes:** "there is a time element applied to the small impulse swing after midnight new york time after 7 a.m new york time and 8 p.m new york time" (cc01_008).
- **Conflicts:** none.
- **Rulebook fix:** M17: state the three protraction anchors (cc01_008) instead of only listing "London protraction models, 0 GMT entries" as out of scope. MT4 server-time caution (T1).
- **BUILD SPEC:** none (fx_only).

### 40. B12-midnight-judas-timing
- **rule_id / kind:** B12 / missing_condition. Scope: fx_only. judgment = false.
- **Rule:** FX: if the daily/4h is reacting from a premium array (bearish), the first impulse after the 00:00 candle above the midnight open is the London Judas (normal: 00:00-~02:00; scalpable from the open before 01:00 per cc09_006); if absent, look for a delayed protraction at or shortly after 02:00 (cc08_005). Monitor 00:00 to ~02:30-03:00; no Judas/setup by then -> no London profile. Sell after the Judas, projecting with 1-2 SD of CBDR/Asian range. Bullish mirror: drop at/after 00:00 below the open into a discount array, then buy; prefer fading the Judas over scalping it.
- **Sources:** cc01_008_K4LtfujVpJs ~00:04:22; cc09_006_OVfn-gDk2dE ~00:13:23; cc09_002_zanmou0ic5U ~00:19:01; cc08_005_eU8WcUftUtY ~00:19:10.
- **Quotes:** "we're going to anticipate price rallying up at New York's midnight candle or thereafter" (cc09_002).
- **Conflicts:** cc09_006 "prior to 1am" (scalp) vs cc08_005 delayed Judas at/after 02:00.
- **Rulebook fix:** B12: add the London Judas timing as an FX note (sources above).
- **BUILD SPEC:** none (fx_only).

### 41. T2-0820-cme-open
- **rule_id / kind:** T2 / missing_rule. Scope: fx_only. judgment = true.
- **Rule:** Add open_0820 (FX). Bullish day: NY long = buy the decline after 08:20 into a discount OB/FVG inside the NY KZ; bearish: the rally after 08:20 into a premium array is the NY Judas to short; targets ADR5 extreme and next 4h/1h array, 80% off if ADR5 hit before 10:00. Tag swing points formed ~08:20 as CME-open turning points. London close (bullish day): the rally after 10:00 that makes the HOD is the protraction to sell. For index futures test 08:30/09:30 as analogs [our interpretation].
- **Sources:** cc08_002__2nUKLAD9ig ~00:07:22; cc09_006_OVfn-gDk2dE ~00:20:37; cc09_007_-oMtfDvc18Y ~00:08:24.
- **Quotes:** "if you're bullish in New York you're looking for 8 20 and a due to swing dropping down after 8 20" (cc09_006).
- **Conflicts:** none.
- **Rulebook fix:** T2: add the 08:20 CME open (FX) and the per-session Judas list (cc09_006 ~20:37).
- **BUILD SPEC:** none (fx_only). The index analog is section 3 T5 `pre_0820`.

### 42. new-ipda-true-day
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** true_day = 00:00-15:00 NY (cc08_002); 15:00 bond close ends the daily range (cc08_001); keep a 16:00 index-close parameter. Inside the true day, 03:00-10:00 NY is the high-volume window (cc12_004), not an alternative true day. Prefer being positioned before 03:00 or in its first half; entries after the NY open get reduced objectives (soft switch, not a filter). CC day-trade variant: done by noon, FOMC days to ~15:00; list as a conflict with T10/M5 last-hour trades.
- **Sources:** cc08_002__2nUKLAD9ig ~00:05:19; cc08_001_-cXnnHjy9s0 ~00:16:11; cc12_004_Oec_0NM_OeY ~00:07:25.
- **Quotes:** "every day at 3 P.M New York time ends the ipta true day" (cc08_002); "the bulk of the daily volume will be between 3 AM and 10 a.m New York time" (cc12_004).
- **Conflicts:** cc08_001 "nothing after 15:00, done by noon" vs T10/M5 last-hour 15:00-16:00/16:15 (Ep 01; 032; Ep 08). A strict 03:00-10:00 filter would remove most bot entries (T5 09:30-11:00; T6 SB 10:00-11:00).
- **[our interpretation]:** the reduced-objective factor.
- **Rulebook fix:** T12: define the true day (cc08_002 ~5:19) and the 03:00-10:00 volume window (cc12_004 ~7:25); list the CC noon / 15:00 cutoff against T10/M5.
- **BUILD SPEC (bias_htf + targets_partials):**
  - Where: (1) `htf.table` (~95) daily OHLC: with `true_day="ipda"` the daily candle is built from 00:00-15:00 bars (open = first bar at/after 00:00, close = last bar ending at/before 15:00) instead of the session day. (2) `_targets`: with `late_obj_k < 1`, for entries after 570 the ladder keeps only rungs within `late_obj_k x adr5` of the entry (nearer targets). (3) CC variant preset `cc_daytrade`: `am_exit=720`, PM off (`pm=(0,0)`), FOMC days `pm=(840, 900)`.
  - Params: `true_day: str = "session"` ("session" / "ipda"), `late_obj_k: float = 1.0` (1.0 = off; test 0.5).
  - Test: `test_bias_htf.py::test_true_day_ohlc`. A day with a 15:30 high: with "ipda" the daily high excludes it. `test_targets_partials.py::test_late_obj_k`: a 10:05 entry with rungs at 0.3 and 0.8 ADR5 keeps only the first with 0.5.

### 43. T1-pdh-0gmt-boundary
- **rule_id / kind:** T1 / unlisted_contradiction. Scope: fx_only. judgment = true.
- **Rule:** FX (cc01_003, 2016): PDH/PDL were taken from the platform's 0 GMT day (20:00 NY in DST) and extended to the next 0 GMT boundary. List this as a conflict with T1 (cc08_002 midnight NY). Index: keep the pdh_boundary switch {rth, globex_18:00, midnight_ny}, default RTH for SPY.
- **Sources:** cc01_003_B7_cjybYQ0g ~00:20:51.
- **Quotes:** "draw them out to where zero gmt is which is eight o'clock in that evening" (cc01_003).
- **Conflicts:** T1 "ignore platform GMT dividers" vs cc01_003 0 GMT day.
- **Rulebook fix:** T1: list the cc01_003 0 GMT PDH/PDL boundary as an FX conflict.
- **BUILD SPEC:** none (fx_only). The index boundary switch already exists as L2 `pd_hl_session="eth"` (rule_coverage.md section 4).

### 44. T2-0gmt-open-condition
- **rule_id / kind:** T2 / missing_condition. Scope: fx_only. judgment = true.
- **Rule:** Primary open = 00:00 NY. Use the 0 GMT open only if price has stayed close to it (little range since 0 GMT, i.e. consolidation), e.g. 0 GMT-to-midnight range < 20% ADR5 (our threshold). FX-only.
- **Sources:** cc09_001__TNhWRPa6GA ~00:02:36.
- **Quotes:** "if the range from the zero GMT hour hasn't produced much of a range ... you can still incorporate that opening price" (cc09_001).
- **Conflicts:** none.
- **Rulebook fix:** T2: add the condition to the 0 GMT open (cc09_001 ~2:36).
- **BUILD SPEC:** none (fx_only).

### 45. new-cbdr-asian-range-filter
- **rule_id / kind:** new / missing_rule. Scope: fx_only. judgment = true.
- **Rule:** FX London precondition: CBDR (14:00-20:00 prior day) and Asian (20:00-00:00) must be small, tight consolidations. Wide, erratic or trending (net move > 0.7 x range, our interpretation) -> avoid London. CBDR > 50 pips -> likely pass on London (soft). Asian > 40 pips -> only the delayed-protraction profile if all its criteria are met, else no London. Index analog only as a test switch.
- **Sources:** cc08_006_stK2gNqhLaM ~00:10:59, ~00:09:28.
- **Quotes:** "if the agent range is greater than 40 Pips I'm going to consider the delayed protraction profile" (cc08_006).
- **Conflicts:** N9 (015): overnight range too narrow -> no NY AM trade (opposite sense, different session).
- **Rulebook fix:** M17 / L13: add the CBDR/Asian size preconditions for London (FX).
- **BUILD SPEC:** none (fx_only).

### 46. new-overnight-trend-from-2000
- **rule_id / kind:** new / missing_rule. Scope: general (fx-only per the checker). judgment = true.
- **Rule:** [fx-only] If price trends one way from 20:00 NY (sustained move, net > 0.7 x range, our interpretation): no London entries; tag `overnight_trend`; any retracement against it, if it comes at all, is usually in the NY session. Index use only as a test tag.
- **Sources:** cc08_006_stK2gNqhLaM ~00:09:45.
- **Quotes:** "that's usually a poor indication of a London session" (cc08_006).
- **Conflicts:** none.
- **Rulebook fix:** M17: add as an FX London precondition (cc08_006 ~9:45).
- **BUILD SPEC:** none (fx-only per the checker). If an index tag is wanted, add it to item 33's study (`overnight_trend` column), not the engine.

### 47. T3-london-news-manipulation
- **rule_id / kind:** T3 / missing_condition. Scope: fx_only. judgment = true.
- **Rule:** [fx-only] London (01:00-05:00 NY): check for a medium/high-impact release for the pair's currencies; expect the manipulation (stop run against bias) just before or at it; enter on the reversal after. No London news = wild-card day (cc08_006), not a clean setup.
- **Sources:** cc08_001_-cXnnHjy9s0 ~00:12:47.
- **Quotes:** "there should be some kind of a manipulation just before or at the time of the news release" (cc08_001).
- **Conflicts:** none.
- **Rulebook fix:** T3: add the London news condition as an FX note.
- **BUILD SPEC:** none (fx_only).

---

## H. Week and Friday timing (T14, M14)

### 48. T14-tuesday-london-70
- **rule_id / kind:** T14 / shortened. Scope: fx_only. judgment = false.
- **Rule:** [fx] Stats: bullish weeks P(week low in Tuesday London) ~77%; bearish weeks P(week high at Tuesday London open) ~70% (cc08_001 ~21:13). Test as stats first.
- **Sources:** cc08_001_-cXnnHjy9s0 ~00:21:13.
- **Quotes:** "you have a 70 likelihood that Tuesday's limit open will create the high of the week" (cc08_001).
- **Conflicts:** none.
- **Rulebook fix:** T14: add the 70% bearish figure and the London-open timing (cc08_001 ~21:13).
- **BUILD SPEC:** none (fx_only). The index weekly-extreme study is section 3 day_week_context **T14** (`study_week.py`); add a "Tuesday 01:00-05:00" bin there when it is built.

### 49. T14-weekly-template
- **rule_id / kind:** T14 / missing_rule. Scope: general. judgment = true.
- **Rule:** Weekly template (cc01_002, generic): Sunday open consolidation -> Monday expansion -> reversal Monday or Tuesday (forms the weekly low or high) -> expansion -> midweek consolidation -> then either reversal or retracement (late week). Label weekday states and test as stats only; reading Monday's expansion as a Judas against the bias is our interpretation.
- **Sources:** cc01_002_XwYYWBttWro ~00:24:06.
- **Quotes:** "Sunday's open consolidation then there's an expansion move in Monday then what there's a reversal on Tuesday or or Monday" (cc01_002).
- **Conflicts:** none.
- **Rulebook fix:** T14: add the weekly template (cc01_002 ~24:06) as a stat to test.
- **BUILD SPEC (day_week_context; extends section 3 T14 `study_week.py`):**
  - Where: `study_week.py` (to be created per section 3 T14): per ISO week, label each weekday as "consol" (range < 0.6 x ADR5), "expansion" (range >= ADR5 and close in the outer quarter) or "reversal" (takes the prior day's extreme and closes beyond its 50% the other way) [our interpretation], record which day made the weekly high and low, and count how often the sequence Mon expansion -> Mon/Tue reversal -> expansion -> Wed consol -> Thu/Fri reversal or retrace occurs. No engine change.
  - Params: none.
  - Test: `test_day_week_context.py::test_week_state_labels`. Synthetic five-day week built to the template: labels match and the weekly low day = Tuesday.

### 50. M14-tgif-timing
- **rule_id / kind:** M14 / missing_condition. Scope: index. judgment = true.
- **Rule:** Friday TGIF, bullish week: if the 09:30 open makes a Judas swing (false rally that reverses), the week high can be in at the open and shorts are armed after the bearish shift. If there is no Judas at 09:30 and price keeps climbing, expect the week high at lunch or going into 13:30-14:00, then arm PM shorts (e.g. 14:00-15:00 SB) after a bearish shift. Mirror for bearish weeks. 084 alternative: London close 10:00-12:00.
- **Sources:** 066_wTR-vhOdMgo ~00:46:41.
- **Quotes:** "then I would anticipate a lunch time or going into 1 30 to 2 o'clock then create the high" (066).
- **Conflicts:** 084: London close 10:00-12:00 high.
- **[our interpretation]:** "Judas at 09:30" = 09:30-10:00 runs above the week-to-date high and a bearish MSS forms before 10:15.
- **Rulebook fix:** M14 timing: replace "weekly high assumed in by ~13:30" with the two branches (066 ~46:41) and keep 084 as the alternative.
- **BUILD SPEC (day_week_context; extends section 3 M14.3 `tgif_timing`):**
  - Where: the `tgif` side gate in `run_day` (~2912). With `tgif_branch` on, on Fridays with `tgif_short` (`tgif_long` mirror): if a Judas (definition above) forms, allow TGIF shorts from 600 after the MSS; otherwise block TGIF shorts in the AM and allow them only from `tgif_pm_from` (810) after a bearish MSS whose high formed between 690 and 840.
  - Params: `tgif_branch: bool = False`, `tgif_pm_from: int = 810`.
  - Test: `test_day_week_context.py::test_tgif_branch`. Friday with a 09:40 run above the week high and a 10:05 MSS: short at 10:12 allowed. Friday climbing to 13:45 then an MSS: AM shorts blocked, a 14:05 short allowed.

### 51. T13-mm-sell-model-times
- **rule_id / kind:** T13 / missing_rule. Scope: fx_only. judgment = false.
- **Rule:** MM sell model time map (104, GBPUSD example): return to original consolidation in the London open; buy-side run and smart-money reversal into the 07:00 NY open; breaker/OB/2022-model entries in the 07:00-09:00 NY open kill zone; take most off at the original consolidation; final target below the relative equal lows, arriving in the London close 10:00-12:00 NY. Context/timing tags only.
- **Sources:** 104_iKsIbUblSWM ~00:54:40.
- **Quotes:** "return to original consolidation when does that occur London open" (104).
- **Conflicts:** none.
- **Rulebook fix:** M1: add the MM time map as an FX example (104 ~54:40).
- **BUILD SPEC:** none (fx_only).

### 52. T3-1400-caps-extreme
- **rule_id / kind:** T3 / missing_condition. Scope: fx_only. judgment = true.
- **Rule:** [fx-only] Expect the projected daily extreme in the London close window 10:00-12:00. If the trend carries past noon NY, expect the day's extreme to be capped by ~14:00 NY (cc08_004 ~11:36). Do not project the move beyond 14:00.
- **Sources:** cc08_004_JKzEhfwV1dY ~00:11:36.
- **Quotes:** "two o'clock usually caps the higher low of the day if we continue through London close Killzone" (cc08_004).
- **Conflicts:** none.
- **Rulebook fix:** T3 / L13: add the 14:00 cap as an FX note.
- **BUILD SPEC:** none (fx_only).

---

## I. Session relationships and range-day scalps

### 53. new-ny-continues-london
- **rule_id / kind:** new / missing_rule. Scope: general (taught on FX). judgment = true.
- **Rule:** [taught on FX] Default: the NY session continues London's direction. Exception: London's move reaches an unmet HTF premium/discount array as NY opens (or NY trades into it). Then expect a NY session reversal, with NY making the day's extreme and the day closing beyond the whole London range (cc09_005 ~12:05, ~29:00-31:00). If NY trades through that resistance/support cluster instead, the run was for stops and HTF order flow resumes. Next day, look for continuation via a Judas against the 0 GMT / midnight open toward the opposing liquidity (cc09_008 ~34:17).
- **Sources:** cc09_005_KrGTimL3YRQ ~00:30:13; cc09_008_cqf8nH54bb8 ~00:34:17.
- **Quotes:** "New York will always be expected to be a continuation" (cc09_005).
- **Conflicts:** none.
- **[our interpretation]:** London direction = sign(05:00 close - 00:00 open); "reaches an HTF array" = within 1 tick of a 4h/D FVG/OB edge from `htf` arrays at 07:00-09:30.
- **Rulebook fix:** T9 / T3: add the London -> NY default and its exception (cc09_005; cc09_008), marked "taught on FX".
- **BUILD SPEC (bias_htf):**
  - Where: `run_day` at 570: compute `ctx.london_dir` and `ctx.london_at_array`. Tag `ny_vs_london` = "cont" / "rev_setup" on AM trades. With `london_dir_gate` on: if not `london_at_array`, AM setups against `london_dir` are blocked; if `london_at_array`, both sides allowed (the reversal is expected). Report win rates by tag before turning the gate on.
  - Params: `london_dir_gate: bool = False` (tag always written).
  - Test: `test_bias_htf.py::test_london_dir_gate`. London down, no HTF array reached: an AM long is blocked. London down into a 4h BISI: an AM long is allowed.

### 54. new-london-close-scalp-large-range
- **rule_id / kind:** new / missing_rule. Scope: general (taught on FX). judgment = false.
- **Rule:** [taught on FX] London close counter-trend scalp only when today's range has reached >= 1.25-1.33 x ADR5 on an explosive one-sided move. Between 10:00 and 11:00 NY, on signs of weakness or once the projected numbers are filled, scalp a retracement back into the daily range (size not given in this lesson; ~20% is our assumption). No trade when the range is below ADR5 or the move was not explosive.
- **Sources:** cc09_005_KrGTimL3YRQ ~00:12:05.
- **Quotes:** "I like to only do it when the average daily range of the last five days has been exceeded at least one and a quarter to one and a third" (cc09_005).
- **Conflicts:** none. Item 34's windows: cc09_006 puts this scalp at 10:30-13:00, cc09_005 at 10:00-11:00.
- **[our interpretation]:** "weakness" = an MSS against the day's move; target 20% of the day range; exit by 12:00; "one-sided" = day open within 15% of the day's opposite extreme.
- **Rulebook fix:** new rule after T3 London close: "London-close counter-trend scalp only on >= 1.25-1.33 x ADR5 explosive days (cc09_005 ~12:05; cc09_006/007 windows)."
- **BUILD SPEC (setups_models; also defines the `london_close` window for item 34):**
  - Where: `setups.py` new `lc_scalp(ctx, sd, i, p, session)` called from `_scan_core` when `p.london_close[0] <= t < p.london_close[1]`. Gate: day range from 00:00 >= `lc_adr_k x adr5(hist)` and the one-sided test; `sd` = against the day's move; trigger = the normal MSS + FVG; target = entry + `lc_retrace` x day range (towards the day's open); stop = beyond the day's extreme + `stop_buffer`; force exit at `am_exit`. Own done key `LC`.
  - Params: `lc_scalp: bool = False`, `london_close: tuple = (600, 720)` (variants (600, 660), (630, 780)), `lc_adr_k: float = 1.25`, `lc_retrace: float = 0.2`.
  - Test: `test_setups_models.py::test_lc_scalp`. Day up 1.4 x ADR5 from London, bearish MSS at 10:20: short armed with target = 20% of the day range. Day up 0.9 x ADR5: no trade.

### 55. L8-time-decides-fill
- **rule_id / kind:** L8 / shortened. Scope: index. judgment = true.
- **Rule:** Vacuum block from an 08:30/early-NY gap: expect a full fill, so use the far edge (close of the last candle before the gap) as the entry/target, not the inner OB. Gap at 10:00-11:00 or later (incl. FOMC): expect a bounce at the OB inside the gap with the remainder left open. Register that remainder as an FVG to revisit in a later session. London vacuum blocks are rare.
- **Sources:** cc04_009_shPGUz9pU-A ~00:08:35.
- **Quotes:** "if it was gapped up late in the afternoon chances are it probably would leave the gap open" (cc04_009).
- **Conflicts:** none.
- **Rulebook fix:** L8: add the entry consequence (full fill vs OB), the later-session remainder FVG and the London note.
- **BUILD SPEC:** already listed in rule_coverage.md section 3 levels_detectors **L8** ("`vacuum_block()` at releases (08:30 near/MT/far; 10:00+ near/MT)") with the same content, and built (`levels.vacuum_block`, `vacuum_blocks`; section 4). No new spec.

### 56. new-swing-check-before-kz
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** [parked swing idea] For 4h swing execution, review the charts about one hour before each kill zone (e.g. ~01:00 for London 02:00, ~06:00/07:20 for NY) to set or adjust limits at daily/4h PD arrays. No intraday monitoring is needed.
- **Sources:** cc06_004_osRUnIpGIJ0 ~00:31:13.
- **Quotes:** "you only have to check it like an hour before the kill zones" (cc06_004).
- **Conflicts:** none.
- **Rulebook fix:** section 2.6 (swing models, parked): add the routine note.
- **BUILD SPEC:** none (parked with the swing idea).

### 57. N8-consolidation-pm-news
- **rule_id / kind:** N8 / missing_condition. Scope: general (bonds-taught). judgment = true.
- **Rule:** [bonds-taught] On a consolidation day, AM setups are expected (scalps, done preferably by 11:00, before noon at the latest; don't force PM trades) UNLESS a PM-session news driver is scheduled. Then the AM setup is not expected (likely just consolidation ahead of the release), so skip or tighten the AM filter.
- **Sources:** cc10_008_RgpxhuVp5Xg ~00:16:34.
- **Quotes:** "unless PM session news drivers are due out consolidation days typically offer setups in am session" (cc10_008).
- **Conflicts:** none.
- **Rulebook fix:** N8 (cc10_008 ~9:01-17:19): add the PM-news exception.
- **BUILD SPEC (day_week_context; extends section 3 N8.3 `consol_day_rules`):**
  - Where: in the N8.3 consolidation-day branch (`run_day` session gate). With `consol_pm_news_skip_am` on, when the day is tagged consolidation (N8.1 / N8.3 predictor, or `sloppy_day` chop) and `release_times(day)` or the FOMC tag has an event at/after 720, mark `done["AM"] = True` at 570 (PM rules unchanged; FOMC days keep their own N3 rules).
  - Params: `consol_pm_news_skip_am: bool = False`.
  - Test: `test_day_week_context.py::test_consol_pm_news_skip_am`. Consolidation-tagged FOMC day: no AM trade. Same day without a PM event: AM setups allowed.

---

## J. Bonds (ZB) session clock (bonds_only, rulebook fixes only)

### 58. bonds-session-clock
- **rule_id / kind:** T5 / wrong. Scope: bonds_only. judgment = false.
- **Rule:** [bonds-only] ZB: AM session 08:00-12:00 NY (may end early ~11:00 when European traders square up; 11:00-13:00 is NY lunch), PM session 12:00-15:00. AM+PM form the bond trading day. Analysis session 08:20-15:00 (cc10_006). ICT's personal entry window 08:20-11:00 is a kill zone, not the AM session definition. Remove "08:20-11:00 (cc10_007)" from T5's session list (it belongs in T3) and list the bond split as a conflicting source in D1/D7.
- **Sources:** cc10_007_JpV-J31mxhg ~00:01:53, ~00:07:13; cc10_006_CGbSpa_9Z9Y ~00:01:02.
- **Quotes:** "New York am session is defined by 8 A.M New York time to noon" (cc10_007).
- **Conflicts:** cc10_007 bond AM/PM vs index T5/T9 windows; cc10_006 08:20-15:00 analysis session vs 08:00 session start.
- **Rulebook fix:** T5: remove "08:20-11:00 (cc10_007)" from the session list; add a ZB session line as above; list it in D1/D7.
- **BUILD SPEC:** none (bonds_only; no ZB intraday data).

### 59. bonds-signal-0800-0830
- **rule_id / kind:** T3 / missing_condition. Scope: bonds_only. judgment = true.
- **Rule:** [bonds-only] Bond setups: preferred signal window 08:00-08:30 NY, target time ~08:20 (CME open). Signals can occur from 08:00 and occasionally slightly before (exact earliest time = our interpretation). The 08:00-09:00 opening range (bodies plus wicks, plus adjacent prior highs/lows) is the reference range.
- **Sources:** cc10_006_CGbSpa_9Z9Y ~00:11:44.
- **Quotes:** "I generally prefer to see it occur between 8 A.M and 8 30" (cc10_006).
- **Conflicts:** none.
- **Rulebook fix:** T3: add the ZB signal window (cc10_006 ~11:44).
- **BUILD SPEC:** none (bonds_only).

### 60. bonds-london-reference
- **rule_id / kind:** T3 / shortened. Scope: bonds_only. judgment = false.
- **Rule:** [bonds-only] Mark the 02:00-05:00 London session's high/low, stops, liquidity voids, FVGs and other PD arrays, and carry them as reference arrays/targets for NY-session (08:00-15:00) ZB trading. Counsel (not an absolute ban): do not trade ZB during London; focus on NY hours.
- **Sources:** cc10_007_JpV-J31mxhg ~00:03:22.
- **Quotes:** "use the information that is seen by overnight trading during the London session to look for stops liquidity voids fair value gaps" (cc10_007).
- **Conflicts:** none.
- **Rulebook fix:** T3 (line 426): add the ZB London reference-map note.
- **BUILD SPEC:** none (bonds_only).

### 61. bonds-am-volume-swing
- **rule_id / kind:** new / missing_rule. Scope: bonds_only. judgment = false.
- **Rule:** [bonds-only] The ZB AM session (08:00-12:00, may end ~11:00) has the day's peak volume (08:00-09:30) and generally forms the NY session's key extreme (low on bullish days, high on bearish). Stat to test: share of days whose session extreme falls in 08:00-12:00 (and within 08:00-09:30) vs 12:00-15:00.
- **Sources:** cc10_007_JpV-J31mxhg ~00:04:00.
- **Quotes:** "the am session has a built-in Advantage because it generally will see the largest volume of the day" (cc10_007).
- **Conflicts:** none.
- **Rulebook fix:** add under the ZB session line (item 58).
- **BUILD SPEC:** none (bonds_only).

### 62. bonds-pm-three-outcomes
- **rule_id / kind:** T9 / shortened. Scope: bonds_only. judgment = false.
- **Rule:** [bonds-only] Classify each ZB PM session (12:00-15:00) vs the AM leg as continuation, reversal or consolidation. The larger move is more often in the AM. If the AM used a large part of the ADR, expect an abbreviated PM (or skip it, per X10).
- **Sources:** cc10_007_JpV-J31mxhg ~00:04:20.
- **Quotes:** "the PM session generally will have a continuation or reversal and then the other thing is a consolidation" (cc10_007).
- **Conflicts:** none.
- **Rulebook fix:** T9: add the consolidation outcome for ZB (cc10_007 ~4:20).
- **BUILD SPEC:** none (bonds_only).

### 63. bonds-po3-template
- **rule_id / kind:** T12 / missing_rule. Scope: bonds_only. judgment = false.
- **Rule:** [bonds-only, one example, hypothesis] Bullish split-session PO3 for ZB: 08:00-09:00 OR; at the ~09:30 equities open, a Judas run below the OR low; AM rally into ~11:00; 11:00-12:00 retrace holding near the OR; PM rally to the HOD before 14:00; retrace/consolidation by 15:00. Bearish mirror. Treat it as a template to test (HOD/LOD time distribution, ZB vs index), not an established stat.
- **Sources:** cc10_007_JpV-J31mxhg ~00:10:40.
- **Quotes:** "price makes the high today ahead of two o'clock New York time and goes in consolidation at 3 pm" (cc10_007).
- **Conflicts:** T12 index: opposite extreme 15:00-16:00.
- **Rulebook fix:** T12: add as a ZB hypothesis (one example).
- **BUILD SPEC:** none (bonds_only).

---

## K. Timeframe modularity and regime templates

### 64. T-new-tf-modular-no-time-htf
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = false.
- **Rule:** Keep the analysis modular. The monthly/weekly HTF bias module uses only relative strength, seasonals, COT/sentiment (B20), market profile, intermarket, structure/IOF and PD arrays/key levels, with no time-of-day or session filters. Time-of-day tools (section T: kill zones, macros, opens, sessions) apply from the daily down.
- **Sources:** cc12_002_Ad-votrg6WQ ~00:46:41.
- **Quotes:** "it's not required on these time frames monthly and weekly" (cc12_002).
- **Conflicts:** none.
- **Rulebook fix:** B5: add "Tools per timeframe (cc12_002 ~46:00): no time-of-day analysis on monthly/weekly; time-of-day tools from the daily down."
- **BUILD SPEC (bias_htf, guard test only):**
  - Where: `htf.table` (~95) and `weekly_bias` (~870): no change expected. Add a regression test that the weekly/monthly bias columns are invariant to intraday session parameters.
  - Params: none.
  - Test: `test_bias_htf.py::test_htf_weekly_ignores_time_of_day`. Build `htf.table` twice with different `or_minutes`, `am`, `pm`, `london_kz_start` values: the weekly and monthly columns are identical.

### 65. T13-po3-breaker-regime
- **rule_id / kind:** T13 / missing_condition. Scope: general. judgment = true.
- **Rule:** Training-wheels template: regime = trading between the last daily bearish and bullish breakers. Bearish (off a daily bearish breaker): after the midnight open, a London rally above the open = Judas, sell short in London, expansion down into NY, reversal/retrace into the London close (10:00-12:00). Bullish (off a daily bullish breaker): the open trades down in London (Judas), go long, rally into the London close or the NY close. Needs the daily/4h PD-array map.
- **Sources:** cc12_003_3B7Reg2Yiqs ~00:23:12.
- **Quotes:** "when you're bearish look for the open the rally up for Judah swings sell short and London" (cc12_003).
- **Conflicts:** none.
- **[our interpretation]:** the regime = the side of the most recent daily breaker that price last traded off.
- **Rulebook fix:** T13: add the breaker-regime PO3 as a "training wheels" template (cc12_003 ~22:10-23:40).
- **BUILD SPEC (bias_htf):**
  - Where: `htf.table` adds column `brk_regime` (+1 / -1 / 0) from daily `levels.breaker_zone` on the daily frame: the last daily breaker that price reacted from (a touch of the zone followed by a daily close away from it). `htf_bias` gains the mode "breaker" (want = `brk_regime`). In `run_day`, tag `po3_judas=1` when London (02:00-05:00) traded past the midnight open against `brk_regime` before NY.
  - Params: `htf_bias` accepts "breaker" (no new field).
  - Test: `test_bias_htf.py::test_breaker_regime_column`. Daily series with a bearish breaker retested and rejected: `brk_regime = -1` the next day; a London rally above the midnight open sets `po3_judas`.

### 66. T3-london-then-ny-reposition
- **rule_id / kind:** T3 / missing_rule. Scope: general. judgment = false.
- **Rule:** With the HTF bullish, look for the long in the London open kill zone, aiming for the LOD. If London fails (stopped out or no setup), look for a NY open kill zone setup to reposition or get a new long in the same HTF direction. Bearish mirror, aiming for the HOD. Close most intraday positions 10:00-11:00. Bot (no London entries): the NY AM entry plays the reposition role.
- **Sources:** cc12_004_Oec_0NM_OeY ~00:07:52.
- **Quotes:** "if I fail in London I look for a New York open setup to reposition" (cc12_004).
- **Conflicts:** none.
- **Rulebook fix:** T3: add the London-first, NY-reposition order (cc12_004 ~7:35-8:25).
- **BUILD SPEC (silver_bullet + management_exits):**
  - Where: the only engine London entry is `sb_london` (`sb_model.run_sb`, 03:00-04:00). With `london_reposition` on: a losing `sb_london` trade does not set `lost_side` / the AM done key for the same side; the AM may re-enter in the same HTF direction (`want`) and only that direction. A winning `sb_london` trade still uses the existing rules.
  - Params: `london_reposition: bool = False`.
  - Test: `test_management_exits.py::test_london_reposition`. `sb_london` long stopped at 03:40 with `want=+1`: an AM long at 09:50 arms; an AM short does not.
