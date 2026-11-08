# Handoff: card defaults build, after stage S1 (2026-11-08, ~22:45 UTC)

Continues `mentorship/handoff_cards_2026-11-08.md` (read it first; its standing rules still hold).
Worktree `C:\Users\mason\bottrading\.worktrees\scb`, branch `claude/project-thread-y9jsd2`, PR #55 (open, never merge). Head b39a8e8.

## Scope (Mase 2026-11-08)
Build the missing card defaults in reviewed stages, get the suite green, then run the 2021 screen once (fresh tag, restart, don't resume).
Tie picks: MONDAY A, PYRAMID-WHERE A, FED-SPEECH **A** (changed from D at 21:34 UTC; D is dropped), CONTRACT B, OVERNIGHT-HOLD B, FIXED-RR A, VENOM-STOP B.

## Steps
1. Legacy-defaults rerun of the 832 failing IDs. The first launch (PID 8072) died at once with an empty log (command line too long).
   Relaunched 21:45 UTC on ad87c02 as PID 12128 via `%TEMP%\bt\legacy_rerun.ps1` (pytest `@%TEMP%\bt\rerun_ids.txt`, `MENTORSHIP_LEGACY_MODULES` = the 81 failing modules).
   Log `%TEMP%\bt\legacy_rerun.log` (UTF-16), ends with `SUITE EXIT n`. It was at 69 % at 22:40 UTC. Source files were edited during the run (S1); rerun any surprising failure.
2. Stage S1: DONE and reviewed (1a98b5b, c2d3214, review fixes b39a8e8).
   - FED-SPEECH A: `fed_chair_skip_am=True`. newscal now blocks every entry before 13:30 on a FED_CHAIR day, London and lunch included. Note: calendar.FED_CHAIR is unverified.
   - EXIT-DEPTH B: `depth_trail=0.75` (me2._depth_trail). From 75 % of the way to the final rung, the stop trails one tick under each closed bar's low. Every day; only the trail half is built.
   - ATH-RULE A: `ath_rule="no_top_pick"`, `ath_near_frac=0.02` (cards_rules.ath_block, gate after _CG1.order_ok). The ATH comes from `backtest.Prepared.ath` (ath_map over the loaded day frames). Paper sees only `history_days` of history, so its "ATH" is an N-day high.
   - TGIF-TIMING B: `tgif_thu=True` (TAG_ONLY, acts only with tgif). TWO-SIDED A: `neutral_5050="armed"`. TF-CHOP A: SAME_AS_ENGINE.
   - RANGE-REGIME A: reverted to NOT_BUILT. drange_scalp was the wrong rule and made `Params().bx` non-empty, which breaks the bias CSV cache and many `bx == ""` tests. Build it properly: a PDH / PDL turtle soup back into a multi-week daily range, targeting the FVG just inside the old extreme. Keep it out of `bx`.
   - tests/_legacy.py LEGACY and study.CARDS_S1_OLD (PRE_OWNER / CURRENT) hold the old values. The earlier card stages (3a-3f) did NOT pin theirs into study.PRE_OWNER / CURRENT; check that when fixing tests.
   - New tests: tests/test_cards_rules.py (4). tests/test_cards.py still passes (10).
3. Stage S2 (next): FVG-VALID B, OB-VALID B, OB-CLOSE A, WICK-PRIORITY B, WICK-SELECT A, RANGE-ANCHOR B, FVG-CARRY A, FPFVG-DEF A. Also RANGE-REGIME A (above).
   - Look first for existing switches: Params has ~3,500 lines. Grep `wick_partial_longest`, `pool_body_edge`, `grades60_src`, `sd_anchor`, `measuring_anchor`, `grade_confluence`, `fvg_state_filter`, `ob_cisd`, `overnight_5m_fvgs`, `trail_first_fvg`.
   - Put new concepts in mentorship/cards_rules.py (HITS, check_params) and new defaults in Params with a "<CARD> <pos> (scorecard default)" comment.
4. Stage S3: PREMARKET-RANGE A, ORG-CE-WINDOW A, ORG-AFTER-CE A, ORG-SIZE B (`org_*` switches exist: org_draw, org_half_draw, org_gap_fill_frac, org_reprice, org_ce_if_flow).
5. Stage S4: OVERNIGHT-HOLD B (OSOK: hold to a daily FVG CE; the engine flattens at the session close; bh7s.py has a study-only OSOK), CONTRACT B (per-level back-adjusted frame; price_frame has only whole-frame options), VENOM-STOP B (the Venom model is not in the engine at all, so the model must be built first; PREMARKET-RANGE E is its 08:00-09:30 range).
   - TWO-SIDED (rollover-week "trade very light") and TGIF-TIMING (measure from the high after Thu 13:00) are partial; noted in cards.py.
6. Fix the tests (handoff 1 "Next on the tests"), then run one full suite, detached.
7. Restart the 2021 screen (run-backtest-screen skill, fresh tag) and report in $ at $1k risk (choose 2019-22, check 2023-26, by day type).

## How each stage goes
Build, run `tests/test_cards.py` + `tests/test_cards_rules.py` (only when no other pytest runs), then a smoke backtest. `%TEMP%\bt\smoke.py` runs `B.run` on ES 5m 2023-09-05..11-10; pass extra Params dicts as args.
Then commit and push, run the second-agent review (read-only, no pytest), fix, and push again.
