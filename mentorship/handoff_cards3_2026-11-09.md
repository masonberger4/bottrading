# Handoff: card defaults build, after stage S2 (2026-11-09, ~00:45 UTC)

Read first: `mentorship/handoff_cards2_2026-11-08.md`, then `mentorship/handoff_cards_2026-11-08.md`. Their standing rules still hold.

## Where it is
- PR #55 (S1) was merged by Mase. New work is on branch `claude/project-thread-ufyth4`, PR https://github.com/masonberger4/bottrading/pull/57 into `mentorship`. Do not merge it; only Mase merges.
- Worktree `C:\Users\mason\bottrading\.worktrees\scb` (now on `claude/project-thread-ufyth4`). Python: `C:\Users\mason\bottrading\.venv\Scripts\python.exe`.
- Head 91f6466. `tests/test_cards.py` and `tests/test_cards_rules.py` pass (17 tests).

## Steps (thread numbering)
1. DONE. The legacy-defaults rerun finished: 143 failed and 689 passed of the 832 IDs. The still-failing IDs are in `mentorship/legacy_rerun_fail_ids_2026-11-08.txt`, and the full log is at `%TEMP%\bt\legacy_rerun_utf8.log`. Per handoff 1, "Next on the tests": every ID that passed only assumed the old defaults, so pin those modules to the legacy values. The 143 are real bugs or unreachable `Params` uses.
2. DONE. PR #55 conflicts resolved (taken from base: FED-SPEECH without D), and Mase merged it.
3. Stage S2 DONE and reviewed (1d267e5, review fixes 91f6466). Rules are in `cards_rules.py` (`card_map`, `array_gate`, `range_gate`). The hooks are at the head of `strategy._finish_order` (`array_gate`), after `_CG1.order_ok` (`range_gate`), and `ctx.cards` (the day's row of `backtest.Prepared.cards`, passed as the `run_day(cards=)` kwarg).
   - FPFVG-DEF A `fpfvg_def="time"`: the first engine-bar FVG with a 09:31-09:59 middle candle. It stays a PD array all of its ISO week.
   - FVG-CARRY A `fvg_carry_days=20`: an unfilled FPFVG is carried for 20 trading days. The "first FVG after a turtle soup" part is queued. FPFVG-DEF and FVG-CARRY act only through the two validity gates; the FPFVG is not an entry or target array of its own.
   - FVG-VALID B `fvg_valid="first_or_grade"` ("fvg" kind only). A valid FVG is one of: the first gap of the leg after the sweep, a gap overlapping an active same-side FPFVG, or a gap holding a grade line. The grade lines are dealing-range octants (sweep ext .. `sw["ref_px"]`), ORG quadrants k/4 for k = -8..12 (ORG >= `grade_min_pts` = 2), and FPFVG octants.
   - OB-VALID B `ob_valid="grade"`: every kind with "ob" as a `_` token. The OB zone (body low .. entry or zone_top) must hold a grade line. The propulsion-block inheritance is not built.
   - OB-CLOSE A `ob_arm="intrabar_htf"` (the old default was "leave"). B is the new `ob_arm="high"`. Review fix: a trade-through bar that closed back under the open arms the limit one tick under the close.
   - WICK-PRIORITY B `wick_priority=True`: when candle 1's upper wick (side space) is at least as tall as the gap, the entry moves to the wick CE and the stop to the body top minus pad. The order's fvg_bottom / fvg_ce / zone_top become the wick, ce_hold and the ladder are dropped, and the stop survives the later stop rules (`tags["wick_first"]`).
   - WICK-SELECT A `wick_pick="reach"` (TAG_ONLY: acts only with `wick_partials`). RANGE-ANCHOR B `leg_fib="body"`.
   - RANGE-REGIME A `range_regime="fade"`. A range-bound day means no new 20-day RTH extreme in the last 5 days and a prior close inside the 20-80 % band. On such a day, no long entry above the PDH and no short below the PDL. The "target the FVG inside the old extreme" part is queued.
   - Old values are in `tests/_legacy.py` LEGACY and `study.CARDS_S2_OLD` (PRE_OWNER / CURRENT).
   - Smoke (`%TEMP%\bt\smoke2.py <start> <end>`, ES 5m): on 2023 before the review fixes, new defaults gave 4 trades / -$56.5 and all S2 off gave 2 / -$21.9 (the engine trades very little on plain `B.run`). A post-fix rerun is running detached (PID 4036), and its output goes to `%TEMP%\bt\smoke2y_fix.out`. Check its `HITS` line for `fvg_not_valid` vs `fvg_grade` / `fvg_first` and `ob_not_valid` vs `ob_grade`.
   - Review notes left open: study DECISIONS "A12-same-candle-retrace" and "A21-intraday-fib-bodies" now equal the defaults, so in the screen they are no-op variants. Consider pointing them at the old values. `_rth` uses 09:30-16:00 for futures too.
4. NEXT: Stage S3. Cards: PREMARKET-RANGE A, ORG-CE-WINDOW A, ORG-AFTER-CE A, ORG-SIZE B. The `org_*` switches exist: org_draw, org_half_draw, org_gap_fill_frac, org_reprice, org_ce_if_flow. Check what each card's A or B says in `mentorship/scorecard/positions.csv` and `evidence.csv`, then map it to the existing switches before building anything new.
5. Stage S4: OVERNIGHT-HOLD B, CONTRACT B, VENOM-STOP B. See handoff 2, step 5.
6. Fix the tests: the 143 legacy-rerun failures, plus whatever S2-S4 broke. Then run one full suite, detached, using the start-laptop-run skill.
7. Run a fresh 2021 screen with the run-backtest-screen skill and a new tag, and report in $.

## How each stage goes (unchanged)
1. Build the stage.
2. Run the card tests, only when no other pytest is running.
3. Run a smoke backtest.
4. Commit and push.
5. Get a second-agent review (read-only, no pytest).
6. Fix the findings and push again.
