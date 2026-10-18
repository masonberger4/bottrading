# Build log

One line per item: id | done / partial / skipped | Params switch(es) | default | note.

## Package owner_directives_and_bugs (2026-10-18)

Sources: `owner_directives.md`, `owner_directive_specs.md` (#1-#14), `rule_coverage.md` section 3.
Tests: `tests/test_owner_directives.py` (unit tests + no-look-ahead runs covering every new switch).

- #14 breaker zone (D6, A13, A13.2) | done | `breaker_zone` ("range" / "body"; "leg"/"last" raise NotImplementedError, other values ValueError) | "range" | shared `levels.breaker_zone` / `breaker_candle` / `breaker_mt`; `_scan` and `levels.breakers()` use the same helper (breakers emits the breaker-candle zone with its MT); study variant D6_breaker_range -> D6_breaker_body
- #5 bearish unicorn (A14, M4) | done | `unicorn_sides` ("both" / "long" / "short", validated in `__post_init__`) | "both" | Trade fields unicorn_side, bz_top, bz_bottom; reported by backtest.report and study
- #6 breaker MT respect (A13.3, Ep02.3, Ep05.1) | done | `breaker_mt_mode`, `breaker_mt_respect`, `breaker_mt_entry_floor`, `breaker_mt_exit_after_t1`, `conf_breakers` | "range", True, True, False, False | lost breaker on a close below the MT after the break; unicorn entry floor MT+1 tick (gap wholly below the MT dropped); pending cancel on a close below; exit at the close below (fill bar included); OB-MT respect kept; conf_breakers adds breaker zones (inv = MT) to confluence (breakers() sped up with bisect)
- #12 risk 1.2% / 1.3% (E8, E11) | done | `account_equity`, `risk_pct`, `max_total_risk_pct`, `risk_basis`; `risk_dollars` / `max_total_risk` now None-overrides | 100000, 0.012, 0.013, "fixed" | first unit min(1.2%, 1.3% cap, notional) in all three engines; adds shrink to the 1.3% cap, open risk clamped at 0; entry_risk_pct / peak_risk_pct fields; equity basis = start-of-day equity from closed trades; study preset LEGACY_1PCT_2PCT; reentry_half = 0.6%
- #2 five handles = minimum (L15, M3, X14a, Ep03.24) | done | `t1_fixed_pts`, `t1_fixed_all`, `day_target_pts`, `sb_target_mode` | 0, False, 0, "draw" | filter tag renamed x_room_lt_min (also used by the lock); SB exits at the draw levels ("fixed" = old +5 list); day_target counts main-engine trades only
- #1 last hour / PM to 16:15 (T9-T11, Ep01.11) | done | `last_hour` (900,950), `last_hour_sweet`, `last_hour_strict`, `session_close`, `flatten` | (900,950), (915,945), False, 0=auto, 0=session close | session_close resolved once per run (975 futures/CFDs with an evening session, 960 SPY/ETFs) in backtest.run and paper.py, never from the day's last bar; day frames run to 16:15, history frames (rth) stay 09:30-16:00; Trade.lh_sweet; report by lh_sweet
- #8 close before noon (X10, Ep03.23, D16) | done | `am_exit_mode`, `am_exit_extras` | "close", True | am_exit now also closes SB-AM, London SB and Ma Deuce; tighten = test-only, runs once; AM-family pending orders cancelled at t+tf >= am_exit
- #7 opposing HTF FVG caps the trade (Ep02.10, L9, X3f, Ep02.5) | done | `htf_resist_cap`, `htf_resist_tfs`, `htf_resist_src`, `htf_resist_buffer_pts`, `htf_resist_min_room`, `htf_resist_live`, `htf_targets_30m`, `runner_htf_exit` | True, (15m,30m,1h,4h,D), ("fvg",), 0.5, 0, False, False, "" | confluence `src` column + `resistance()` / `support()`; cap applied in the main engine, SB (draws) and Ma Deuce (08:00); x_htf_resist / x_htf_resist_nodata tags; Trade resist_tf/lo/hi/capped; with the lock, a cap before the draw becomes the final exit (x_lock_capped) [our interpretation of "the locked draw must be on the near side of the cap"]
- #11 OB entry before the break (M1.4, D10, Ep07.2, Ep07.5) | done | `ob_entry`, `ob_entry_px`, `ob_arm`, `ob_stop`, `ob_entry_cancel_on_mss`, `ob_adds` | "pre_break", "body_top", "leave", "mt", False, True | `_ob_at_low` (closed bars, frozen once its window is complete), shared `_finish_order` tail for every entry path; entry_kind "ob_pre"; body-violation cancel on c[i-1]; leg_pd bypassed; pre_break drops the sweep at the MSS; "both" keeps the lower entry; OB re-entry adds [our interpretation]; CLI --ob-entry/--ob-entry-px/--ob-stop; study CURRENT pinned to post_mss
- #4 news dealing range (N5, N5.1, N5.2, Ep04.5, Ep02.1) | done | `news_wait`, `news_wait_min`, `nfp_floor_min`, `news_range_max_min`, `news_range_pivot`, `news_range_target`, `news_range_pd` | "range", 30 (fixed mode only), 30, 90, 0, True, False | calendar NEWS_0945 (PMI on ISM days) + release_times(); range made = later of the first swing high/low after the release (+ NFP 30-min floor) [our interpretation]; gate per session window (AM/PM/NEWS/PRE9, SB windows); range low/high as sweep pools, opposite extreme as target; Trade news_wait_min_actual / news_pd; "off" = old behaviour
- #9 lock one draw per session (B3, L14, L14a, M0.1, M3.2) | done | `draw_lock`, `draw_lock_pick`, `draw_lock_neutral`, `draw_lock_levels`, `draw_lock_partials`, `draw_relock`, `draw_lock_near_cap`, `draw_lock_min_pts` | "session", "nearest", "skip", "frozen", True, False, False, 5.0 | `htf.table(cut_min)` per lock time (backtest.lock_tables / study cache, same in paper.py); `mark_levels` from bars closed by the lock; side gate in main engine, SB (London SB locks at 02:00, Ma Deuce at 08:00 [our interpretation]); one final target T (ladder last rung = T); delivered -> session (and its SB window) done; locks in result.attrs["locks"]; Trade draw_*; draw_lock_min_pts = 5-handle minimum distance [our interpretation]
- #13 front-month prices (DATA1, Ep02.2, N7.5) | done | `price_frame`, `round_pools`, `round_pool_step_pts` | "front_month", True, 0 = per symbol (ES 50, NQ 100, YM 500) | `backtest.load_meta` derives adj = adjusted - raw from the existing *_db / *_dbraw CSVs (cached parquet) instead of rebuilding the CSVs; databento_data.build now writes `adj`/`roll` for future rebuilds; engine stays back-adjusted, absolute levels at R + adj of the latest closed bar; reports convert entry/stop/t1/t2/draw/bz/resist to real prices (Trade.adj, contract, roll_day); round pools as sweep pools and targets on futures with meta only
- #3 year end (Ep01.9, N7.4) | partial (awaiting owner) | `year_end`, `year_end_map`, `year_end_days`, `year_end_flat_frac` | "off", "squaring", 1, 0.25 | calendar is_trading_day / last_n_trading_days / last_trading_day_of_year; december_dir; day_context(hist, day, p) tags + block["year_end"]; gate in run loop, SB and Ma Deuce. Default OFF: the Ep 01 example runs against the mapping in owner_directives.md - owner must confirm
- #10 sloppy days (B17.4, N8.1, Ep08.2) | partial (awaiting owner) | `sloppy_mode`, `sloppy_tests`, `sloppy_big_mult`, `sloppy_chop_frac`, `sloppy_chop_cross`, `sloppy_chop_from`, `sloppy_release_frac`, `sloppy_scalp_pts` | "off" (tag only), (big_prev, chop, nfp_week), 2.0, 0.35, 4, 120, 0.25, 5.0 | sloppy_day + Chop class [our interpretation]; stand_aside (no entries/adds, drops pending; day reasons -> `skips`), scalp (single exit min(+5, T1), no adds) in all three engines; Trade.sloppy tag always filled; neutral_skip kept as the old alias; "premium_run" raises NotImplementedError. Default tag-only until the owner answers (and the nfp_thu question)
- M1.2 swing-low intact bug | done | `displacement_mult` (option) | 0.0 | intact() starts at the swing low's bar + 1
- M7.1 lunch high never a target | done | `seen_from_created`, `pm_off_lunch`, `pm_judas_1330` | True, False, False | root cause: the `seen` filter used today's high from midnight, which always spent the session's own pools (lunch, overnight, London, AM, OR highs); now each pool is spent only by bars after it formed. Also fixed a look-ahead: London (02:00-05:00) pools are no longer visible before 05:00 (affected a 03:00 London SB)
- shared: breaker_zone() | done | (see #14) | | levels.breaker_zone / breaker_mt / breaker_candle
- shared: VI wiring | done | `vi_arrays` | False | confluence rows src 3 (dies on a close beyond the far edge), htf "vi" arrays and draws
- shared: adr5(), next_trading_day() | done | (helpers) | | strategy.adr5; calendar.next_trading_day / prev_trading_day; `_split` news-ahead now skips holidays (N3.4 fix)
- shared: turtle-soup core (M12) | partial | `turtle_soup`, `ts_max_pts`, `ts_back_bars`, `ts_need_htf` | "", 5.0, 3, False | levels.turtle_soup core + the 2023 variant (no MSS; limit at the swept level, stop below the false-break extreme); cc_limit / cc_1h_ob / or60 / external variants belong to setups_models
- shared: level kinds carried into pos | done | (none) | | order level_kinds -> pos["level_kinds"]
- shared: stateful bias column (flip) | partial | `htf_bias="flip"`; htf.table(flip_triggers) | ("ob_mt", "wk_dc") | column machinery + B8a/B8c triggers, applied from the next session; B8b/d/e/f triggers raise NotImplementedError until bias_htf adds them
- pending notes Ep01.11, X14a, Ep03.24, Ep01.9, N5.1, D10, E8 | done | | | rule_coverage.md section 3 notes rewritten to the owner versions; section 4 added with the status changes; rulebook header + T9/T10/T11/L9/L15/N5/E8/E11/X10/X14/D10/App. A Ep01 lines corrected

Regression: `study.PRE_OWNER` (every owner default switched back) reproduces the engine of commit
833350f exactly (ES 5m 2024 Q1 with SB + Ma Deuce: 23 trades, net 4693.52; test
`test_pre_owner_switches_reproduce_the_old_engine`).

Effect note (ES 5m, 2024 H1, lot 1, a quick look - not the study): all owner defaults 5 trades;
cap off 35; lock off 14; cap and lock off 81; pre-owner engine 2. The #7 cap and the #9 lock remove
most setups; the OB-before-the-break entry (#11) is what adds them. The owner A/B is the study:
`python -m mentorship.study` decisions D0_pre_owner_directives, Ep02.10_resist_cap_off,
B3_draw_lock_off and the other new variants.

## Review pass (2026-10-18): fixes to owner_directives_and_bugs + the not-built items

Tests: `tests/test_review_fixes.py` (synthetic one-day scenarios run through `run_day`, helper unit
tests, ES/SPY data tests, and no-look-ahead runs covering every switch the review listed plus every
new one). `test_owner_directives.py` updated for D6 leg/last.

- #9 frozen rungs (major) | fixed | (none) | | `mark_levels` keeps EVERY intact candidate in `lock["marked"]` as (v, kind, name, dir), both sides; frozen rungs = marked arrays (any side) and same-side pools between entry+min_rr*risk and T. Scenario test: a locked long scales out 50/25/25 at 102.75 / 103.5 and ends at T 108.25
- #9 traded-through test (major, M7.1 reintroduced) | fixed | (none) | | each candidate has a creation bar (overnight 09:30, AM/lunch 13:30, round handles the session start, the rest midnight) and is dropped only if bars after it formed and before the lock traded through it. ES 5m 2023-01..2024-06: PM locks now pick lunch_low 73 / lunch_high 68 / am_high 58 / am_low 52 of 369 (before: 0 lunch picks)
- #5/#6/#14 under ob_entry="pre_break" (major) | documented, owner question | study variants `A13.3_ob_both_breaker_mt`, `A13.3_ob_both_breaker_mt_off`, `A13.3_post_mss_breaker_mt_off` | | they act only on the FVG path; ES 2023-01..2024-06 defaults: 25/25 trades `ob_pre`, 0 unicorn. With `ob_entry="both"` the OB order still wins every time (25 trades, same list): the FVG/unicorn order arrives later at a higher entry and the lower entry is kept. Question 1 in owner_directives.md
- #7 x #9 (major) | owner question + tag | `lock_capped` Trade field (report column) | | defaults: 22 of 25 trades had the locked draw replaced by the cap; `draw_lock_near_cap=True`: 10 trades, 7 still capped (the lock-time cap is measured at the lock price; the trade's cap at its entry). Question 2 in owner_directives.md
- tests M1.2 / M7.1 (major) | done | | | swing low on its own bar intact and swept after an earlier lower low; lunch high a PM target under an AM high (old rule drops it); London high/low hidden at 03:00, a target at 05:30 (both sides)
- look-ahead coverage (major) | done | | | truncation runs: synthetic A (turtle 2023 gap stop, raw frame, round pools 10 / round_step 5, floor_strict, leg zone, stop_flip breaker, partials off, ob_adds off, both, news_range_pd, news_range_target off, year_end long, last_hour_sweet, sloppy premium_run/fomc_week/inside_bisi stand_aside, sloppy_run_days, sloppy_fomc_nfp, breaker_mt_respect alone, draw_lock_pick, round_pool_from midnight); synthetic B (or60, ts_entry level, last zone, year_end tag, stop_flip smt, SB fixed target, sb_rebalance_ext, am_exit_extras off, ts_gate_mss); cc_limit + year_end_map with; external; 2023 + ts_need_htf; ES (near_cap, resist_min_room, resist_buffer, flip all triggers, round_step, both); ES cc_1h_ob (ts_r_mults, ts_be_r); ES 1m London SB lock + rebalance. Spec unit tests added for #6, #11 (a-d, f), #2 (a-c, e), #8 (a-c, f), #9 (c, e, f, h, i), #10 (i, iii-v), #12 (b, SPY), #13 (a, c), #5 exact mirror (range and body)
- #6 entry floor (minor) | fixed | `breaker_mt_floor_strict` | False | spec 6b: a unicorn gap wholly below the MT leaves the unicorn pick only (may still be the plain-FVG entry); the stricter old rule is the switch [our interpretation]; variant A13.3_floor_strict
- #9 London SB / Ma Deuce locks (minor) | fixed | (cut 120 in `backtest.lock_cuts`) | | London lock uses the htf table cut at 02:00 and is marked delivered inside run_sb (pending dropped, no re-arm); own lock times = owner question 3
- #9 paper vs backtest (minor) | fixed | (none) | | `backtest.prepare` / `day_kwargs` build every run_day input once; `backtest.run` and `paper.evaluate` both use them (paper now gets conf, gaps, closes, lock tables, 45-day history); test: paper lock == backtest lock on ES 2024-03-14 14:00
- study caches (minor) | fixed | | | `_bias_cache(tf, cut, vi, flip)` keyed on vi / flip triggers and passed through; `_lock_cache` uses `B.lock_cuts`; PRE_OWNER adds `am_exit_extras=False` (golden test still 23 trades, net 4693.52); comment lists the fixes the baseline cannot undo (London-pool look-ahead, _split holidays, M1.2, mark_levels, causal roll_day)
- #13 (minor) | fixed | `round_pool_from` | "session" | `prepare` warns when round_pools is on but inert on a futures symbol; roll_day is now causal (known from the roll's bar); spec test (c) on real data: at 09:30 on 2023-01-03 the untaken round handle above is 3900.00 only with a session anchor (overnight traded 3906.75) - so "session" is the default [our interpretation of Ep 02 + spec test c], "midnight" the switch; owner question 4
- Params validation (minor) | fixed | | | htf_resist_src / htf_resist_tfs / sloppy_tests / flip_triggers / new enums validated in __post_init__
- M12 turtle 2023 wording (minor) | fixed | `ts_entry`, `ts_stop` | "array", "array" | M12.1: limit at the PD array top (capped at the swept level [our interpretation]), stop below the array / nearest gap (038) / extreme; the old reading = ts_entry="level", ts_stop="ext" (variant M12.1_turtle_2023_level)
- docs (minor) | fixed | | | rule_coverage section 2 rows point to section 4; section 4 rows for B3/L14a (fixed, note), D10, M12.x, B8a-f, B17.4, L17, M3.10, DATA1 calendar roll; shared table consistent

Not-built items, now built (all switches, default off unless noted):
- #10 sloppy tests | done | `sloppy_tests` += "premium_run", "fomc_week", "inside_bisi"; `sloppy_run_days`, `sloppy_run_lookback`, `sloppy_fomc_nfp` | 3, 20, True | [our interpretation]; default mode still tag-only (owner question 5 + nfp_thu)
- #3 year end | unchanged | | "off" | still waits for the owner's mapping answer
- B8b/d/e flip triggers | done | `flip_triggers` (+ "flip_pd3", "flip_close_above", "flip_thu_wopen") | ("ob_mt", "wk_dc") | close_above sets neutral (rule_coverage B8d); deterministic test + flip-column no-look-ahead test
- B8f | done | `stop_flip` ("breaker" / "smt") | "off" | stopped out beyond the trade's breaker far edge (or an SMT trade) -> the other side only for the rest of the day
- M12.3 / M12.4 / M12.5 | done | `turtle_soup` = "cc_limit" / "cc_1h_ob" / "or60" / "external"; `ts_cc_below_pts`, `ts_r_mults`, `ts_be_r`, `ts_gate_mss` | off | confluence `valid()` lists the arrays; cc_1h_ob gets its own 1R / BE-2R / 5R management (order fracs + be_at); bar mechanics [our interpretation]. ES 2023-01..2024-06: cc_1h_ob 2 trades (lock and cap off)
- D6 breaker_zone "leg" / "last" | done | `breaker_zone` | "range" | leg = L1 low .. H high (070), last = the last up-close candle's range (cc05_014)
- L17 | done | `round_step_pts` | 0 | targets down / limit entries up to the step on the real front-month price; stops not rounded
- M3.10 | done | `sb_rebalance_ext` | 0 | A7 immediate rebalance (next candle back to the prior candle's extreme within a tick, no gap) in the SB window -> the SB draw must be at least N ES pts away
- #9 test (i) | done | | | see paper vs backtest above
- #13 roll_kind="calendar" / roll_spread | NOT built | | | needs paid Databento ES.c.0 data - owner go-ahead (question 6)

Effect note (ES 5m 2023-01..2024-06, lot 1, defaults after the fixes): 25 trades (net -7236), 22
lock_capped, 1 multi-exit trade; cap off: 118 trades (net +282), 10 multi-exit; near_cap: 10 trades.
The rungs now exist, but the #7 cap usually sits closer than the first rung - the cap choice
(question 2) decides whether the 50/25/25 ladder runs in practice.

Existing tests touched: `test_mentorship.py` smt/htf-targets and ep07 look-ahead runs now set
`htf_resist_cap=False` (with the lock fixes the cap left them only 2 trades; the cap has its own
look-ahead runs) and the smt run compares with `check_dtype=False` (None vs bool); 
`test_owner_directives.py` D6 leg/last no longer raise; round-level unit test pins
`round_from="midnight"`. Results: test_review_fixes 41 passed, test_owner_directives 24 passed
(golden PRE_OWNER still 23 trades / 4693.52), test_mentorship 26 passed, test_strategy passed.

## Package levels_detectors (2026-10-18)

Sources: `rule_coverage.md` section 3 "levels_detectors" (36 items), the rulebook rows they cite,
`owner_directives.md` (nothing in it overrides these items). Tests: `tests/test_levels_detectors.py`
(detector / helper unit tests, run_day scenarios, and no-look-ahead runs - synthetic A / B and ES
5m - covering every switch below). Study: one `DECISIONS` variant per switch (prefix = rule id).
Regression: with `sweep_ticks=0, fvg_c2_dir=False, nwog_trading_days=False` (added to `study.PRE_OWNER`
and `CURRENT`) the engine reproduces HEAD 76d3d9e trade-for-trade (ES 5m 2023-06..2024-03: default,
post-MSS and both+SB+pool_swings configs identical).

- B21 IPDA 20/40/60 | done | `ipda_pools`, `ipda_next`, `ipda_eq_day` (+ `ipda_eq_frac`, `ipda_eq_days`) | False, False, "off" (0.15, 10) | backtest.HIST_DAYS 45 -> 61; ranges rolled from yesterday on RTH sessions; pools in _sell_side / _targets / mark_levels; next = the first untaken of 20 -> 40 -> 60; range day = near EQ of all three + both sides run [our interpretation], "skip" = no entries before the first release
- A1 swing tiers | done | `mss_ref`, `mss_ref_fallback` | "stl", "lower" | `levels.swing_tiers` (a tier is known with its right neighbour); fallback = lower tiers then the old highest high, "none" = no MSS; the stale rulebook pivot_n note is fixed
- A2 booking tick | done | `sweep_ticks`, `sb_draw_pools_only` | 1.0 (spec default), False | applied in the _scan sweep, `_level_intact`, `_smt`, the _targets seen filter and the SB swept tag; on ES tick-grid prices it changes only exact touches (a touched pool is not spent); pool_swings=True is covered by the existing look-ahead test and variant A2_pool_swings
- A5 FVG sub-rules | done | `fvg_c2_dir`, `fvg_quadrants` (+`fvg_quad_min_pts`), `fvg_vi_extend`, `fvg_skip_above_pool` (+`fvg_pool_gap_pts`), `htf_ce_draw`, `fvg_q_hold`, `fvg_state_filter`, `fvg_keep_filled` | True (spec), rest off | `Zone.q`; the c2 check runs in Side, confluence and the htf table (backtest.htf_kw, part of the study cache key); Trade.fvg_state tag (open / repriced / rebalanced); htf_ce_draw acts in the lock (mark_levels preference) and the no-lock draw
- A13 breaker helper | done (owner directives) | `breaker_zone` | "range" | unchanged; now also used by breaker_entry / breaker_ll / breaker_time
- B1 run or rebalance, else consolidate | done | `vi_targets`, `wick_days`, `no_draw`, `skip_no_draw` (+`no_draw_adr`) | False, 1, False, False | VI rows in confluence / htf came with the shared VI wiring; no draw = no marked level within 1 x ADR5 of price at the session start [our interpretation], tag `no_draw`
- L1 session pools | done | `am_range_end`, `prev_am_pool`, `session_priority`, `org_pools` | 810, False, False, False | priority prev PM (09:30 open within a quarter of its range [our interpretation]) > London > previous AM; the ORG pool = the prior close when it lies beyond the 09:30 open
- L2 liquidity matrix | done | `daily_level_needs_array`, `daily_level_needs_flow`, `pd_hl_session`, `pool_today_hl` | False, False, "rth", False | ETH sessions from backtest.prepare (`Prepared.eth`, prior dates only); array = confluence (or HTF tag) at the sweep extreme; flow = the D structure trend
- L5 NWOG | done | `gap_quarters`, `nwog_skip_holiday`, `nwog_halfway`, `gap_run_stop` (+`gap_run_tol_pts`), `nwog_trading_days` | False, False, False, False, True (fix) | trading-day count via calendar.prev_trading_day; holiday week = fewer than 5 trading days; halfway -> the next NWOG near edge is the draw (lock and no lock); run stop = sweep extreme within 2 ES pts of the nearest gap level [our interpretation]
- L7 ORG | done | `org_draw`, `org_break_min`, `org_half_draw`, `org_q_hold`; `org_close` default 0 = per symbol | "off", 30, False, False | ORG history max(org_days, 5) + 1 sessions; breakaway = no reach to the 25% level by 10:00 [our interpretation]; org_draw is also a lock preference after 09:30; org_q_hold is a tag
- L10 wick CEs | done | `wick_days`, `wick_weekly`, `wick_both`, `wick_session`, `wick_invalidate`, `wick_partial` | 1, False, False, "rth", False, False | default mismatch fixed in the docs (wick_levels is ON); wick_partial = frozen lock rungs; wick_invalidate = a close back through the prior lower-wick CE exits
- M2.1 gaps as sweep pools | done | `pool_gaps`, `gap_pool_edge` | False, "far" | unique keys gap_<kind><n>; only levels below the last close
- T2 opening prices | done | `release_open`, `release_open_stop`, `bias_open` | False, "", "midnight" | 08:30 release days, AM: bodies since 08:30 hold the 08:30 open (1 tick); stop beyond the open or the 08:30 candle wick CE
- Ep01.5 breakaway | done | `breakaway` | "off" | the first FVG formed at / after the MSS bar; tag / hold (a body close below its CE exits) / next_fvg (not an entry)
- Ep01.6 breaker body close | done | `breaker_ll`, `breaker_cand_to`, `breaker_entry` | False, "ext", "off" | lower low + real pivots + a body close above H; candle from the L1 -> H leg ("h"); breaker entry (A13.4, shared): "fallback" when no FVG within fvg_wait, "prefer" at once; limit at the zone top, stop beyond the sweep, #6 MT cancel / exit. With the default ob_entry="pre_break" the sweep ends at the MSS, so breaker entries need post_mss / both
- Ep02.8 daily VI top-down | done | `vi_arrays` (shared), `vi_news_draw` | False, False | htf table columns vi_up / vi_dn; on release days the lock prefers the nearest live daily / weekly VI draw
- Ep03.3 VI daily draw | done | `vi_body_death` | False | dead once a later own-TF body spans it (confluence rows and the htf table); D_vi draws were already named by the table
- Ep05.1 breaker MT levels | done | `breaker_levels` (+ the #6 switches) | False | entry clamp / body-close exit came with owner #6; new: a unicorn without an OB MT stops below the breaker zone
- Ep06.7 prefer rel-eq | done | `eq_pref` | "off" | "rank": rel-eq sweeps win and the nearest "pool_eq" target is the draw; "require": only rel-eq sweeps / draws; kind "pool_eq" keeps the pool exit rules (POOL_KINDS)
- Ep08.10 matrix | done | `matrix_full`, `matrix_days` | False, "bot" | "ict": today (to the session start) + yesterday + the day before, plus m3h / m3l; matrix_full = ETH sessions (= pd_hl_session "eth")
- A3 REH/REL | done | `eq_bodies`, `eq_rank` | False, False | bodies cluster, line at the extreme wick, untaken by bodies and the line not traded through; rank = touches, then spread; eq_tol 0.25 / 1.0 study variants
- A7 immediate rebalance | done | `imm_rebalance_disp` | "off" | `levels.immediate_rebalances`; "or" passes displacement_mult, "require" gates the MSS; Trade.imm_rebal tag; daily open_to_pdh / open_to_pdl tag (lv_tags)
- A9 volume imbalance | done | `vi_min_gap_pts`, `vi_body_death`, `vi_stop`, `vi_porous_n`, `vi_htf_draw` | 0, False, False, 0, False | stop below the nearest unpierced VI under the entry; porous = >= N VIs in the leg -> no trade; HTF VI draw (no lock)
- A11 BPR | done | `bpr_max_gap_bars`, `bpr_targets`, `bpr_abort` | 0, False, False | abort = a body close below the midpoint of the BPR under the entry [our interpretation]
- A13.1 breaker structure | done | `breaker_ll` | False | see Ep01.6
- A13.5 time distortion | done | `breaker_time` | "off" | `levels.session_block` (Asia / London / NY AM / lunch / PM) [our interpretation]; "hl2" = H, L2 and the break; "all" adds L1
- A15 mitigation block | done | `mit_targets`, `mit_body_respect` | False, False | swing order FIXED by default (A low before X, higher low B, no run below A); `legacy=True` keeps the old order (test_mentorship pinned to it); the fix only moves the `mitigation` tag
- D6 breaker zone modes | done | `breaker_zone` (leg / last built earlier), `unicorn_pref` | "range", True | unknown values raise (built earlier)
- D21 NWOG / ORG conventions | done | `org_days` (history widened), `monday_ce`, `nwog_quarters`, `org_sweep` | 5, False, False, False | org_sweep = the kept ORGs' high / CE / low below price as pools
- L3 higher pools | done | `ipda_pools`, `ipda_next`, `or_extra`, `pw_pm_full_session` | False | or_extra = the other OR length (OR60 next to OR30); week / month H/L from ETH sessions
- L8 vacuum block | done | `vacuum_blocks` | False | `levels.vacuum_block` at release bars (08:30 / 09:45: near, MT, far; 10:00+: near, MT); 09:30 / 18:00 are the ORG / NDOG (not duplicated)
- M0.2 window pools | done | `session_priority`, `prev_am_pool` | False | shares L1
- Ep01.4 BPR rule | done | `bpr_rule` | False | known-time BPRs (Zone.i = the later gap), the A11 midpoint exit and the first target capped at the next BPR above (no trade under 1R)
- Ep02.9 breakaway tag | done | `breakaway="tag"` | "off" | shared with Ep01.5
- Ep08.1 daily wick CE / FVG edges | done | `wick_days`, `wick_session`, `wick_react`, `daily_fvg_exact` | 1, "rth", "off", False | wick_react tag / require: the sweep extreme within eq_tol of a prior lower-wick CE; daily FVG near edges as "exact" targets (no exit buffer)
- M1.2 swing-low intact | done (owner directives) | `displacement_mult` | 0 | unchanged

Limits worth knowing (all items built): the no-lock draw overrides `vi_htf_draw`, `org_half_draw`
and the `eq_pref` draw act only with `draw_lock="off"` (with the lock, mark_levels picks the draw;
htf_ce_draw / nwog_halfway / org_draw / vi_news_draw are lock preferences there); partner contexts
(SMT) keep RTH levels and get none of the new pool keys (SMT is None for those sweeps).
