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

## Review pass (2026-10-18): fixes to levels_detectors

Tests: `tests/test_levels_review.py` (helper / gate unit tests and no-look-ahead runs that cut at
entry AND exit times, comparing exit_time / exit_reason of the trades closed by each cut, so the
lvx exits - q_close, breakaway_ce, wick_inv, bpr_abort, release_open - are covered; use_bias with
the 09:30 / 08:30 open in PRE9 / NEWS / PRE7 windows, a 09:00 AM window, the lock, SMT, ES with
confluence). Study: one variant per new switch / old default / interpretive threshold.

- T2 bias_open (blocker) | fixed | (none) | | `_open_known`: an open is read only once its bar is in (index <= i, as release_open's k830); a pre-09:30 window falls back to the midnight open. The review's reproduction (RW 5m 2026-04..06, pre_0900, bias_open 0930) is now a look-ahead test
- L2 daily_level_needs_array (major) | fixed | `daily_level_array_tfs` | ("15m", "30m", "1h", "4h", "D", "W", "M") | only HTF confluence timeframes count; a 1m / 5m array alone is rejected (no confluence: the HTF tag as before). Variant L2_daily_needs_array_any_tf = the old gate
- Ep08.1 daily_fvg_exact (major) | fixed | (none) | | `_drop_near_exact`: non-pool levels within a tick of an "exact" daily FVG edge are dropped before `_exit_px`, so the ladder holds only v
- L7 org_draw under the lock (major) | fixed | (none) | | the ORG far edge is a lock preference from the 09:30 lock (the lock is taken while the 09:30 bar is in, so its open is known); breakaway (`_org_break`, no reach to the 25% level in 09:30 .. +org_break_min) is applied at the lock when known, else `_lock_step` re-marks the lock without the preference (same lock time, `org_pref=False`, tag `org_break_i`) once it is. org_half_draw is now a lock preference too (CE reached, far edge not, by the lock: acts on 09:45 / 10:00 lock days). Preferred draws keep their own name in `marked` when a plain candidate shares the level
- Ep01.6 / A13.1 breaker defaults (major) | fixed | `breaker_ll`, `breaker_cand_to` | True, "h" | the spec is imperative; the old rule is pinned in study.PRE_OWNER / CURRENT (golden test unchanged: still reproduces 833350f); variants A13.1_breaker_ll_off, Ep01.6_breaker_cand_ext
- B21 / L3 IPDA ranges (major) | fixed | `ipda_session` | "eth" | ranges and the ipda_eq_day "both sides run" test from daily full-session candles (`Prepared.eth`, now built when an IPDA switch is on); a date without an ETH candle (SPY) uses its RTH session; "rth" = the first build (variant B21_ipda_session_rth)
- B1 no_draw (minor) | fixed | | | t_lock = min(session lock, the current bar's start minute): bars closed before it only, and the 09:30 open (ORG / NWOG) only once the 09:30 bar is in
- L1 am_range_end (minor) | fixed | | | validated 570 < am_range_end <= 810; the AM range is a target from am_range_end (12:00 with 720), not from 13:30
- A2 booking tick in the lock (minor) | fixed | | | `mark_levels.intact` uses `_thru` / `_spent_up` with `_tick(p)` (sweep_ticks 0 keeps the old touch rule); on tick-grid prices only sweep_ticks > 1 changes it
- A2 / SMT new pools (minor) | fixed | | | `_smt` passes p to the partner `_sell_side` (creation bars via the shared `_level_created`); swing lows (keyed by bar index) have no twin
- A5 BPR c2 rule (minor) | fixed | | | `levels.balanced_ranges(..., o, c, c2_dir)`; Side.bprs passes them
- A11 bpr_targets (minor) | fixed | | | only BPRs not traded into since they formed (as vi_targets); variant A11_bpr_targets_any_pair
- Ep08.10 matrix "ict" in the lock (minor) | fixed | | | mark_levels drops pdh3 / pdl3 and adds m3h / m3l (a 3-day extreme always equals today's / pdh1 / pdh2's level, so it only adds a name)
- inert switches (minor) | fixed | | | vi_htf_draw is now also a lock preference (as htf_ce_draw); `Params.__post_init__` warns for vi_news_draw without the lock, vi_news_draw / vi_htf_draw without vi_arrays, and the eq_pref draw under the lock
- A9 / Ep03.3 VI death intraday (minor) | fixed | | | with vi_body_death the Side VIs of vi_targets, vi_stop, vi_porous_n and fvg_vi_extend are alive until a later body spans them (`_vi_alive`)
- A15 legacy order (minor) | fixed | `mit_legacy_order` | False | Side.mitigations / opp_mits; variant A15_legacy_order
- T2 release_open hold (minor) | fixed | | | a body close below the 08:30 open (minus a tick) after arming cancels the pending order and exits the trade (lvx "release_open")
- L8 vacuum_blocks (minor) | fixed | | | the far edge only for the 08:30 release (spec: 08:30 near / MT / far; 10:00+ near / MT); 09:45 = near / MT like 10:00
- paper history (minor) | fixed | | | `paper.history_days`: (HIST_DAYS + 1) sessions in calendar days for 5m / 15m, 48 days for 1m (Schwab's limit); `paper.short_history` warns when an IPDA / org_days switch lacks history
- study thresholds (minor) | done | | | B21_ipda_eq_frac_010 / _025, B21_ipda_eq_days_20, A5_fvg_quad_min_8, A5_fvg_pool_gap_2, B1_no_draw_adr_05 / _15, L7_org_break_15 / _60, L5_gap_run_tol_4, A11_bpr_abort_gap12; A1_mss_ref_fallback_highest now runs with ob_entry="post_mss"; L7_org_half_draw_lock, A9_vi_htf_draw_lock
- Monday NWOG before 09:30 (found by the new look-ahead test) | fixed | (none) | | DayCtx built today's NWOG (Friday close -> today's 09:30 open) from the whole day, and the PRE7 / PRE9 / NEWS targets, sweep pools (pool_gaps), the gap-run stop, the halfway rule and a pre-09:30 lock read it before 09:30 printed. `_nwogs(ctx, i)`: before the 09:30 bar the 4 prior NWOGs (`DayCtx.nwog_prev`); the AM (from 09:30) is unchanged. RW 5m 2026-06-22 PRE7 short: t1 733.185 (full) vs 731.5775 (cut at the entry) before the fix
- tests (minor) | done | | | the full test_mentorship.py and the other suites rerun on the final code (results below); look-ahead cases added for use_bias with pre_0900 / post_news / pre_0700 and a 09:00 AM window, and for exits

Results (final code): test_levels_review 22 passed; test_mentorship 26 passed (full file);
test_levels_detectors look-ahead 4 passed; the non-look-ahead parts of test_levels_detectors /
test_owner_directives / test_review_fixes / test_strategy pass except 3 tests that fail only with
another session's uncommitted owner-answer defaults in strategy.py (year_end="december",
sloppy_mode="stand_aside"; not part of this commit) - with those two hunks reverted, all 3 pass
(year_end, PRE_OWNER golden, sloppy alias).

Limits after this pass: the eq_pref DRAW still acts only without the lock (the rel-eq sweep pick
applies with it); vi_news_draw still acts only in the lock (it needs the htf table row).

## Package setups_models (2026-10-18)

Sources: `rule_coverage.md` section 3 "setups_models" (incl. the M0.4 / M1.2 placement notes),
`mentorship_rules.md` 2.1 / 2.6 / Appendix A, `digests/models.md`. Code: `mentorship/setups.py` (new:
the setup branches and gates, side space), hooks in `strategy._scan_core` (sweep / MSS block),
`_finish_order`, `run_day` (slots, order types, adds, exits), `_smt`, `_mss_ref`, `_turtle`;
detectors in `levels.py` (ote_band, three_drives, wick_ce, leg_sibi, ifvg_passes, reaper,
reclaimed_obs, tf_pivots, failure_swing); `sb_model._arm` (A20 in the SB), `pre_open.run_ma_deuce`
(M15), `backtest.combine(pick=)` (Ep03.11). Tests: `tests/test_setups_models.py`. Study:
`study.DECISIONS` variants prefixed with the rule id. Every new switch is OFF by default.
New engine order flags (run_day `_fill_at`): market (next open), stop_entry (buy stop), through
(limit needing N beyond), cancel_low, exit_at, runner, po3_open; new slots LH (own last hour),
PMR (PM reversal), MOC.
NOTE: the FVG-path switches (unicorn / IFVG / 2022 pick / stops / OTE / on-side / reaper / arrays)
act after the MSS, i.e. with `ob_entry="post_mss"` or `"both"`; under the owner #11 default
(`pre_break`) the sweep is consumed at the break (as for the existing FVG-path switches). The
study variants set `ob_entry="post_mss"` where needed.

- A19 MSS after a sweep | done | `mss_ref` += "parent" (start of the staircase of lower highs [our interpretation]), `mss_ref_fallback` (existing), `mss_on_side` | "stl", "lower", "off" | "last" = the existing "stl"
- A19.2 which swing / equal lows | done | `mss_ref` "itl" (existing), `mss_eq_wait`, `mss_ref_fallback` (= mss_fallback) | False | no MSS while a relative-equal low within eq_tol below the swept level is untaken
- A20 displacement | done | `disp_mult`, `disp_follow`, `disp_through_pts`, `disp_fvg_after_break` (also in the SB: `setups.disp_ok_sb`) | 0 / False | disp_mult = (break close - OB body top) >= N x OB body (cc04_003); disp_follow confirms the MSS at the next close (above the break close)
- M1 AM market maker model | done | `am_htf_draw`, `am_discount_array`, `speed_check` (= rip_through), `ob_entry` "pre_break" (existing, D10), `stop_mode="ob_near"` | off | HTF draw = the htf table draw_up / draw_dn beyond the entry; discount array = a 1m BISI open by closes or a 5m OB (zones_tf) at the sweep extreme
- M2 2022 model | done | `fvg_pick="2022"`, `no_breakout_fvg`, `stop_mode="ce2"` / `"fvg_candle"`, `add_leg_cut`, `m2_target`, `three_drives` | off | m2_target [our interpretation]: the draw beyond the day's range EQ, rel-eq ("larger") pool first; add_leg_cut: adds at or below the leg EQ, none once price traded past 75% of the leg
- M12 turtle soup | done | `turtle_soup` (earlier), `ts_need_htf` (earlier), `ts_need_flow` (new: daily D structure its way) | off |
- M12.1 2023 no-MSS turtle | done (review pass, earlier) | `turtle_soup="2023"`, `ts_entry`, `ts_stop` | off | unchanged
- Ep08.4 MSS swing validity | done | `mss_ref="origin"` | "stl" | the highest swing high between the swept level's creation and the sweep extreme [our interpretation]
- A19.4 two MSS = on side | done | `mss_on_side="tag"` | "off" | lv_tags "on_side" at the fill when a higher low + a close above the high before it printed between arming and the bar before the fill
- M0 common skeleton | done | `candle_draw_bias` ("daily"/"weekly"), `session_priority` (existing L1 / M0.2 = pool priority), `entry_arrays` | off | candle draw [our interpretation]: the nearer untaken prior-candle extreme from the midnight open; once one side is taken today the other is the draw
- M0.5 enter on any PD array | done | `entry_arrays` = ob / breaker / ote / wick_ce / vi / reclaimed_ob (turtle soup = `turtle_soup`) | () | the highest array between the sweep extreme and the close (the first the retrace reaches) beats the FVG; with no FVG by fvg_wait the arrays are used before the sweep is reset (entry_kind arr_<name>)
- M1.1 HTF draw and discount array | done | `mm_context` ("tag"/"require"), `daily_vi_targets` | off | daily VIs need vi_arrays (warned when inert)
- M1.3 speed check | done | `speed_check`, `speed_bars`, `body_low_cancel` | False, 3, False | the leg's last SIBI closed above within speed_bars of the extreme, else the sweep is dropped; a trade below the swing low's lowest body cancels the pending order / is a stop on the fill bar
- M2.3 FVG choice | done | `fvg_pick="2022"` | "last" | VI + OB aligned, else the first in the leg's discount, else the deeper of the last two
- M4 breakers / unicorns | done | `breaker_entry` (+ "classic"), `breaker_mt_entry_floor` (existing = unicorn_mt_floor), `unicorn_open_only`, `breaker_zone="leg"` (existing) + `adv_breaker`, `breaker_retest_add`, `cc_swings` | off |
- M4.1 classic breaker entry | done | `breaker_entry="classic"` | "off" | the breaker top when it sits above the FVG entry (reached first), MT cancel (#6), stop beyond L2; breaker fallback when no FVG
- M5 PM last hour / MOC | done | `pm_last_hour_model`, `pm_ep01` | off | last-hour sweeps 15:15-15:45 only, orders cut at 15:45, skip once the HTF objective is done (a lock this way delivered / the htf draw traded today [our interpretation])
- M5.1 Ep 01 last-hour version | partial | `pm_ep01` | False | nested 1h-in-4h FVG known by 15:00, 4h CE body hold, refusal at the 1h low from 15:15, breakaway FVG -> its top, stop below the FVG candle's open, single exit at the draw; the adds (FVG / breakaway / breaker) and the trail are the engine's generic add / trail switches, not an Ep 01-specific sequence
- M10 IFVG entry | done | `ifvg_entries` (existing), `ifvg_entry`, `ifvg_stop_pts`, `ifvg_min_risk_pts`, `ifvg_depth`, `ifvg_061` | off | 061: a body close at the lower FVG's high / CE triggers a market entry
- M11 IR / CISD / wick CE | done | `ir_entries`, `cisd_ob_entries`, `wick_ce_entries` | off | see M11a-c
- M12.2 short at an old high | done | `turtle_soup` (mirrored side, no MSS), `ts_adds_breakers` | off | turtle-soup trades add at each new breaker (L.breakers) formed after the fill
- M12.3 CC variants | done (review pass, earlier) | `turtle_soup` cc_limit / cc_1h_ob / or60 | off | unchanged
- M12.5 depth / back gate | done (review pass, earlier) | `ts_gate_mss` | off | unchanged
- M13 OTE | done | `ote` ("filter"/"limit"), `leg_pd_strict`, `ote_leg_stop`, `ote_stack_tag` | off | 62-79% band, 70.5% limit; the target rule uses the existing targets (pools / HTF OBs)
- M16 index SMT / sick sister | done | `smt_entry`, `sick_sister` | off | see M16.1 / M16.2
- M16.1 CC AM SMT entry | done | `smt_entry`, `smt_turtle`, `smt_exit`, `smt_entry_syms` | False, False, 660, ("ES","MES") | pool "l0500" (05:00-09:30 low, from 09:30) + London / overnight; an SMT-confirmed sweep -> buy STOP above the last down-close candle since the low (or a turtle-soup limit), stop below the low, out at 11:00
- D10 early OB / turtle entries | done (owner #11, earlier) | `ob_entry`, `turtle_soup` | "pre_break" | unchanged
- Ep01.13 last-hour run | done | `last_hour_setup` (= `last_hour_own_slot` + `lh_unengaged` + `lh_htf_done_skip`) | off | own LH slot after the PM trade; LH draw beyond today's high so far
- Ep01.15 nested FVGs | done | `nest_tfs` | () | the sweep extreme inside an open same-side FVG (confluence FVG rows only) on every listed timeframe, known by the extreme's close; no confluence -> no trade
- Ep03.11 stronger index | done | `smt_pick` ("leader"/"laggard"; `backtest.combine(pick=)`), Trade `ext_px` / `leg_hi_px` | "first" | causal: each fill's smt tag is known at its sweep; same-bar ties by the relative leg
- Ep04.3 PO3 bullish | done | `require_judas`, `po3_runner`, `judas_window` | off, 60 | runner: the last ladder fraction has no target (BE / close)
- Ep04.5 news dealing range | done (owner #4, earlier) | `news_wait`, `news_range_target` | "range" | unchanged
- Ep04.7 two MSS | done | `mss_on_side="require"` | "off" | a higher low after the first MSS, a close above the high before it, entry from the second leg's FVGs, the first leg's FVG still open (timeout pending_minutes)
- Ep05.4 unicorn rules | done | `unicorn_only`, `unicorn_entry="overlap"`, `add_on_vi`, `unicorn_open_only` / tag unicorn_open (`unicorn_open_min`), `adds_in_breaker` | off, 30 |
- Ep05.8 MM sell model | done | `mmxm_ctx`, `mmxm_breaker` | off | draw = the parent swing (the original consolidation's far side) [our interpretation]; a body close beyond the entry FVG's CE exits (the ce_hold rule)
- Ep07.6 speed and distance | done | `mss_max_bars`, `mss_disp`, `mss_ref_sibi` | 0, 0, False | mss_disp = breaking candle range >= N x mean range of the prior 10 bars [our interpretation]
- Ep08.15 turtle soup | done | `turtle_soup`, `ts_need_htf`, `ts_max_run` | off | ts_max_run [our interpretation]: the failure close within N minutes of the spike extreme
- Ep08.16 5m equal lows MSS | done | `mss_ref_tf` | 0 | the last swing high on m-minute bars (complete buckets only); two equal ones -> the higher
- A8 IFVG rules | done | `ifvg_depth` (passes / both-way count), `ifvg_hold`, `ifvg_after_htf` | off | depth: untouched -> far edge, re-traded / both ways -> CE at most (stop beyond)
- A14 unicorn | done | tag unicorn_open, `unicorn_only`, `unicorn_open_only` | off |
- A18 reclaimed OB | done | `reclaimed_ob` (and entry_arrays "reclaimed_ob") | False | down-close candles on the sell side of the curve followed by a bounce, reclaimed by a close above their high after the low; limit at the highest one's top
- A24 not codeable (umbrella) | partial | `reaper` | off | the Reaper is built; implied FVG (never defined) and inducement (= the sweep step) stay as they are
- A24.2 Reaper | done | `reaper`, `reaper_confirm` | off | the FVG in the discount half of the breaker's L1 -> H leg cut through on the way to the lower low; limit at its top (or market after a reaction candle), out on a body close below its CE
- B18 SMT (umbrella) | done | `smt_windows`, `smt_need_array` (smt_at_pd), `smt_min_gap_pts`, `smt_pick` | off |
- B18.1 SMT qualifier | done | `smt_min_gap_pts`, `smt_need_array`, `smt_rel_eq` | off | rel-eq twin [our interpretation]: the partner's lowest swing low within pivot_n bars of the cluster's swing times
- B18.2 SMT windows | done | `smt_windows`, `smt_pre` | (), False | outside the windows the sweep's smt is None
- N6 news profile | done | `news_profile`, `news_ce_target`, `news_no_unicorn` | off | first leg = which news-range extreme printed first; NFP / CPI / FOMC days: no unicorn / breaker entries
- T10 last hour / MOC | done | `moc_run`, `moc_cap_pts`, `moc_pool_exit` | False, 10, False | 15:40 bar: market entry toward the nearest liquidity untouched today (lock / bias side), stop below the low since 15:10, target capped at 10 handles, needs min_draw_pts; pool exit = all off at the first pool
- T13 day templates / PO3 | partial | `require_judas`, `po3_hold`, `profile_tags`, `nfp_sd` | off | profile tags are the EXPECTED profile from D / 4h structure at arming [our interpretation] (the CC classification needs a discretionary HTF map); po3_hold: after a close above the reference open, a close back below exits
- M2.7 three drives | done | `three_drives` | "off" | levels.three_drives: the last two confirmed swing lows + the sweep extreme are lower lows with a smaller last push
- M4.2 unicorn conditions | done | `unicorn_rules` | False | the unicorn needs the Judas, entry inside the overlap, MT floor
- M4.3 advanced breaker | partial | `adv_breaker` | False | limit at the A-B leg MT with 1 tick through to fill, stop beyond L2, target B + 1x(B - A); the "bias on side" entry inside the A-B leg / on the sell-side run before the break is not built
- M4.4 turtle soup + breaker pyramid | done | `ts_breaker_pyramid` | False | one add at the first breaker formed after a turtle-soup fill
- M4.5 CC breaker / failure swing | done | `cc_swings`, `cc_fail_pts` | "off", 5.0 | breaker swing: retest of the broken high, stop below the new low; failure swing: a higher low within cc_fail_pts above an intact pool, the first close above the high before it, retest limit, stop below the failed low
- M5.2 2022 model in the window | done | `last_hour_strict` (existing #1), `last_hour_own_slot`, `entry_arrays` vi / ob, `pm_last_hour_model` | off |
- M6 PM reversal | done | `pm_reversal` | False | slot PMR; needs a delivered lock the other way, the AM extreme taken in the PM, an IFVG at the extreme; targets the old daily levels and the lunch extreme (side space)
- M7 PM off lunch | done | `pm_lunch_target`, `pm_lunch_org`, `pm_judas_1330` (existing = pm_judas_filter) | off |
- M7.2 lunch into the ORG | done | `pm_lunch_org` | False | the lunch sweep extreme inside today's ORG
- M7.3 13:30 Judas into an array | done | `pm_judas_array` | False | pseudo-pool = the top of the nearest same-side HTF array beyond the 13:30 open
- M11a immediate-rebalance entry | done | `ir_entries` | False | with a bias (lock / htf), market after an A7 IR; stop below the IR candle; out on a close below the displacement candle's EQ [our interpretation of the range]
- M11b CISD OB entry | done | `cisd_ob_entries` | False | wick CISD over the OB body top; limit min(EQ, OB top); OB-low cancel; stop below the OB
- M11c wick-CE long | done | `wick_ce_entries` | False | limit at the sweep candle's wick CE once the next candle closed above it; target 0.5 pt before the swing high
- M12.4 external turtle soup | done (review pass, earlier) | `turtle_soup="external"` | off | unchanged
- M15 Ma Deuce | done | `md_big_candle`, `md_second`, `md_ladder`, `md_need_news`, `md_eth`, `md_blocked` | off | ladder CE / lower quadrant / 1h BISI low (no lock); 2nd entry = one add before 08:30; blocked() + skip_news routing
- M16.2 sick sister | done | `sick_sister` | False | fewest reference highs (PDH 1-3, overnight, London, prior PM) taken by the session start among the index and its partners; the day's discount; targets its untaken references
- Ep01.16 hold above the 4h CE | done | `pm_4h_ce` | False | from 15:00 every close above the nearest same-side 4h FVG's CE (known by 15:00)
- Ep01.17 started by 15:25 | done | `lh_start_by` | 0 | last-hour sweep extreme at or before the minute; the breakaway check = pm_ep01 / `breakaway` (existing)
- Ep01.22 clean delivery | done | `clean_leg`, `clean_body` | -1, 0 | at most N down-close candles from the low to the break; their bodies <= N x the mean up-close body
- Ep04.4 PO3 bearish | done | `po3_require_bias`, `po3_inclusive`, `require_judas` | off |
- Ep05.6 08:00 OB move | done (test variant only) | `pre_0700` (existing) | False | study variant Ep05.6_0800_ob_move
- M0.4 MSS displacement leaves an FVG | done | `disp_body_mult`, `disp_follow` (+ `disp_fvg_after_break`) | 0, False |
- M1.2 swing-low intact bug | done (owner directives, earlier) | `displacement_mult` | 0 | unchanged

Results (setups_models): tests/test_setups_models.py 31 passed (unit + 15 synthetic + 2 ES/NQ no-look-ahead runs); test_mentorship -k look_ahead 12 passed; the other suites (non-look-ahead) 102 passed, 3 failed - the same 3 fail at HEAD (year_end, PRE_OWNER golden, sloppy alias: owner-answer defaults). With every new switch off, ES Jan-Mar 2024 trades (defaults and PRE_OWNER, SB + Ma Deuce on) are identical to HEAD.


## setups_models review fixes (2026-10-18)

Fixes for the setups_models review findings, then the items left partial. Code: `setups.py`,
`strategy.py` (`_scan_core`, `run_day`, `_finish_order`, `_ob_pre`, `_smt`, `_lock_times`,
`_lock_step`), `levels.implied_fvgs`, `pre_open.run_ma_deuce`, `backtest.prepare` / `lock_cuts`,
`study.py`. Tests: `tests/test_setups_models.py` (review-fix unit tests, ES runs with exits / adds
compared, and evidence that each switch fires). With every switch at its default, ES 5m
2023-11-15..2024-03-31 trades are identical to HEAD (defaults, SB + Ma Deuce on, and post_mss with no
lock / cap).

### Findings and fixes

| Finding | Fix | New / changed switches |
|---|---|---|
| ~40 switches inert under owner #11 `pre_break` | The MSS-validity gates (A20 disp_*, M0.4, Ep07.6 mss_max_bars / mss_disp, M1.3 speed_check, A19.2 mss_eq_wait, Ep01.22 clean_*, M1.2 displacement_mult, A7 imm_rebalance_disp, the mss_ref variants) now act on the default OB order: the order carries its sweep (`sw_ref`); a break that fails the gates (or a timing drop) sets `ob_void` and the still-pending OB order is cancelled at the next bar; "hold" fills it only after the gated MSS. The FVG-path-only switches stay FVG-path: owner question 7. Study: FVG-path variants use `SM_POST` (post_mss + no #9 lock + no #7 cap); new `*_ob_cancel` / `*_ob_hold` variants | `ob_pre_gate` "cancel" (default) / "hold" / "off" [our interpretation] |
| M5 / M5.1 15:15-15:45 window (owner #1) | `setups.lh_window`: 15:00-15:50, the sweet spot only with `last_hour_strict`; the M5 cut is the window end | - |
| Ep01.13 / M5.2 own LH slot traded with no lock (owner #9) | The own LH slot locks its own draw at 15:00 (`_lock_times` "LH", PM mark-up cut at 15:00, htf table cut 900 in `lock_cuts`); the slot trades only toward it and is done when it is delivered. Owner question 8 | `lh_no_lock` (first build) |
| Ep04.7 require: timeout from the first break | `_fvg_wait_from`: fvg_wait runs from the second break; the first leg's FVG is re-checked on every bar up to arming | - |
| A24.2 reaper_confirm unreachable | The reaction candle (wick in, close >= CE) is tested before the "above the top" check; "wait" while unconfirmed; a body close below the CE kills the Reaper (the FVG path may use the sweep) | - |
| A20 / M0.4 / M2.3 wrong OB | `setups.ob_low`: the OB at the sweep low (order_block_blend over [ext_i-3, ext_i]) for disp_mult, disp_body_mult and the 2022 VI+OB pick | - |
| M15 md_eth inert | `backtest.prepare` builds the ETH sessions with `ma_deuce and md_eth` (paper uses prepare) | - |
| M15 Ma Deuce never trades / ladder off under the lock | Funnel keys `md_x_*` (strategy.FUNNEL). ES 5m 2023-06..12 with FUT + defaults: `M15_ma_deuce_full` is stopped by md_need_news (145 days), the big candle (14) and no daily FVG (10); plain `ma_deuce` by no daily FVG (76), not past the inverted FVG at 08:00 (33), risk (30), wrong half (14), #7 cap (8), lock side (4), chop (2) - 0 trades; with lock and cap off 3 trades. 2019-2022 (lock / cap off): 5-12 a year, nearly all stopped. The ladder now runs under the #9 lock / #7 cap: every rung capped at the locked draw / the cap, the cap is the last rung when it cuts the ladder; the scalp cap applies to every rung | - |
| M5.1 / Ep01.16 / Ep01.17 inert | pm_ep01: owner window, every nested 1h/4h pair tried (nearest 1h first), no leg-discount wait at the fill (no_leg_wait), no PO3 open filter (synth_po3); the 4h CE hold moved to the pair's 4h FVG under `pm_4h_ce`; pm_4h_ce on other LH trades rejects when no 4h FVG exists; lh_start_by also gates pm_ep01. ES 2022-12-30 (the Ep 01 day): long pm_ep01 armed 15:15, filled 15:20 at 3842.00 (ICT: 3839.25 ~15:25), one add, out at the draw (lock / cap off; the default 15:00 LH lock picks the AM low below that day) | `synth_po3` |
| M16.1 smt_entry inert | Three causes: the PO3 open filter (x_wrong_side_of_open on most candidates; the CC model has no PO3 - now skipped), the #11 OB order armed a bar later replaced the SMT order (pre-break model entries now block the OB order), and no re-arm after a new low (smt_sent reset on re-anchor). ES 2023 with lock / cap off: 25 smt_stop trades. With the owner #7 cap on, the remaining candidates are capped (x_htf_resist). Study variants list SPX (the CFD study symbol) in smt_entry_syms | - |
| Look-ahead coverage | `_no_look_ahead(exits=True)` also cuts at exit times and compares exit time / reasons / adds / net of every trade closed by the cut; min_trades >= 1 everywhere; each ES / synthetic run asserts its switches fired (entry kinds, tags, exit reasons, FUNNEL); smt_pick look-ahead via truncated ES + NQ books combined | - |
| Ep08.4 origin | `setups.leg_origin`: walked back from ext_i while no close above the high and no higher swing low intervened | `mss_ref="origin_max"` (first build) |
| smt_pre narrowed "any" | `_smt_window_ok`: windows only when smt_windows is set; smt_pre adds 05:00-09:30 | - |
| unicorn_only | picks among the unicorns (fvg_pick inside them) | - |
| moc_run / IR / PO3; cc failure | synthetic setups skip the PO3 open filter (`synth_po3`); cc failure arms on the first bar where the swing low B is confirmed AND a close above H printed since B (the break used to come before B was known) | `synth_po3` |
| M6 pm_reversal | with no session lock, the htf table's draw the other way traded today = objective met; the 10-bar IFVG window marked [our interpretation] | - |
| A19.4 tag | each of the two legs must leave an FVG still open at the fill; the first MSS of an OB order comes from its sweep | - |
| M13 ote_stack_tag | any swept sell-side pool of the sweep machine (not only swing / rel-eq keys) | - |
| Ep03.11 smt_pick variants | `study._dec_job` runs the partner book and combines when smt_pick != "first"; IVARIANTS also carry both | - |
| M16.2 sick sister | references = PDH 1-3, the overnight high (ctx.pd "pmh" = midnight -> 09:30, from 18:00 with globex_pool), London, prior PM; entry below sick_depth of the day's range | `sick_depth` 0.25 [our interpretation; 0.5 = first build] |
| Ep05.8 mmxm | rel-eq requirement; the CE exit reuses the ce_hold rule (order flag, exit reason ce_close) | `mmxm_rel_eq` |
| A20 in the SB | every breaking close after the leg extreme is tried; the first that passes is the MSS | - |

### Items left partial by the first build (now built)

- M4.3 `adv_breaker_pre` | done | with the bias on side (the lock side / htf bias), the first close back above A after the run below it -> market entry, stop beyond L2, target B + 1x(B-A) [our interpretation of the trigger]; takes the OB order's place for that sweep.
- M5.1 `pm_ep01_adds` | done | Ep 01 sequence: add in the entry FVG (CE), in the breakaway gap (its top; after the fill the stop goes below that gap's candle bodies from the next bar), on a breaker; trail under each later FVG's bodies. Generic adds / trail are off for these trades.
- A24.1 `implied_fvg` | done | `levels.implied_fvgs`: wick-CE to wick-CE across a displacement candle with overlapping outer wicks [our interpretation]; entry kind implied_fvg. Inducement = the sweep step (A24.3, FULL).
- T13 `cc_profile` | done | six CC profiles at 13:30 (AM leg, opposing 4h / D array at the AM extreme, no news after 10:00 + AM range < 0.5 ADR5 = consolidation, NFP = seek_destroy) [our interpretation]; "tag" / "gate" (PM direction; consolidation profiles out at 14:00).
- Ep05.8 rel-eq | done | `mmxm_rel_eq`.
- Ep05.6 | study variant only, by spec.

### ES trade counts per study variant (review probe)

ES 5m 2023-06-01..2023-12-31, FUT sizing (es_pt 1, lot 1), every other Params at its default plus
the variant (the reviewer's setting). "= base" means entries identical to the base run.
| Variant | Trades | = base | Entry kinds (non ob_pre) / tags / exits of note |
|---|---|---|---|
| base | 15 |  |  |
| A19_mss_ref_parent | 2 |  | fvg 2 |
| A19.2_mss_eq_wait | 5 |  | fvg 5 |
| A19.4_on_side_tag | 5 |  | fvg 5 |
| Ep04.7_on_side_require | 0 |  |  |
| Ep08.4_mss_ref_origin | 1 |  | fvg 1 |
| A20_disp_mult2 | 2 |  | fvg 2 |
| A20_disp_through_1 | 5 |  | fvg 5 |
| A20_disp_fvg_after_break | 4 |  | fvg 4 |
| A20_disp_all_sb | 13 |  |  |
| M0.4_disp_body_mult1 | 4 |  | fvg 4 |
| M0.4_disp_follow | 0 |  |  |
| Ep07.6_mss_max_bars6 | 3 |  | fvg 3 |
| Ep07.6_mss_disp15 | 3 |  | fvg 3 |
| Ep07.6_mss_ref_sibi | 6 |  | fvg 6 |
| Ep08.16_mss_ref_tf5 | 5 |  | fvg 5 |
| M1_am_htf_draw | 15 | yes | mm_ctx 1 |
| M1_am_discount_array | 9 |  | mm_ctx 1 |
| M1_stop_ob_near | 5 |  | fvg 5 |
| M1.1_mm_context_require | 9 |  | mm_ctx 1 |
| M1.1_daily_vi_targets | 15 | yes |  |
| M1.3_speed_check | 4 |  | fvg 4 |
| M1.3_body_low_cancel | 5 |  | fvg 5 |
| M2_no_breakout_fvg | 5 |  | fvg 5 |
| M2_stop_fvg_candle | 5 |  | fvg 5; am_exit 1 |
| M2_stop_ce2 | 4 |  | fvg 4 |
| M2_add_leg_cut | 5 |  | fvg 5 |
| M2_m2_target | 5 |  | fvg 5; draw_m2 5 |
| M2.3_fvg_pick_2022 | 5 |  | fvg 5 |
| M2.7_three_drives_require | 7 |  | three_drives 7 |
| M4_unicorn_open_only | 5 |  | fvg 5 |
| M4_breaker_retest_add | 5 |  | fvg 5 |
| M4.1_breaker_classic | 2 |  | breaker 2; breaker_mt 1 |
| M4.2_unicorn_rules | 5 |  | fvg 5 |
| M4.3_adv_breaker | 21 |  | adv_breaker 16, fvg 5 |
| M4.4_ts_breaker_pyramid | 18 |  | turtle_soup 5 |
| M4.5_cc_swings_breaker | 16 |  | cc_breaker_swing 1 |
| M4.5_cc_swings_failure | 15 | yes |  |
| A14_unicorn_only | 1 |  | fvg 1 |
| Ep05.4_unicorn_overlap | 5 |  | fvg 5 |
| Ep05.4_add_on_vi | 5 |  | fvg 5 |
| Ep05.4_adds_in_breaker | 5 |  | fvg 5 |
| M5_pm_last_hour_model | 4 |  | fvg 4 |
| M5.1_pm_ep01 | 13 |  | pm_ep01 1 |
| M5.2_last_hour_own_slot | 12 |  |  |
| M5.2_entry_arrays_vi_ob | 7 |  | fvg 4, arr_ob 3; am_exit 1 |
| Ep01.13_last_hour_setup | 12 |  |  |
| Ep01.13_lh_parts | 12 |  |  |
| Ep01.16_pm_4h_ce | 12 |  |  |
| Ep01.17_lh_start_by_1525 | 12 |  |  |
| T10_moc_run | 17 |  | moc_run 2 |
| T10_moc_pool_exit | 15 | yes |  |
| M6_pm_reversal | 20 |  | pm_reversal 5 |
| M7_pm_lunch_target | 3 |  | fvg 3; draw_lunch 1 |
| M7.2_pm_lunch_org | 7 |  |  |
| M7.3_pm_judas_array | 16 |  |  |
| M10_ifvg_ce_stop3 | 2 |  | fvg 1, ifvg 1 |
| M10_ifvg_061 | 5 |  | fvg 5 |
| A8_ifvg_depth_hold | 2 |  | fvg 2 |
| A8_ifvg_after_htf | 3 |  | fvg 3 |
| M11a_ir_entries | 24 |  | ir 9 |
| M11b_cisd_ob_entries | 16 |  | cisd_ob 11 |
| M11c_wick_ce_entries | 39 |  | wick_ce 29 |
| M12_ts_need_flow | 17 |  | turtle_soup 3 |
| M12.2_ts_adds_breakers | 18 |  | turtle_soup 5 |
| Ep08.15_ts_max_run | 17 |  | turtle_soup 3 |
| M13_ote_filter | 3 |  | fvg 3 |
| M13_ote_limit_stop | 8 |  | fvg 8; am_exit 1, breaker_mt 1 |
| M13_leg_pd_strict | 5 |  | fvg 5; ote_stack 3 |
| M16.1_smt_entry | 18 |  | smt_stop 3 |
| M16.1_smt_turtle | 16 |  | smt_turtle 1 |
| M16.2_sick_sister | 1 |  |  |
| Ep03.11_smt_pick_leader | 15 | yes |  |
| Ep03.11_smt_pick_laggard | 15 | yes |  |
| B18.1_smt_min_gap1 | 4 |  |  |
| B18.1_smt_rel_eq | 5 |  |  |
| B18_smt_need_array | 3 |  |  |
| B18.2_smt_windows | 5 |  |  |
| N6_news_profile | 13 |  | news_profile 2 |
| N6_news_ce_target | 15 | yes |  |
| N6_news_no_unicorn | 5 |  | fvg 5 |
| T13_po3_hold_profiles | 15 |  | profile_up_close 7, profile_down_close 4, profile_reversal 4; po3_hold 1 |
| T13_nfp_sd_skip | 13 |  |  |
| Ep04.3_require_judas | 9 |  |  |
| Ep04.3_po3_runner | 15 |  | am_exit 1 |
| Ep04.4_po3_bias_inclusive | 16 |  |  |
| Ep01.15_nest_tfs | 0 |  |  |
| Ep05.6_0800_ob_move | 15 |  |  |
| Ep05.8_mmxm | 3 |  | fvg 3; draw_mmxm 3 |
| Ep01.22_clean_leg2 | 4 |  | fvg 4 |
| A18_reclaimed_ob | 6 |  | arr_reclaimed_ob 4, fvg 2; am_exit 1 |
| A24.2_reaper | 5 |  | fvg 5 |
| A24.2_reaper_confirm | 5 |  | fvg 5 |
| M0_candle_draw_daily | 14 |  |  |
| M0_candle_draw_weekly | 13 |  |  |
| M0.5_entry_arrays_all | 2 |  | arr_ote 1, arr_wick_ce 1 |
| M15_ma_deuce_full | 15 | yes |  |
| M15_ma_deuce_ladder | 15 | yes |  |
| A20_disp_mult2_ob_cancel | 13 |  |  |
| A20_disp_mult2_ob_hold | 0 |  |  |
| A20_disp_through_1_ob_cancel | 15 | yes |  |
| M0.4_disp_body_mult1_ob_cancel | 14 |  |  |
| M0.4_disp_follow_ob_hold | 0 |  |  |
| Ep07.6_mss_max_bars6_ob_cancel | 14 |  |  |
| Ep07.6_mss_disp15_ob_hold | 0 |  |  |
| M1.3_speed_check_ob_cancel | 12 |  |  |
| A19.2_mss_eq_wait_ob_hold | 2 |  |  |
| Ep01.22_clean_leg2_ob_hold | 2 |  |  |
| A19_mss_ref_parent_ob_hold | 0 |  |  |
| Ep08.4_mss_ref_origin_ob_hold | 0 |  |  |
| Ep08.4_mss_ref_origin_max | 0 |  |  |
| A19.4_on_side_tag_ob | 2 |  |  |
| D10_ob_pre_gate_hold | 2 |  |  |
| M5.1_pm_ep01_adds | 13 |  | pm_ep01 1 |
| M5.1_pm_ep01_strict | 13 |  |  |
| M5_pm_last_hour_model_strict | 4 |  | fvg 4 |
| M5.2_lh_no_lock | 17 |  |  |
| T10_moc_run_synth_po3 | 17 |  | moc_run 2 |
| M16.2_sick_depth_eq | 1 |  |  |
| Ep05.8_mmxm_rel_eq | 0 |  |  |
| A24.1_implied_fvg | 6 |  | fvg 5, implied_fvg 1 |
| M4.3_adv_breaker_pre | 18 |  | adv_breaker_pre 11 |
| T13_cc_profile_tag | 15 | yes | cc_seek_destroy 2, cc_two_session_down 4, cc_am_decline_pm_reversal 1, cc_unclear 1 |
| T13_cc_profile_gate | 10 |  | cc_two_session_down 2, cc_am_decline_pm_reversal 1 |

Notes: the "= base" check compares entry times / prices and net P&L, so tag-only variants
(T13_cc_profile_tag) show "yes" by design; Ep03.11 smt_pick acts only in a combined book (the probe
runs ES alone; the decisions harness now combines). The `*_ob_cancel` variants change 1-3 trades
(the OB order usually fills before the break); the `*_ob_hold` variants turn the OB entry into an
entry after the gated MSS (0-2 trades in 7 months).

### Status changes

- Built, unverified (0 trades / no change on ES 2023H2 with FUT + defaults; fires elsewhere):
  Ep04.7 mss_on_side="require" (2 trades with the on_side tag on ES 2023-08-28..10-06, ES_BASE),
  M0.4 disp_follow (FVG path), M1.1 daily_vi_targets, M1 am_htf_draw (no AM trade removed),
  M4.5 cc_swings="failure" (fires on synthetic), T10 moc_pool_exit (no last-hour pool exit hit),
  N6 news_ce_target, Ep01.15 nest_tfs (0 trades with SM_POST; nested 15m fires in the ES test run),
  Ep05.8 mmxm_rel_eq, Ep08.4 mss_ref "origin" / "origin_max" with the OB hold (0) - "origin" alone
  on the FVG path: 1 trade, M15 Ma Deuce (all switches; the gate funnel above; trades on ES 2020
  in the test window), the `*_ob_hold` variants with 0 trades (A20 disp_mult 2, M0.4 disp_follow,
  Ep07.6 mss_disp 1.5, A19 parent).
- Verified on ES 2023H2 after the fixes (were inert or unverified in the review): pm_ep01 (1, plus
  the Ep 01 day 2022-12-30), smt_entry (3 smt_stop) / smt_turtle (1), moc_run (2), pm_reversal (5),
  Reaper variants run (FVG fills; no Reaper fill in 2023H2: unverified), cc_swings breaker (1),
  adv_breaker_pre (11), implied_fvg (1), cc_profile gate (5 fewer trades).
- Status changes in the first-build list above: M4.3, M5.1, A24, T13 partial -> done (review pass);
  A24.2 reaper_confirm, M15 Ma Deuce, Ep05.8 rel-eq, T10 moc_pool_exit, Ep04.7 require ->
  "built, unverified (0 trades on ES 2023H2)".

Results (review pass): tests/test_setups_models.py: unit + synthetic look-ahead (with exits on the
exit / add sets) 23 passed; ES runs (look-ahead with exits / adds and per-switch evidence, Ep 01
day, LH lock, md_eth, smt_pick combine, Ma Deuce 2020) passed; test_mentorship -k look_ahead 12
passed. Defaults identical to HEAD on ES 5m 2023-11-15..2024-03-31 (defaults, SB + Ma Deuce,
post_mss without lock / cap).

## Package entries_stops_sizing (2026-10-18)

Sources: `rule_coverage.md` section 3 "entries_stops_sizing" (45 items incl. L14b), `owner_directives.md` #7 (REVISED), `rulebook_gaps/stops_sizing_scaling_in.md`, `mentorship_rules.md` E1-E12 / D11 / D12.
Code: new `mentorship/entries.py` (entry prices, stop modes and modifiers, OB zone helpers, sizing rules, risk state, add rules, extra entry zones) with hooks in `strategy._scan_core` / `_finish_order` / `run_day` / `_arm_add` / `_after_close`, `sb_model._arm` and `pre_open` (Ma Deuce fill). `backtest.run` carries the E10 risk state across days.
Tests: `tests/test_entries_stops.py` (unit tests, hand-made one-day scenarios through `run_day`, synthetic + ES no-look-ahead runs covering every new switch, `study.DECISIONS` coverage check). Study variants: name prefix = rule id (`Ep08.17_*`, `E6_*`, `A12_*`, ...); `PRESET_EP07` in strategy.py.
New defaults (spec / owner): `stop_tick_pts=0.25` (Ep08.17: one-tick stop pad instead of 0.01), `nfp_no_adds=True` (E12f), `add_arrays=("htf_fvg",)` (owner #7 revised: the HTF FVG behind the trade is an add zone). `study.CURRENT` and `PRE_OWNER` pin all three back (`stop_tick_pts=0`, `nfp_no_adds=False`, `add_arrays=()`), so the golden window still reproduces.
Check: with the three legacy switches the engine reproduces HEAD exactly (ES 5m 2023-10-02..11-17, FUT, draw_lock off: 29 trades, net -7610.53).

- E6 stop modes + modifiers | done | `stop_mode` fvg_c1_low / fvg_bodies / fvg_open / sweep / ob_mt_pure, `stop_all_ineff`, `stop_ineff_wick`, `stop_pad_ticks`, `ce_stop_pad_pts`, `mohawk_ticks`, `nfp_stop_wide` | "ob_mt", off, True, 0, 0, 0, off | `entries.gap_stop` (FVG path) and `entries.refine_stop` (every entry path, in `_finish_order` before the risk check); each modifier only ever moves the stop away (E7); `nfp_stop_wide` = lowest body of bars sweep-3..now on a jobs day [our interpretation of "behind all HTF bodies"]; `Params.pad` / `trail_pad` / `tick` properties replace `stop_buffer` everywhere
- E6c stop beyond the sweep | done | `stop_mode="sweep"` | off | sw.ext - pad; the study variant runs max_risk_pts=25
- A4 mohawk | done | `mohawk_ticks`, `sweep_body` | 0, False | stops and trails N ticks wider, lvx exit "mohawk" on a body CLOSE beyond the raw level, the "fresh gap" test tolerates an N-tick poke; sweep_body = a candle body must trade through the level (unranked, off)
- A12 order blocks | done | `ob_zone`, `ob_stub_frac`, `mt_close_stop`, `ob_disp_mult`, `ob_cisd`, `ob_targets_1m`, `opp_ob_mt` | "", 0.25, False, 0, "off", False, False | ob_zone "sensitive" = high down to the open (entry at the open when the wick <= ob_stub_frac of the range, else the wick CE), "range" = the full range high; mt_close_stop = hard stop at the OB far edge + body close below the MT exits (lvx ob_mt_close); ob_disp_mult on the FVG path (move away >= N x the OB body); ob_cisd "tag" / "cancel" (OB low must hold); opposing bearish OBs (the up-close run before a SIBI) as targets, spent once the MT traded [our interpretation of "other half not revisited"]
- A13.4 breaker first-touch entry | done (built by setups_models) | `breaker_entry` | "off" | verified in tests: "prefer" gives a limit at the breaker top, stop beyond the sweep extreme, cancel / exit on a close below the MT (#6)
- M1.4 OB entry before the break | done (owner #11) | `ob_entry` | "pre_break" | verified in tests
- M2.4 no new low before the fill | done | `no_new_extreme` | False | order flag: a closed bar below the sweep extreme cancels the pending order; leg high frozen at arming for the leg_pd wait
- E2 / D11 entry price modes | done (SB: no ladder) | `entry` edge / ce / edge_1tick / iofed / ladder, `iofed_ref`, `entry_ladder_fracs`, `sb_entry`, `run_cancel` | "edge", "c2_high", (0.5, 0.3, 0.2), "edge", "t1" | `entries.entry_px`; unknown values raise; ladder = one order sized on the average risk of the rungs, deeper rungs rest as limits (entry-ladder fills are stored in Trade.adds but do not count as pyramid adds); SB uses `sb_entry` (no ladder); run_cancel "last" / "off" loosen the "ran to target without us" cancel
- E5 order hygiene | done | `evolve_fvg`, `wait_structural` | False, False | sw["ev_g"] guard: after an armed order (evolve) or a rejected one (wait_structural) the sweep stays alive and only a gap NEWER than the last one re-arms; evolve takes only untouched gaps; alive for one order lifetime
- E6b / E6d / E6f / M2.5 / Ep01.20 stops | done | see E6 | | fvg_candle and ce2 were built by setups_models; ob_mt_pure = OB MT - `ob_mt_pure_pad_pts` (2); fvg_open = under the middle candle's open
- Ep01.20 trail reference | done | `trail_ref` | "gap" | "body" trails under the three FVG candles' lowest body instead of the gap bottom
- E9 size rules | done | `size_rules`, `size_down`, `size_up_rules`, `size_up`, `htf_target_pts`, `low_prob_tests` | (), 0.5, (), 1.5, 10, ("against_bias",) | rules news_eve / fomc_week / august / against_macro (htf table react or draw opposes) / decoupled (ES vs partner since 09:30 opposite and both > 0.1%) / low_prob (against_bias, no_htf, sloppy) [our interpretation]; size-ups bpr / htf_target ("HTF 5000" read as an HTF array within htf_target_pts of the entry) test-only, still capped by the 1.3% total
- E10 / Ep08.12 loss handling | done | `loss_halving`, `halving_floor`, `winback_frac`, `no_max_after_loss`, `after_loss_mult`, `after_loss_adds` | False, 0.25, 0.5, False, 1.0, True | risk state {m, deficit, peak} carried across days by `backtest.run` (run_day `risk_state=`); halve per loss to the floor, back to full after winback_frac of the peak drawdown is won back; paper.py starts a fresh state each day (live carry-over not wired)
- E11 contract caps | done | `max_contracts_initial`, `max_contracts_total`, `units_per_contract` | 0, 0, 0 (= lot) | first unit capped, adds shrink to the contracts left
- E12 adds | done | `add_points`, `add_cutoff`, `nfp_no_adds`, `no_adds_nfp`, `add_fvg_low_end` | "top", 0, True, False, False | adds default reconciled with the docs: `adds=(0.5, 0.33, 0.17)` is ON (the rules text said "adds=() off"; fixed in mentorship_rules.md)
- E12b add arrays / hold | done | `add_arrays`, `add_hold`, `add_htf_tfs` | ("htf_fvg",), False, (15m, 30m, 1h) | vi / ifvg / ob / breaker / htf_fvg; add_hold cancels an add on a body close below its array (acts on market adds; a limit add fills before any close below)
- owner #7 (revised): FVG behind the trade = add zone | done | `add_arrays` "htf_fvg" | on | the same-side HTF FVG (confluence table) whose top lies between the stop and the close and at or under whose top the position was filled (price traded up through it): one add at its top; never a target
- E12c / Ep04.10 / E12 low end | done | `add_low_end`, `add_fvg_low`, `add_fvg_low_end` | False | one add at the gap bottom + 1 tick after a body close inside the last add's FVG (else the entry FVG), no close below since, units in open profit, no partial; size = the smallest earlier add
- E12e / D12 add cut | done | `add_cut`, `add_cutoff`, `add_cut_ref` | "", 0, "range" | no new add and a pending add cancelled once the highest high since the fill covered EQ / 75% of the leg / (1 - add_cutoff) of sweep-extreme..locked draw (or the leg); mirrored through side space
- E12f no adds | done | `nfp_no_adds`, `decoupled_no_adds`, `low_prob_no_adds` | True, False, False | jobs day / decoupled / low probability (order flag low_prob)
- D12 leg filters | done | `leg_pd_min` | 0 | entry >= this fraction of the leg (0.21 = the 79% OTE floor); the `D12_leg_062` study variant is now leg_pd 0.38 + leg_pd_min 0.21 (62-79% RETRACE; it was inverted)
- Ep02.2 round pools / entry arrays | done (built by levels_detectors / setups_models) | `round_pools`, `entry_arrays` | True, () | verified in tests
- Ep02.3 MT stop | done | `mt_close_stop` | False | see A12
- Ep07.2 VI entries + preset | done | `vi_entries`, `PRESET_EP07` | False | VI zones (both candles after the extreme: an index offset of one bar vs an FVG) as entry zones, entry_kind "vi", not an IFVG; preset = ob_entry both + vi_entries + ep07_stop/body_exit/trail + vi_hold + edge_1tick + VI adds
- Ep07.4 VI holds | done | `vi_hold` (+ existing `vi_stop`) | False | lvx vi_hold: a body close below the VI under the entry exits
- Ep08.5 OB at the anchor open | done | `ob_entries` | "off" | "prefer" at the break, "fallback" when no FVG follows it: limit at the first candle's open of the down-close run, MT stop; entry_kind "ob_anchor"
- Ep08.17 one-tick stop / range | done | `stop_tick_pts`, `engage_range_pts` | 0.25, 0 | DEFAULT ON per the spec; engage_range_pts = no entry before the range since midnight is N ES points
- L14b IRL / ERL | done | `irl_entries`, `erl_range_swings`, `erl_exits_only` | (), False, False | irl_entries "fvg" / "ob" / "void" (void = liquidity voids as entry zones, "ob" = array entries); erl_range_swings = P/D range up to the highest confirmed swing high; erl_exits_only = pool targets only (a locked draw that is an array refuses the trade) [our interpretation]
- A16 propulsion block | done | `prop_entry`, `prop_mt_exit`, `prop_zone` | False, False, "range" | `entries.prop_block`: entry = block top - 1 tick (a limit below the market), body-close exit under its MT; unit-tested (inert on the synthetic window: no propulsion block precedes an arming there)
- A21.3 OTE | done | `ote_cancel`, `leg_depth_tag` (band + 70.5% entry were built by setups_models: `ote`) | False, False | ote_cancel = the 79% line cancels a pending order; leg_depth_tag adds leg_shallow / leg_ote / leg_deep + leg_third_N to lv_tags
- E1 order types | done | `add_order`, `entry_order` | "limit", "limit" | add_order "market": the open after a retest bar; entry_order "stop_cc": a buy stop at the array top, refused when price is above it (never a chase)
- E3 fills | done | `tick_pts`, `fill_through`, `exit_fill_through` | 0.25, 0, 0 | main engine (via order flag `through`), SB and Ma Deuce; the Ma Deuce `<=` touch fill is now a strict print through (like the main engine)
- E4 retrace candle | done | `retrace_candle` | "off" | "closed" = a down-close candle printed between arming and the fill; "intrabar" = the fill bar opens above the limit
- E8 risk % | done (owner #12) | `risk_pct`, `max_total_risk_pct`, `risk_basis` | 0.012, 0.013, "fixed" | verified, nothing new
- Ep01.18 / Ep01.19 adds | done | `add_on`, `add_retest_away_pts`, `add_body_stop` | "", 2.0, False | add_on "retest" = one add at the entry gap top once a close is add_retest_away_pts above it; "breaker" = breaker_retest_add; add_body_stop moves the stop under the add gap's three candle bodies from the next bar (like the Ep 01 sequence)
- Ep03.9 OB anchor | done | `ob_entry_px` "open" / "high" | "body_top" | open = the first candle's open, high = the range top
- Ep04.6 midnight-open tolerance | done | `mo_tol_pts` | 0 | the entry may sit up to N ES points above the reference open
- Ep05.5 breaker fallback | done (built by setups_models) | `breaker_entry="fallback"` | "off" | verified in tests

### entries_stops_sizing - review fix pass (2026-10-18)

Findings fixed (tests in `tests/test_entries_stops.py`, section "Review fixes, second pass"):

- Owner #7 add zone (`entries.more_add_arrays`): `htf_add_used` is spent only after an add is really ARMED (a failed arm - no risk room under the 1.3% cap, `add_ok` false - leaves the shot for a later bar, e.g. after a trail has freed risk). How the zone gets room is now explicit: new switch `htf_add_extra_risk_pct` (default 0 = the cap binds; study `Ep02.2_add_htf_fvg_extra_risk` = 0.5% above it). Under the default 1.2% entry risk the room before T1 is ~0.1%, so the default zone arms a small add (34 shares of 533 in the scenario test) - documented as a near no-op until the stop has moved. Scenario tests: the add arms and fills for a long and for the mirrored short (zone patched into side space); unit tests: a real bearish FVG above a short (side-space conversion), a short filled below the zone gets no add.
- E2 / D11 ladder: `_finish_order` caps the WHOLE ladder (`cap_initial` on the planned total, rungs scale together), stores `plan_shares` (rung 0 + later rungs) and `_arm_add` sizes pyramid adds from it (adds were ~half size). Rung fills respect `max_contracts_total` (`cap_add`; a rung with no room is dropped). A `stop_cc` order is one stop: no ladder.
- E1 `stop_cc`: the +1 tick shift now happens BEFORE stop / risk / min-max risk / size, so the sizing is at the real fill price (scenario test: `ob_arm="touch"` fills; 600 shares = 1.2% at the shifted price; armed above the market it is still refused).
- Sizing, stop-modifier and loss-state hooks now reach the Silver Bullet and Ma Deuce (the "PO fill" of the spec = pre_open.py): `refine_stop` (E6d stop_all_ineff, E6f nfp_stop_wide, A4 mohawk; the Ma Deuce "sweep" is the inverted FVG [our interpretation]), `size_mult` (E9), E10 loss_halving and Ep08.12 after_loss_mult, E11 `cap_initial` (and `cap_add` for the Ma Deuce second entry), A4 mohawk body-close exit. They run after the bar loop, so they read the day's CLOSED trades as of their order bar via `ctx.risk_view` (`entries.extras_risk_mult`): never a later loss in the same day. The main loop cannot see the extras' trades (produced later). The carried E10 state is replayed in exit-time order over all of the day's trades at the end of `run_day` (`entries.replay_risk_state`). The end-of-data close now goes through `_after_close` (E10 / day-loss saw it never).
- A4 mohawk coverage: `trail_pad` in `setups.ep01_manage` trails and its add `stop_to`, the AM-tighten stop, `add_body_stop`, and the SB / Ma Deuce trails and AM-tighten.
- A21.3 `ote_cancel` (`entries.ote_cancel_level`): set only for an entry in / under the OTE band and never loosens the `ob_cisd="cancel"` level (the higher one wins).
- Ep08.17 `engage_range_pts`: checked before the FVG-path sweep is consumed, so the setup waits for the range instead of being dropped (the check in `_finish_order` stays for the other paths).
- Ep01.18 `add_on="retest"`: the entry zone top is stored with the order (`zone_top`) and used; the old 2 * CE - bottom stays as the fallback.
- E12e / D12: `add_cutoff_read` ("covered" default = no adds once 1 - add_cutoff of the range is covered; "progress" = once add_cutoff of the range is covered from the sweep low); variant `E12e_add_cutoff25_progress`.
- E9: `size_up_cap_pct` (default 0): extra total-risk cap for an order a size-up fired on. With 0 the 1.3% cap clamps size_up to ~1.08x (documented); variant `E9_size_up_cap` is a real 1.5x. The "HTF 5000" rule stays [our interpretation].
- Stop pad: a warning when `stop_buffer` is set while `stop_tick_pts > 0` (it is dead); the tick scales with es_pt (SPY 0.025).
- NFP default: `nfp_day` defaults to True (jobs days are traded), so `nfp_no_adds=True` is NOT a no-op in default runs (the finding assumed they were blocked); variants `E12f_nfp_day_adds_blocked` / `_allowed` added; the existing scenario test covers it.
- Look-ahead found by the new Silver Bullet / Ma Deuce test and fixed: E9 `low_prob` (`against_bias`) and `against_macro` read the 09:30-cut htf row for PRE7 / PRE9 / Ma Deuce orders (`entries.bias_row_known`: the row is used only from 09:30).
- paper.py: the E10 state is carried across days (`load_risk_state` / `save_risk_state`, `risk_state_<symbol>.json` next to the CSV; a same-day restart re-simulates from the day's start state).

Still NOT built (kept on the list): E2 ladder entry for the Silver Bullet (`sb_entry` is edge / ce / edge_1tick / iofed); ob_zone / ob_entry_px outside the pre-break OB path (documented scope); the SB pyramid / adds do not exist, so E12 add rules do not apply to it.


## Package targets_partials (2026-10-18)

Sources: `owner_directives.md` #7 REVISED, `rule_coverage.md` section 3 (36 items), the `rulebook_gaps` BUILD SPEC (targets_partials) notes for A6 / L4 / X3.
Code: new `mentorship/targets.py` (speed bump, HTF array levels with identity, target sources, SD engine, rung planner, mid-trade partials),
hooks in `strategy._finish_order` / `_targets` / `mark_levels` / the run_day ladder loop, `sb_model._arm`, `pre_open.run_ma_deuce`,
`confluence.opposing_ext`, `levels.rejection_blocks` (window + wick test fixed), `backtest.report` (capture), `study.DECISIONS` (~80 variants).
Tests: `tests/test_targets_partials.py` (unit tests, run_day scenarios, no-look-ahead runs on entries AND exits for every new switch).
How the ladder works now: main rungs share the ladder fractions as before; extra rungs (wick CE, -0.5 SD, halfway, inner levels) each take
`partial_extra_frac` (capped by `partial_extra_cap`); protected rungs (speed bump, wick CE, -0.5 SD) that fall off the rung cap become extras.
No plan is built when no switch is on and no bump exists (the old ladder code runs unchanged; `htf_resist_cap=False` reproduces the old results exactly).
`Trade.rungs` = the ladder at the fill ("level:kind:share|...", engine frame), `Trade.capture` = (avg exit - avg entry) / (best high - avg entry).

- Owner #7 REVISED (Ep02.10, L9, X3f) | done | `htf_resist_mode`, `htf_resist_cap_tfs`, `htf_bump_max` (`htf_resist_cap`, `htf_resist_tfs/src/buffer/min_room/live` as before) | "bump", ("1h","4h","D","W"), 2 | DEFAULT: an opposing HTF FVG between price and the draw gets a protected "bump" rung (near edge - buffer, up to htf_bump_max, an entry inside the array uses its CE or far edge [our interpretation]); "cap" = first build; "split" = cap on cap_tfs, bump on the rest; SB and Ma Deuce follow; the lock keeps its draw (no lock_capped in bump mode); htf_resist_live and draw_lock_near_cap act on the cap timeframes only; an FVG behind the trade is never a target (tested)
- X3 umbrella | done | `ladder_all_pools`, `wick_ce_partial`, `sd_neg05_first`, `halfway_partial`, `smt_bank`, `resistance_mode`, `capture_frac` + `Trade.capture` / `Trade.rungs` | all off | the umbrella names are aliases of the X3a/c/d/g/f/h switches below; `backtest.report` has a "capture" block
- X3a scale out at each pool / run down | done | `run_down`, `ladder_all_pools`, `ladder_max_levels` | False, False, 0 | one piece per rung (first keeps ladder_fracs[0], the rest even), up to 6 rungs (or ladder_max_levels); all_pools = pools + bumps only; level kinds carried in `pos["level_kinds"]`
- X3c wick-CE partial | done | `wick_partials` (`wick_ce_partial`), `wick_partial_tfs`, `wick_partial_longest`, `wick_partial_protect`, `wick_partial_min_pts` | False, ("D",), True, True, 2.0 | a partial exit_before_pts before the CE of a wick between entry and the last rung, from prior daily candles ("D") and completed 15m/30m/1h/4h candles of the day frame, untraded since; with two or more only the longest (065A); protected rung
- X3d -0.5 SD / halfway | done | `sd_half_partial` (`sd_neg05_first`), `halfway_partial`, `halfway_min_pts` | False, False, 2.0 | -0.5 SD of the sd_anchor range = protected first partial exempt from min_rr; halfway rung between the first two mains (026 ~14:57) [one gap only - our interpretation]
- X3f full pull vs partials by resistance | done | `resistance_mode`, `res_low_max`, `res_high_min` | "off", 1, 3 | obstacles = untouched opposing FVGs/voids + untaken swing highs + 15m+ opposing arrays between entry and the draw; low -> one exit at the draw; high -> run down
- X3g/X3 SMT bank | done | `smt_bank`, `smt_bank_frac`, `smt_bank_min_r` | False, 0.5, 0.5 | our bar prints a new high since the fill, the sister index does not -> bank 50% of what is left once, when >= 0.5R in profit [our interpretation of "refuses to break"]; the 80% "sister breaks against the trade" half is not built
- X3h capture 80-85% | done | `capture_frac`, `Trade.capture`, report block | 0 (0.85 = ICT) | last rung at entry + frac x (rung - entry); applies to a locked draw too when set
- X3b slow days / JOLTS / SB | partial | `sb_split`; study `X3b_slow_frac_*` | False | the Silver Bullet can scale out with `_split` (slow / news-ahead); JOLTS dates before 2026 NOT added: bls.gov gave no archive and no source in the repo, nothing invented
- A6 breakaway / measuring gap | done | `measuring_gap`, `measuring_band`, `measuring_mid_frac`, `trail_breakaway` | False, (0.3,0.7), 0.15, False | measuring gap = FVG after the extreme with its near edge in the band and CE within 0.15 of the leg's 50%, still open; tag only; trail_breakaway = stop under the first FVG after the extreme once a close is above it, while price retraced at most to its half; the entry-gap breakaway tag already existed (`breakaway`)
- Ep03.5 measuring target | done | `measuring_target`, `measuring_anchor`, `measuring_pool_pts`, `proj_measuring` | False, "far", 1.0 | anchors far (gap notes: 061/062) / near (A6's first reading) / ce / dup; kept only when a pool lies within measuring_pool_pts (062); 0 = always
- A22 matrix targets | done | `matrix_targets`, `breaker_first`, `skip_exhausted` | (), False, False | breaker (near edge + MT), mitigation, rejection blocks as targets; breaker_first ends the run before the nearest untouched opposing breaker (skip if < min_rr) [our interpretation]; skip_exhausted retires HTF arrays price already traded into (needs 5 sessions of history; gaps never retired, 039)
- L4 pool quality | partial | `pool_rank`, `pool_rank_reach`, `rel_tfs`, `draw_below_eq`, `lrlr_max`, `pool_runner_pts` | False, 3.0, (), False, -1, 0 | pool_rank / draw_below_eq act in the #9 lock (marked-level ranking by name -> timeframe) AND on the non-lock path; lrlr_max, rel_tfs pools and clean_eq_pref act on the non-lock path only (the lock names the nearest marked level); gap-note extras (hrlr_time_k, clear_path, session_pool_first, eq_beyond_imb, resist_def) NOT built
- L9 FVG targets | done | `fvg_over_ob`, `fvg_remainder`, `weekly_gap_ce_only` | False, False, False | OB overlapping an FVG dropped; partly traded FVG keeps traded extreme / CE / far edge; NWOG CE only (gap notes htf_gap_final etc. not built)
- L11 / A17 rejection-block targets | done | `rb_targets` ("ladder"/"replace"), `rej_targets`, `pool_body_edge`, `rb_min_wick_frac` | "off", False, False, 0.5 | body edge of the swing candle as an extra rung or instead of the pool wick; `levels.rejection_blocks` now reads +-pivot_n candles and takes `min_wick_frac` (old zones unchanged for pivot_n=1); gap-note old_high_ladder (speed rung 20%) not built
- L12 SD targets | done | `sd_anchor`, `sd_swings`, `sd_cluster_ticks`, `sd_roles`, `sd_align`, `sd_align_tol_pts`, `sd_no_pool_fallback`, `sd_levels` 0.5-4.5 validated | "leg", 3, 0, False, False, 1.0, False | per-anchor first level beyond the pool; clusters of >= 2 anchors within N ticks; the "time" alignment is NOT coded (no rule gives a clock); the old block runs unchanged for the plain leg anchor
- D23 / Ep06.4 SD anchor + close hits | done | `sd_anchor` leg / broken / downleg / fulcrum / london (=manip) / multi, `sd_close_hit`, `sd_close_window` | "leg", False, () | fulcrum = first swing high after the extreme, measured after a close above; london only after its high is taken; close hit = rung hit by a bar close inside the window, filled at the close; models.md note corrected
- L14d untraded targets only | done | `target_hygiene` ("arrays","htf","wick") | () | non-pool levels traded through before the sweep today are retired (gap/ORG levels exempt); HTF arrays touched since they formed; traded prior-day wick CEs
- M8 ORG repricing | done | `org_reprice` | False | after the 09:30 Judas away from the ORG (sweep extreme below the ORG near edge, printed after the open) T1 = the ORG near edge, nearer rungs dropped
- M14.2 TGIF zone / M14.4 TGIF exits | done | `tgif_zone`, `tgif_zone_levels`, `tgif_cap`, `tgif_stand_down`, `tgif_exits`, `tgif_exit_fracs` | False, (0.20,0.225,0.25,0.30), 0.30, 0.40, False, (0.25,0.25,0.5) | Friday on a tgif day in the day's direction only; weekly range = Monday-Thursday full sessions (eth) + today so far; levels replace the ladder; 40% retraced = no trade; no room inside the zone = skip (x_tgif_room)
- X1 targets | done | `target_ltf_obs`, `keep_inner_levels`, `inner_min_pts` | False, False, 1.0 | LTF order blocks as targets (shares A12's untouched-OB list); levels under min_rr stay as small early partials
- Ep02.5 30m / runner | done earlier (owner directives) | `htf_targets_30m`, `runner_htf_exit` | False, "" | already built; 30m also in `htf_resist_tfs`
- Ep03.22 final HTF | done | `final_htf` | False | last rung = nearest 4h/D/W array near edge (FVG/OB/gap/VI); not under a locked draw
- A10 voids / leg start | done | `void_targets`, `leg_start_target` | False, False | true price gaps (near edge, CE); the start of the one-sided displacement leg [CC] (one counter candle allowed)
- A23 wick CE | done | `wick_daily_src`, `wick_week`, `wick_tfs`, `wick_read` (`wick_days`, `wick_weekly`, `wick_session` existed) | "", False, (), "off" | wick_tfs adds the nearest two 1h/4h long-wick CEs as targets; wick_read "exit": the bar after a wick rung closing back through the CE ends the rest; default doc fixed in the rulebook earlier
- L13 projections | done | `proj_breaker`, `proj_measuring`, `proj_org_k`, `proj_ext` | False, False, (), () | breaker A-B leg = ext -> MSS reference, B + (B - A), needs a breaker; ORG size multiples beyond the far edge; 1.27/1.62 extensions only inside an opposing array
- L16 ADR5 | done | `adr_target`, `adr_frac`, `adr_early`, `adr_early_frac` | False, 0.65, False, 0.8 | day low + 65% of ADR5 as a target; ADR reached before 10:00 -> 80% off, runner stays
- L17 rounding | done earlier (review pass) | `round_step_pts` | 0 | already built and tested
- Ep01.21 intermediate swing | done | `inter_swing_target` | False | nearest untaken short-term high before the draw is a rung (kind "swing")
- Ep03.19 one unit at a time | done | `mgmt="unit"` | "ladder" | equal pieces per rung
- Ep04.11 clean REH | done | `clean_eq_pref` | False | smoothest equal-high pool (spread + pokes) is the draw (non-lock path)
- Ep04.12 target order / bulk first | done | `target_order`, `ladder_fracs_bulk`, `ladder_news_day` (`daily_vi_targets` existed) | (), (0.8,0.1,0.1), False | chain eq -> daily -> vi, the bulk on the first target; news day takes the 80/20 split
- Ep07.1 old close draw | done | `close_draw` | False | closes of the last 5 sessions and last week's close that price has not traded back to, as pools
- Ep08.9 measured move | done | `mm_targets`, `mm_anchor` | False, "leg" | range projected once more from the leg high or the broken MSS swing
- M7.1 | done earlier (owner directives) | `pm_off_lunch`, `pm_judas_1330`, `seen_from_created` | | already built

Gap-note BUILD SPEC items NOT built (outside the 36): old_high_ladder / speed_frac, hrlr_time_k / clear_path / hrlr_news_only / resist_def, session_pool_first,
eq_beyond_imb, htf_gap_final, sd_arm / sd_ref_roll / sd_multi_tiers / sd_cap_htf / sd_htf_extreme / sd_premium_consol / sd_last_hour_k / sd_deep_conv / proj_exit_ticks,
mm_anchor reanchor/impulse, proj_breaker_k, ladder presets (004 / 037 / 041 / 096), partial_mode, energy_split, fixed_partials, confluence_weight, void_ladder,
eq60_rung, subrange_first, no_collapse_htf, runner_htf, weekly_hl_rung, overnight_5m_fvgs, htf_ob_open, ob_target_order, adr_conv_target, adr_ext, nwog_ladder.

Test results: `tests/test_targets_partials.py` 44 passed (unit, run_day scenarios, look-ahead on entries and exits incl. ES 2024-01-08..02-09);
`tests/test_mentorship.py -k look_ahead` 12 passed; all other test files 248 passed (one fix: `capture_ratio` tolerates a bare pos dict).
Probe (ES 5m 2024-01..02, default lock): speed bump default 10 trades, cap 2, htf_resist_cap=False 11.


## Package targets_partials - review fixes (2026-10-18)

- Owner #7 speed bump (major): the bump is no longer a main ladder rung. It is a small protected EXTRA rung (`htf_bump_frac` = 0.25 each, all extras under `partial_extra_cap`), so the draw side keeps most of the position; `htf_bump_max` default 2 -> 1. A bump nearer than min_rr x risk (but >= `inner_min_pts`) is still taken as the protected extra (`htf_bump_below_min`, default True; False = the old drop). Silver Bullet and Ma Deuce use `targets.bump_fracs` (bump rung = htf_bump_frac, the other rungs share the rest like the old ladder); SB gets one extra ladder slot per bump. `resistance_mode="low_full"` yields to any extra (bump, wick CE, -0.5 SD) instead of silently dropping it; `tgif_exits` fixed fractions still drop extras (documented, the TGIF ladder is fixed by rule).
- Ep06.4 sd_close_hit (major): engine SD rungs are now tagged `sd` (`sd_half` / `sd_mm` / `sd_ext` / `sd_cluster` under `sd_roles`), so the close rule acts (ES 2024-06-03..25 with sd_first_beyond off: one trade changes). `sd` is treated like `array` everywhere else.
- fill_plan fractions (major): the old engine rule is back - with K <= len(ladder_fracs) the first K-1 rungs take ladder_fracs[k], the last takes the remainder (a 2-rung 50/25/25 ladder is 50/50, not 66.7/33.3). The normalised variant is gone, nothing relies on it.
- A23 wick_read now arms on `wick_ce` as well as `wick` rungs. Ep04.12 target_order relabels only the daily-VI rungs `vi` (N6 news CE stays `array`); the locked draw stays the last pick. X3h capture: None when the best run is under 1R, clipped to [0, 1]. proj_breaker mutes the FUNNEL counters around its `_breaker` call. `extreme_since` reads 120 sessions (was 30). The `sd_anchor="manip"` mapping is marked [our interpretation] in Params.
- Close-based exits (smt_bank, adr_early, wick_revisit, sd_close_hit): documented as market-on-close exits at the deciding close, like htf_heavy / ce_close / lvx exits; no data past that close is used.
- Built (was not built): X3g 80% bank when the sister index breaks against the trade (`smt_bank_against_frac`, study `X3g_smt_bank_against80`, exit tag `smt_bank2`).
- Study: `Ep02.10_bump_max2`, `Ep02.10_bump_frac50`, `Ep02.10_bump_drop_inner`, `X3g_smt_bank_against80`.
- Tests (tests/test_targets_partials.py, new section "review fixes"): old fractions, bump share and majority, SD kind + close rule (unit and ES run_day), target_order draw, low_full yields, capture clipping, X3g 80% (unit + look-ahead), SB / Ma Deuce ES look-ahead (default bump path).
- Still NOT built (kept on the list): X3b JOLTS dates before 2026 (no source, none invented); L12 sd_align "time" (clock) alignment; L4 lrlr_max / rel_tfs / clean_eq_pref under the #9 lock (the lock names the draw; documented) and the gap-note extras hrlr_time_k, clear_path, hrlr_news_only, resist_def, session_pool_first, eq_beyond_imb; Ep03.22 final_htf under a locked draw (documented); the gap-note BUILD SPEC items outside the 36 (old_high_ladder / speed_frac, htf_gap_final, sd_arm / sd_ref_roll / sd_multi_tiers / sd_cap_htf and the other sd_* extras, mm_anchor reanchor/impulse, proj_breaker_k, ladder presets 004/037/041/096, partial_mode, energy_split, fixed_partials, void_ladder, eq60_rung, weekly_hl_rung, nwog_ladder, adr_conv_target / adr_ext and others); `mgmt="unit"` stays equal fractions over at most the rung cap (not a literal one-contract-at-a-time exit) and is not applied in SB / Ma Deuce.
- Left as documented limits (minor findings): `mitigation` matrix target is not checked for being traded through unless `mit_body_respect`; `targets.breakaway_gap` stays separate from the entry-gap `breakaway` tag (different definitions: a post-extreme gap that stays open vs the entry's gap); `plan_active` sends every bump trade through the planner by design.


## Package management_exits (2026-10-18)

Sources: `owner_directives.md` (#2 five handles = minimum, #8 close before noon), `rule_coverage.md` section 3 (46 items), the rulebook X4-X16 lines,
`experienced_rules.md` row 18 (re-entry lock / target), the Ep 03 / 04 / 07 caption notes.
Code: new `mentorship/manage.py` (breakeven, trail variants, the per-position data fixed at the fill, all mid-trade exits, the time stop, the session / day
stops, the re-entry gate, the SMT bias), hooks in `strategy.run_day` (position loop, fill, scan guards, `_after_close`, `_risk_mult`, `_finish_order`
for the day-trade stop), `sb_model.run_sb` (be_on, time stop, am_bulk, day stops, PM consolidation) and `pre_open.run_ma_deuce` (time stop, am_bulk, day
stops), `setups.add_ok` (add_in_pd), `study.DECISIONS` (~80 `<rule id>_...` variants), `mentorship_rules.md` (the stale "Bot:" lines of X4-X14 rewritten).
Tests: `tests/test_management_exits.py` (unit tests of every exit / stop on hand-made bars, `_after_close` unit tests, run_day scenarios, the synthetic
window with a real re-entry, no-look-ahead runs on entries AND exits for every new switch on the synthetic window and a short ES window).
Parity: with `late_cutoff=0` the trades of the commit before are identical (ES 5m 2023-10..11 and 2024-03..04, default / free / SB+Ma Deuce configs,
`reentry_half` and adds on). The one DEFAULT behaviour change is T11 `late_cutoff=945` (no adds / fades from 15:45).
How the exits work: `manage.exits` runs once per closed bar after the legacy exit tests; market-on-close exits fill at that bar's close (like ce_close /
htf_heavy), the objective and the re-entry target are limits that fill at their price when the high reaches them. Position data fixed at the fill
(`manage.init_pos`): the pd3 array list, the leg MT / offside level / IR EQ, the pool levels of the ladder, the fixed leg for the add cuts, the day-trade flag.
Session / day stops are ONE function (`manage.stops_from`) over the closed trades, read by the main loop (`apply_stops` -> done flags), the Silver Bullet and
Ma Deuce (`extras_blocked`, as of the order bar, so no later trade is seen). The stops are TWO-WAY since the review fixes (below): `run_day` runs a fixed
point so the main loop also sees the Silver Bullet / Ma Deuce trades as of their exit time, and Ma Deuce sees the SB's.

- M2.6 premium pyramid / 25% cutoff / larger pool | done | `add_in_pd`, `add_pd_level`, `add_leg_at_fill`, `pool_size_rank` (+ the existing `add_cutoff`, `add_cutoff_read`, `add_cut_ref`) | False, 0.5, True, False | add price on the entry side of the leg's EQ; the leg high is fixed at the fill (highest high from the sweep extreme through the fill bar) for add_cutoff / add_cut / add_in_pd / add_leg_cut; pool_size_rank = alias of pool_rank (L4). `add_cutoff` itself stays 0 by default: the two sources disagree on the reading of the "25% line" (study: `M2.6_add_cutoff25_fixed_leg`, `_leg_at_arming`, `E12e_add_cutoff25_progress`)
- Ep04.10 / E12c add at the FVG low end | done earlier (entries_stops_sizing) | `add_fvg_low`, `add_fvg_low_end`, `add_low_end` | False | verified in this package: one add at the last add FVG's bottom + 1 tick after a body close into it; study `Ep04.10_add_fvg_low`
- X3g SMT bank 50% / 80% | done earlier (targets_partials) | `smt_bank`, `smt_bank_against_frac` | False, 0 | `smt_exit_against=True` (B18.3) = the 80% at 100%
- X4 breakeven pad | done | `be_pad_pts`, `be_cost_pad` | 0.0, False | BE = average entry + pad (+ 2 x cost_per_share); every BE move goes through `manage.be_move` (never on a day trade); the Silver Bullet now follows `be_on` (t1 / expansion, others read as expansion; default expansion = a later close beyond the first target) and Ma Deuce uses the pad. REVIEW FIX: the SB / Ma Deuce default is back to the first build (BE the moment the first target / rung is taken, `extras_be_on="t1"`); `extras_be_on="follow"` makes them follow `be_on` (t1 / expansion / after_mss / stall / pool / off). Study `X4_be_pad_cost`, `X4_be_t1`, `X4_sb_follows_be_t1`, `X4_extras_follow_be_*`
- X5 trailing umbrella | done | `ladder_trail`, `trail_after`, `trail_first_fvg`, `trail_pad_pts`, `trade_type` | "fvg", 1, False, 0.0, "session" | see X5a / X5c / Ep03.10 / Ep03.20; `trail` (every new FVG) stays off
- X5a breakaway / measuring trail, trail pad | done | `ladder_trail="breakaway"` / `"measuring"`, `trail_pad_pts` (+ the existing `trail_breakaway`) | "fvg", 0.0 | after `trail_after` rounds of partials the stop goes under the breakaway gap (targets.breakaway_gap) / the measuring gap (targets.measuring_gap) once a close is above it; trail_pad_pts 0 = stop pad + mohawk (0.25 = one tick = the default pad). Study `X5a_*`
- X5c day trade keeps its stop | done | `trade_type`, `day_stop` | "session", "open" | trade_type "day": the stop is the 08:30 candle open / its lower-wick CE minus the pad (when below the entry and the min risk holds; futures only), tagged `day_trade`; no BE, no ladder / FVG / Ep07 trail. Study `X5c_*`
- X6 FVG abort | done | `fvg_abort_mode`, `fvg_abort_tf`, `fvg_abort_body` (`fvg_abort`) | "rule", 5, False | a 5m candle CLOSE beyond the entry FVG's far edge arms the abort at that candle's low (the whole body with fvg_abort_body); only the NEXT 5m candle trading below it confirms (exit at the low, the open on a gap), otherwise the arm is cleared; 1m bars are grouped into 5m candles. "legacy" = the first build
- X7 / X7a three arrays | done | `pd3_exit`, `pd3_n`, `pd3_list`, `pd3_dynamic`, `pd3_legacy` | False, 3, (fvg, vi, ob, breaker), False, False | the nearest `pd3_n` arrays under the fill price and over the stop, fixed at the fill (FVG bottom, VI bottom, OB MT, breaker MT, the entry array); a close below each marks it broken (sticky); the second break tags `pd3_warn`, the third exits (only with a full list); `pd3_dynamic` re-reads the list every bar (arrays formed after the fill join). Study `X7a_*`
- X7b half off on VI + FVG + OB MT | done | `pd3_half`, `pd3_half_frac` | False, 0.5 | a close below the lowest of the nearest VI bottom, FVG bottom and OB MT (all three must exist at the fill) takes half off once
- X7c three fails stop the session | done | `session_stop_after_fails`, `session_fail_mode` | 0, "trades" | consecutive failed trades of the AM family / PM (SB, pre-open, Ma Deuce share the family) end that family; "arrays" counts only losers that ended on a structural failure; the flags are re-enforced after `reentry_half` re-opens one (the audit's third-entry leak is closed)
- X8 other invalidations umbrella | done | see X8b-X8g, `ce_hold` (X8a), `ep07_body_exit` (X8f) | |
- X8b leg-candle MT | done | `leg_mt_exit` | False | a close below the MT (`mt_mode`) of the first up-close candle at/after the sweep extreme; any time (also after the first partial)
- X8c IR EQ | done | `ir_eq_exit`, `ir_eq_wick` | False, True | trades tagged `imm_rebal` with the entry above the leg's EQ: out at the EQ on a wick (default) or a body close
- X8d propulsion MT | done | `prop_exit` (alias of `prop_mt_exit`) | False | the existing A16 lvx exit
- X8e offside test | done | `offside_exit`, `offside_level` | False, "open" | [our interpretation] the nearest up-close candle above the entry (within 12 bars before the sweep through the fill): a close above its open (or its upper-wick CE) passes the test; the high reaching it with a close below arms it, then a close below the average entry exits
- X8g meander | done | `meander_bars` | 0 | N consecutive closes inside the entry FVG (bottom..top) without a close above its top (a rejection resets), before the first partial; `pos["fvg_top"]` stored at the fill
- X9 time stops umbrella (SB / Ma Deuce) | done | `time_stop_extras` | True | the Silver Bullet and Ma Deuce follow `time_stop_min` / `time_stop_bars` / `time_stop_ref` (pts, leg_high, array_far - REVIEW FIX: the leg high / zone top are now passed) / `time_stop_frac`; the invalidation exits (far_edge, meander, abort, pd3, leg MT, IR EQ, offside, first-FVG fail) run there too with `invalidations_extras` (default True; each is still its own switch)
- X9a deliver in 2-3 candles | done | `time_stop_ref`, `time_stop_bars` | "pts", 0 | pts = `time_stop_pts` of progress, leg_high = reach the leg high, array_far = the entry zone's top; bars: the fill candle is the first. One rule for the three engines (`manage.time_stop_frac`)
- X9c far edge in 2 minutes | done | `far_edge_min`, `far_edge_frac` | 0, 0.5 | after the entry FVG's bottom is touched, a close at its CE within `far_edge_min` minutes or `far_edge_frac` is off (1 = all); meaningful on 1m bars (a 5m bar is judged at its own close)
- X9d lethargic -> cut half | done | `time_stop_frac` | 1.0 | 0.5: the time stop cuts half once (`time_cut`), a remainder at minimum size is closed (`manage.cut_qty`)
- X10 AM exits | done earlier (owner #8) | `am_exit`, `am_exit_mode`, `am_exit_extras` | 720, "close", True |
- X10b bulk off | done | `am_bulk_t`, `am_bulk_frac` | 0, 0.8 | AM-family units filled before `am_bulk_t` lose `am_bulk_frac` at the close of the bar ending `am_bulk_t` (main engine, SB-AM, Ma Deuce)
- X10c hold AM SMT trades | done | `smt_hold_until`, `smt_hold_exit` | 0, False | AM trades with the SMT tag skip the soft exits (time stop, meander, far edge, abort, bulk) until `smt_hold_until`; what is left is closed then with `smt_hold_exit`
- X11 PM exits umbrella | done | `pm_done_by` (X11a), `pm_consol_exit` (X11c), flatten (X11b / X11d), `late_cutoff` (T11) | |
- X11c consolidation PM exit | done | `pm_consol_exit` | 0 | PM trades are out at that time (840) on a day `setups.cc_profile` (13:30 classifier) calls a consolidation profile, and no PM entry starts after it (also the Silver Bullet PM window)
- X12 objective hit | done | `obj_stop`, `obj_source` | False, "draw" | the locked draw (else the last ladder level) / the last array rung: everything off at the objective, then every done flag for the day (SB / Ma Deuce read it through `stops_from`); a trade that took every rung also ends the day (`Trade.final_hit`, also set by the Silver Bullet / Ma Deuce when they take their draw; their `objective` limit exit is not built - they exit at the draw anyway)
- X13 after a loss umbrella | done | see X13a / X13b / D18 | |
- X13a AM loss, no reversal | done | `reverse_in_session`, `lost_side_session`, `loss_ends_morning` | False, False, False | reverse_in_session: the session may reverse once after a loss, opposite side only, at full risk; lost_side_session: the `reverse_after_loss=False` lock lasts the session (reset at the PM); loss_ends_morning: an AM-family loss ends the morning (wins over reverse_in_session / reentry_half; SB, pre-open and Ma Deuce included)
- X13b gated re-entry | done | `reentry_gate`, `reentry_fomc_ok` (`reentry_half`) | False, False | the re-entry re-opens the trade's OWN done key; with the gate: not on FOMC, the draw (locked, else the last level) not traded since the fill, the same side, a restored sweep (its extreme after the stop-out) and an FVG made after the stop (`fvg_i` of the order, else its arming bar)
- X14 after a win umbrella | done | see X14a / X14b / X14d | |
- X14a 5 handles then stop | done earlier (owner #2) | `day_target_pts` | 0 (test switch) | 5 handles = minimum room, not the goal
- X14b chop: one win and stop | done | `chop_one_win` | False | the winner of a trade filled on a chop (`Chop.on`) or slow day (`_slow_day`, shared with `_split`) ends the day
- X14d no re-entry after a winner | done | `no_trade_after_win` | False | any winner ends the day for every setup (SB / Ma Deuce / pre-open included)
- D14 breakeven / trailing modes | done | `be_on` "after_mss" / "stall" / "off", `be_stall_bars`, `be_stall_min_r`, `ladder_trail="off"` | "expansion", 2, 1.0 | after_mss: a close above the leg high after the fill; stall: `be_stall_bars` bars without a new high once >= `be_stall_min_r` in profit; stale docs in Params / mentorship_rules.md rewritten; study variants `D14_*`
- D18 re-entry after a stop-out | done | `reentry_risk`, `reentry_lock_r`, `reentry_target_r`, `lost_side_session` | "budget", 0, 0, False | reentry_risk "loss": half of the LOSING trade's own risk (`entry_risk_pct`); lock: at `reentry_lock_r` R the stop moves to the level that keeps the prior loss repaid (held under the best price); target: the re-entry is off at `reentry_target_r` R (limit); `Trade.reentry`
- Ep03.10 first FVG trail | done | `trail_first_fvg`, `first_fvg_fail`, `first_fvg_fail_after_t1` | False, False, False | stop under the first FVG after the shift once a close is above its top and no body closed below it; fail: a body close below its bottom exits
- Ep03.15 BE after buy-side | done | `be_on="pool"` | | pool levels carried from the fill (`pos["pool_levels"]`); BE when the high reaches the first pool; no pool in the ladder -> the expansion rule
- Ep03.20 trail after two rounds | done | `trail_after`, `ladder_trail="measuring"` | 1 | the FVG trail and the measuring / breakaway trails start after N rounds of partials (study `Ep03.20_trail_after2`, `Ep03.20_trail_measuring`)
- Ep04.13 done by 15:00 | done | `done_if_target`, `done_target_before` | False, 900 | the final ladder level hit before 15:00 ends the day (`Trade.stop_day = "done_target"`); `pm_done_by` unchanged
- Ep07.5 down-close adds / up-close exits | done | `add_mode`, `tp_upclose` | "fvg", False | add_mode "downclose": a closed down-close candle after the fill that holds above the stop and the entry array's bottom arms an add at its close [our interpretation]; tp_upclose: the add units are sold into the first up-close candle closing above the add
- Ep07.7 below the swing-low bodies | done | `ep07_body_fixes` | True | with `ep07_body_exit`: the test also runs on the FILL bar and a pending order is cancelled by a bar that traded below the bodies
- T11 late cutoff | done | `late_cutoff` | 945 (DEFAULT) | from 15:45 no adds (pending adds cancelled) and no fades (an entry against the locked draw's side, else against the 09:30 open); 0 = off (study `T11_late_cutoff_off`)
- A13.3 breaker leg / MT exit / MT entry | done earlier (owner #6) | `breaker_zone="leg"`, `breaker_mt_respect`, `breaker_mt_entry_floor`, `breaker_mt_exit_after_t1` | |
- B18.3 SMT uses | done | `smt_bias`, `smt_exit_against` (+ `smt_bank*` X3g, `smt_pick` existing) | "off", False | smt_bias: our overnight range took the previous RTH low while the sister held its own (+1; mirror at the high -1; both: the later one) read from bars before 09:30; "tag" = `smt_bias_agree` / `smt_bias_against`, "filter" = only with the bias [our interpretation of "Uses: bias"]; smt_exit_against = the X3g 80% bank at 100% (the name `smt_exit` already means the M16.1 time exit)

Notes
- Limits (before the review fixes, now removed; see "management_exits review fixes" below): Ma Deuce did not see an earlier Silver Bullet trade; the invalidations were main-engine only; the SB read after_mss / stall / pool as expansion.
- `session_stop_after_fails` counts the failed trades the three engines closed before the order bar; `X7c` "arrays" is a judgment call [our interpretation] (structural exit reasons: stop, abort, pd3, ce_close, breaker_mt, body_low, first_fvg_fail, leg_mt, ir_eq, offside, meander, far_edge, ...).
- ES fire evidence (2024-01-08..02-09, free config): `M2.6_add_in_pd`, `M2.6_add_cutoff25_*`, `X4_sb_follows_be_t1`, `X9a_time_stop_leg_high`, `X9_time_stop_sb_md`, `X10b_am_bulk_1100`, `X13a_loss_ends_morning`, `X7c_fails2_trades_sb` change trades; synthetic window: `D18_*`, `X13b_*`, `X7c_*`, `X5c_*`, `M2.6_pool_size_rank` change trades. The rest are verified by the unit / scenario tests (the real windows are too sparse: 3-25 trades).
- Test results: `tests/test_management_exits.py` 54 passed (unit, `_after_close`, run_day scenarios, the synthetic window with a real re-entry, look-ahead on entries AND exits for 14 switch sets on the synthetic window and 5 on ES 5m 2024-01-08..02-02 with SB + Ma Deuce); `tests/test_mentorship.py -k look_ahead` 12 passed; test_strategy / test_owner_directives / test_review_fixes / test_targets_partials / test_entries_stops 206 passed; test_setups_models / test_levels_detectors / test_levels_review / test_portability 95 passed. Parity: ES 5m 2023-10..11 and 2024-03..04 (default, free, SB + Ma Deuce + adds + reentry_half configs) give identical trades to the commit before, also with the default `late_cutoff=945`.
- Known limits: `tp_upclose` treats every add after the fill as an add unit (entry-ladder rung fills E2 would be sold too if both are on).


### management_exits review fixes (2026-10-19)

Findings of the review of the package above, fixed in `manage.py`, `strategy.py`, `sb_model.py`, `pre_open.py`, `setups.py`, `entries.py`, `targets.py`,
`study.py`; tests in `tests/test_management_exits.py` (section "review fixes"). Default behaviour: every default is the pre-package behaviour except the
documented `late_cutoff=945` (T11); with all new switches at their defaults the ES 5m trades of the SB + Ma Deuce configs (2023-10..11, 2024-01..02, default / free /
adds / re-entry / loss-halving configs) are identical to the commit before the package (checked against `0ec979a` with `late_cutoff=0`).

Major
- Day / session stops are now TWO-WAY (X14d, X13a, X7c, X12, X14b, Ep04.13). `strategy.run_day` is a thin wrapper over `_run_day_once`: with a stop switch on and the
  Silver Bullet / Ma Deuce on, it runs a fixed point (`stops_passes`, default 3; 1 = the old one-way order). Pass 1 as before; the extras' closed trades are then fed back
  (`state["ext"]`): the main loop applies `stops_from(main + extras)` once per bar with `ts = the bar` (so an extras trade counts from its exit time only), Ma Deuce reads the
  SB's trades through `ctx.ext_other` (it runs first), and passes repeat until the extras' trades stop changing. The result has no look-ahead (every decision reads trades
  closed by its own bar; look-ahead sets `stops2` / `stops3` pass on the synthetic window and on ES). Side effects (locks, log, skips, the E10 risk state) come from the last
  pass only. ES 5m 2023-10..2024-02 (SB + Ma Deuce): `no_trade_after_win` one-way 46 trades, two-way 45 (an SB win now ends the main engine's day).
- X4 default restored: the SB and Ma Deuce breakeven is back to "BE the moment the first target / rung is taken" (`extras_be_on="t1"`, the pre-package behaviour; the package had
  silently changed the SB to `be_on` expansion). `extras_be_on="follow"` follows `be_on` in BOTH engines with every mode: t1, expansion (a later close above the first
  target), after_mss (a close above the leg high), stall, pool (the ladder's pool levels, kinds taken from the draws the rungs came from), off; the pad applies to the "t1"
  default too. This is a switch, not a default change: no owner sign-off needed. Study `X4_extras_follow_be_*`.
- Silver Bullet / Ma Deuce get the position fields `manage.exits` reads (`manage.extras_init`: entry zone, sweep / leg extreme, leg high, level kinds, draw) and call
  `manage.exits(..., extras=True)`: first-FVG fail (Ep03.10), abort (X6), three arrays (X7a, tag `pd3_n<k>`), half off (X7b), leg MT (X8b), IR EQ (X8c), offside (X8e), meander
  (X8g), far edge (X9c) and the PM consolidation exit (X11c). `invalidations_extras` (default True) = on whenever the individual switch is on. [our interpretation: SB sweep = the
  leg extreme before its MSS, zone = the setup FVG; Ma Deuce sweep and zone = the inverted FVG.] The time stop passes the leg high / zone top in both engines (X9a `leg_high` /
  `array_far` no longer fall back to pts). Not applied there (by design): the objective limit exit (the draw is their last rung), the re-entry rules, up-close take profit.
  X10c `smt_hold_*` is inert in the SB / Ma Deuce: their trades carry no SMT tag (limit, as before).

Minor
- M2.6: `add_in_pd` is checked in `_arm_add` (every add path: FVG add, Ep04.10 low end, retest, Ep01 CE add, down-close, arrays) and in `add_ok`; the leg the add rules measure is its
  own `pos["leg_fill"]` (set whenever a leg exists; `add_leg_at_fill` False = the leg as it was), `pos["leg"]` stays the real leg for after_mss / leg MT / IR EQ / time stop. OPEN
  QUESTION for the owner: `add_cutoff=0.25` stays OFF by default (the two sources disagree on "covered" vs "progress"; study `M2.6_add_cutoff25_*`, `E12e_add_cutoff25_progress`); this item
  is NOT built as a default. `pool_size_rank` is only the alias of the existing `pool_rank` (L4) - no separate M2.6 ranking was found in the sources.
- X5c: `manage.raise_stop` is the one place a stop is lifted; trail_breakaway, the Ep01 trail, M5.1 stop_to_next, `am_exit_mode="tighten"` and the D18 lock all use it, so a day
  trade is never trailed. An order that cannot get the day stop (no 08:30 candle yet / its level not below the entry / risk too small) stays a session trade and counts the funnel
  key `x_day_trade_unavailable`.
- B18.3: `smt_exit_against` is the same rule as the X3g 80% bank at 100% and works without `smt_bank`; the name `smt_exit` is taken by M16.1, so it is kept under this name [OWNER:
  confirm]. `smt_bias` is still our reading (overnight divergence at the previous RTH high / low, first partner only) [OWNER: confirm]. Study variants added for both.
- X13a: `reverse_in_session` passes the `reverse_after_loss=False` lock for its one reversal (the pair "beginner lock for the day / experienced reverse once" can be combined), and
  it applies when `reentry_half` is on but its gate refused the re-entry.
- X13b / D18: the order carries `fvg_i` (FVG entries) so "an FVG made after the stop" is tested on the FVG bar; `reentry_stop_only` (new, off) restricts the re-entry to stop /
  stop_gap exits (D18 "after a stop-out"); the lock stop stays under the close.
- X7a: the fixed list is cut to the nearest `pd3_n` at the fill and tagged `pd3_n<k>` / `pd3_short` (fewer arrays than `pd3_n`: it can never fire).
- X11c: `consol_day` uses the explicit index of the first bar at or after 13:30 in the main engine and the SB (also when 13:30 is missing).
- Study variants: `M2.6_add_pd_level_03`, `_add_in_pd_low_end`, `_add_in_pd_ep01_adds`, `D14_be_stall_3bars` / `_min_r_05`, `Ep03.10_first_fvg_fail_after_t1`, `X6_fvg_abort_tf1` / `tf15`,
  `X7a_pd3_n2` / `n4`, `X7b_pd3_half_033` / `067`, `X9_time_stop_extras_off`, `X9a_*_sb_md`, `X6_abort_sb_md`, `X7a_pd3_sb_md`, `X8b_leg_mt_exit_sb_md`, `X8e_offside_sb_md`,
  `X8g_meander4_sb_md`, `X9c_far_edge2_sb_md`, `Ep03.10_first_fvg_fail_sb_md`, `X6_invalidations_extras_off`, `X7c_stops_one_way`, `X14d_no_trade_after_win_two_way`,
  `X13a_reverse_in_session_lost_side` / `_reentry_gate`, `D18_reentry_stop_only`, `Ep04.13_done_target_1030`, `B18.3_smt_bias_tag` / `_filter`, `B18.3_smt_exit_against` / `_bank`.
- Commit trailer: the commits of this work carry the attribution line the session's harness gives (the model that actually wrote them); earlier commits keep theirs (nothing was pushed, history untouched).

Fire evidence (ES 5m 2023-10-02..2024-02-29, free config, SB + Ma Deuce, 50 trades in the base; "rows" = trade rows that differ from the base): extras_be follow + be_on t1 8, after_mss 16,
stall 16 (follow with expansion / off / pool: 0 - no SB / MD trade retraced between T1 and the expansion close in this window; the 5m SB scenarios in the tests show them), abort 30, pd3 16, leg_mt 4,
far_edge 32, first_fvg_fail 18, offside 12, ir_eq 2, time leg_high 70, pm_consol 4 (46 trades), no_trade_after_win one-way 46 trades / two-way 45, add_in_pd 2; meander 4, time array_far,
fails-2 and loss_ends_morning do not change a trade in this window (the scenario tests exercise them: Silver Bullet hand-made days, Ma Deuce on the 2020-03-02 bars).

Tests (`tests/test_management_exits.py`, 54 -> 94 tests incl. 38 look-ahead runs): Silver Bullet scenarios through `run_day` (BE default and every `extras_be_on="follow"` mode, time stop refs, bulk, meander, abort,
three arrays, leg MT, first-FVG fail, far edge, `invalidations_extras=False`), `run_sb` with injected main-engine trades (day / session stops, X11c block and exit), Ma Deuce on the real
2020-03-02 ES bars with a flat tape after the fill (time stop refs, bulk, meander), the two-way stops (fake SB trade: win / loss / late win; wrapper side effects; Ma Deuce reads the SB),
`add_in_pd` on every add path, the leg independence, the day-trade guards (trail_breakaway, Ep01 trail), reverse / re-entry fall-through, `reentry_stop_only`, `fvg_i` on the orders,
`pd3_n` slicing and tags, `smt_exit_against` alone, `consol_day` without a 13:30 bar, and the vacuous run_day far-edge assertion replaced (far edge / meander / pd3 through run_day). Look-ahead:
19 sets (6 new: extras_a / b / c, stops2, stops3, adds2 - covering obj_source htf_ce, first_fvg_fail_after_t1, fvg_abort_tf, pd3_half_frac, the extras modes and the two-way stops) on the synthetic
window AND on ES 5m 2024-01-08..02-02 with SB + Ma Deuce (all 19; before: 5 of 14 on ES).

## Package news_calendar_times (2026-10-19)

Sources: `rule_coverage.md` section 3 "news_calendar_times" (31 items), `owner_directives.md` / `owner_directive_specs.md` (#1 last hour, #4 news dealing range - built earlier),
the rulebook N1-N5 / T4-T9 / M9 / D1 / D8 / D9 and the notes. Code: `mentorship/newscal.py` (new; helpers), `calendar.py` (event sets, NFP-date helpers), `strategy.py` (Params block "package
news_calendar_times", `blocked()`, the run_day windows / gates / pending handling), small hooks in `entries.size_mult`, `manage.stops_from`, `sb_model.run_sb`, `pre_open.run_ma_deuce`,
`backtest.lock_cuts`; `study.DECISIONS` (one or more variants per switch, prefix = rule id). Tests: `tests/test_news_calendar.py` (unit tests of the calendar and every helper, hand-made one-day
scenarios through `run_day`, 14 no-look-ahead sets on synthetic windows + 2 on ES). With all the new switches off and the three new defaults off (see "Defaults that change the engine") the
trades are identical to the commit before.

Format: id | done / partial / skipped | Params switch(es) | default | note.

- N1 NFP Friday | done | `nfp_first_hour`, `nfp_no_adds` (E12f, existed), `nfp_day_from` (D8), Trade.news_tags "nfp" | True, True, 0 | the first hour after 08:30 on a jobs day: no PRE9 / NEWS window, no Ma Deuce (the 09:30 AM window with the owner-#4 30-minute NFP floor stays); `nfp_day_from` = entries from that minute (test)
- N3 FOMC overall | done | `fomc_flat`, `fomc_eve_risk`, `fomc_after_am_block`, `fomc_only_am`, `fomc_no_reentry`, `fomc_whipsaw_skip_london` | 840, 1.0, False, "off", True, False | flat at 14:00 = the exit of everything OPENED before the release (`fomc_flat`; reason `fomc_flat`) and cancel of orders armed before it - a PM trade after 14:45 is untouched; eve = size multiplier through `entries.size_mult` (main engine, SB, Ma Deuce); after-FOMC AM block; no re-entry = a loss on an FOMC day is a DAY stop in `manage.stops_from` (all sessions, SB and Ma Deuce through `extras_blocked`, the two-way fixed point only on FOMC days) and `reentry_half` is skipped; the London skip after a whipsaw (both sides of the 13:00-14:00 range taken in 14:00-15:00 of the FOMC session) covers LON and the London SB
- N3.1 14:00 release, observe to 14:45 | done | `fomc_observe`, `fomc_pm_block_from`, `sb_fomc_pm` | "off", 0, False | "defer" scans from 14:00 and holds the newest order; it is armed (arm bar = the bar before) at `fomc_pm_from` if price did not trade back to its entry and did not run to T1 meanwhile (`newscal.held_valid`) [our interpretation]; "judas" = defer + the M9.2 side rule, first allowed minute 14:30; `fomc_pm_block_from=840` opens 13:30-14:00 (flat by `fomc_flat`); `sb_fomc_pm` runs the SB PM window from max(a, fomc_pm_from) (off: the old build skipped the window - kept so the golden window stays)
- N5 other releases | done | (owner #4: `news_wait`, ... built earlier) + `news_claims`, `news_minutes` | False, False | calendar: `is_jobless_claims` (Thursday 08:30, Wednesday before a holiday Thursday), `FOMC_MINUTES` (decision + 21 days, 14:00), `release_times(claims=, minutes=, pmi=)`; both count as releases for the dealing-range wait only when switched on (low impact); `FED_CHAIR`, `is_auction_day`: see N5.5 / N5.6
- N5.1 / N5.2 | done (owner #4, earlier) | `news_wait`, `news_wait_min`, `nfp_floor_min`, ... | "range" | unchanged; `calendar.PMI` added
- T4 opening range | done | `or_no_entry`, `or_end`, `or_deep`, `or_deep_win`, `or_deep_pd`, `or_bias`, `or_bias_filter`, `or_wide`, `or_wide_adr`, `or_wide_end` | False, 600, False, (577, 586), 0.25, "off", True, False, 0.5, 630 | AM orders may be ARMED in the OR but fill from `or_end`, the pending expiry counts from then (`newscal.fill_ok`, order key `anchor_i`); `or_deep` = fills inside 09:37-09:46 allowed when the entry lies in the lower (upper) `or_deep_pd` of the prior RTH range [our interpretation of "deep in discount"]; `or_bias`: "judas" (the OR extreme made first was the Judas -> the other way) / "close" (the OR close vs its midpoint), read from `or_end`, filter or tag; `or_wide` (CC 09:30-10:30 OR >= `or_wide_adr` x ADR5): only toward the end farther from the OR close, from `or_wide_end`
- T5 NY AM session | done | `pre_0820` | False | PRE8 window 08:20 -> 09:00 / 09:30 (the AM start; 08:30 with am_from_0830), skipped on 08:30 release days; lock and snapshot at 08:20 (`pre_at[500]`, `lock_cuts`); PRE7 then ends at 08:20
- T8 lunch | done | `lunch`, `lunch_win`, `lunch_exit`, `pm_carry_draw`, `draw_done_skip` | False, (710, 810), 810, False, False | LUNCH session = the AM family's model with the AM lock (a delivered AM draw ends it), AM range as a pool known before it starts (`ctx.am_lunch_hl`, no look-ahead), out by `lunch_exit`, exempt from `am_exit`; `pm_carry_draw`: the PM lock keeps the AM's undelivered draw if it is still ahead of price; `draw_done_skip`: no lunch / PM entry once the AM draw is delivered. Validation: `lunch_win[0] >= am[1]`
- M9 news Judas | done | `news_judas` ("block"), `news_judas_ref_min` | "off", 60 | reference pools = high / low of the `news_judas_ref_min` minutes before the release (today's bars) [our interpretation]; the first bar from the release that trades beyond one of them is the first run (a bar beyond both: the opposite of its close); that direction is closed from that bar on; per driver release of the session's news gate
- M9.1 first run = losing side | done | `news_judas="wait"` | "off" | also no entry before a first run has happened (no reference bars - e.g. RTH-only data - means no gate)
- D1 AM from 09:30 vs 10:00; or_no_entry | done | `or_no_entry`, `or_no_entry_news1000`, `or_deep_pd` | False, False, 0.25 | on 10:00-release days the dealing-range gate already holds the AM past 10:00, so `or_no_entry` skips them unless `or_no_entry_news1000`
- D8 news day options | done | `nfp_day_from`, `skip_post_fomc_am`, `nfp_no_adds`, `fomc_no_reentry` | 0, False, True, True | + the verified blocked() bug: the NFP-week blocks are relative to the week's real jobs date (`calendar.nfp_date` / `nfp_shift`; Thursday NFP: Wednesday = the day before, Tuesday PM = two days before; Friday weeks exactly as before; a jobs date that is not Thu / Fri has no week block)
- Ep01.10 AM 08:30-11:00 | done | `am_from_0830` | False | AM window from 08:30 (`Params.am_win`), lock at 08:30 (snapshot `pre_at[510]`, `lock_cuts`), PRE9 / NEWS windows are dropped (no double scan); 08:30 release days: the dealing-range gate holds the AM
- N3.2 never hold into the release | done | `fomc_flat`, `fomc_am` | 840, "open" | `fomc_am`: "recipe" = the AM only when the HTF table's reaction and draw agree and are not neutral [our interpretation of the trending-day recipe; unknown before 09:30 = no]; "skip" = sit out; the SB windows follow through `newscal.sb_gate` / `blocked()`
- N3.3 FOMC-only day AM consolidates | done | `fomc_only_am` | "off" | an FOMC-only day = the decision is the day's only release; "tag" (`fomc_only_am` in lv_tags), "scalp" (single exit min(+5, T1), no adds, via the #10 scalp machinery), "skip"; day tag `fomc_only`
- N3.4 day before light / day after AM out | done | `pre_fomc_risk`, `skip_post_fomc_am`, `skip_pre_fomc` | 1.0, False, False | `pre_fomc_risk` (D8 spelling) and `fomc_eve_risk` (N3 spelling) multiply; the `_split` holiday fix was built in the owner-directives package (calendar.next_trading_day)
- N3.5 no re-entry on FOMC | done | `fomc_no_reentry` | True | see N3
- N4 CPI | done | `pre_cpi`, `pre_cpi_risk`, `skip_pre_cpi`, `pre_flat_0830` (existed), `flat_0830_extras` | "off", 0.5, False, True, True | the 08:29 flat now covers PRE7 / PRE8 / LON main-engine trades (always, `pre_flat_0830`), and - with `flat_0830_extras` (new default on, pins in the old-build presets) - Ma Deuce (exit at the close of the bar ending 08:30; 2024-03-14 PPI: the golden window's Ma Deuce short is now out at 08:25 for +695 instead of stopped at 08:30 for -1132) and the London SB on 08:30 release days
- N5.4 two drivers | done | `skip_two_drivers`, `two_driver_gate` | False, True | two drivers = 08:30 data and a 09:45 / 10:00 release on one day (PMI + ISM alone are one); the gate: no pre-open window ends before the day's last morning release (`x_two_driver`); the AM waits for its release range anyway (owner #4); day tag `two_driver`
- N5.5 Fed chair at 10:00 | partial | `fed_chair_skip_am` | True | `calendar.FED_CHAIR` = the semi-annual testimony days 2019-2025 typed from memory - UNVERIFIED, 2026 unknown; `FED_CHAIR_EXTRA` for the owner's own dates; default on per the spec - OWNER TO VERIFY the dates (study / golden presets pin it off)
- N5.6 Treasury auction AM | partial | `skip_auction_am` | False | `calendar.is_auction_day` = the 3-/10-/30-year auctions on the Tue / Wed / Thu of the week with the second Wednesday (approximate; `AUCTION_EXTRA` / `AUCTION_SKIP` correct it); coupon auctions at month end (2-/5-/7-year) are not covered
- T7 macros | done | `macro_gate`, `macro_only`, `macro_by`, `macro_done_skip`, `moc_htf_done`, `run_done_adr` | False, "off", "arm", False, False, 1.0 | 13:30 and 13:39 ("2:00 macro") windows added to `newscal.MACROS_T7`; every macro the arm minute lies in is in Trade.macro_wins ("HHMM|HHMM"; Trade.macro_win keeps the first, as before); gate = the order armed (or, `macro_by="start"`, its sweep started) inside a macro; "the run is done" = a session draw lock delivered or the day's range >= `run_done_adr` x ADR5 [our interpretation]; MOC = the 15:15-15:45 sweet-spot window. Main engine only (the SB windows are fixed windows)
- T9 PM session | partial | `pm_skip_after`, `pm_skip_lh`, `pm_bad_am_start`, `pm_continue_am`, `pm_ob_entry` | 0, False, 0, "off", "off" | skip = no PM trade by the minute -> no new PM arm (the owner's last hour stays unless `pm_skip_lh`); bad AM = a closed morning trade with a net loss -> the PM starts at 13:45; continue = the AM direction (09:30 open -> the 11:55 close) as tag / filter; `pm_ob_entry` is a tag / require TEST on the ordinary sweep -> MSS -> FVG entry (entry inside the last unbroken AM / lunch down-close order block), NOT a separate order-block entry path (partial)
- M9.2 FOMC real move | done | `fomc_judas`, `fomc_judas_end`, `fomc_stage2_cont` | False, 870, False | the range 14:00 -> `fomc_judas_end` (14:30: the coverage correction, no source for 14:25); the first run through the 13:00-14:00 range is the Judas; the PM opens at the end and only the other side trades, to `fomc_pm_from` (all PM with `fomc_stage2_cont`)
- D9 CPI tests | done | `skip_pre_cpi`, `pre_cpi` | False, "off" | `calendar.eve_of` uses next_trading_day (holidays skipped)
- Ep01.11 PM 15:15-15:45 | done (owner #1, earlier) | `last_hour`, `last_hour_sweet`, `last_hour_strict` | | unchanged
- Ep02.1 09:45 release wait | done | `wait_0945`, `calendar.PMI` | True | the 09:45 PMI is a release for the dealing-range wait (False = only 08:30 / 10:00 / 14:00)
- Ep06.1 kill zones | done | `london_kz`, `london_kz_start`, `ny_kz_futures` | False, 120, False | LON window london_kz_start -> 05:00 (futures with bars at that time only), the London range is not a pool while it forms; `ny_kz_futures` = the futures kill zone 08:20-11:00: the PRE8 window on release days too (the news gate holds them), futures only
- Ep07.8 macro 09:50 | done | `macro_only` ("0950" / "all"), `macro_by` | "off", "arm" | the start-or-arm test
- shared: `release_times(d, claims, minutes, pmi)`, `nfp_date`, `nfp_shift`, `fomc_info`, `eve_of`, `two_drivers`, jobless claims, FOMC minutes | done | | | calendar.py (cached helpers)
- shared: Trade.news_tags | done | | | "|"-joined day tags on every trade (main engine, SB, Ma Deuce): nfp, nfp_week, fomc, fomc_only, fomc_eve, fomc_after, cpi, pre_cpi, two_driver, fed_chair, auction, claims, minutes

Defaults that change the engine (all pinned off in `study.CURRENT` and `study.PRE_OWNER`, so the old build / the golden window reproduce): `fomc_no_reentry=True` (N3.5; `reentry_fomc_ok` opts out),
`nfp_first_hour=True` (N1), `fed_chair_skip_am=True` (N5.5), `flat_0830_extras=True` (N4), `fomc_flat=840` (affects a position held into 14:00 on an FOMC day only - with `am_exit` at noon, none), `two_driver_gate=True` and `wait_0945=True` (act only on top of
`pre_0900` / `post_news` / the PMI day). Everything else is off.

Judgment calls (all marked [our interpretation] in the code): the Judas reference pools and the both-sides bar, the held FOMC order's validity, "deep in discount", the OR bias definitions, "the day's run is
done", the AM direction for the PM, the AM-OB test for `pm_ob_entry`, the trending-day recipe, the auction rule, "no double scan" for am_from_0830.

Tests: `tests/test_news_calendar.py` (56 tests, ~1.5 min): calendar (NFP-date helpers, `blocked()` on Friday and Thursday NFP weeks, jobless claims incl. holiday shifts, FOMC minutes, release_times flags,
FOMC info / eve / two-driver / auction / chair sets), every day rule and risk multiplier, `fomc_no_reentry` through `stops_from` / `extras_blocked` / `apply_stops`, one-day scenarios through `run_day`
(FOMC AM recipe / skip / scalp / tag, flat at the release, eve and pre-CPI sizing, post-FOMC AM, PRE8 / LON / am_from_0830 windows incl. the no-double-scan, lunch session and its range, PM skip,
macro gates, OR no-entry fills, news Judas block / wait on a CPI day, FOMC observe / defer held order, FOMC whipsaw London skip), unit tests of every `newscal` helper (first_run, judas_gate,
or_dir, wide_or_dir, am_dir, side_filter, post_order, fill_ok, held_valid, carry_lock, gate, pm_start, sb_start / sb_gate), Ma Deuce flat before 08:30 on real ES bars (2024-03-14), and 13 no-look-ahead
sets (full vs truncated runs with exits, each set trades and changes the engine in its synthetic window - asserted) + 2 on ES 5m (FOMC week 2023-10-30..11-10, CPI week 2023-10-09..16, Silver Bullet and
Ma Deuce on). Full suite after the change: 485 passed (includes `tests/test_mentorship.py -k look_ahead` and the golden `test_pre_owner_switches_reproduce_the_old_engine`).
Two existing tests were adapted (not weakened): `test_reverse_in_session_falls_through_when_the_reentry_gate_refuses` sets `fomc_no_reentry=False` (it uses 2024-01-31, an FOMC day, as an incidental date);
`test_after_close_reentry_half_ungated_gated_fomc_and_draw` passes unchanged because `reentry_fomc_ok=True` opts out of the day stop.

Regression: with `fomc_no_reentry`, `nfp_first_hour`, `fed_chair_skip_am`, `flat_0830_extras`, `fomc_flat` pinned off (study.CURRENT / PRE_OWNER do this) the trades are identical to the commit before: ES 5m
2023-10..2024-02 with SB, Ma Deuce, pre-open windows and London SB: 36 trades, net -7069.55 both; with the new defaults on, the same 36 trades; the golden window (PRE_OWNER, ES 5m 2024 Q1) 23 trades, net 4693.52.

### news_calendar_times review fixes (2026-10-19)
- N5 calendar: marked PARTIAL. 2019-2025 PCE / GDP / retail / JOLTS dates NOT built (no verified source; fabricating them was refused). Built: Conference Board consumer confidence (last Tuesday 10:00, `news_conf_board`, default off so results do not move; counts in `release_times(conf=)`, `two_drivers`, the `conf_board` tag only with the switch).
- N5.5: `fed_chair_skip_am` default now OFF (the FED_CHAIR list is unverified, ends 2025, lacks speeches); the day rules (chair, auction, two drivers, post-FOMC AM) now apply to the NY AM family (AM / PRE9 / NEWS) only, not London / PRE7 / PRE8 / lunch. fomc_am skip and pre-day skips are unchanged.
- N5.6: `calendar.AUCTIONS` overlay added, `is_auction_day` no longer cached; marked [our interpretation]. Month-end 2/5/7-year, 20-year, TIPS dates are NOT built in.
- N4: PRE8 pending orders are cut at 08:30 on 08:30 release days with `pre_flat_0830` (as PRE7).
- N1: `nfp_first_hour` floors PRE8 and the AM at 09:30 on jobs days (PRE8 dropped, `am_from_0830` AM start floored).
- M9.2: the FOMC Judas gate and held_valid apply on FOMC decision days only (not on minutes days).
- T4: `or_bias_filter=False` writes the tags `or_bias_with` / `or_bias_against` / `or_bias_flat`; `or_deep_win` is read at the bar close (5m: closes 09:40 / 09:45); `london_kz_start` must be one of PRE_AT_MINUTES (60..300 hourly, 420, 500, 510, 540) or Params raises.
- NFP-week `blocked()` rules marked [our interpretation]; tests for the Thursday-NFP Fri-after and Tue-NFP weeks.
- Gates documented as MAIN-ENGINE ONLY (not built for the Silver Bullet / Ma Deuce): news_judas, fomc_judas, side filters (or_bias, or_wide, pm_continue_am), or_no_entry / or_deep, macro gates, fomc_observe, fomc_only_am scalp / tag, and the calendar day rules for Ma Deuce (unless md_blocked). Orders armed outside the scan loop (re-entry, pm_reversal, held orders) skip post_order.
- Still NOT built: T9 `pm_ob_entry` OB entry path (tag / require only; `pm_skip_after` default 0, spec value 870 left off); the 14:00-14:25 FOMC range pool; the Judas gate with news_wait off; or_wide tag-only mode; SB / Ma Deuce hooks for the gates; DOL / Fed verification of claims / minutes dates (derived; 2025-01-09 mourning day, 2020-03-15 emergency meeting unhandled); a reverse_in_session + fomc_no_reentry test; verified chair calendar.
- Look-ahead: new sets fomc_c, gates_c, macro_0950 (fomc_flat_before, fomc_judas_end, fomc_whipsaw_skip_london, pre_cpi_risk, two_driver_gate, or_deep_win, or_bias_filter, lunch_win, news_conf_board, macro_only 0950, fomc_only_am tag); flat_0830_extras is in the ES look-ahead test (default on). New study variants: N5.5_fed_chair_skip, N4_pre_cpi_small_03, T4_or_deep_win_1000, T8_lunch_win_1150, T8_lunch_exit_1200, N1_nfp_first_hour_ny_kz, N5_news_conf_board.

## PAUSE 2026-10-19 ~13:25 ET (laptop restart) - stage 8 day_week_context

Stopped in the stage 8 **Fix** step. Build and Review are done; the Fix step was part-way (it had added
tests/test_day_week_context.py, 27 tests, and was running it when stopped - result unknown); the Test
step did not start. All work is saved in the local WIP commit `5c6ae35` on mentorship (not pushed;
GitHub is at `dc77a3f`, stage 7). Last fully green suite on mentorship: stage 7 (`dc77a3f`).
sb-build is at `cfdbbb1`, complete, full suite 448 passed. Details, what is left and the exact resume
commands: `mentorship/digests/RESUME.md`.

## day_week_context (stage 8, 49 items; rule_coverage.md section 3) - built 2026-10-19, finished after the laptop restart

New files: `mentorship/daycontext.py` (plan / helpers: calendar, holiday and early-close, weekly profiles, day templates, consolidation / inside / outside days, TGIF, ADR), `mentorship/study_week.py` (T14 weekly-extreme study). ~100 Params switches, every one with a `study.py` DECISIONS variant (prefix = rule id). Tests: `tests/test_day_week_context.py` (unit + scenario), `tests/test_day_week_scenarios.py` (behaviour tests of the dynamic gates and side rules), `tests/test_day_week_lookahead.py` (one variant per run, 5m and 1m with Silver Bullet / Ma Deuce).
Format: id | status | switches | default | note

B15 | done | org_tell, org_tell_level, org_tell_wait, org_bias_gap, org_bias_src, org_gap_fill_frac | off | tag / filter; gap tag modes write tags
B16 | done | sunday_scenario, sunday_away_mult, sunday_min_gap_pts, sunday_no_gap_trade | off | futures only (Sunday 18:00 open); Monday and the Tuesday after a Monday holiday; no_gap blocks like neither unless sunday_no_gap_trade
B17.4 | done | sloppy_mode, sloppy_tests (earlier, owner #10: default stand_aside with big_prev + chop), daily_range_regime, drr_tests, drr_days, drr_net_frac, drr_range_mult | stand_aside / off | daily_range_regime off / tag / scalp / skip: range (last drr_days sessions net < drr_net_frac of their range, range < drr_range_mult x mean daily range), inside_bisi, premium_run; reachability tests for all three
N7 | done | umbrella of N7.1-N7.6 | mixed | see below
N7.1 | done | skip_holiday_eve, holiday_eve_bank, early_close_flat | off / off / on | EARLY_CLOSE flattening on by default
N7.2 | done | skip_post_holiday_am, post_holiday_pre_open, post_holiday_pm_sync | on / off / off | post-holiday AM blocked in the NY AM family (AM / PRE9 / NEWS); post_holiday_pre_open adds PRE7 / PRE8 (Ma Deuce); London never. Scope still to confirm with the owner
N7.3 | done | holiday_week_thu_fri | off | holiday_week tag always
N7.4 | done | year_end (earlier), year_first_am_from | december (map squaring) / 0 | owner #3 answer is the default; December mapping still needs owner confirmation
N7.5 | done | roll_week_src, roll_risk, skip_roll_week | calendar / 1.0 / off | independent roll tag; data roll flag used for src data / either
N7.6 | done | august_risk, august_from_day, skip_august | 1.0 / 1 / off |
N8 | done | adr5 helper + adr_basis | rth | umbrella of N8.x
N8.1 | done | consol_skip | on | range < 0.35 ADR5 and 4+ midnight-open crosses; expansion resumes trading
N8.2 | done | trend_recipe, trend_small_frac, trend_contract, trend_news, trend_array_days | off | tag / only / side [our interpretation of "small ranges, react into an array, 08:30 news"]
N8.3 | done | consol_day_rules, consol_predictors, consol_min_predictors, consol_or_frac, consol_am_out, consol_eq_tol, consol_pm_rule, consol_pm_pools | off | tag / apply (small-OR AM, out by 11:00, PM only if stop pool intact)
N8.4 | done | big_day_am_skip, big_day_range_mult, big_day_org_frac | off | AM off, PM kept
N8.5 | done | expansion_due, expansion_frac, expansion_targets, adr_basis | off / rth | tag + targets
N8.6 | done | sd_no_hold, sd_week_skip, sd_week_months, sd_week_news, sd_context_required | off |
N9 | done | umbrella of N9.x | | 
N9.2 | done | eve_draw, pre_draw_pm | off | eve_draw columns; gate in run_day
N9.3 | done | objective_done_skip | off | draw hit before 12:00 -> PM done
N9.4 | done | min_on_range_frac, min_raid_pts, raid_ref, on_range_from | 0 | 
N9.5 | done | macro_no_move, macro_no_move_pm, macro_no_move_wins, macro_no_move_pm_wins, macro_move_pts, macro_ref_min | off |
N9.6 | done | london_adr_skip, london_adr_win | 0.8, (120, 300) | on by default per the spec; old presets pin 0.0. London window = 02:00-05:00, the same as ctx.sess['london'], T3 and raid_ref='london' (was 02:00-08:00; study variant N9.6_london_adr_win_0800 keeps it)
N10 | done | monday_mode, tue_off_monday, mon_wed_extreme, thu_fri_break, friday_first_pool, friday_week_done, strong_thu_no_long (+mirror/mult/frac) | off / trade | thu_reversal tag
N10.2 | done | monday_mode, tue_off_monday | trade / off | also in Silver Bullet and Ma Deuce per-order rules
N10.3 | done | pool_mon_wed, mon_wed_extreme, thu_fri_break | off | mw_break tags
N10.4 | done | friday_slow_split, friday_objective, friday_week_done, no_fri_after_strong_thu | on / off | friday_week_done "trades" needs final_hit (set by all three engines)
M14 | done | tgif_model, tgif_model_skip | off | umbrella forcing the sub-switches except those in the skip list
M14.1 | done | tgif_htf_array, tgif_htf_tfs | off | 4h / D / W array, NWOG / NDOG, Sunday 18:00 range
M14.3 | done | tgif_timing, tgif_week_sweep | off | all three engines
T14 | done | tue_week_extreme + study_week.py | off | study run on ES 5m 2019-2026 (407 weeks): Tuesday-London low in 1.3% of bullish weeks, Tuesday low 19%, bearish-week high on Tuesday 24.6%: the claim does NOT hold, so the switch stays off (contested alternative). Mon-Wed extreme 89.7% holds; by Wednesday's 05:00 London end 64.2% of the week's range (30-50%: 21%), by the 10:00 London close 67.0% (30-50%: 16.5%)
X10d | done | am_range_skip_pm | 0 | AM range >= k x ADR5 -> PM and SB_PM done
X15 | done | max_trades_week, week_left | off | sorted by entry time before truncating; paper.py cap
X15d | done | week_done_on_draw, week_done_levels, week_done_pick | off | also first day of the week (NWOG CE)
B11 | done | b11_inside_week, b11_inside_week_days, nr_tags, nr_expansion | off | inside_week scalp, nr3 / nr7 / inside_bar_body; nr_expansion evaluates NR3 / NR7 without nr_tags (nr_tags: reporting tags + inside_body)
B11b | done | outside_day_rule, outside_day_mirror | off | block longs until the outside day's high trades
B11c | done | b11_inside_expansion, b11_inside_week | off |
B23 | done (report-only) | seasonal_tag, seasonal_map, seasonal_map_b, seasonal_fail_day | off | tag only, never gates
X16 | done | journal_tags | on | tags adr5_prev, adr5_today, prev3_taken, entry_array_tf
X16a | done | (fields adr_prev / adr_fill) | | day_ranges CSV via study_week
X16b | done | (taken_3d tag) | | the last three sessions' highs / lows vs today's bars to the fill (including those an intervening session took); adr5_today is a post-hoc whole-day column, study only
X16c | done | weekly_extremes() | | kill-zone labels
X16d | done | (entry_tf tag) | | 
D19 | done | max_trades_week, be_counts_as_win | off / on | week_left budget across engine / SB / Ma Deuce, paper.py cap
D20 | done | monday_mode, monday_small_range | trade / 0 |
Ep01.8 | done | low_vol_inside, low_vol_holiday_adj | off |
Ep01.9 | done (earlier) | year_end, year_end_map | off | owner #3
Ep02.7 | done | first_day_wait, first_day_skip_am | 0 / off | first_day_wait is a floor on the AM entry minute (values <= the order's own time move nothing)
Ep03.24 | done (earlier) | t1_fixed_pts, t1_fixed_all | off | owner #2

Known gaps: B23 is report-only by design; T14 `tue_week_extreme` is built but unsupported by the study (off). Silver Bullet and Ma Deuce DO read the dynamic gates: `_DW.gate()` (N8.3 PM rule, N9.5 macro_no_move, N9.2-N9.6, X10d, X15d, monday / sunday / tgif gates) is called from `run_sb` (session "AM" / "PM" / "LON") and `run_ma_deuce` (session "PRE8"); Ma Deuce's windows end before the first macro window and before the PM, so macro_no_move / consol_pm_rule cannot fire there by construction. `side_ok` / `order_ok` are wired in both too (tested in `test_silver_bullet_and_ma_deuce_call_the_day_week_gate`).

### day_week_context review fixes (2026-10-19)
- B17.4: `daily_range_regime` built (see the row above) with reachability tests for the range, inside_bisi and premium_run readings and the three modes through plan / run_day.
- Look-ahead: `tests/test_day_week_lookahead.py` replaces the merged chunks. ONE study variant per run, 5m main engine on a window chosen by the switch (August, the March roll week, Christmas / New Year / MLK, July, FOMC / NFP / CPI stretch; a wider window as the last resort for the "only" modes) and the same variants again on 1m with Silver Bullet, Ma Deuce and the 07:00 / 09:00 pre-open models on (a window with at least one extras trade is preferred); at least one trade per run is required.
- Behaviour tests: `tests/test_day_week_scenarios.py` (long and mirrored short): org_tell, org_gap_state, org_bias_gap, sunday_state / gate (Monday and post-holiday Tuesday), eve_draw / pre_draw_pm, overnight_stats / min_on_range_frac / min_raid_pts, london_adr_hit (window, session, default), macro_failed, objective_done, am_range_done, am_ran_pool, consol_day_rules (apply, OR wait / big / missing, 11:00 exit), partners_in_step / post_holiday_pm_sync, big_day_am_skip / big ORG, monday_small_range, seek_destroy / sd_week, strong Thursday both ways, thu_fri_break, pool_mon_wed, tue_week_extreme, tue_off_monday, tgif_week_sweep, tgif_context, expansion_levels, daily_arrays_touched, seasonal (+ htf tag), taken_3d, weekly_extremes / day_ranges, the Silver Bullet / Ma Deuce gate wiring.
- N9.6 London window: one London (02:00-05:00) for london_adr_skip and raid_ref="london" (`london_adr_win` drives both).
- nr_expansion evaluates NR3 / NR7 without nr_tags. B16: the Tuesday after a Monday holiday gets the Sunday check; `sunday_no_gap_trade` decides the no-gap case (default: blocked like neither). N9.2 `pre_draw_pm` covers the NY AM family (AM / PRE9 / NEWS). N7.2 `post_holiday_pre_open` (opt-in) adds PRE7 / PRE8.
- X16b `taken_3d` / `prev3_taken` read the last three sessions' extremes (an intervening session's take no longer hides them); `adr5_today` documented as post-hoc.
- D19 / X15: the week-budget truncation now runs after the position left open at the data end is added.
- N8.3 `consol_day_rules`: a missing opening range is not "small" (`x_dw_consol_or_missing`).
- study_week: the by-Wednesday share is reported for both the 05:00 London kill-zone end and the 10:00 London close (M14.3 / rulebook); T14 result recorded in the T14 row.
- Docs: rule_coverage section 8 (and "Now built" notes in section 2), the rulebook Bot notes (X15, N7.5), the defaults in this log (year_end, sloppy_mode).
- New study variants: B11_nr_expansion_nr3, B17.4_daily_range_tag / _scalp / _skip / _all_tests, B16_sunday_no_gap_trade, N7.2_post_holiday_pre_open, N9.6_london_adr_win_0800.


## Package bias_htf (2026-10-19)

Sources: `owner_directives.md` (#9 lock one draw per session, the standing decisions), `owner_directive_specs.md` section 9, `rule_coverage.md` section 3
"bias_htf" (45 items), the rulebook B1-B23 / L14 / A21 / M0 / D15 / D22 lines, `digests/bias.md`, the Ep 02 / 03 / 06 / 08 notes.
Code: new `mentorship/bias_htf.py` (the `htf.table` columns, the COT / open-interest loaders, the intermarket flags from the free daily files) and new
`mentorship/bias_day.py` (the bar-level rules: bias side per session, side / order / gate / scalp / size hooks, lock helpers, opening prices); hooks in
`htf.table` (new `bx` keyword = `Params.bx`, absent when empty so the old table and its cache keys are unchanged), `strategy.run_day` (bias value, per-session
`want`, plan hook, `ctx.lock_t`), `strategy.mark_levels` / `_lock_step` (ordered / largest pick, extent target, lower-timeframe draw, hygiene, conditional relock),
`daycontext.side_ok / order_ok / gate / scalp_now` (one funnel for the main engine, the Silver Bullet and Ma Deuce), `entries.size_mult`, `backtest` (table_kw,
`combine`, `prepare(ref_df=)`), `levels.opens(src)` / `map_midnight`, `paper.evaluate(ref_df=)`, `study.DECISIONS` (~85 variants after `X16_journal_tags_off`).
Tests: `tests/test_bias_htf.py` (unit + engine scenarios, long AND mirrored short, table without look-ahead at the 09:30 and 13:30 cuts),
`tests/test_bias_htf_lookahead.py` (full vs truncated runs: every new variant alone on ES 5m, five switch groups on ES 1m with the Silver Bullet, Ma Deuce and the
pre-open models).
Defaults: every switch is OFF / the old value except `want_all_engines=True` (inert while `htf_bias` is "off") and the per-session bias read described below.

How the bias reaches the bar loop. `htf_bias` names a table column (`bias_day.bias_col`): react, draw, pd, combo, flip as before, plus ordered (draw_ord), iof,
combo2, ob_mt, mwd, nwog (nwog_bias), candle (bc_D / bc_W), draw_pd, wk (wk_bias), pd20. The row is read PER BAR (`bias_day.want_at`): from 09:30 the ordinary
table, before 09:30 the table cut at the latest lock time that has passed (a pre-open window used to read the 09:30 row = overnight bars that had not printed;
without a cut table - `draw_lock="off"` - a pre-09:30 session now has no bias and `bias_neutral="skip"` skips it). The main loop, the Silver Bullet and Ma Deuce all
call `daycontext.side_ok`, which calls `bias_day.side_ok` (B3 `want_all_engines`); the day-level rules come back through `daycontext.gate` / `scalp_now` the same way.
Look-ahead: every table column reads sessions before the row's day plus the overnight bars closed by the cut; the intermarket flags read sessions before the day.

Checklist (id | status | switches | default | note):

B2 | done | `draw_lock_pick="ordered"`, `htf_bias="ordered"`, `draw_ext_target` | nearest / off / False | `htf.table` columns draw_ord, draw_ord_lvl, draw_ord_kind, draw_ord_name, draw_ext_lvl, draw_ext_name (bx "ord"): the nearest inefficiency (FVG / VI / opening gap) either side first, else liquidity by premium / discount (discount: the buy-side, premium: the sell-side, 0: the nearer), a tie is neutral; the lock does the same over its marked levels (`bias_day.ordered_side`, arrays before pools); `draw_ext_target` makes the nearest array beyond a pool the locked target (the pool a rung, `lock["ext_from"]`)
B3 | done | `draw_lock_pick="largest"`, `want_all_engines`, `judas_required`, `judas_min_pts` | nearest, True, off, 2.0 | table cut per session start was built earlier (owner #9); now also the bias READ is causal per bar (`row_for`); Silver Bullet and Ma Deuce honour `htf_bias`; "largest" = the side whose ordered candidate is the farther [our interpretation of "the day's largest move"]; `judas_required` tag / filter: the bias side waits until price has been delivered against it by `judas_min_pts` from the session's first open
B6 | done | `htf_bias="iof"` / `"combo2"`, `iof_days`, `iof_min` | off, 10, 2 | `iof_score`: down-close candles retested and held (+1) or closed through (-1), up-close candles run through (+1) or held as resistance (-1), pivot raids reversed at once (+1 / -1 mirror) [our interpretation of "respect"]; combo2 = react, else IOF, else P/D
L14 | done | `draw_first` (umbrella), `draw_first_skip`, `conf_target_hygiene` is `target_hygiene` "htf" | off | `draw_first="session"` = draw_lock session + ordered pick + HTF hygiene + `draw_ext_target` + `cond_draw`; hygiene extension: with "htf" in `target_hygiene` the lock's confluence draws (`htf_ce_draw`, `vi_htf_draw`) drop arrays price has traded into since they formed (`bias_day.untraded_arrays`; gaps are kept)
L14a | done | `draw_first="session"` | off | the owner #9 lock (built earlier) plus the B2 order, a side gate in all three engines and the session done when delivered
A21 | done | `pd_day_range`, `pd_zone`, `ote_band`, `pd_body_multiday`, `day_pd` | 20, half, (0.62, 0.79), True, swing | zones half / third / deep (0.3 / 0.7) / ote (the retracement band measured from the extreme) apply to the 20-session range (`pd20`, `pd20_pos`) and to the swing range's `pd`
A21.2 | done | `day_pd="20d"`, `htf_bias="pd20"` | swing | `pd` (and combo / combo2 / draw_pd) become the P/D of the 20 prior sessions' range
A21.4 | done | `pd_body_multiday` | True | bodies for the multi-day range, wicks stay for intraday legs
B5 | done | `weekly_gate`, `news_topdown`, `bellwether_15m` (+ `vi_arrays` earlier) | off | weekly_gate: no side against `wk_bias` (weekly arrays' reaction, else the weekly-close flip); news_topdown: on a release day the nearer daily VI sets the side (needs `vi_arrays`); bellwether_15m: the last completed 15m close against the midpoint of the last four 15m bars [our interpretation]; VI rows in C = `vi_arrays`
B7 | done | `htf_bias="ob_mt"`, `how_rule` | off | `ob_mt` state + `ob_mt_lvl` (the last daily OB's MT); `how_in`: in a rally week a daily close below 50% of the last down-close candle; "no_long" blocks longs for the rest of the week (not a short signal)
B8 | done earlier | `htf_bias="flip"`, `flip_triggers` | ob_mt, wk_dc | stateful `flip` column, tests in test_review_fixes; new study variant `B8_flip_all_triggers`
B8a | done earlier | `flip_triggers` "ob_mt" | on | (same column)
B8b | done earlier | `flip_triggers` "flip_pd3" | off |
B8c | done earlier | `flip_triggers` "wk_dc" | on |
B8d | done earlier | `flip_triggers` "flip_close_above" | off | the result is neutral
B8e | done earlier | `flip_triggers` "flip_thu_wopen" | off |
B8f | done earlier | `stop_flip` | off | engine switch (breaker / smt); test_stop_flip_after_a_breaker_stop_out
B9 | done | `objective_neutral`, `bias_persist`, `next_array_on_fail`, `nof_days` | off, 0, False, 3 | objective_neutral day / week / both: the previous day's draw (obj_day) or the week's weekly-class draw (obj_week) delivered -> the bias reads neutral; persistence: an opposite sign counts only after `bias_persist` sessions in a row or when the close-based flip column agrees (plain readings kept as `<col>0`); next_array_on_fail: a bullish daily array closed through within `nof_days` and an intact weekly array below that price traded into and holds above its CE -> react +1 (mirror -1)
B10 | done | `htf_bias="mwd"`, `mwd_nest`, `mwd_disp_mult` | off | month / week / day states (`bias_htf.tf_states`: a displacement candle closing beyond the last swing; a counter displacement only marks the state correcting; the opposite structure break turns it) and cases A / B / C (`mwd_case`, `mwd_zones`); mwd_nest tag / filter: cases B / C enter only inside the weekly / monthly arrays [our interpretation of "displacement from a discount array"]
B13 | done | `weekly_open`, `weekly_open_early_days` | off, 2 | sun18 / mon00 / either (bx "wo": wo_sun, wo_mon, wk_dir, wo_expired): the week's direction side enters below the open on Monday-Tuesday and above it from Wednesday, until a daily array opposing the week is reached
B14.1 | done | `nwog_regime`, `nwog_leave_adr`, `nwog_returns_cons` | off, 0.5, 2 | returns to the current NWOG after a session fully outside it; "cons" (>= 2 returns or converging gaps) tag / scalp / skip, "trend" (left sharply, <= 1 return) tag
B14.2 | done | `nwog_converge_pts` | 10.0 | this NWOG's CE within the distance of the previous one, or three in a row each closer = converging -> "cons"
B14.3 | done | `nwog_bias`, `nwog_bias_reclaim`, `htf_bias="nwog"` | off, low | +1 above the NWOG high, -1 below its low, hold until reclaim ("low" literal 036 / 058, "ce", "high" = widest hold)
B17 | done | `neutral_gate`, `neutral_gate_mode` | (), tag | tests fifty_fifty, premium_chop (before 09:30 only), draw_delivered, range_market (the B17.4 reading), decoupled; tag / skip / scalp
B17.1 | done | `neutral_5050`, `fifty_react_ratio` | off, 0.5 | "armed": both sides armed in one window -> the window is stood aside (the second arming is refused, `gate`); "react": both sides' reaction weights alike (table column `fifty`)
B17.3 | done | `objective_met_stop` | off | day / week / both: no new trades while the previous day's / the week's draw is delivered
B17.5 | done | `decoupled_mode`, `decouple_corr`, `decouple_days`, `smt_both` | off | daily S&P / Nasdaq-100 return correlation of prior sessions (or an opposite-sign prior day) and the live partner test (`entries.decoupled`): tag / scalp / skip; smt_both: SMT at the previous day's high AND low in the overnight range with no bias (no lock side, no want) = no trade
B19 | done | `intermarket_model` (umbrella), `intermarket_model_skip` | off | dxy_gate "block", bond_range "scalp", bond_dir "filter", decoupled_mode "scalp"
B19.1 | done | `dxy_gate`, `dxy_gate_days` | off, 20 | the dollar's prior close above the highest high of the 20 sessions before it and above the close before: no longs ("tag" only reports)
B19.3 | done | `bond_range`, `bond_range_days`, `bond_range_frac`, `bond_dir` | off, 10, 0.3 | the 10-year yield's last-10-session span under 30% of the 60-session span: tag / scalp / skip; bond_dir "filter": rising yields -> no longs
B20 | done | `cot_oi_model` (umbrella), `cot_oi_model_skip` | off | cot_tag / oi_tag / wpr_tag "tag" (optional enhancers, cc06_002 ~0:24)
B20.1 | done (data) | `cot_tag`, `cot_market` | off | `bias_htf.load_cot`: CFTC LEGACY-format CSV or TXT files (TFF files are skipped) in data/mentorship/cot, usable from the Monday after the Friday release, commercial net vs the midpoint of the trailing 52-week range; NO COT FILE IS SHIPPED in the repo (downloading needs a go-ahead): the tag is inert (one warning) until files are supplied; unit-tested on a synthetic file
B20.2 | done (data) | `oi_tag`, `oi_days`, `oi_pct` | off, 10, 0.125 | `bias_htf.load_oi`: Databento statistics (stat_type 9) or an open_interest CSV at data/mentorship/ES_oi.csv, ROLL-SUMMED per day; tags oi_rise / oi_drop on a +-12.5% change over 10 sessions; no OI file in the repo: inert (one warning)
B20.3 | done | `wpr_tag`, `wpr_len` | off, 14 | weekly Williams %R from our own weekly bars: <= -80 long, >= -20 short; "filter" blocks the counter side
B22 | done | `qshift_tag`, `qshift_size`, `qs_turn_pct`, `qs_cons_pct`, `qs_due_lo`, `qs_due_hi` | off, 1.0, 0.03, 0.07, 63, 84 | qs_state turn / cons from the 60-session change against the 60 before, qs_due = 63-84 sessions after the last shift began, qs_trend = the 252-session trend; qshift_size multiplies the risk against that trend while a shift is due [our interpretation]
L14c | done | `matrix_tf_lower` | off | the table's react_tf (W / D) and react: the draw is the opposing array one timeframe lower (W -> D, D -> 4h) from the confluence arrays
L14e | done | `cond_draw`, `cond_draw_adr` | off, 0.25 | a close 0.25 x ADR5 beyond the lock price away from the draw switches the lock ONCE to the nearest marked level on the other side, the failed target spent; a pending order of the old side is dropped
M0.1 | done | `htf_bias="candle"`, `bias_candle` | off, D | bc_D / bc_W: the nearest unreached draw from the candle's open (the session open; the weekly open for W with weekly-class draws first); `want` applies in Silver Bullet / Ma Deuce (B3)
D15 | done | `smt_pick="trend"`, `one_market` | first, False | trend = leader on trend days, laggard on consolidation days (`backtest.consolidation_day` from the trades' day tags); one_market drops the other instrument's trades after the day's first fill
D22 | partial | `bias_open_src` ("data" / "spy" / "es_map"), `es_symbol` | data, /ES | "spy" re-reads the 04:00 stand-in from a futures frame; "es_map": `levels.map_midnight` + `prepare(ref_df=)` / `paper.evaluate(ref_df=)` map a futures midnight open onto the traded instrument by the prior-close ratio. `paper.snapshot` fetches `es_symbol` bars through Schwab when the switch is on, NOT exercised against the live feed
Ep02.6 | done | `no_narrative_scalp`, `bias_neutral="scalp"` | off | no daily narrative (the bias column 0, `combo` when `htf_bias` is off) -> every order of the day is a scalp (one exit min(+5, T1), no adds)
Ep03.12 | done | `htf_bias="draw_pd"`, `mmbm_zone` | off | draw and premium / discount agree (daily VI draws preferred when `vi_arrays` is on); mmbm_zone tag / filter: the entry in the discount half of [sweep low .. draw]
Ep06.6 | done | `midnight_target`, `midnight_confirm`, `midnight_below_ok` | off | the midnight open as a target rung; the bias side needs price beyond it in its direction; with `use_bias` a confirmed side may enter on the far side of the open
Ep08.2 | done | `chop_mode`, `chop_on_adr`, `chop_in_array` | off, 0.35, True | "skip" = wait for 09:30 (the pre-open windows), "skip_day", "scalp"; chop = the 09:30 price inside a daily / weekly array, or an overnight range under 0.35 x ADR5
Ep08.3 | done | `bias_open="all"` | midnight | the entry must be on the right side of EVERY open already printed (midnight, 08:30, 09:30; an open counts only once its own bar closed)

Known gaps: D22's live path (`paper.snapshot` fetching `es_symbol` bars) is not exercised against the Schwab feed; B20.1 / B20.2 need data files that are not in the repo; the "judgment" thresholds above are marked [our interpretation]
and exposed as Params. The ES 5m reachability probe (2023-11..2024-02, baseline 23 trades) is recorded under "Probe" below.

### Probe: ES 5m, 2023-11-01..2024-03-01, one variant at a time (baseline BASE 23 trades)

`same` = the same entries as the baseline (the switch only tags, rescales or reshapes exits, or never fired in this window - no futures pre-open windows, no COT / OI file, a single instrument). Funnel keys are the bias_htf rejections (counted per bar and side).

| variant | trades | entries vs baseline | bias_htf funnel |
|---|---|---|---|
| B2_ordered_pick | 23 | DIFF |  |
| B2_htf_bias_ordered | 18 | DIFF |  |
| B2_draw_ext_target | 23 | DIFF |  |
| B3_largest_pick | 31 | DIFF |  |
| B3_want_all_engines_draw | 13 | DIFF |  |
| B3_want_main_only_draw | 13 | DIFF |  |
| B3_judas_filter | 21 | DIFF | x_bh_judas=280 |
| B3_judas_tag | 23 | same |  |
| B6_iof | 3 | DIFF |  |
| B6_combo2 | 5 | DIFF |  |
| B6_iof_days5 | 4 | DIFF |  |
| L14_draw_first | 19 | DIFF | x_cond_draw=50 |
| L14_draw_first_no_cond | 23 | DIFF |  |
| L14a_draw_first_pick_only | 23 | DIFF |  |
| L14_conf_hygiene | 21 | DIFF |  |
| L14c_matrix_tf_lower | 25 | DIFF |  |
| L14e_cond_draw | 17 | DIFF | x_cond_draw=43 |
| A21_pd_zone_third | 5 | DIFF |  |
| A21_pd_zone_ote | 1 | DIFF |  |
| A21_pd_zone_deep | 5 | DIFF |  |
| A21.2_day_pd_20d | 12 | DIFF |  |
| A21.2_pd20_bias | 12 | DIFF |  |
| A21.4_pd_bodies_off | 12 | DIFF |  |
| B5_weekly_gate_filter | 10 | DIFF | x_bh_weekly_gate=1507 |
| B5_weekly_gate_bias | 3 | DIFF |  |
| B5_news_topdown_side | 21 | DIFF | x_bh_news_topdown=440 |
| B5_bellwether_filter | 1 | DIFF | x_bh_bellwether=1884 |
| B5_bellwether_tag | 23 | same |  |
| B7_ob_mt_bias | 1 | DIFF |  |
| B7_how_rule_no_long | 23 | same | x_bh_how=126 |
| B8_flip_all_triggers | 1 | DIFF |  |
| B9_objective_neutral_day | 2 | DIFF |  |
| B9_objective_neutral_week | 2 | DIFF |  |
| B9_bias_persist2 | 4 | DIFF |  |
| B9_next_array_on_fail | 4 | DIFF |  |
| B10_mwd_bias | 6 | DIFF |  |
| B10_mwd_nest_filter | 3 | DIFF | x_bh_mwd_nest=4 |
| B13_weekly_open_sun18 | 20 | DIFF | x_bh_weekly_open=654 |
| B13_weekly_open_mon00 | 20 | DIFF | x_bh_weekly_open=611 |
| B13_weekly_open_either | 20 | DIFF | x_bh_weekly_open=578 |
| B14.1_nwog_regime_scalp | 23 | same |  |
| B14.1_nwog_regime_skip | 18 | DIFF | x_bh_nwog_cons=350 |
| B14.2_nwog_converge_skip | 13 | DIFF | x_bh_nwog_cons=1142 |
| B14.3_nwog_bias_filter | 7 | DIFF | x_bh_nwog_bias=1702 |
| B14.3_nwog_bias_ce | 3 | DIFF |  |
| B17_neutral_gate_fifty | 22 | DIFF | x_bh_ng_fifty_fifty=165 |
| B17_neutral_gate_premium_chop | 23 | same |  |
| B17_neutral_gate_draw_delivered | 7 | DIFF | x_bh_ng_draw_delivered=1484 |
| B17_neutral_gate_range_market | 23 | same |  |
| B17_neutral_gate_decoupled | 5 | DIFF | x_bh_ng_decoupled=1906 |
| B17.1_neutral_5050_armed | 23 | same |  |
| B17.1_neutral_5050_react | 22 | DIFF | x_bh_fifty_fifty=165 |
| B17.3_objective_met_stop_day | 11 | DIFF | x_bh_objective_met=1090 |
| B17.3_objective_met_stop_week | 13 | DIFF | x_bh_objective_met=1014 |
| B17.5_decoupled_scalp | 22 | DIFF |  |
| B17.5_smt_both_skip | 23 | same |  |
| B19_intermarket_model | 22 | DIFF | x_bh_bond_dir=588, x_bh_dxy_gate=123 |
| B19.1_dxy_gate_block | 23 | same | x_bh_dxy_gate=123 |
| B19.3_bond_range_scalp | 23 | same |  |
| B19.3_bond_dir_filter | 22 | DIFF | x_bh_bond_dir=690 |
| B20_cot_oi_model | 23 | same |  |
| B20.1_cot_tag_filter | 23 | same |  |
| B20.2_oi_tag | 23 | same |  |
| B20.3_wpr_tag_filter | 23 | same | x_bh_wpr=328 |
| B22_qshift_tag | 23 | same |  |
| B22_qshift_size_half | 23 | same |  |
| M0.1_bias_candle_D | 15 | DIFF |  |
| M0.1_bias_candle_W | 15 | DIFF |  |
| D15_smt_pick_trend | 23 | same |  |
| D15_one_market | 23 | same |  |
| D22_bias_open_src_spy | 26 | DIFF |  |
| Ep02.6_no_narrative_scalp | 23 | same |  |
| Ep03.12_draw_pd | 6 | DIFF |  |
| Ep03.12_mmbm_zone_filter | 21 | DIFF | x_bh_mmbm_zone=3 |
| Ep06.6_midnight_target | 23 | same |  |
| Ep06.6_midnight_confirm_filter | 2 | DIFF | x_bh_midnight_confirm=338 |
| Ep06.6_midnight_below_ok | 28 | DIFF |  |
| Ep08.2_chop_skip | 23 | same |  |
| Ep08.2_chop_scalp | 23 | same |  |
| Ep08.3_bias_open_all | 19 | DIFF |  |
| L14c_react_tf_tag | 23 | same |  |
| M0.1_bias_candle_tag | 23 | same |  |
| A21_pd20_column_only | 23 | same |  |
| Ep08.2_chop_skip_day | 20 | DIFF | x_bh_chop=620 |
| B14.3_nwog_bias_tag | 23 | same |  |

## bias_htf review fixes (2026-10-19)
Reviewed findings of package bias_htf, fixed or answered. Tests: `tests/test_bias_htf.py` (value-level tests added), `tests/test_bias_htf_lookahead.py`.

| item | change |
| --- | --- |
| B2 `draw_ext_target` (L14 `draw_first`) | Was dead under `draw_lock_pick="ordered"` (a pool is only picked when no array is marked, so nothing lay beyond it). Now `mark_levels` looks for the nearest array beyond the locked pool among ALL marked arrays of that side AND the untraded HTF arrays of `conf` (`bias_day.untraded_arrays`, CE as the target, name `ext_htf_<tf>`); `lock["ext_from"]` is the pool and `_targets` adds it as a ladder rung. Test: lock with a stub confluence (target 112.5, ext_from 108.0), the helper on both sides. The table columns `draw_ext_lvl / name` stay (empty by construction: in the table a pool is only chosen when NO inefficiency exists); the live extent is the lock. |
| B10 `mwd_case` | A correcting week (`cw`) is no clean week: month + week bullish with the week correcting returns case C (arrays of the month only); case B needs a clean week and a correcting / stateless day. Weekly-as-month with a correcting week also returns C. Mirror tests added. |
| L14e `cond_draw` | Redefined: a draw FAILS when the OTHER side's nearest marked level (>= `draw_lock_min_pts` from the lock price) is taken before the draw is reached; the taken level is spent and the lock moves ONCE to the next marked level beyond it (none: no relock). A retrace (the Judas, B3) is no failure. `cond_draw_adr` removed. `cond_draw` is no longer part of the `draw_first` umbrella (owner question 9b). The failed lock is appended to `all_locks` (`failed=True`) so the lock report keeps it. Variants: `L14e_cond_draw`, `L14e_cond_draw_umbrella`. |
| owner #9 default `draw_lock_pick` | Not flipped (it changes every baseline); recorded as owner question 9a in `owner_directives.md`. |
| D22 `es_map` | `backtest.run(..., ref_df=)` now reaches `prepare`; `study._dec_job` loads the databento ES frame for the variant `D22_bias_open_src_es_map`; look-ahead test `test_no_look_ahead_es_map_midnight_through_backtest_run` (full vs truncated frame AND truncated ref); a mock-feed test of `paper.snapshot` (fetch, failed fetch -> warning, no fetch when off). |
| B20.1 / B20.2 | Docs corrected: `load_cot` reads the LEGACY "Commercial Positions" columns only (TFF files are skipped). The OI tag is now a plain change tag `oi_rise` / `oi_drop` (was oi_up / oi_dn); the "drop of 10-15% into HTF support" test is not built (needs the array state). Still inert without data: owner question 9c. |
| B17.1 `neutral_5050="armed"` | The second side's order now cancels the pending first order too (`strategy` sets `pending=None`) and blocks the rest of the window; a side is registered only when its order is armed (`bias_day.register_armed`), not for orders that fail other filters. |
| Ep06.6 `midnight_below_ok` | The waiver covers the MIDNIGHT open only and uses `continue`, so a failing 08:30 / 09:30 open (Ep08.3 `bias_open="all"`) still binds. Engine test with a patched `reference_opens`. |
| B7 mirror | New column `low_in` (decline week, then a close above 50% of the last up-close candle); `how_rule` = `"tag" / "no_long" / "no_short" / "both"`. The "rally week" precondition is marked [our interpretation]. Variants `B7_how_rule_no_short / both / tag`. |
| B13 `wo_expired` | The row's own overnight range counts (expiry on the morning the array is hit); the 60-session array age is `weekly_open_array_days` (bx key `woa`). |
| B9 | `_persist`: a 0 reading resets the run; `draw_ord_lvl / name / kind` follow the held sign. `_next_array` recomputes `combo2`. Params inert note for `bias_persist / next_array_on_fail / objective_neutral` with `htf_bias="off"`. Exact-list persistence test. |
| A21.2 / B2 | With `day_pd="20d"` the ordered liquidity pick is re-made after the 20-day P/D replaces `pd`. |
| D15 | `consolidation_day` ignores the 09:30-derived bias_htf tags (`bh_nwog_cons / bh_bond_range / bh_chop`) for fills before 09:30. `study.main_index` passes `one_market`. (A combine look-ahead run is not added: `combine` is a pure function of already-causal trade rows.) |
| B3 | Params inert note when `htf_bias` is on, `draw_lock="off"` and a window before 09:30 exists. |
| B17.5 / B14.2 | Both thresholds marked [our interpretation] in Params; new `nwog_converge_mode="shrink"` (three gaps in a row each closer, any size) as the primary B14.2 reading, variant `B14.2_nwog_converge_shrink`. The default `decouple_corr=0.5` almost never fires: owner question stays. No hit-rate probe was run. |
| M0.1 | `bias_candle_open="session" / "midnight"` (daily candle opens at 00:00, the weekly at the Monday 00:00 open); variants `M0.1_bias_candle_D_midnight / W_midnight`. |
| B22 | `size_mult` reads the cut row before 09:30 (`row_for`). Dead variable removed from `bellwether`. |
| Tests and variants | Value-level tests: `how_in / low_in`, `wpr`, `obj_day`, `bc_D / bc_W` (both signs), `wo_expired` (overnight, age), `_persist`, `mwd_case` (cw), `ext_target`, `cond_relock`. The study-variant coverage test now checks exact switch values (no substring match); variants added for `bias_neutral scalp / both`, `news_topdown tag`, `weekly_gate tag`, `objective_neutral both`, `objective_met_stop both`, `neutral_gate_mode tag / skip`, `bond_range skip`, `decoupled_mode skip`, `cot_tag / wpr_tag / mwd_nest / smt_both / how_rule tag`. |
| Not done | Value tests for `nwog` hold-until-reclaim, `qs_state`, `_next_array`, `mwd_zones`, `fifty / neutral_5050 armed` at the engine level; the B22 `qshift_size` for the SB / pre-open models beyond the row read; the B15 combine look-ahead. |

## Package silver_bullet (2026-10-19, branch sb-build)

Sources: `rule_coverage.md` section 3 `silver_bullet` (12 items), `rulebook_gaps/silver_bullet.md` (22 gaps, 19 build specs), `silver_bullet.md`, `owner_directives.md` (#2 5 = minimum room, #8 close at 12:00, #9 one draw per session, #7 speed bump, #10 sloppy days).
Code: `mentorship/sb_model.py` (rewritten; the window loop, the arming and the day reads), the `# --- silver_bullet package` block at the end of `Params` (strategy.py, 83 switches), four Trade fields (`sb_win`, `sb_n`, `sb_sweep_depth`, `sb_pre_run_ticks`; `entry_kind` carries fvg / ifvg / ifvg_breaker / ob / conf), `backtest.lock_cuts` (two cuts) and `backtest.combine` (session key, `sb_one_market`, `sb_am_done`), `study.py` (78 variants in `DECISIONS`, `SB_ONLY` base; the two `B.combine` call sites pass `sb_one_market` / `sb_am_done`), `tests/test_silver_bullet.py`. Every shared edit is commented "SB package". The Silver Bullet stays OFF (`sb_model=False`).
Defaults: all new switches reproduce the previous build except two, both listed under "Default changes" below. With `sb_pw_pools=False` and `sb_cancel_sticky=False` the ES 5m / 1m and synthetic runs of the old build match trade for trade (test `test_defaults_reproduce_the_pre_package_build_...`).

Conventions: a long rule is written once in side space and mirrored; bars are used only after they close; an order armed on bar i fills from i+1; the window loop sorts the windows by start time, and a later window reads only what an earlier one had printed before it opened.

### The 12 rule_coverage items

- M3 umbrella | done | `sb_mss_required` / `sb_need_mss`, `sb_fvg_pick`, `sb_one_per_day`, `sb_entry` (E2, existing, honoured), `sb_room_mode`, `sb_rebalance_ext` (existing), `sb_mgmt` "gap424"/"layered057", `sb_stop` | True, "evolving", False, "edge", "exit", 0, "fixed", "fvg_ob" | MSS off = displacement + FVG only (tagged `sb_no_mss`; both sides can then arm, fix the side with a lock or bias); room measured to the exit price or the raw draw
- M3.2 | done | `sb_draw_first`, `sb_pw_pools`, `sb_ote_draw`, `sb_htf_fallback`, `sb_use_bias` | False, True, False, False, False | the 054 list (PDH/PDL, London and prior PM H/L for the AM, AM and lunch for the PM, PWH/PWL, NWOG/ORG arrays, the htf-table draws, a classic OTE) is marked at the leg start and ONE draw is locked (nearest at least `draw_lock_min_pts` away, owner #9); only that side trades; the locked target is always in the draw list; stored in `ctx.lock["SB_<window>"]` (`window` field)
- D2 | done | `sb_fvg_in_window`, `sb_fvg_from`, `sb_evolve`; `mss_mode` ("wick" = a wick through the swing is the break), `mt_mode` (body / range OB mean threshold) and `sb_entry` honoured | False, 0, True | `mss_ref` (the A1 tiers) is NOT used: the SB keeps its short-term pivot reference (documented limit)
- T6 | done | `sb_last_hour` (+`sb_lh_window` 900-950, owner #1), `sb_0700` (+`sb_0700_window` 420-510, flat `sb_0700_flat`=509), `sb_london_window`, `sb_moc_extra` (+`sb_moc_window` 915-945) | False | windows sort by start; London 02:00 / 07:00 06:00 / last hour 14:30 leg starts [our interpretation]; moc is dropped when `sb_last_hour` is on (the hour covers it)
- L14g | done | `sb_htf_targets`, `sb_pw_pools`, `sb_ote_draw`, `sb_htf_fallback` | False, True, False, False | `sb_htf_targets` merges the main scan's conf targets, `fvg_targets` and `_lv_finish_targets` into the SB draw list
- M3.1 | done [our interpretation] | `sb_extra` ("pm2", "early"), `sb_early_start` | (), 590 | pm2 = a second PM entry (056 "two chances"); early = fills from 09:50 (the macro; test only)
- M3.3 | done | `sb_use_bias`, `sb_need_mss` | False, True | `sb_use_bias` applies the engine's `want` (htf_bias column of the WINDOW's own cut row), `weekly_bias` and `use_bias` (the T2 / D22 entry-in-the-discount-of-the-reference-open test) to the SB
- M3.5 | done | `sb_need_sweep`, `sb_sweep_max_pts`; Trade.`sb_sweep_depth` | False, 0 | depth = ES pts the leg low ran beyond the nearest level it swept [our interpretation]
- M3.8 | done | `sb_stop` ("fvg_ob" = "090", "fvg2", "entry_candle", "swing", "fvg_ce"), `sb_stop_pts` | "fvg_ob", 2.0 | fvg2 = 2 pts beyond the entry but not inside the FVG (057); entry_candle is set and sized at the fill (086 / 076); fvg_ce = beyond the CE of the deeper of the last two FVGs (069)
- M3.9 | done | `sb_cascade`, `sb_one_market`; `backtest.combine` session key | False | the combine key was (date, session): an SB window now owns its own slot (key = setup for sb_*); `sb_one_market` keeps the first SB market of the day; cascade = a classic window (London / AM / PM) only when no earlier classic window FILLED [our interpretation]
- M3.10 | done earlier | `sb_rebalance_ext` | 0 | unchanged
- M3.11 | done | `sb_mgmt` "gap424"/"layered057" (+`sb_gap424_fracs`), `sb_runner_if_weekly` | "fixed", (0.4, 0.2, 0.4), False | 4/2/4 at the near edge / 25% in / CE of the nearest opposing NWOG, ORG or HTF gap ahead of the entry (falls back to the normal ladder when the gap is not 5 pts away)

### Gaps (rulebook_gaps/silver_bullet.md)

- 1 IFVG entry | done | `sb_ifvg` ("add"/"prefer"), `sb_ifvg_reaper`, `sb_ifvg_stop` ("candle"/"breaker"), `sb_ifvg_market` | "" | base-tf + 5m bearish gaps closed through by the displacement; entry_kind ifvg / ifvg_breaker; market = buy the open after a down-close candle that traded into the zone (stop under that candle)
- 2 room overshoot | done | `sb_room_overshoot_pts` | 0 | counts beyond a pool in the room test only; the exit stays at the pool
- 3 room untaken / ORG chop | done | `sb_room_untaken`, `sb_org_chop`, `sb_org_chop_bars`, `sb_fail_mode` ("skip"/"scalp") | False, 6, "skip" | scalp = half size, one exit at the nearer pool, tag `sb_scalp`
- 4 FX room | none (fx_only, rulebook text only)
- 5 no-sweep discount array | done | `sb_sweep_alt` ("discount_array") | "" | four conditions of the spec (the week's initial FVG is proxied by any earlier bullish FVG of the frame holding the low)
- 6 BPR below the break | done | `sb_bpr_exclude` | False
- 7 immediate rebalance | done | `sb_imm_tag`, `sb_am_done` (combine) | False | Trade.imm_rebal on the SB trade; funnel counter `sb_runaway` when the window ends with none
- 8 supercharge | done | `sb_supercharge` (`sb_supercharge_seasonal` is reserved: B23 is not built) | False | Mon-Wed, week extreme not yet in (within 0.5 ADR5), weekly profile aligned, daily not ranging -> all but one lot at the SB target, stop NOT moved to breakeven, runner to the HTF draw; otherwise the full exit at the SB target
- 9 OB entry (049) | done | `sb_entry_arrays` "ob", `sb_ob_min_pts` | ("fvg",) | needs a locked draw or the htf bias on that side; scalp to the next short-term high; no MSS needed
- 10 three-array confluence (090) | done | `sb_entry_arrays` "confluence", `sb_conf_mode` ("tag"/"entry"), `sb_conf_min`, `sb_conf_tol_pts` | "tag", 2, 1.0 | the group must agree with the OB mean threshold; entry mode puts the limit at the group's mean but not under the MT; a 1m close under the MT exits (wicks allowed)
- 11 entry timeframe | none (needs sub-minute data; the bot stops at 1m)
- 12 FVG from the 09:30 leg | none needed (already how the SB arms); rulebook text only
- 13 premise | done | `sb_premise` ("htf_array"/"smt"/"either") | "" | htf_array needs `ctx.conf` (none = not provable = no trade); smt uses strategy._smt on the sister (True = the sister did NOT take its twin level)
- 14 several entries | done | `sb_max_per_window`, `sb_adds`, `sb_extra` pm2, `sb_moc_extra` | 1, False | a target hit ends the window; a stop-out allows the next FVG; adds = half size at the FVG top on a return into the filled FVG / at a new same-side FVG, inside the 1.3% cap
- 15 reverse after an HTF-array target | done | `sb_reverse_after_target` | False | ONE counter trade: a close beyond the first run's origin, its own FVG and room; the lock side is ignored for it
- 16 which FVG | done | `sb_fvg_pick` ("evolving"/"first"/"any_in_leg") | "evolving" | any_in_leg holds one limit per FVG, the nearest hit fills first
- 17 cancel threshold | done | `sb_cancel_ticks`, `sb_cancel_sticky`; Trade.`sb_pre_run_ticks` | 0, True | see Default changes
- 18 large-range candle | done | `sb_lrc_mult`, `sb_lrc_mode` ("tag"/"wait"/"skip") | 0, "tag"
- 19 stop width | done | `sb_stop` "swing", `sb_max_stop_pts`, `sb_wide` ("skip"/"size") | 0, "skip"
- 20 simple EQ rule | done | `sb_simple` | False | entry must be in the discount of the leg (premium for shorts), one exit at the first non-pool level beyond EQ
- 21 consolidation | done | `sb_cons_wait`, `sb_cons_bars`, `sb_cons_pts`, `sb_cons_body_mult` | False, 10, 2.0, 2.0
- 22 NWOG expansion | done | `sb_nwog_expansion` ("tag"/"require") | ""
- 045 abort (silver_bullet.md 2.5) | done | `sb_abort` | False

### Direction filters

- draw first, ONE direction per day | done | `sb_draw_first` + `sb_day_dir` ("lock" = the first window's locked side, "first_trade" = the first fill's side), `sb_day_dir_delivered` ("hold"/"free") | "off", "hold" | later windows trade only that side; "free" releases it once a target printed
- displacement size | done | `sb_disp_pts` (the MSS candle's body), `sb_disp_leg_pts` (low -> MSS close), `sb_disp_range_mult` (range vs the 20 bars before the low) | 0 | the A20 `disp_*` switches also act in the SB (setups_models)
- ES/NQ/YM sync | done [our interpretation] | `sb_sync` ("tag"/"require"), `sb_sync_mode` ("dir"/"mss"), `sb_sync_min` | "off", "mss", 1 | each sister closed higher at the arming bar than at our low's bar and (mss) broke its own last swing high; no sister present = no data (tag `sb_sync_na`, passes)
- spotty-day skip | done [our interpretation] | `sb_spotty` ("tag"/"skip"), `sb_spotty_tests`, `sb_spotty_min`, `sb_spotty_bars` | "off", (no_disp, no_fvg, whipsaw), 2, 30 | read once from the bars before the window (filters.md: ICT gives no measurable definition)
- weekly-profile alignment | done [our interpretation] | `sb_weekly` ("tag"/"require"), `sb_weekly_neutral` | "off", "allow" | side +1 when the week's low is in on Mon/Tue and the last close is above the week open (mirror -1); Mondays are neutral for the side, but the supercharge's "week extreme not yet in" read is open on a Monday (`fresh`)

### Default changes (the only two) - OWNER QUESTIONS

1. `sb_pw_pools=True` (the spec says "sb_pw_pools=True"; ICT's 054 draw list has PWH/PWL): the previous SB did not offer them. Set False for the old draw list.
2. `sb_cancel_sticky=True`: in the previous build a pending order whose target had traded was cancelled and re-armed on the very same bar (the FVG was still untouched), so "cancel if the target trades first" never held. A cancelled draw is not re-armed any more. False = old behaviour.
3. Judgment calls to confirm: `sb_one_per_day` = one SB per day (all windows), `sb_cascade` = classic windows only; `sb_day_dir_delivered` default "hold"; `sb_extra` "early"; the sync / spotty / weekly definitions above; the IFVG market-entry reading; `sb_moc_extra` dropped when `sb_last_hour` is on.

### Look-ahead audit (found and fixed while building)

- the rebuilt window loop reads the run_day locks' whole-day `delivered` flag only up to the current bar (`delivered_i <= i`); the 15:15 window looks at the PM draw and PM targets as of its own open (`_moc_ok`); cascade / one-per-day count only fills before the later window opens.
- pre-09:30 windows (London, 07:00) no longer read the overnight range (`pml`, premarket), the London pool before 05:00 or today's ORG in the new sweep / discount-array / gap424 / ORG-chop reads, and use their own htf-table cut for the bias (the old `swept` tag read `pml` in the London window: guarded).
- `cancel_below` (confluence) reads the previous bar's close, not the bar that may have filled.
- Not mine, noted: `DayCtx` builds the NWOG list with `zip(hist[-21:], hist[-20:] + [df])`, which is misaligned (no NWOG at all) when the history has fewer than 21 sessions; real runs have 21+.

### Tests

`tests/test_silver_bullet.py` (104 tests, 22 min with the ES look-ahead runs): unit and run_day scenarios for every rule item, gap and filter; mirror invariance (19 behaviours, long = short); the synthetic-data look-ahead loop (full vs truncated) for five switch groups; ES 5m x2 and ES 1m look-ahead (skip without data); the old-build signature test (`sb_pw_pools=False`, `sb_cancel_sticky=False` -> the recorded trades); the study-variant build test; and a meta test that every new switch is named by a test. Also checked by hand: ES 5m 2023-04..06 and ES 1m 2024-01..02 plus synthetic runs of the old build reproduce trade for trade with the two defaults switched back.


### Review fixes (sb-build, after ecf38c6)

1. management_exits hooks ported into `_run_window` / `_manage` (guarded by `_mg(p)`, which returns mentorship's `manage` module only when the Params carry `time_stop_extras`, so this branch runs without it and the merge needs no textual hunk in the loop): `pm_consol_exit` PM skip, `extras_blocked` (`blk`), `be_on` ("t1" or after expansion; `t1_i`, `be_done`; default now follows `be_on="expansion"` like the engine and mentorship), `time_stop_extras` (`fill_t`, `best`), `am_bulk_t` / `am_bulk_frac`, `final_hit` and `mark_day_stop`. The `be_on`, blk and am_bulk paths are tested (the last two with a stub of `manage`); re-run the golden / signature tests after the merge.
2. `sb_stop="entry_candle"` and limit IFVG entries no longer read the fill bar's own low: the stop is the last closed bar's low minus the pad, else (limit retraced below it) the stop armed with the order. The fill bar can now stop the trade out.
3. look-ahead tests also compare exits: for cuts after exits, `exit_time`, `exit_reason`, `gross` of the trades closed by the cut must agree; the `filters` group needs >= 3 trades.
4. `sb_no_overlap` (default True, Params): no SB fill while an earlier SB trade of any window is open.
5. `sb_spotty="tag"` only tags (arming before the window is unchanged); only "skip" waits for the read.
6. Supercharge: Monday has `early_up = early_dn = fresh = 1`, so it can fire Mon-Wed; `sb_supercharge` with `sb_mgmt` other than "fixed" is rejected by check_params (it was silently inert).
7. `sb_runaway` counts both sides and only inside the window.
8. rule_coverage section 6 marks D2, gap 7 and gap 8 PARTIAL, `layered057` an alias, `sb_use_bias` opt-in.
9. study: `M3.11_sb_ladder`, `layered057`, `M3.3_sb_use_bias_po3`, no_overlap off, entry_candle, conf / cons / window variants; the SPX/NDX combine passes `sb_one_market` / `sb_am_done`.
10. Session locks replaced mid-day (ORG breakaway, `draw_relock`) are recorded in `ctx.lock_hist` (strategy._lock_step, "SB package"); the SB reads the lock in force at each bar (`_lock_at`), not the day's final one.
11. `sb_moc_extra`'s "no PM SB hit its target" condition also binds the 15:00 last-hour window. Not changed: `sb_x_*` funnel counts are per re-arm bar (inflated), `_first_lock` adds the previous-session H/L for the AM window only, `sb_need_mss` stays an alias, `sb_pw_pools` / `sb_cancel_sticky` default changes are still open owner questions.

## Merge sb-build into mentorship (2026-10-20)

`git merge --no-ff sb-build` into `mentorship` (nine mentorship stages: owner directives ... bias_htf; sb-build: the silver_bullet package). Conflicts and how they were resolved (nothing dropped, no default changed):

| File | Resolution |
|---|---|
| `backtest.combine` | one signature `combine(*runs, pick, one_market, sb_one_market, sb_am_done)`: `one_market` (bias_htf Ep 05, applied to the whole combined book) and `sb_one_market` (SB package M3.9, only the Silver Bullet's market) stay distinct; the `_sk` slot key (SB window = own slot) is used by the pick/leader/laggard/trend path and the default path; `CONSOL_MARKS` / `consolidation_day` kept. |
| `strategy.py` | Params blocks of both packages kept (management_exits ... bias_htf, then silver_bullet); Trade tag fields of both kept (`final_hit ... eve_draw_done`, `sb_win / sb_n / sb_sweep_depth / sb_pre_run_ticks`). |
| `sb_model.py` | sb-build's rewrite is the base; mentorship's hooks were re-applied onto it: `extras_init` (+ `ext / zone / level_kinds / draw` on every order, `_kinds`), `extras_t1` / `extras_be_bar` (default `extras_be_on="t1"` = the old breakeven at the first target; replaces the sb-build "follow be_on" port), `time_stop_frac(leg_hi, zone_top)`, `manage.exits(extras=True)`, X10b `am_bulk`, X11c PM consolidation, N4 `pre_0830`, N3 `fomc_flat` / `fomc_whipsaw` / `sb_start` / `sb_gate`, N8.3 `consol_out`, `flat_for` (N7.1), the day_week_context / bias_htf funnel (`budget_full`, `gate`, `side_ok`, `order_ok`, `scalp_now`, tgif side block), `friday_first_pool`, `Trade.ext_px`. The position basis follows `sb_adds` so a breakeven after an add uses the average entry. |
| `study.py` | all variants of both sides (no key clash); `CURRENT` / `PRE_OWNER` pin both sides' old defaults; `combine` callers pass `one_market`, `sb_one_market`, `sb_am_done`; the second market runs when any of them is on. |
| `rule_coverage.md`, `build_log.md` | both sections kept (the SB coverage section is renumbered 10; per item the more-built status). |

Interaction pinned in a test (no default changed): `want_all_engines` (bias_htf B3, default on) makes the Silver Bullet honour `htf_bias` through `bias_day.side_ok`, which is the same thing as the opt-in `sb_use_bias` (M3.3). `test_m33_use_bias_binds_the_sb_to_the_htf_and_weekly_bias` now pins `want_all_engines=False` so it still tests the SB-own switch. Owner question: with `want_all_engines=True` the Silver Bullet already follows the htf bias whenever `htf_bias` is not "off"; `sb_use_bias` then only adds the weekly bias and use_bias (discount of the open). Keep both, or fold `sb_use_bias` into `want_all_engines`?

## Caption-gap pass: levels_detectors#1/3

Sources: `rulebook_gaps/bias_htf_intermarket.md` (125, 128, 129, 151, 181), `day_selection_news_calendar.md` (49), `definitions_pd_arrays_structure.md` (1, 3, 5, 6, 8, 10, 12, 13, 21, 24, 32, 35, 36, 37, 38, 41, 43, 47, 54, 57, 60, 64, 67). Binding order: owner directives (nothing in them changes these items), the item's build spec, rulebook / coverage. Detectors are in `levels.py` (pure; every zone carries the bar at which it is known), the engine glue in the new `ld2.py`, switches in the Params block "caption-gap pass, levels_detectors #1/3" (all default to the built behaviour), study variants named by the gap id in `study._LD1_DECISIONS`, tests in `tests/test_caption_gap_ld1.py` (unit tests per item, Params / study checks, no-look-ahead runs full vs truncated on synthetic data and ES 5m; the ES test skips without data). `Zone` gained optional `bi`, `levels`, `tag`, `n` fields (defaults keep the old equality). Rulebook text: `mentorship_rules.md` rules A3, A5, A6, A8, A9, A11, A12, A13, A16, A17, A21, A23, B5, B10, B21, N8, L5, L8 plus the new L18 (initial FVG references) and A25 (converged arrays).

- bias_htf_intermarket#125 X3-l8-vb-exhaustion-gap | done | `vb_context` | False | `levels.vb_context` classifies each vacuum-block rung of `_lv_target_arrays` valid / exhaustion / invalid (bullish VB: bias +1 when `htf_bias` is on - read from the htf-table row known at the bar (`bias_day.row_for`: before 09:30 the lock-time cut, never the 09:30 row; no row known = the bias clause is skipped) - and the lower edge below the 20-day EQ; 5 straight up days or a last close above the high of the 20 sessions BEFORE that close (review fix: the last close's own session was inside the window, so the clause could never fire) = exhaustion, tagged `vb_exhaustion`, dropped)
- bias_htf_intermarket#128 X3-b21-ipda-anchor | done | `ipda_anchor` | "rolling" | "month" = windows end on the session before the first trading day of the last closed month (2023-11-14 -> 2023-09-29, `ctx.ipda_last`), "swing" = the last daily MSS (`levels.daily_mss_end`); `backtest.hist_days(p)` keeps 45 more prior sessions for those two; the quarterly-shift anchor of the rule text has no build spec and is not built
- bias_htf_intermarket#129 B21-ipda-windows-arrays | done | `ipda_arrays_first20` | False | `htf.Arr.ipda_w` (age of `known`, set per day); the daily FVG / OB / VI rows of the bias table and of the Confluence (`_ipda_mask`) use only the first window (20, then 40, then 60 sessions) that still has an open array; W / M / intraday rows and the opening gaps are untouched; older than 60 sessions = excluded
- bias_htf_intermarket#151 X3-b5-15m-pools-5m-gaps | done | `pool_tf` | 1 | swing pools (`pool_swings`) and relative equal highs / lows come from `levels.tf_pivots` of the pool_tf-minute bars mapped to their base-bar extreme (review fix: also the resistance count, smoothness, the touch count and the inter-swing target, via `targets._ph`); session H/L and PDH/PDL unchanged
- bias_htf_intermarket#181 X3-b10-topdown-transposition | done | `topdown_targets` | False | 4h / D / W / M were already Confluence timeframes with their own `tf` (item 71 itself is outside this chunk); the switch adds them to the target ladder's HTF sources (`ld2.htf_target_tfs`)
- day_selection_news_calendar#49 N8-consolidation-builds-orders | done | `consol_pools` | False | the released `Chop` range (`rel_i`, frozen hi / lo) = pools `consol_l` / `consol_h` (sweep pools and buy-side targets from the bar after the release)
- definitions_pd_arrays_structure#1 A11-bpr-one-pass-definition | partial | `bpr_def`, `bpr2_two_candle`, `bpr2_trail`, `bpr2_cont_trigger` | "overlap", False, False, False | `levels.single_pass_bprs` (gap / range / two_candle forms, Zone kind "bpr2", `tag` = the role, `bi` = the balanced bar); `Side.bprs` returns them once balanced, so bpr_targets / bpr_abort / bpr_rule / size_up use them; trail = stop to the BPR low - 1 tick after a new FVG above its high; the continuation trigger is a trade TAG (`bpr2_cont`), not an entry permission; VI / NDOG / NWOG are not Type 2 candidates
- definitions_pd_arrays_structure#3 X-efficient-delivery-two-pass | partial | `two_pass_state`, `shield_passes` | False, 3 | `levels.pass_state` + `ld2.drop_efficient`: intraday gap bands crossed both ways leave the target list, bands crossed >= shield_passes times hide the array targets beyond them (NDOG / NWOG kept; review fix: only `array`-kind levels are matched, so a pool or wick sitting on a band edge stays; voids and wick bands are not evaluated as bands, the hook sits after the main target path only); HTF bands and the retrace cap / stop beyond a balanced band on the ENTRY side are not built
- definitions_pd_arrays_structure#5 A12-ob-candle-selection | partial | `ob_pick`, `ob_skip_encapsulated` | "blend", False | `levels.order_block_blend(pick=, s=, skip_encap=, htf_zone=)`; applied to the entry OBs (`_ob_at_low`, the scan OB, `_ob_anchor`); the OBs inside HTF arrays (bias table / Confluence) keep the blend; "original" omits the 012 later-candidate validity rule; "clearly smaller" = at most half the previous body
- definitions_pd_arrays_structure#6 A12-consolidation-ob-open-level | done | `cons_ob_open` | False | `levels.consolidation_ob_opens` on 1h bars (>= 4 overlapping bars within 1.5x the mean bar range [our interpretation]); the open is a target rung and an entry array (`entry_arrays` accepts "cons_ob_open"); a body close beyond it retires it
- definitions_pd_arrays_structure#8 A8-inversion-any-pd-array | done | `inversions` | () | `levels.invert` / `inverted_arrays` (kind "inv_<array>", `levels` = (lo, mt, hi)); OB, breaker, VI from the Side arrays, ORG / NWOG from the frame's closes; support role = entry zone (like ifvg_entries), resistance role = targets (lo, MT); a close back through the MT retires the role
- definitions_pd_arrays_structure#10 A12-mt-all-blocks-ce-all-gaps | done | `mit_mt_invalid` | False | `mitigation_blocks(with_mt=)` (MT = the block candle's body mean per D4), `mitigation_alive(use_mt=)`; the VI / void CE is `Zone.mid` (already built)
- definitions_pd_arrays_structure#12 A13-breaker-candle-selection | done | `breaker_candle`, `breaker_body_swing` | "extreme_close", False | OWNER QUESTION 1; "extreme_body" = ties to the biggest body; body_swing keeps only candidates whose close is the extreme of all bodies of the leg
- definitions_pd_arrays_structure#13 A13-breaker-zone-extent | partial | `breaker_zone` ("blend", "leg_disruptor" added) | "range" | blend = the union of the consecutive same-colour candles around the picked candle; leg_disruptor = from the first opposite-colour candle of the A->B run to B; the 1-tick zone-high overshoot and the mitigation tag are not built
- definitions_pd_arrays_structure#21 A6-breakaway-identification | partial | `breakaway_def`, `breakaway_ctx_pts` | "first_after_mss", 10.0 | "context" needs a valid HTF array of the side within ctx_pts of the leg origin (Confluence rows or the HTF FVG zones), "second_mss" = the first FVG after a swing high formed after the first break is closed through; the analogue form (c) and the "stays outside at the next open" confirmation are not built (the existing `breakaway="hold"` CE exit applies)
- definitions_pd_arrays_structure#24 A5-caffeine-bar-bisi | done | `single_bar_fvg_strict` | False | `fvgs(single_bar=)` tags c2 range >= 2x the mean of the prior 20 bars; a tagged gap dies on any trade below its low (`ld2.gap_open`), not judged on NFP / FOMC days
- definitions_pd_arrays_structure#32 A5-broken-fvg-reclaim | done | `fvg_reclaim` | False | `levels.reclaimed_fvgs` (a swing away + the first close back above, >= 4 bars after the break, judged again after each chop); entry zone when the bias is not against the trade and the zone is in the discount of the leg
- definitions_pd_arrays_structure#35 B5-htf-arrays-anchor-transpose | partial | `htf_entry_arrays` | () | `Side.zones_tf` FVGs / OBs of the listed minute bars as fixed entry zones between the sweep extreme and the market; VIs, IFVGs, breakers, rejection blocks and wicks are not projected, and the LTF refinement and the "HTF level governs the stop" note are not built
- definitions_pd_arrays_structure#36 N-initial-fvg-reference | done | `initial_fvg` | () | `ld2.build_init_fvg` (day / week / mon10; the week's first trading session [our interpretation]); `Trade.init_fvg_respected` and lv_tags `initfvg_<name>_<untested|respected|disrespected>` as of the entry bar
- definitions_pd_arrays_structure#37 A9-vi-definition-no-wick-condition | done | `vi_wick_overlap`, `vi_multi` | True, False | OWNER QUESTION 2; `volume_imbalances(wick_overlap=, multi=)` (multi = up to 3 candles, zone = the free band), Zone.tag "void" when the wicks do not overlap either; also in the bias table / Confluence via `htf_kw`
- definitions_pd_arrays_structure#38 A9-vi-delivery-state | partial | `vi_dead_rule`, `vi_two_sided_draw` | "full_span", False | `levels.vi_state` (open / reached / target_hit / dead) and `vi_body_dead(rule=)`; the rule and the two-sided draw (a wick never retires an open daily / weekly VI) act in the bias table, the Confluence rows and - review fix - the intraday Side VIs (`Side.vi_dead_rule` read by `_vi_alive`, so entries, stops and targets honour "overlap"; both imply `vi_body_death`); reached / target_hit are not used by the engine, the parent TF is the VI's own TF
- definitions_pd_arrays_structure#41 A9-daily-vi-forward-levels | partial | `vi_flip_support`, `vi_flip_entries` | False, False | `ld2.build_vi_flip` / `_vi_flip_live`: each daily VI of the ISO week (known at the later session's close) with edges + midpoint, role from the VI's own direction (review fix: a bearish VI is "support", a bullish one "resistance", whatever the later close); once reached its levels are `array` targets only for the OPPOSING role (`vi_flip_target_levels`), the support role (a short: resistance) is an ENTRY array with `vi_flip_entries` (`vi_flip_entry_zones`, tag `vi_flip`, between the sweep extreme and the market); retired by a 60m body close beyond its far edge [our interpretation]; the hourly-FVG pairing is not required
- definitions_pd_arrays_structure#43 A16-propulsion-context-sequence | done | `pb_def` | "a16" | `propulsion_blocks(pb_def=, need_confirm=, bias=)`; step (1), the bullish context, is wired as `Side.ctx_bias` (set from `ctx.cur_bias` each bar): "cc04_008" blocks are dropped while the bias is against the side, an unknown / neutral bias does not test it [our interpretation]; "cc09_008" does not check that the OB is still valid
- definitions_pd_arrays_structure#47 A17-rejection-block-levels | done | `rb_level`, `rb_ce_level` | "close", False | OWNER QUESTION 3; `rejection_blocks(level=)` returns `levels` = (level1, level2, W); rb_ce_level adds level2 and W to the `rb_targets="ladder"` rungs; the entry use ("a little through level1, level2 holds, stop beyond W") is not built
- definitions_pd_arrays_structure#54 A21-dealing-range-energetic-swing | partial | `leg_anchor` | "mss_leg" | `levels.dealing_range` ("energetic": the latest swing low with a bullish FVG within 5 bars, cluster tie-break; review fix: the impulsive-leg test is real - >= 60% up-closes, or an FVG inside the leg, or >= 1 ATR - and an inner swing low of a consolidation is skipped); acts in the leg_pd arm / fill checks, leg_pd_min, the leg depth tags and (review fix) the OTE band / leg_pd_strict of `setups.ote_adjust`; the 60m weekly planning leg is not built
- definitions_pd_arrays_structure#57 A23-wick-quarter-strength | partial | `wick_quarters`, `wick_bias_line`, `judas_wick_cap` | False | q25 / q75 in `wick_midpoints(quarters=True)`, the `wick_tier` tag of the sweep (`wick_tier_<very_bearish|normal|overshoot|failed>`, very_bullish for longs), bias line = a body close at or below the CE of the 1h lower-wick tail at the sweep low stops the adds (tag `wick_bias_lost`), Judas cap tag (`judas_cap_held` / `judas_cap_lost`); review fix: the 1h candle of the sweep is read only once it has CLOSED (no look-ahead); the heavy-stance q25 entry level and the reduce / exit step of a lost bias line are not built (it only stops the adds)
- definitions_pd_arrays_structure#60 confluence-stacked-arrays | partial | `converge_rank` | False | `levels.converged_count` (OBs / VIs overlapping the gap, wick CEs inside it, twice when within 2 ticks of its CE); the entry gap pick prefers the highest count and tags `converged_N`; the ranking of partials / targets is not built
- definitions_pd_arrays_structure#64 A3-diagonal-support-is-liquidity | done | `diag_pools`, `diag_min_swings` | False, 3 | `levels.diagonal_lows` (a strictly rising chain within the REL tolerance of one line); `_sell_side` key "diag" = the extrapolated line while untaken and under the last close
- definitions_pd_arrays_structure#67 L5-nwog-high-low-labelling | done | (none, always on) | | `htf.opening_gaps` columns `dir` ("down" when the Friday close is above the Sunday open), `close_before`, `open_after`; `gaps_for_day(with_dir=True)` passes the direction on (detector level only: not surfaced as a trade tag); high / low were already max / min of the two prices

### Owner questions (caption-gap pass)

1. `breaker_candle` (A13 #12): the spec names "last" as the bot default (015, 043); the built behaviour since owner directive #14 (the highest-close up-close candle, 029 / 048) stays the default as `extreme_close`. Switch the default to "last"?
2. `vi_wick_overlap` (A9 #37): the spec default is True (the wick-overlap rule as built) although the captions (009, 036, 027) describe a bodies-only VI. Make the ICT definition (False) the default?
3. `rb_level` (A17 #47): the default is the 2023 "close" reading (level1 = the extreme close of the same-colour candles); the cc04_006 reading (any open / close) was the built behaviour. It changes every use of level1: `rb_targets` "ladder" / "replace" and `matrix_targets` with "rejection"; the three older study variants A22_matrix_targets, L11_rb_ladder and L11_rb_replace are therefore pinned to `rb_level="open_close"` (their built behaviour). Keep "close" as the default?
4. `vb_context` (L8 #125): a neutral bias (`want` 0) counts as invalid for both vacuum-block directions ("want == +1"); the bias reading is the htf-table row known at the bar (pre-09:30 orders read the lock-time cut); the bias clause is skipped when `htf_bias` is off or no row is known yet.
5. The quarterly-shift anchor of B21 (#128) is named in the rule text but has no build spec; only rolling / month / swing are built.
6. `balance_tf` (A11 #75, levels_detectors#2/3): the default is now the spec's "own" (an HTF FVG is balanced only by closes of its own timeframe; review fix). The earlier build retired a WEEKLY array on DAILY closes - that is `balance_tf="legacy"` (study variant `A11-htf-gap-own-tf_legacy`); `backtest.table_kw` always passes `balance_tf` so cached bias tables of the old default are not reused. This changes weekly arrays in every default bias table. Keep "own"?
7. `nwog_cfd_src` (L5 #68): "auto" = the built behaviour = "sunday_bars" (a frame with no Sunday-evening bars simply has no NWOG). A silent fall-back to the Monday 09:30 variant would grow NWOGs on SPY extended-hours frames that never had them, so the fall-back is explicit: "monday_0930" (every weekend, review fix: the Monday after the break, not the Sunday bars' date) and "sunday_else_monday" (the per-weekend fall-back: Sunday bars when present, else Monday 09:30); "sunday_bars" flags the missing weekends in `opening_gaps(...).attrs["nwog_unavailable"]`.
8. `consol_body_range` (A21 #127): the spec default is True and names the delivery-state box (`state_machine`, item 125, another package, not built). The builder applied it to the N8 `consol_pools` range, which silently changed `consol_pools=True`; review fix: it is now an opt-in (default False, study variant `A21-consolidation-range-def` turns it on) and N8 keeps the wick range of the chop test. Move the default to True once the delivery-state package exists?
9. `Trade.org_dir` (L7 #105) is a new always-on trade column (no switch; "" before 09:30 or without an ORG): the spec asks to "add org_dir to DayCtx/Trade tags"; it is not part of `lv_tags`, so tag-based studies are unchanged.
10. `fvg_vi_extend_ce` (A5 #117) defaults to True as the spec says, but only acts when `fvg_vi_extend` (off) is on.
11. `bk_depth` (A6 #93): the item text says "[our interpretation] default any_open" while its Params line says `bk_depth="ce"`; the Params line (the A6 rule, at most 50%) was taken as the default and "any_open" (062, cc04_009) is the switch. Which one should be the default?
12. `ipda_anchor` (B21 #130, levels_detectors#3/3): the item says `ipda_anchor="month"` = the windows end on the first trading day of the CURRENT month and `"daily"` is the default; the earlier build (bias_htf_intermarket#128, tested) already uses "month" for the LAST CLOSED month's first day (cc05_001 ~53:44) and "rolling" for the daily roll. Both are kept: the item's reading is the new value "current_month", "daily" is accepted as an alias of "rolling" (the default is unchanged). Rename the values?
13. `daily_level_needs_array` (L2 #76): the item wants the bool to become "any" / "fvg" with "any" = today's True; True / "any" stay equal and the default stays False (the L2 owner reading, Ep 08, says any PD array plus time of day suffices; 058 / 076 say an FVG is required). The "fvg" mode only gates the swept daily level on a same-side FVG within a tick of it; the entry is NOT moved to the FVG CE (the engine builds its own PD-array entry). Is a real flip-retest setup wanted? ANSWERED by building it (levels_detectors#3/3 review): `flip_retest_entry` (off) is the real flip-retest setup at the FVG CE; the gate-only reading stays the default.
14. `or_minutes` (T4 #21): now validated to {0, 20, 30, 60} as the item says; any other value used to be accepted silently.
15. Trendline tolerances (new-trendline-trap-target #116 vs new-trendline-trap #137): #116 says touches within 0.1 x ADR5 of the line, #137 says a few ticks (`tl_tol_ticks`, 4). Both are used as written - `trendline_pools` the ADR5 tolerance, `trendline_trap` the tick tolerance. One tolerance for both? Review fix: `tl_tol_adr` (0 = ticks) lets the trap use the ADR5 tolerance as well; the question stays open.
16. `wick_lod_tag` / `wick_untraded` (L10 #42): the item first says a touched wick CE "stays as a reference" and then (build spec) drops it once a later daily bar traded through it by a tick; the build spec was followed (`wick_untraded`, off).

### Review fixes (caption-gap pass, levels_detectors#1/3)

Fixed: wick_bias_line look-ahead (#57: the sweep's 1h candle is used only once closed); vb_context bias row per bar and a working exhaustion clause (#125); `vi_dead_rule` on the intraday Side VIs (#38); daily-VI roles from the VI direction, opposing-role targets and the support entry array `vi_flip_entries` (#41); a real impulse test, a consolidation-pivot skip and the OTE band on the energetic anchor (#54); `rb_level` variants pinned (#47); cc04_008 bullish context (#43); array-only matching in `drop_efficient` (#3); pool_tf routed through the resistance count / smoothness / inter-swing users (#151); dead code removed from `_judas_cap_tag`. Still not built (partial, listed above): #1 continuation trigger as permission, VI / NDOG / NWOG as Type 2 candidates; #3 HTF bands, retrace cap, entry-side balanced-band stop; #5 HTF OBs and the "original" validity rule; #13 overshoot / mitigation tag; #21 analogue form (c) and next-open confirmation; #38 reached / target_hit and parent-TF logic in the engine; #41 hourly-FVG pairing; #54 60m weekly leg; #57 q25 entry, reduce / exit; #60 ranking of partials / targets; #128 quarterly-shift anchor (no spec); #47 RB entry use; #35 non-FVG / OB array types; #67 `dir` label as a trade tag; #129 voids / breakers / rejection blocks in the IPDA windows and `paper.history_days` for month / swing anchors; #8 inversion levels entered as zones.

`tests/test_caption_gap_ld1_review.py`: engine-level look-ahead of wick_bias_line (mid-hour bars never flag), the exhaustion clause and the pre-09:30 bias row, vi_dead_rule on a Side, VI roles / targets / entry zones, the impulse / consolidation tests and the OTE anchor, engine-level checks of bpr2_trail, bpr2_cont, judas cap, rb_ce_level, diag_min_swings and ob_skip_encapsulated, look-ahead runs of the switch groups (each asserted to change the trades; the gaps group runs with post-MSS orders because the synthetic day only produces FVG entries there) and a stricter every-switch-is-named test.

### Tests (caption-gap pass, levels_detectors#1/3)

`tests/test_caption_gap_ld1.py`: 40 unit / plumbing tests (one per item: detector fixtures with the spec's cases, the Params defaults and validation, `htf_kw`, the study variants, every new switch named by a test) and 6 no-look-ahead runs (full vs truncated at entry AND exit times: four switch groups and a post-MSS / breakaway set on synthetic 5m 2026-04-06..05-15, and ES 5m 2023-10-02..11-10 with the IPDA month anchor + array windows, VI definition / states, Type 2 BPRs, inversions of ORG / NWOG, reference FVGs, HTF entry zones, reclaimed FVGs, converged picks, the two-pass state - skipped without `data/mentorship/ES_5min_db.csv`). All 46 pass on Windows; nothing platform specific. The full suite on 4 workers (1135 passed, 14 failed in 1:27:37) found three causes, all fixed: `Confluence` objects built without `__init__` by older tests (`_ipda_mask` now reads `first20` / `dends` with getattr), `Zone` equality including the new `levels` field (rejection-block tests; equality and hashing ignore the new fields again), and the study variant `A21-dealing-range-energetic-swing` clashing with `leg_pd=0` of `test_bias_htf_lookahead.py` (the variant now sets only `leg_anchor`); the affected files (targets_partials, owner_directives, mentorship rejection, portability, levels_detectors, levels_review, the A21 look-ahead variant) pass again, and the 43 other new variants pass the per-variant look-ahead test of `test_bias_htf_lookahead.py` (they follow `X16_journal_tags_off` in `study.DECISIONS`). The default behaviour is unchanged (the owner_directives golden window and the old-default pins still reproduce).

## Caption-gap pass: levels_detectors#2/3

29 specs of `rulebook_gaps/definitions_pd_arrays_structure.md` (68, 72, 74, 75, 85, 90, 91, 93, 95, 96, 105, 116, 117, 118, 123, 127, 128, 134, 140, 142, 156, 161, 167) and `rulebook_gaps/levels_liquidity_targets.md` (1, 2, 5, 12, 13, 18). Detectors in `levels.py`, `htf.py` (opening gaps incl. the CFD source and the rebalanced-NWOG machine, daily / weekly arrays) and `confluence.py`; engine glue in the new `ld3.py`; 39 new Params fields (every one defaults to the built behaviour); study variants named by gap id (`study._LD2_DECISIONS`); tests in `tests/test_caption_gap_ld2.py`.

Items (file#N gap-id | status | Params switch(es) | default | note):

- levels_liquidity_targets#1 A2-which-old-high | done | `active_old_pool` | False | `levels.first_old_beyond` over the daily swing highs (3-candle pivots of the completed sessions, 61-session history); pool `old_hi` / `old_lo` in `_targets` (created = the day start), `_sell_side` (`old_lo`, today's low through bar i-1: the sweep bar is not in it) and `mark_levels` (lock candidates); recomputed per bar
- levels_liquidity_targets#2 A2-round-number-pool | done | `round_pool_mode`, `round_conf_pts` | "pool", 1.0 | "confluence" keeps a handle only with an old high / low (PDH/PDL, prior week / month), rel-eq, active-old (A2) or engineered pool within `round_conf_pts` (`ld3.confluence_refs`; review fix: not every other pool); "tag_only" never a pool; lv_tag `round_conf` on a sweep at / of a handle (`ld3.round_tag`)
- levels_liquidity_targets#5 A3-engineered-liquidity | done | `engineered_pools`, `eng_short_pts` | False, 3.0 | `levels.engineered_pools` on 15m / 1h pivots (`tf_pivots`) and daily pivots; created at the bar the confirming low is known, untaken test per bar; ranks like a rel-eq pool (`eq_pref`); sell-side mirror `eng<tf>_<bar>`; the score (bars H1..H2, +1 for an opposing FVG known by the creation bar) breaks ties among engineered sweeps; counts as rel-eq in the sweep pick (`rank` / `require`); a sweep of one is tagged `engineered`; the target-side ranking by score is not built
- levels_liquidity_targets#12 L1-rth-session-pools | done | `rth_pool_spent` | False | previous PM / AM / lunch pools are spent only by prints from 09:30 (`_targets` via `ld3.rth_spent_up`, `_level_created`, the previous-AM lock candidate); London stays spent by any print; prev_pm is not a lock candidate in `mark_levels` (as before)
- levels_liquidity_targets#13 L3-midnight-session-opening-ranges | done | `session_ors` | () | `ld3.build_sors` ((start_minute, minutes) windows of today's frame, created = the bar after the window); pools in `_lv_target_pools`, `_lv_sell_side` and `mark_levels` (`sor_<start>_<min>`); the Asian 20:00 range needs the prior evening in the frame (ETH data)
- levels_liquidity_targets#18 L5-partial-redelivery | done | `nwog_rebalanced` | False | `levels.nwog_redelivery` (causal state machine: far edge, back through, CE failure, lone exit FVG within 1 pt of the gap edge) run per NWOG by `htf.nwog_rebalanced` at `prepare`; `gaps_for_day(reb=)` returns a `GapList` carrying it; the ladder keeps the near edge and the exit FVG's near edge once the sequence has completed by the bar's close; review fix: gap taller than 2 pts, the sequence within the first 5 sessions, the exit FVG the lone FVG of the leg and closing outside the gap, and a later full redelivery to the Friday close ends it (table value `(known, near, exit, until)`)
- definitions_pd_arrays_structure#68 L5-cfd-nwog-mapping | done | `nwog_cfd_src` | "auto" | `htf.opening_gaps(nwog_src=)`: "sunday_bars" (= auto) flags the weekends without a Sunday bar (`attrs["nwog_unavailable"]`), "monday_0930" (Friday last close -> the Monday 09:30 open, known when that bar closes), "sunday_else_monday" (per weekend fall-back), "none"; plumbed through `htf_kw` / Confluence / `prepare`; a Monday-09:30 NWOG is known when that bar closes, so it is in force from the next session (`gaps_for_day` reads 09:30); OWNER QUESTION 7
- definitions_pd_arrays_structure#72 A2-open-float | partial | `open_float_pools`, `float_denied_bars`, `float_denied_adr` | False, 20, 0.3 | `ld3.float_pools`: untaken swing highs (lows) formed after the day's extreme, only while continuation is denied (no new extreme for N bars, range since it under k x ADR5); the consolidation-duration weight of `pool_rank` is not built
- definitions_pd_arrays_structure#74 A24-implied-fvg-defined | already built (`implied_fvg`) | `implied_fvg` | False | `levels.implied_fvgs` + the entry path (A24.1); only the rulebook text moved (A5 bullet, A24 list)
- definitions_pd_arrays_structure#75 A11-htf-gap-own-tf | done | `balance_tf` | "own" | `htf._arr_alive(bal=)`: "own" = completed weekly closes retire a weekly array (and weekly extremes decide its draw), "next_lower" = 4h closes for a daily array; the Confluence arrays already use own-TF closes; "legacy" = the earlier weekly-on-daily-closes behaviour; OWNER QUESTION 6
- definitions_pd_arrays_structure#85 A7-immediate-rebalance-definition | done | `ir_def`, `ir_overshoot_ticks`, `ir_body_mult` | "a7", 2.0, 1.5 | `levels.immediate_rebalances(mode=)`: "open_space" (the candle that bounds the open space: the most recent earlier candle whose high is below every low since [our interpretation]), "zero_width" (large c2, c3 low == c1 high to the tick); read by `Side.irs` (so `_ir_in_leg` and M11a `ir_entries`), entries are tagged `ir_fast_<mode>` (also on the `imm_rebalance_disp` path); review fix: `immediate_rebalances_ex` returns the bound level and the displacement candle (the nearest one) so `ir_entry` takes its level, EQ and stop from the right candles; the Silver Bullet's own `sb_model.immediate_rebalance` is not switched
- definitions_pd_arrays_structure#90 A12-open-vs-wick-gap-criterion | done | `ob_anchor_rule`, `ob_anchor_passes` | "wick_len", 2 | `levels.ob_anchor_state` (closed_in / gap / rule; the displacement candle that leaves the wick area is not an extra pass [our interpretation]) in `entries.ob_entry_price` (pre-break OB) and the Ep08.5 anchor entry; the ~5 pip probe allowance beyond the open and the body-midpoint invalidation (cc04_013) are not built; "twice" counts overlapping bars
- definitions_pd_arrays_structure#91 A12-tf-relative-ob | partial | `htf_ob_ltf_drill` | False | `htf._arrays(drill=)`: a wrong-coloured swing-extreme daily candle takes the last opposite-colour 1h bar at / before its extreme (open .. extreme, MT = body midpoint); the "also the high of an inefficiency" weight and the Confluence (4h / 1h) arrays are not drilled
- definitions_pd_arrays_structure#93 A6-breakaway-depth-qualification | partial | `bk_depth`, `bk_state`, `bk_bpr_ce` | "ce", False, False | `levels.bk_state` (candidate / retraced / qualified / dead); `targets.breakaway_gap(p)` feeds `trail_breakaway` and `ladder_trail` "breakaway"; entry tag `bk_<state>` (review fix: a qualified gap later filled is dead); the IFVG-as-breakaway measuring target (084) and the 075 close-into-it variant are not built
- definitions_pd_arrays_structure#95 A9-vi-breakaway | partial | `vi_breakaway` | False | `levels.vi_breakaway` (consolidation / mss / leg) drops a breakaway VI from the VI entry zones (`extra_entry_zones`); an opposing VI that left a consolidation is dropped from `vi_targets` (the mss / leg clauses need a setup, so only the consolidation clause applies to targets); VIs in the bias table / Confluence are untouched
- definitions_pd_arrays_structure#96 A6-gap-hierarchy-common | partial | `gap_classes`, `trail_skip_common` | False, False | `ld3.gap_class` (breakaway / measuring / common) tags the entry gap `gap_<class>`; CC body gaps `levels.common_gaps_cc` tag `cc_common`; `trail_skip_common` stops the new-FVG trail and `trail_first_fvg` behind a common gap; `levels.common_gaps_cc` requires the whole candle below the space [our interpretation]; partials / adds referencing breakaway / measuring gaps and the CC common gap as a trend-direction limit zone are not built
- definitions_pd_arrays_structure#105 L7-org-close-and-direction | done | (none) | | verified: `org_close` auto = the last RTH bar before the session close (ES 16:10 5m bar = the 16:14 1m bar, SPY 15:55) - test; new `Trade.org_dir` ("discount" / "premium"); OWNER QUESTION 9
- definitions_pd_arrays_structure#116 new-single-candle-daily-inefficiency | partial | `single_pass_draw` | False | `levels.single_pass_ranges` (large candle, none of the 5 bars before it above its low) as typ "spr" daily arrays (levels 0 / 25 / 50 / 75 / 100% on `Arr.levels`); the table draws the ladder CE -> 25% level -> candle low (`htf.spr_target`, skipping traded levels) until a later low / high trades through the candle; the LTF BISI lows inside it are not built
- definitions_pd_arrays_structure#117 A5-vi-extended-ce | done | `fvg_vi_extend_ce` | True | verified the extended zone's CE (`fvg_ce = (top + bottom) / 2` of the extended zone) and added the wick-linked VI case (`ld3.vi_link`); only acts with `fvg_vi_extend`; OWNER QUESTION 10
- definitions_pd_arrays_structure#118 A11-balanced-range-body-filled | done | `balanced_range` | False | `levels.balanced_bodies` (>= 3 overlapping candles both ways, then a displacement departure; EQ in `levels`); `ld3.balanced_filter` adds the near edge / EQ as array targets and drops everything past the EQ of a range above the entry unless a close since went beyond its top
- definitions_pd_arrays_structure#123 M1-original-consolidation | done | `orig_consol`, `orig_consol_touches`, `orig_consol_tol_pts` | False, 3, 0.5 | `levels.smooth_edge_range` used by `mmxm_ctx` (the draw is the smooth-edge level around the parent swing high); `orig_consol` is an added on-switch (the spec lists only the two tuning numbers)
- definitions_pd_arrays_structure#127 A21-consolidation-range-def | partial | `consol_body_range`, `consol_eq_touches` | False, 2 | `levels.consolidation_box` (max / min body, EQ touched from both sides); acts on the N8 `consol_pools` range and the B21 daily consolidations; the `delivery_state` box of item 125 is another package (the switch is an opt-in until then); OWNER QUESTION 8
- definitions_pd_arrays_structure#128 A3-clean-high | done | `eq_min_sep_bars` | 0 | `equal_clusters` / `equal_levels(bars=, min_sep=)` and `_eq_levels`; with the switch on a slightly higher second high no longer spends the first (the pool is the cluster's most extreme price)
- definitions_pd_arrays_structure#134 A1-impulse-swing-unit | done (helper) | (none) | | `levels.impulse_legs` (review fix: a leg ends at the FIRST swing after the opposite-type run, so the answer at a bar never changes with later bars) / `leg_is_impulsive`; not wired into `ote` / `leg_pd` (the A21 `leg_anchor="energetic"` anchor carries the same test) and the parent-leg choice (item 130) belongs to another chunk
- definitions_pd_arrays_structure#140 A12-void-up-down-ob | partial | `void_rt_ob` | False | `levels.void_round_trip_obs` (causal: known when the drop has reached the rally's low) as OB arrays in the bias table (D / W) and the Confluence arrays (4h and above); the LTF refinement is not built
- definitions_pd_arrays_structure#142 A15-stoprun-variant | done | `mit_def` | "a15" | `levels.mitigation_blocks(variant="stoprun")` (review fix: every confirmed swing high of the last 6, not only the newest, can be U) read by `Side.mitigations` / `opp_mits`; "trades back above U" = a close above U's high [our interpretation]
- definitions_pd_arrays_structure#156 M4-failure-swing-no-new-extreme | done | `fs_def` | "m4" | `levels.failure_swing(fs_def=)`; `cc_failure_order` also skips the intact-level test under "no_new_extreme" (the first swing may have traded through K)
- definitions_pd_arrays_structure#161 B21-data-range-fv-eq | done | `ipda_fv`, `ipda_consol_eq` | False, False | `ld3.build_ipda_x` (open daily FVGs and `levels.daily_consolidations` of the 60 sessions the windows end on); array targets via `_lv_target_arrays`; `_ipda_eq` tests price against the consolidation EQs with no CPI / NFP / FOMC; the consolidation thresholds are ours (>= 5 bars, bodies <= 1.5x the mean range); one 60-session set is used (a superset of the 20 / 40 / 60 windows; per-window distinctions are not drawn); an FVG is open until one bar spans it
- definitions_pd_arrays_structure#167 A5-twice-traded-not-fvg | done (with #90) | `ob_anchor_rule` | "wick_len" | counted with item 90 (same switch, variant `A5-twice-traded-not-fvg`)

### Tests (caption-gap pass, levels_detectors#2/3)

`tests/test_caption_gap_ld2.py`: unit / plumbing tests for every item (detector fixtures with the spec cases, Params defaults and validation, `htf_kw` / `table_kw`, the study variants, every new switch named by a test) and 4 no-look-ahead runs (full vs truncated at entry AND exit times: two switch groups and a post-MSS set on synthetic 5m 2026-04-06..05-08, and ES 5m 2023-10-16..11-10 with the HTF array definitions, the rebalanced NWOG / Monday NWOG, session opening ranges and the IPDA data range - skipped without `data/mentorship/ES_5min_db.csv`). Look-ahead findings fixed while building: `void_round_trip_obs` first reported the zone at the END of the drop run (the answer at a bar depended on later bars); it is now known at the first bar the drop reaches the rally's low.

### Review fixes (caption-gap pass, levels_detectors#2/3)

Fixed: `bk_state` keeps scanning after qualification (a qualified gap later filled to the far edge / CE is dead, #93); `mitigation_blocks(variant="stoprun")` tries every confirmed swing high of the last 6 as U (#142); `htf.opening_gaps` Monday variant finds the Monday after the break (a Sunday-bar frame no longer loses every NWOG) and the new `nwog_cfd_src="sunday_else_monday"` is the real per-weekend fall-back (#68); `balance_tf` default is now "own" (#75, owner question 6; `backtest.table_kw` always passes it); `nwog_redelivery` is selective (gap > 2 pts, first 5 sessions, lone exit FVG that closes outside the gap, un-rebalanced by a later full redelivery to the far edge; 17 of 51 ES NWOGs in 2023 instead of 27, #18); `ir_entry` takes the bound level / displacement candle / EQ of its own definition (`immediate_rebalances_ex`, `Side.ir_info`; `ir_fast_<mode>` also on the `imm_rebalance_disp` path, #85); engineered pools: `engineered` tag, score (opposing FVG known by the creation bar) breaks ties, counted as rel-eq in the sweep pick (`eq_pref` rank / require, #5); the A2 round-handle confluence refs are old highs / lows, rel-eq, active-old and engineered pools only (#2); `consol_body_range` is an opt-in again (#127, owner question 8); `impulse_legs` is causal (a leg ends at the first swing, #134); the study variant for `balance_tf` "own" is now `..._legacy`; `common_gaps_cc` interpretation marked (#96); "inert switches" warnings removed from the tests.

Still not built: #72 consolidation-duration weight of `pool_rank`; #91 the "also the high of an inefficiency" weight and the 4h / 1h Confluence array drill; #93 IFVG-as-breakaway measuring target (084) and the 075 variant; #95 `vi_breakaway` in the bias table / Confluence rows and the mss / leg clauses for opposing-VI targets; #96 partials / adds referencing breakaway / measuring gaps and the CC common gap as a trend-direction limit zone; #116 LTF BISI lows inside the single-pass range; #127 the delivery-state box; #140 LTF refinement of the void round-trip OB; #90 the ~5 pip probe allowance and the body-midpoint invalidation (cc04_013); #117 the ~2 pt weekly overshoot allowance for the extended-zone CE; #5 target-side ranking by engineered score; #134 wiring `impulse_legs` into `ote` / `leg_pd` and the parent-leg choice (item 130); #161 distinct 20 / 40 / 60 window handling; #105 `org_dir` on `DayCtx` (only `Trade.org_dir`, empty before 09:30 even for a later fill).

`tests/test_caption_gap_ld2_review.py`: unit tests of each fix, prefix-invariance tests of every new detector (zone detectors, immediate rebalances in all three definitions, impulse legs, engineered pools, `bk_state`, `ob_anchor_state`, `nwog_redelivery`, `nwog_rebalanced` on ES), table-level tests of every HTF array switch (each changes the bias table on real ES bars - except `void_rt_ob`, which prints no round trip there, and the Sunday-bar `sunday_else_monday` - and none looks ahead), and one engine test per study variant of the package (`PINS`): on a pinned 2-week ES window the switch must change the entries / stops / targets / tags OR the pools and targets the engine saw (`_trace_run` records `_targets` / `_sell_side` per closed bar), the truncated runs must see exactly the same per bar before the cut, and the entries / exits of runs cut at entries and exits must match (variants that act only through the bias table or equal the default on ES are named in `TABLE_ONLY`).

## Caption-gap pass: levels_detectors#3/3

27 specs: `rulebook_gaps/levels_liquidity_targets.md` (19, 28, 40, 42, 70, 74, 76, 87, 104, 112, 113, 114, 116, 127, 128, 129, 130, 148, 165), `models_setups_entries.md` (41, 67, 137, 138, 197) and `times_sessions_macros.md` (21, 22, 29). Detectors in `levels.py` (reactionary highs, parent pools, three-touch trendlines, head and shoulders, IPDA forward intervals / sequence, monthly candles, the time-distortion mask and FVG body hold, `order_block_blend(outside=)`), `htf.py` (the RTH weekend gap `nwog_rth`, the holiday-week NWOG pick, `tf_lookback` for the table), `confluence.py` (`tf_lookback` array lives, `min_known`), `bias_day.py` (`tue_open_ref`), `ld2.py` (`ipda_windows` incl. the 63 / 126 / 252-session windows and the "current_month" anchor, `ob_blend(outside)`, the FVG hold in `gap_open`), `ld3.py` (`sor_windows`), engine glue in the new `ld4.py` (pools, draw prefs, gates / tags, ORG state, wick state, H&S order); 36 Params switches (all default to the built behaviour), study variants named by gap id (`_LD3B_DECISIONS`), `tests/test_caption_gap_ld3.py`, rulebook text and this log. Engine plumbing: `run_day(prev_full=)` (the previous trading day's full frame: previous London range, LR zone), `backtest.hist_days(p)` widens the history for the long windows (default still 61), `backtest.day_kwargs` passes the day's open for the holiday pick.

Items (file#N gap-id | status | Params switch(es) | default | note):

- levels_liquidity_targets#19 L5-rth-and-eth-gap-views | done | `gap_views` | "auto" | "both" adds kind `nwog_rth` (the last RTH close of the Friday - the last bar starting before `org_close` / `session_close` - to the Monday 09:30 open, known when that bar closes, so a Monday's own RTH gap is in force from Tuesday) next to the ETH `nwog`, no de-duplication; `htf.gaps_for_day` selects both with the NWOG rules; review fix: `nwog_rth` follows the NWOG rules everywhere they are applied (`weekly_gap_ce_only`, `nwog_quarters`, the A8 "nwog" inversion arrays, the halfway rule, the lock candidates) and the holiday "closest" pick treats the ETH and RTH rows of a weekend as ONE NWOG
- levels_liquidity_targets#28 L5-holiday-nwog | done | `nwog_holiday_pick`, `tue_open_ref`, `tue_open_time` | "all", False, "0930" | "closest" (with `nwog_skip_holiday`): when THIS week's NWOG is dropped as a holiday week only the remaining NWOG closest to the day's first-bar open (midnight; causal) stays (distance to the gap range, then to its CE), none if there is none; review fix: the candidates are the 60 trading days (`nwog_days` when set), not `nwog_keep`; `tue_open_ref`: a week with a holiday Monday uses the Tuesday opening as the `weekly_open` reference (from that bar on, the completed Tuesday session later; before it no filter) - `bias_day.tue_open_ref`; review fix: `tue_open_time` "0930" (indices) / "midnight" (FX, the 00:00 bar)
- levels_liquidity_targets#40 L7-org-lifetime-sr | done | `org_both_ways`, `org_revisit_gate` | False, False | `ld4.org_state` (up_done / dn_done / the furthest point inside the gap per direction, from the regular sessions since formation + full sessions after the formation day when the eth dict is there + today's bars through the bar); both-done ORGs leave `_targets`, the sell-side ORG levels and the lock; pending targets = [partial extreme, far edge] (0 / 25 / 50 / 75 / 100% inside it); `org_days` up to 60 (the history grows with it); review fix: `org_revisit_gate` - today's revisit of an ORG high / 75% / CE counts only inside 10:00-11:00 / 14:00-15:00 / 15:00-16:00 with a valid confluence array (any timeframe) within 1 pt of the level (NWOGs exempt; the history before today cannot be time-gated)
- levels_liquidity_targets#42 L10-older-daily-weekly-wick-ce | done | `wick_untraded`, `wick_weeks`, `wick_lod_tag` | False, 1, "off" | `ld4.build_wicks`: a wick CE is kept only while no later completed daily bar traded through it by a tick (weekly: the last `wick_weeks` completed weeks, > 1 turns the weekly list on); review fix: today's bars so far count as trading through it too (targets: through bar i; the LOD tag: the bars before the sweep extreme); `wick_lod_tag` tags `wick_lod` when the sweep extreme is within 2 ticks of an untraded lower-wick CE (a short: upper) within 1 pt of a 5m / 15m same-side array (confluence arrays, else the base-bar FVGs); "require" rejects the others, review fix: only on days biased the trade's way (where the LOD expectation applies)
- levels_liquidity_targets#70 new-reactionary-high-liquidity | done | `reactionary_pools`, `reactionary_precond` | False, False | `levels.reactionary_highs` (a pivot high followed within 3 bars by a displacement down-close - body >= `displacement_mult` (1.5 if 0) x the mean of the 10 bars before it - that trades below the pivot candle's low): the latest untaken one is a buy-side `_targets` pool and the `_draw_prefs` draw ("draw_reactionary"); the mirror (reactionary LOW) is the sweep pool `reactionary_lo`; review fix: `reactionary_precond` - price at least 0.5 x ADR5 below the high and no 15m FVG between the close and it [our interpretation]
- levels_liquidity_targets#74 new-parent-pool-bodies-short | done | `parent_pools`, `parent_n` | False, 2 | `levels.parent_pools` (n >= `parent_n` later swing lows within 0.25 x ADR5 above L0 whose bodies stay above L0's low, L0 untaken by wick THROUGH `end` (review fix; it was checked only up to the confirming bar), known at the n-th later low's confirmation): buy-side mirror in `_targets` + `_draw_prefs` ("draw_parent"), sell side `parent_lo<price>` sweep pools; the intermediate levels stay rungs
- levels_liquidity_targets#76 L2-sr-needs-fvg | done | `daily_level_needs_array` ("fvg"), `flip_retest_entry` | False, False | "fvg": the swept daily level needs a same-side FVG (Confluence src 0, `daily_level_array_tfs`) within a tick of it (`ld4.daily_fvg_ok`); review fix: `flip_retest_entry` builds the setup - `ld4.flip_order`: an old swing high (the short's broken low is the mirror) a body close has broken, with an FVG of the breaking leg within a tick of it, the bias for the side: a resting limit at that FVG's CE (stop under the gap, pad), armed once per (level, gap), while price is above the gap and the gap is open (OWNER QUESTION 13 answered by building it)
- levels_liquidity_targets#87 L1-prior-day-london-pm-pools | done | `prev_london_pool` | False | `ctx.sess["prev_london"]` from `run_day(prev_full=)` (the `hist` frames are regular-session only), read by the existing `sess` loops (`_targets`, `_sell_side`) and the lock candidates
- levels_liquidity_targets#104 new-lookback-per-tf-topdown | done | `tf_lookback`, `tf_pools` | {}, False | {"D": 252, "4h": 63, "1h": 15, "15m": 4} trading days: the Confluence array lives per timeframe, the `htf.table` daily lookback (NWOGs keep 60), the daily pivot history (`ld3.daily_hl`) and `hist_days`; review fix: the DayCtx higher-timeframe FVG zones (`p.htf` 15 / 30 / 60 / 240 minutes) honour their own window, and `tf_pools` adds the untaken swing highs / lows of those bars inside their window and older than the prior session as pools (3 nearest per timeframe; sweep pools `tfp<label><n>`, buy-side `_targets` pools; tag `tf_<label>`; `ctx._tp_pool_tf` carries the minutes so `pool_rank` ranks them by timeframe). `confl_rank` (item 94) is another package
- levels_liquidity_targets#112 L3-monthly-ohlc-3m | done | `monthly_ohlc`, `monthly_frame` | False, False | `levels.monthly_candles` (the last 3 completed months from the daily history; review fix: a first month the history starts on the first trading session of is complete, `ld4.history_starts_month`; `hist_days` >= 90) -> `ctx.m_ohlc` (12 levels), lv_tag `m_ohlc` on an entry / target within 1 pt; the scoring input: the 12 levels count as converging levels in `converge_rank` (`ld2.converge_n`); `monthly_frame`: `levels.monthly_range_frame` = the most recent down-close month's low to the high of the most recent up-close month whose high exceeds it [our interpretation] -> `ctx.m_frame`, tags `m_frame_disc` / `m_frame_prem`
- levels_liquidity_targets#113 L3-htf-pd-arrays-intraday | done | `htf_targets` ("W" / "M"), `htf_monthly_arrays` | , False | the Confluence object already builds the "W" and "M" arrays and `_lv_finish_targets` / `_finish_order` read them by label, so `htf_targets` accepts "W" / "M" as is; review fix: `htf_monthly_arrays` - `htf.table(monthly_arrays=True)` builds the monthly FVG / OB arrays (`htf.months`, the analogue of `weeks`; known from the session after the month's last; react weight 3 [our interpretation])
- levels_liquidity_targets#114 L3-3-6-12-month-pools | done | `ipda_windows` | (20, 40, 60) | any non-empty subset of (20, 40, 60, 63, 126, 252) in `ld2.ipda_windows`; `hist_days` grows with the longest; `_ipda_eq` keeps using only 20 / 40 / 60
- levels_liquidity_targets#116 new-trendline-trap-target | done | `trendline_pools` | False | `levels.trendline_highs` (H1 > H2 > H3 pivots, the middle one within 0.1 x ADR5 of the H1-H3 line, newest first): H2 + 1 tick is a buy-side pool for a sweep whose extreme bar lies between H2 and H3 (or re-runs the low between them after H3); OWNER QUESTION 15
- levels_liquidity_targets#127 B21-reference-points-in-windows | done | `ipda_rb`, `ipda_arrays`, `ipda_window_arrays`, `ipda_frame` | False x4 | `ipda_rb`: a window extreme whose wick is longer than its body takes the body edge as the pool (sell side: the lower body edge), the wick extreme is an `array` rung (`ld4.ipda_level`); `ipda_arrays`: review fix - `ld4.build` replaces `ctx.conf` by `Confluence.windowed({"D": ipda_since})`, so EVERY merge (main scan, Silver Bullet, `entries.py`, `targets.htf_levels`) reads only the daily arrays known inside the 60-session window, and `htf.table(ipda_window=<anchor>)` limits its daily arrays / swing draws the same way (`levels.ipda_end_index`, the shared anchor rule); `ipda_window_arrays`: the daily OBs and liquidity voids of the window are array targets beside `ipda_fv`'s FVGs; `ipda_frame`: framed off the window LOW when yesterday closed in the upper half of the longest window (tags frame_low / frame_high, ipda_disc / ipda_prem)
- levels_liquidity_targets#128 B21-progression-20-40-60-beyond | done | `ipda_roll_arrays`, `ipda_beyond_days`, `ipda_converge` | False, 0, False | `levels.ipda_sequence` (with `ipda_next`): equal windows are skipped, the 20-day window rolls out when every bearish daily FVG AND OB of its 20 sessions has been traded to (`ld4.arrays20_exhausted`, an empty window is not 'exhausted'), once all are taken the nearest older daily pivot within N sessions (older than the longest window) is the draw and lv_tag `expansion`; `ipda_converge`: a window extreme within 0.25 x ADR5 of an open premium daily array (FVG / OB) is the preferred draw (tag `ipda_converge`)
- levels_liquidity_targets#129 B21-open-float-forward-windows | done | `ipda_forward`, `ipda_recompute` | False, False | `levels.ipda_forward`: the completed 20-session forward intervals of the anchor `ctx.ipda_D` and the realised D-60..D+59 float as pools (`ipda_f20` / `ipda_f40` / `ipda_f60` / `ipda_float`); pools that are the extreme of two windows are the preferred draw ("draw_ipda_multi"); review fixes: the back windows end BEFORE D with `ipda_forward` for every anchor ("month" always did; "current_month" / "swing" used to include D, which the forward f20 also starts at); `ipda_recompute`: `levels.ipda_markers` - the 20/40/60 look-backs ending at each forward marker D+20 / D+40 / D+60 reached are pools (`ipda_m<j>w<n>`), ranked with the multi-window levels; the forward pools are lock candidates (`mark_levels`). With the "current_month" anchor an interval completes only as the month ends (the anchor then moves): the "month" anchor shows them sooner. Needs an anchored `ipda_anchor`
- levels_liquidity_targets#130 B21-anchor-month-vs-daily | partly built earlier + new value | `ipda_anchor` | "rolling" | "rolling" = daily and "month" (the LAST CLOSED month's first day, not the spec's current month) were built in bias_htf_intermarket#128; new here: the "daily" alias and "current_month" (the windows end ON the first trading day of the current month, fixed all month; on that day itself, which is not complete, they end yesterday) - the spec's behaviour is the new value; OWNER QUESTION 12 (rename the values?) stays open
- levels_liquidity_targets#148 LLT3-london-extreme-preny-range | done | `london_lr_zone`, `ny_hl_frame` | "off", False | `ld4.lr_build` from `prev_full` (E = London high, O = the lowest low between E and 09:30, and the bullish mirror): a short in the premium half of (O, E) up to E itself (a tick of slack) is tagged `in_lr` (the long: the discount half of the mirror; the upper bound is [our interpretation]: "within LR"); "require" rejects the others on days whose bias is the trade's side; `ny_hl_frame`: the prior NY session (09:30-16:00) high / low (`ctx.ny_hl`), tag `in_ny_range` for an entry inside it
- levels_liquidity_targets#165 LLT3-0800-0900-pool-stock-open | done | `or0809_pool` | False | adds (480, 60) to `session_ors` (`ld3.sor_windows`): AM sell-side / buy-side pool from 09:00 and a lock candidate
- models_setups_entries#41 A17-rejection-block-short-protocol | done | `rb_pools` | False | the typ "rb" arrays of `htf._arrays(rb=True)` (`levels.rejection_blocks`, `rb_level` "close", 3-candle pivots; level = the swing candle's close, `src_i` the candle); `htf.table(rb_closes=True)` lists the nearest untaken ones as rb_up / rb_dn and never lets them into the bias columns; `ld4.rb_build` reads the same arrays (untaken ones, the three nearest each) -> sweep pools `rb<n>` (not against the bias) and `_targets` rungs, the MSS after their sweep is a wick pierce (`_scan_core`); computed per day in the DayCtx
- models_setups_entries#67 A12-entry-ob-outside-fvg | done | `ob_outside_fvg` | False | `levels.order_block_blend(outside=)` (candles whose range lies inside the zone are skipped, the blend stops at an opposite-close candle); used by `_ob_at_low` (first FVG after the sweep extreme; also what `entry_arrays` "ob" reads), the FVG-path OB (`ld2.ob_blend`, zone = the entry gap), `_ob_anchor`, the `mss_cisd` reference and (review fix) `setups.ob_low` (the displacement-gate and FVG-choice setups); `entries.ob_blend` is unused
- models_setups_entries#137 new-trendline-trap | done | `trendline_trap`, `tl_tol_ticks`, `tl_trap_entries`, `tl_tol_adr` | False, 4, (), 0.0 | the low between H2 and H3 (side space) is the priority sweep pool `tl23` when `cur_bias` is the trade's side, the sweep must be a turtle-soup poke within `ts_max_pts`, H2 + 1 tick starts the ladder; review fix: `tl_trap_entries` ("ob", "breaker") - `ld4.tl_trap_order`: a resting limit at the bullish OB of L23 (the engine's `_ob_at_low` at the low; "just above" = within `ts_max_pts`) or an LTF bullish breaker reaching the L23 area, price not through the old low, armed once per (L23, kind), stop beyond L23, fixed ladder [H2 + 1 tick (pool), the daily draw of the htf row]; `tl_tol_adr` > 0 unifies the touch tolerance with `trendline_pools` (OWNER QUESTION 15)
- models_setups_entries#138 new-hs-fade | done | `hs_fade`, `hs_tf`, `hs_stop_pts`, `hs_rearm` | False, 60, 0.0, False | `levels.head_shoulders` on `hs_tf` buckets (closed buckets only) + `ld4.hs_order`: a resting limit `ts_cc_below_pts` under the neckline lows (price above them, untraded since the right shoulder was confirmed), bias and a same-side HTF array (review fix: the gate no longer depends on a confluence object - the HTF FVG zones of the frame decide without one, and with neither the pattern is not traded), fixed ladder [S2, head + pool exit], stop `hs_stop_pts` below the entry (else the `ts_max_pts` stop); the inverse shape is the mirrored side; `hs_rearm`: re-armed once per run of the neckline lows (a bar a tick under them, then a close back above)
- models_setups_entries#197 new-intra-week-extreme-raid | done | `week_pools`, `week_raid_days` | False, (1, 2, 3) | pools `week_hi` / `week_lo` = the week so far: the completed sessions of the week (full sessions when the eth dict is there), the evening before today (`run_day(eve=)`, `dw_needs_eve` now also for `week_pools`; the Sunday evening for a Monday) and today's own earlier bars (`ld4.week_now`, per bar); highs Tue-Thu, lows also Monday; the Monday / Tuesday raid of the low also has the prior Friday's low and the previous week's low as pools (`week_lo_pf`, `week_lo_pw`; `ld4.week_prior_lows`); a sweep of one needs a same-side HTF array (own check in `ld4.order_gate`); lock candidates too
- times_sessions_macros#21 T4-or-length | done | `or_minutes` (accepts 20) | 30 | validated to {0, 20, 30, 60}; `ctx.or20` (09:30-09:49 high / low) is always built; OR20 is a pool from 09:50 (`or_end` = 590); OWNER QUESTION 14
- times_sessions_macros#22 L3-or-refs-expire-1100 | done | `or_expire`, `or_fvg_entries` | 0, False | `or_expire` (e.g. 660) removes the `opening_range` pool / target / sweep level from that minute; `or_fvg_entries`: the FVGs formed inside the OR window are entry zones (alive, between the sweep extreme and the close) for setups armed 10:00-11:00 in the main scan AND (review fix) in the Silver Bullet array list (`sb_model._arm_all` candidates tagged `or_fvg`; the Silver Bullet itself stays off by default, `sb_use_bias` / `want_all_engines` untouched)
- times_sessions_macros#29 new-time-distortion | done | `time_distortion`, `td_lunch`, `td_fvg_hold` | False, True, False | `levels.time_distortion_mask` (15 min before each `release_times(day)` entry, from 16:00, 12:10-14:00 with `td_lunch`); review fix: `ld4.attach_td` drops from every Side the swing points and the zones defined on a masked bar (`Side.ph / pl / gaps`, the lazily built inverted FVGs, VIs, mitigation / propulsion sources, breakers, HTF-bar zones, opposing arrays - `Side.td_mask`, `ld4.td_filter`), so pools, relative equals, the MSS reference, entry zones and the Silver Bullet arrays never read them; a pool run in a masked bar starts no sweep; an order-block candle of a masked bar is no OB; the MSS break bar and the extra entry zones (VI, void, reclaimed, HTF, inverted, OR) are masked too; (a) `td_fvg_hold`: 5+ bars with bodies inside the gap and wicks poking out in 10:00-12:00, AFTER the session extreme is set (the extreme precedes the gap's first candle), keeps a gap valid for any gap kind (`gap_open` for single-bar gaps, the `fvg_state_filter`, tag `td_hold`)

### Review fixes (caption-gap pass, levels_detectors#3/3)

Built (were partial / not built): the flip-retest setup at the FVG CE (#76 `flip_retest_entry`); the rejection-block closes as typ "rb" arrays of `htf._arrays` and the `rb_up` / `rb_dn` table columns (#41); the trendline-trap OB and breaker entries and the ladder H2 + 1 tick then the daily draw (#137 `tl_trap_entries`); the H&S re-run re-arm and an array gate without a confluence object (#138 `hs_rearm`); `ipda_arrays` on every merge via `Confluence.windowed` and in `htf.table(ipda_window=)`, the in-window OB / void list and the window frame (#127 `ipda_window_arrays`, `ipda_frame`); per-timeframe windows of the DayCtx zones and the tf pools with their source-timeframe tag (#104 `tf_pools`); the monthly range frame, the scoring input and the complete first month (#112 `monthly_frame`); monthly arrays in `htf.table` (#113 `htf_monthly_arrays`); the OB side of the 20-day exhaustion and the convergence preference (#128 `ipda_converge`); the marker recompute, D outside the back windows and forward lock candidates (#129 `ipda_recompute`); the Monday low raid, the evening and today's bars in the week so far, the Friday / previous-week blend (#197); the OR FVGs in the Silver Bullet array list (#22); time distortion on every swing / zone source, the sweep, the OB candle and the body hold for any gap (#29); `setups.ob_low` with the outside zone (#67); the revisit gate of the ORG (#40 `org_revisit_gate`); today's bars in the untraded-wick checks and the `require` scope (#42); `reactionary_precond` (#70); `parent_pools` untaken through `end` (#74); `tl_tol_adr` (#116, owner question 15); `ny_hl_frame` (#148); the 60-day / one-weekend closest pick, `tue_open_time` and `nwog_rth` following the NWOG rules (#19, #28). #130 relabelled (partly built earlier + the new value). The lr_state upper bound is labelled [our interpretation]. 15 new switches in all (tuning numbers and defaults off): `flip_retest_entry`, `tl_trap_entries`, `tl_tol_adr`, `hs_rearm`, `htf_monthly_arrays`, `tf_pools`, `ipda_window_arrays`, `ipda_frame`, `ipda_converge`, `ipda_recompute`, `monthly_frame`, `ny_hl_frame`, `tue_open_time`, `org_revisit_gate`, `reactionary_precond`; 14 study variants (`_LD3C_DECISIONS`, name prefix = gap id).

Tests: `tests/test_caption_gap_ld3_review.py` (units for every fix; spec-named `test_or20_pool`, `test_or_refs_expire`, `test_time_distortion_mask` are aliased in `tests/test_levels_detectors.py`) and no-look-ahead runs (full vs truncated at entry AND exit times) on a synthetic futures frame WITH overnight bars (`syn_overnight`: opening gaps, Confluence, HTF table, eth sessions - the paths the plain `B.synthetic` frames never reached: wick_lod, daily_fvg_ok, conf_targets / ipda_since, the week and H&S array gates, multi_window_levels, the ipda_level body-edge branch, the expansion tag, ...); `ld4.HITS` (a plain call counter, no effect on results) lets `test_every_review_switch_ran_in_the_synthetic_runs` ASSERT that each added switch's code path really executed in those runs (instead of a string-containment check); the ES run (skips without data) covers both groups on real overnight data; the month-anchor `ipda_forward` is in the synthetic "ipda" group. Not covered by an executed path in the synthetic runs (unit tests only): `hs_rearm`'s re-run (needs a repeated H&S run), the Tuesday reference (needs a holiday Monday in the traded window), `tl_tol_adr` (a tuning number).

Owner / process notes: the commit trailer of the three earlier levels_detectors commits reads "Claude Sonnet 5.5" (history is not rewritten); this commit carries the trailer of the model that wrote it. The first-pass spec-named tests are now aliased where the specs name them.

### Tests (caption-gap pass, levels_detectors#3/3)

`tests/test_caption_gap_ld3.py`: unit / plumbing tests for every item (detector fixtures with the spec cases, glue on stub contexts and on real DayCtx frames, Params defaults and validation, `htf_kw` / `hist_days`, the study variants, every new switch named by a test and in a look-ahead run) and no-look-ahead runs (full vs truncated at entry AND exit times: three switch groups and a post-MSS set on synthetic 5m 2026-03-16..05-08, and ES 5m 2023-09-18..11-10 with the gap view, anchored IPDA windows with forward intervals, previous London / LR zone, week pools, ORG state, wick state, rejection-block closes, `tf_lookback`, then the structure switches and the bias / weekly-open / holiday-pick set).

Checks run for this package: every new switch at its default leaves the trades of 28 earlier configurations (synthetic 5m 2026-04-06..05-15, seeds 3 and 5, default / bias / post-MSS / the levels_detectors#1 and #2 look-ahead groups; ES 5m 2023-10-16..11-10 and 2024-01-22..02-16 with the HTF, IPDA, ORG, wick, OB and implied-gap switches) identical to the commit before this package (old tree vs new tree, every column); all 29 new study variants pass the per-variant ES no-look-ahead run of `tests/test_bias_htf_lookahead.py` (`-k` on the variant names).

## Caption-gap pass: setups_models#1/7

Sources: `rulebook_gaps/bias_htf_intermarket.md` (2, 3, 19, 23, 42, 48, 49, 50, 51, 54, 67, 69, 89, 92, 98, 113, 123, 124, 126, 192, 199, 206, 207), `day_selection_news_calendar.md` (5, 6, 12, 21, 90, 91, 92), `definitions_pd_arrays_structure.md` (15, 16, 18, 19, 33, 46). Binding order: owner directives (none of the items changes a default; #7 revised stays the speed-bump rule), the item's build spec, rulebook / coverage. The engine glue is the new `sm2.py` (later setups_models chunks extend it); hooks in `strategy.py` (`_finish_order`: the open-tolerance grade in the use_bias block, `sm2.order_gate` after the levels_detectors gate, extra targets, late tags; `_scan_core`: sweep SMT bias gate, MSS reference, MSS / HTF agreement, breaker by close; `_breaker`; `_scan`: day-life breaker retests and the mitigation entry; `_smt`, `_smt_window_ok`, `_sell_side`, `_level_created`, `_after_close`, `run_day`: the release setups and `ctx.sides_map`), `setups.py` (`finish_gates`, `pm_reversal`), `backtest.combine` (the D15 picks), `levels.py` (`compressed_run` / `compressed_highs`), `report_decisions.m3_scan`, `study.py` (`_SM1_DECISIONS`, `study_pick`). Every new switch defaults off / to the built behaviour; the trades of 18 configurations (synthetic 5m seeds 3 and 5 x 5 configs, ES 5m two 4-week windows x 4 configs) are identical before and after (old tree = 0067553 in a worktree vs this tree, every column but the ten new ones).

Items (file#N gap-id | status | Params switch(es) | default | note):

- bias_htf_intermarket#2 BH-B12-midnight-open-tolerance | done | `open_tol_pts`, `wk_open_side` | 0.0, False | a wrong-side entry within `open_tol_pts` of the reference open is accepted when the session's extreme since 00:00 (13:30 PM) went beyond the open the Judas way AND an MSS followed it (`sm2.open_tol_ok`; an OB-before-the-break order has no MSS yet, so it stays strict); `Trade.open_grade` "best" / "allowed" (tagged while the tolerance is on); `wk_open_side` tags `Trade.wk_open_side` = sign(entry - the Sunday 18:00 open) (`_open_known(ctx, "sunday")`, from the evening session before a Monday / the completed first session's all-hours open later in the week; a tag only)
- bias_htf_intermarket#3 BH-B12-po3-sequence | done | `po3_seq`, `po3_seq_below_pts` | "off", 3.0 | (1) a bar traded beyond the reference open after 00:00 (13:30), (2) a LATER close back across it before the MSS bar, (3) entry within `po3_seq_below_pts` of the open on the right side; "tag" sets `Trade.po3_seq` (+ lv_tag), "filter" rejects orders without it (`x_po3_seq`)
- bias_htf_intermarket#19 BH-A8-opposing-FVG-inversion-confirms | done | `ifvg_narrative` | "off" | "block": against a bullish unmet draw (`ctx.cur_bias`) an entry inside an FVG of the order's own orientation that was already closed through the draw's way today is rejected (`x_inverted_against_draw`); "require" adds: a with-draw entry needs a bearish (side space) FVG formed today closed through, retested (a later low inside) and held (no close below its bottom) before the MSS (`x_ifvg_narrative`)
- bias_htf_intermarket#23 BH-B12-gap-up-short-below-0930 | done | `gap_premium_arm` | False | gap = the 09:30 open vs the prior RTH close, HTF array = a same-direction Confluence array (15m..W incl. gap rows, so an old NWOG CE) holding the open within `eq_tol_pts`; longs after a gap up rejected (`x_gap_premium_long`), shorts wait for a bar trading under the 09:30 open (`x_gap_premium_wait`); the sweep's SMT state is tagged `gap_premium_smt` / `gap_premium_nosmt`; no Confluence object = inert
- bias_htf_intermarket#42 BH-compressed-higher-highs | done | `compressed_hh`, `compressed_k`, `compressed_n` | False, 0.1, 3 | `levels.compressed_run` / `compressed_highs` (n consecutive pivot highs each higher by < k x ADR5, all above the dealing-range EQ = the middle of today's range [our interpretation]); a with-trend order whose MSS reference (`sw["ref_i"]`) is one of them is rejected (`x_compressed_hh`), the opposite order after an MSS below the run is tagged `compressed_hh` and the leg low (the low between the day's high before the run and its first high) joins the targets
- bias_htf_intermarket#48 BH-D15-sick-sister-laggard | partial | `smt_pick="laggard_objective"`, `laggard_consol_only` | "first", False | `backtest.objective_met_filter` (in `combine`): once a trade of one instrument reached its last ladder level (`final_hit`) and exited at T, that instrument's later fills go and only the other instrument's fills from T on stay; `laggard_consol_only` restricts it to consolidation days. PARTIAL: "objective met" is read from the trades' outcomes (causal at every later entry), not from the htf.table draw per instrument inside `run_day` (no engine-level `objective_met` tag)
- bias_htf_intermarket#49 BH-D15-middle-index | done (inert until a third series is loaded) | `smt_pick="middle"` | "first" | `combine(pick="middle")` keeps, per slot (date + session), the fill whose `Trade.move_pct` (the move from the session open to the entry in the trade direction) is the median of three instruments' fills (fewer than three fills in a slot: the first); fewer than three RUNS raise ValueError; the studies call `study.study_pick` (middle -> first with two books)
- bias_htf_intermarket#50 BH-D15-clean-swing-point | done | `smt_pick="clean_swing"` | "first" | `Trade.clean_swing` = a 15m pivot (n = 2, closed 15m bars only) between the entry and T1; `combine` keeps the fill that has one (none = the first)
- bias_htf_intermarket#51 D15-short-index-by-premium-depth | done | `smt_pick="depth"` | "first" | `Trade.array_depth` = how far the sweep ran into the highest HTF array of the side holding it (Confluence 15m..W, FVG / OB), `array_respect` = the share of the closed 15m bodies inside it that did not cross its far edge; `combine` keeps the deeper fill (ties: respect, then the earlier)
- bias_htf_intermarket#54 BH-M3-scan-all-indices | done | `markets` | ("ES",) | no engine change: `report_decisions.m3_scan(*books)` (days with a setup, in both markets, in one only, the share of one-market days, setups per day); the study runs the partner book when `len(markets) > 1`; decision variant `BH-M3-scan-all-indices`; rulebook decision 24
- bias_htf_intermarket#67 BH-three-pool-runs-exhaustion | done | `pool_runs_max` | 0 | `sm2.pool_runs`: the leg starts at the last MSS the other way (the other Side's last close beyond its latest confirmed swing extreme; the day's start without one), the pools = the other Side's named sell-side pools formed by then and the swing extremes before it, standing when the leg started and traded a tick through by it (levels closer than `eq_tol_pts` are one pool); >= `pool_runs_max` rejects every continuation order (`x_pool_runs_exhausted`)
- bias_htf_intermarket#69 BH-premium-FVG-CE-vs-far-edge-trap | done | `far_edge_trap` | False | the 60m same-side Confluence FVG holding the entry; the retrace into it (from the bar it was known) that came within 10% of its height of the far edge rejects the order (`x_far_edge_trap`), one held at / under the CE is tagged `ce_hold`
- bias_htf_intermarket#89 B18-am-smt-window-points | done | `smt_win_a`, `smt_win_b`, `smt_open_points` | 300, 570, False | the `smt_pre` window bounds are Params (test 120 / 660; like `smt_pre` alone, they act only together with `smt_windows`); `smt_open_points`: pools `open_0830` / `open_0930` (the opens that have printed, created the bar after the open; the partner twin is the partner's own open)
- bias_htf_intermarket#92 NEW-low-of-day-zone-tag-first | done | `lod_zone_first` | False | `sm2.lod_zone`: at 08:30 the nearest completed 60m candle tail CE (lower wick >= max(0.1 x ADR5, 4 x `eq_tol_pts`) [our interpretation of "tail"]) below the price with a 5m FVG of the side (or a daily array, standing in for the daily inversion FVG) within `eq_tol_pts`; no order until a bar's low <= zone + 2 ticks (`x_lod_zone_first`), then the sweep needs the SMT tag (`x_lod_no_smt`); mirror for a high of day
- bias_htf_intermarket#98 B18-smt-only-with-bias | done | `smt_with_bias` | False | at the sweep an SMT against the bias becomes False with `sw["smt_laggard"]` (tag `smt_laggard`); with no bias an SMT-qualified order is rejected (`x_smt_no_bias`)
- bias_htf_intermarket#113 B5-mature-trend-continuation | done | `mature_flag_block`, `mature_pd` | False, 0.62 | a with-trend order (the prior 5-day close-to-close trend) is rejected when the prior daily close is beyond `mature_pd` of the 20-day range (premium for longs, discount for shorts) or inside an opposing daily Confluence array (`x_mature_flag`)
- bias_htf_intermarket#123 M12-classic-patterns-fade | already built (`hs_fade`) | `hs_fade`, `hs_tf`, `hs_rearm` | False | levels_detectors#3/3 (`levels.head_shoulders`, `ld4.hs_order`: a resting limit under the neckline lows with the bias and a same-side HTF array, partial at the right shoulder, objective above the head); study variant `M12-classic-patterns-fade`; test alias `test_hs_fade_level`
- bias_htf_intermarket#124 X3-a15-mitblock-bear-context | done | `mit_needs_bias` (with `mitigation_entry`) | False | a mitigation-block entry needs `ctx.cur_bias` = its side and an untaken daily pool (`ctx.pd`) or daily array edge beyond; that level is the target (`fixed`)
- bias_htf_intermarket#126 X3-graduated-pricing-second-touch | done | `touch_tag` | False | `Trade.touch_n` (separate approaches within 4 x `eq_tol_pts` above the swept level since it formed, the sweep included); no gate
- bias_htf_intermarket#192 B12-judas-depth-adr | done | `judas_max_adr` | 0.0 | `Trade.judas_depth` = (reference open - sweep extreme) / ADR5 in side terms; > the max rejects (`x_judas_too_deep`)
- bias_htf_intermarket#199 T3-london-close-multiday-reversal | done | `lc_tag`, `lc_reentry` | False, False | `Trade.lc_reversal` (an order armed 10:00-12:00 whose sweep sat at an HTF array and ran under the 09:30 open); `lc_reentry`: after a stopped-out lc_reversal (exit 10:00-12:00) the slot re-opens once (`_after_close` -> `sm2.lc_reopen`) and every order of the re-opened slot must be the same direction, 10:00-12:00, beyond the first extreme at an HTF array (`x_lc_retry`). The AM scan window ends at `am[1]` (11:00 by default), so the effective retry window is 10:00-11:00 unless `am` is widened
- bias_htf_intermarket#206 D15-which-index-contradiction | done | `smt_pick="swept"`, `"fixed_es"` | "first" | "swept" = the "laggard" pick (the SMT-tagged fill), "fixed_es" keeps ES / MES fills only, the SMT tag of a slot (date + session) true for the ES fill when either instrument's tag diverged
- bias_htf_intermarket#207 B18-pm-smt-reference-points | done | `smt_pm_points` | False | `sm2.lunch_post` / `pm_points`: per instrument the 12:00-13:00 low and the first pivot low (n = 1) after 13:00; True when exactly one of them made the lower low
- day_selection_news_calendar#5 N1-nfp-release-4h-fvg | done | `nfp_release_fvg`, `nfp_release_fvg_min`, `nfp_release_fvg_add` | False, 5, True | a limit at the upper edge of the nearest 4h same-side FVG below price whose CE is under the 20-session range EQ [our interpretation of the swing range], the side from the bias known before 08:30 (`sm2.bias_at`: the lock-time cut row, else the Confluence daily / 4h trend), armed on the bar closing at 08:30 and valid until 08:30 + `nfp_release_fvg_min` minutes (the pending-fill block's `cut`); stop = the FVG low - the stop pad (the lower candle body is not on the array); 50% at the first pool, the rest to the table's draw, `be_at` = the first target (breakeven + the cost pad), one add of one lot at the CE; bypasses `nfp_floor_min` / `news_wait` / `nfp_first_hour` for itself only (session "NEWS", done key NFPR)
- day_selection_news_calendar#6 N6-nfp-first-move-fake-if-liquidity | done | `news_profile="pool_test"` | "off" | `sm2.news_move1` / `pool_taken` / `news_pool_gate` (in `setups.finish_gates`): a pool taken by the first leg = "require"; otherwise orders in the counter-move direction are rejected unless their sweep is at a 1h / 4h array of their side (`x_news_pool_counter`); tag `news_pool_test`
- day_selection_news_calendar#12 N5-entry-at-release | partial | `post_news_continuation`, `post_news_run_pts`, `release_ob_entry` | False, 5.0, False | (a) after the 08:30 run-out of >= `post_news_run_pts` in the bias direction, the first opposing candle after its extreme arms a limit at the body top of the last opposing candle before the extreme, stop under it, SD projections (the first two `sd_levels` from the leg high) as targets; (b) a 10:00 release day, the close at 10:00 inside an alive 5m OB of the bias side: a market entry at the 10:00 open, stop under the OB, one exit at the nearest 1m swing high above. PARTIAL: (b)'s "continue only if SMT / sick sister supports it" is not built (always the scalp); (a)'s adds follow the existing `ob_adds`
- day_selection_news_calendar#21 T13-judas-news-driver | done | `require_judas_news`, `judas_news_min`, `judas_news_tag` | False, 30, False | `sm2.judas_news`: the Judas sweep's extreme within +-`judas_news_min` of a release (`newscal.releases`); tag `judas_news`; `require_judas_news` (with `require_judas`) rejects the others (`x_require_judas_news`)
- day_selection_news_calendar#90 DS2-two-session-close-templates | partial | `profile_two_session` | False | PM only: the bias (`bias_at`) = the AM leg's direction (low-before-high and a close above the open for an up close), the AM extreme not in an opposing 4h / D / W Confluence array: orders only the bias way, the sweep key `lunch` (lunch-low sweep) or the entry in the lower half of the day's range (discount FVG tap); tags `two_session_up` / `two_session_down`. PARTIAL: the PM-leg ~= AM-leg measured move and the strong-catalyst "trends through lunch" caveat are not coded
- day_selection_news_calendar#91 DS2-am-move-pm-reversal-templates | done | `pm_reversal_pool`, `pm_reversal_ltf_only` | "am_high", False | M6 `pm_reversal`: "lunch_or_am" accepts the sweep of the lunch extreme even under the AM extreme; `pm_reversal_ltf_only` blocks it when the AM move's origin (the AM low / high) is inside a 4h / D / W / M Confluence array of the AM move's side
- day_selection_news_calendar#92 DS2-consolidation-profiles | partial | `profile_consol_pm` | False | PM only: neutral bias (`bias_at` = 0) and no release from 10:00; after an AM leg the counter side only, the sweep key `lunch` when the AM extreme sat in a 1h+ Confluence array of the AM move's opposite side, else `am_session`; the day's far extreme and London's opposite extreme are extra targets; forces the lunch pool into the PM pool list; tags `consol_am_rally` / `consol_am_decline`. PARTIAL: the AM variants (return to a discount array / expansion from the opening range EQ) and "the PM may just consolidate" are not coded
- definitions_pd_arrays_structure#15 A13-breaker-needs-rebalance-and-fvg | partial | `breaker_needs_disp`, `breaker_disp_bars`, `breaker_break_ref` | False, 3, "wick" | `sm2.breaker_confirmed` (inside `_breaker`): an FVG whose middle candle lies between the sweep extreme and the break, completed within `breaker_disp_bars` of the break; "body_high": a close >= the breaker candle's BODY high since the break. PARTIAL: "price should not trade back into the rebalanced range" is not built
- definitions_pd_arrays_structure#16 A13-breaker-close-vs-wick | done | `breaker_by_close` | False | the breaking bar itself must close its body beyond the swing (`breaker_by_close_ok`; a later close does not turn a wick break into a breaker); the body-close breaker is taken first (as `breaker_entry="prefer"`), a wick-only break goes to the FVG entry. NOTE: `breaker_ll` (default True, A13.1) already wants a body close above the real H, so the switch matters with `breaker_ll=False` or `mss_mode="wick"`
- definitions_pd_arrays_structure#18 A13-breaker-lifetime | done | `breaker_day_life`, `breaker_keep_original` | False, False | `sm2.breaker_register` (the day's breakers per Side, from `_breaker`), `breaker_retest_order` (a remembered alive breaker - no body close under its MT - that price traded into and left again arms a resting limit at its top once per retest, to the day's end incl. the PM last hour; runs in `_scan` when no sweep is active); keep_original: a newer overlapping breaker is not remembered, otherwise it replaces the zones it overlaps
- definitions_pd_arrays_structure#19 A19-break-against-htf-stop-run | done | `mss_requires_htf_agreement`, `stoprun_rearm` | False, False | an MSS against `ctx.cur_bias` is rejected in `_scan_core` (`x_mss_htf`; neutral = counts [our interpretation]); `stoprun_rearm` arms the opposite Side's sweep (level = the broken swing, extreme = the lowest low since the sweep) once per sweep
- definitions_pd_arrays_structure#33 A5-short-into-htf-sibi | done | `htf_sibi_short_zone`, `htf_sibi_need_smt` | False, False | inside a daily same-side Confluence FVG the entry must be on the zone's low side of its CE (`x_sibi_above_ce`), the CE untraded since the array was known (`x_sibi_ce_traded`), SMT with `htf_sibi_need_smt` (`x_sibi_no_smt`); tags `htf_sibi`, `sibi_q1` (the lowest 25%); exit level `htf_sibi_ce` (a body close beyond the CE)
- definitions_pd_arrays_structure#46 A15-mitigation-block-entry | partial | `mitigation_entry`, `mit_entry_px` | False, "near" | `sm2.mit_order` (in `_scan` after the breaker flow, no active sweep): the bias must be the block's side, a resting limit at the block's near edge ("near") / CE ("mid") once per retest while the block is alive (`mit_mt_invalid`), stop beyond the block, normal targets (the `mit_needs_bias` target with #124). PARTIAL: the 041 pre-open consolidation up-close block and the cc06_005 4h block are not built; the "stack with an FVG / OB" preference is the existing `mitigation` tag only

### Owner questions (caption-gap pass, setups_models#1/7)

1. N1 / N5 experienced versions (`nfp_release_fvg` 105, `post_news_continuation` 040, `release_ob_entry` 049): the owner rule says the EXPERIENCED version is the default where ICT distinguishes, but the specs say the bot default stays N1 blocked / N5 waits for the range, and `nfp_first_hour`, `news_wait` and N6 are existing owner-directive defaults (#4). All three are switches, off. Make any of them the default?
2. `smt_pick="middle"` (#49) needs a third instrument (YM / DJI); with the two books of the studies it is inert (`study.study_pick`), and `combine` raises with fewer than three runs as the spec says.
3. `smt_pick="laggard_objective"` (#48) reads "objective met" from the trades (a trade of the leader reached its last ladder level) instead of the htf.table draw per instrument; the draw-based read would need both instruments inside one `run_day`. Acceptable?
4. `breaker_ll` (A13.1, default True) already requires a body close above the real H, which overlaps with `breaker_by_close` (#16) and the `body_high` reference (#15); the new switches matter with `breaker_ll=False`, `mss_mode="wick"` or for the body-high reference.
5. `lc_reentry` (#199) names a 10:00-12:00 retry window but the AM scan ends at 11:00 (`am[1]`); widen `am` or add the lunch session if the owner wants 11:00-12:00.
6. `lod_zone_first` (#92): "tail" and the daily inversion-FVG level are not defined in the source; the built definition (a lower wick >= 0.1 x ADR5, a daily Confluence array) is [our interpretation].

### Tests (caption-gap pass, setups_models#1/7)

`tests/test_caption_gap_sm1a.py` (the 23 bias_htf_intermarket specs: spec-named tests `test_open_tolerance_grade`, `test_po3_sequence`, `test_ifvg_narrative`, `test_gap_premium_arm`, `test_compressed_highs`, `test_smt_pick_laggard_objective`, `test_smt_pick_middle`, `test_pick_clean_swing`, `test_pick_depth`, `test_m3_scan_report`, `test_pool_runs_exhausted`, `test_far_edge_trap`, `test_smt_window_points`, `test_lod_zone_first`, `test_smt_with_bias`, `test_mature_flag_block`, `test_hs_fade_level`, `test_mit_needs_bias`, `test_touch_count_tag`, `test_judas_depth`, `test_lc_reentry`, `test_smt_pick_fixed_es`, `test_smt_pm_points`) and `tests/test_caption_gap_sm1b.py` (`test_nfp_release_fvg`, `test_news_profile_pool_test`, `test_release_ob_entry`, `test_post_news_continuation`, `test_judas_news`, `test_profile_two_session`, `test_profile_consol_pm_path`, `test_pm_reversal_lunch_high`, `test_breaker_needs_disp_and_body_high`, `test_breaker_by_close`, `test_breaker_day_life`, `test_mss_requires_htf_agreement`, `test_htf_sibi_short_zone`, `test_mitigation_entry`, the study-variant test, and no-look-ahead runs: full vs truncated runs cut at every entry and exit time on a 5-week synthetic window (four switch groups + a post-MSS run) with an executed-path assertion (`sm2.HITS`) and on a 2.5-week ES window with every switch on; a test that every behaviour switch of the chunk is in one of those runs). The ES test skips when the local data is absent.

Checks run for this package: the two new test files (50 tests, ES look-ahead included); the existing files that cover the touched code - test_portability, test_strategy, test_review_fixes, test_entries_stops, test_owner_directives, test_news_calendar (263 passed together with the new files), test_setups_models (52 passed), the 45 new study variants through test_bias_htf_lookahead (every DECISIONS variant after X16 is run there on ES 5m windows: all pass; the SMT variants carry no `smt_min` because that harness has no partner book, and the `T13-judas-news-driver` tag variant is separate from the wide-window `_require` variant for the same reason), test_bias_htf / test_day_week_context study-variant checks; the full suite is left to the package Test step. Identity: the trades of 18 configurations with every new switch at its default equal the commit before this package (0067553, a worktree), every column but the ten new Trade fields.

Commit trailer: the harness attribution line (the model that wrote the commit) is used; the task text asks for the "Opus 5.5 (1M context)" line, which this session did not write.
