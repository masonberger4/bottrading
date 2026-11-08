# Handoff: scorecard cards in the engine (2026-11-08, ~21:45 UTC)

## Where it is
- Laptop worktree `C:\Users\mason\bottrading\.worktrees\scb` (inside bottrading; `data\mentorship` and the other data folders are junctions to the main checkout's `data\`). Branch `claude/project-thread-y9jsd2`, PR https://github.com/masonberger4/bottrading/pull/55 into `mentorship` (open, not merged; only Mase merges).
- The branch includes the scorecard data from PRs #52 (merged), #53 and #54 (open; #54 holds Mase's tie picks).
- Use `C:\Users\mason\bottrading\.venv\Scripts\python.exe`. Its packages were zeroed by the Nov 1 disk-full event. I reinstalled the same versions on 2026-11-08 with `python -m pip --python .venv\Scripts\python.exe install --force-reinstall --no-deps -r <freeze>`.

## What is done (step numbers as in the thread)
1-2. Read the inputs and planned the stages.
3a-3f. `mentorship/cards.py` maps all 68 cards and the one-source rules. Tests are in `tests/test_cards.py` (10 pass).
   - 50 cards run on their default. 107 positions are built, 117 are in `NOT_BUILT` with a reason, and there are 60+ switch variants.
   - Variants are named `SC-<card>-<pos>` / `SG-<digest>-<num>-off` in `study.DECISIONS`. `cards.variants(screen=True)` drops the `TAG_ONLY` cards.
3g. The second-agent review found 7 issues; all are fixed (9ea6c99).
- Mase's tie picks (2026-11-08 21:27 UTC) are applied in c8e7c04:
  - MONDAY A (trade Mondays) and PYRAMID-WHERE A (`add_cut="eq"`) are now defaults.
  - FED-SPEECH D, CONTRACT B, OVERNIGHT-HOLD B and VENOM-STOP B are not built (reasons in `NOT_BUILT`); the engine keeps its old behaviour for them.
  - FIXED-RR A is already the engine.

## Tests
- Full suite on 9ea6c99: 4,451 passed, 835 failed (2 h 38 min, 4 workers). Log: `%TEMP%\bt\cards_suite.log` (UTF-16). The failing IDs are in `%TEMP%\fail_ids.txt`.
- Most failures are tests written against the old defaults. `tests/_legacy.py` holds `LEGACY`, the old values of every default that changed, and `LegacyParams`. In `tests/conftest.py`, modules named in `LEGACY_MODULES` (or in the env var `MENTORSHIP_LEGACY_MODULES`) get `Params = LegacyParams`.
- RUNNING NOW: a diagnostic rerun of the 832 failing IDs with the old defaults pinned in every failing module.
  - PID 8072, started ~21:40 UTC, commit c8e7c04.
  - IDs: `%TEMP%\bt\rerun_ids.txt`. Log: `%TEMP%\bt\legacy_rerun.log`; it ends with `SUITE EXIT n`.
- Next on the tests:
  1. Every ID that passes in the rerun only assumed the old defaults. Add its module to `LEGACY_MODULES`, or pin the values inside the test if only part of the module needs them.
  2. Every ID that still fails is a real bug (or used `S.Params` / a module-level `Params()` the patch can't reach). Fix it.
  3. The 3 look-ahead failures: SC-MIN-ROOM-A/C was a harness key clash, fixed in c8e7c04. X3-seasonal-strength-grading likely came from my mid-run edit (seasonal_tag); rerun them.
  4. Then run one full suite, detached. Only one pytest may run at a time.
- Before relying on the `tests/test_news_calendar.py` edit (pins `pre_0900=False`), note that `pre_0900` is back to False by default, so the pin is harmless.

## Open decisions for Mase (asked in the thread, no answer yet)
- Option 1 (recommended): ship what is built (PR #55 after the tests are green), restart the 2021 screen on this engine, and build the 18 missing default concepts in a follow-up.
- Option 2: build all 18 first, then run the screen once.
- The 18 cards whose default is not built: PREMARKET-RANGE, FPFVG-DEF, ORG-CE-WINDOW, ORG-AFTER-CE, ORG-SIZE, TWO-SIDED, RANGE-REGIME, TGIF-TIMING, OB-CLOSE, FVG-VALID, WICK-PRIORITY, TF-CHOP, OB-VALID, FVG-CARRY, WICK-SELECT, RANGE-ANCHOR, ATH-RULE, EXIT-DEPTH. Also not built: the FED-SPEECH D, CONTRACT B, OVERNIGHT-HOLD B and VENOM-STOP B picks.

## Screen restart (step 5)
- The old 2021 screen (2,008 of ~2,487 done) measured variants against the old defaults, so restart it on the new engine instead of finishing it.
- Use the `run-backtest-screen` skill and `runs/laptop_screen.py` (resume-safe). Use a fresh tag so the old job CSVs are not mixed in.
- Variants: `cards.variants(screen=True)` plus the existing DECISIONS. Every variant is measured against the new defaults.
- The bias cache key changes only if `table_kw(Params())` changes; it did not after reverting `seasonal_tag`.
- Report in $ at $1k risk: choose on 2019-22, check on 2023-26, and break out by day type.

## Standing rules
- Use only `C:\Users\mason\bottrading`, never `C:\Users\mason\X`.
- Leave the ict_fetch and Silver Bullet bot processes alone. The Silver Bullet stays off.
- One pytest at a time, launched detached.
- Check in and push every 30 min, and keep a numbered step list in the thread.
- Never merge a PR and never call update_memory.
