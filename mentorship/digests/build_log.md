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
