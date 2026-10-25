# RESUME - caption-gap pass (second build pass)

Last updated 2026-10-24 ~13:20 ET. This file replaces the 2026-10-19 laptop-pause notes. The first pass (all of `rule_coverage.md`), the Silver Bullet merge (`3fb9cd1`) and PR masonberger4/bottrading#3 (mentorship -> master, do not merge yet) are done.

## What the pass is

It builds the 1,080 caption-gap build specs in `mentorship/digests/rulebook_gaps/<topic>.md` (index: `rulebook_gaps.md`). The 1,081st spec, `stocks.py` (bias_htf_intermarket item 220), is parked and has no package.

The specs are grouped by work package and split into chunks of about 27-37 specs. Each chunk runs Build -> Sonnet review -> Fix, and each package ends with one Test step. In that Test step the full suite runs once on 4 workers. The test agent must end its answer with `SUITE GREEN: <n> passed`.

## Packages

| # | Package | Specs | Chunks | Status |
|---|---|---|---|---|
| 1 | levels_detectors | 85 | 3 | done, pushed `0067553` (2026-10-20 21:24 ET). The suite was verified separately: 1432 passed / 1 failed, fixed in `1ddfbd3` |
| 2 | setups_models | 250 | 7 | done, pushed `d3dd9ce` (2026-10-22 05:16 ET): 2363 passed, 0 failed |
| 3 | **entries_stops_sizing** | 104 | 3 | **in progress: chunk 1/3, Build** (resumed 2026-10-24 13:14 ET on top of the uncommitted work the limit-stopped attempt left: 10 modified files plus `mentorship/es1.py`, `tests/test_caption_gap_es1a.py`, `tests/test_caption_gap_es1b.py`) |
| 4 | targets_partials | 132 | 4 | not started |
| 5 | management_exits | 101 | 3 | not started |
| 6 | news_calendar_times | 37 | 1 | not started |
| 7 | day_week_context | 101 | 3 | not started |
| 8 | bias_htf | 243 | 7 | not started |
| 9 | silver_bullet | 27 | 1 | not started |

Per-chunk results are in `mentorship/digests/build_log.md` under "Caption-gap pass: <package>#<k>/<n>". Owner questions are under "Owner questions (caption-gap pass)".

## Rules the agents follow

These are written into the workflow prompts:
- No push.
- No history rewrite: no amend, rebase, reset or force. A cloud backtest is pinned to `3fb9cd1`.
- Nothing is created outside `C:\Users\mason\bottrading`.
- Every rule is a switch. The experienced version and the 2023 Mentorship version are the defaults. Judgment calls are labelled "[our interpretation]".
- Silver Bullet stays off by default. `sb_use_bias` and `want_all_engines` are kept as they are.
- Tests must be portable to Windows and Linux.
- Builders and fixers run ONLY their new tests and the existing test files for the code they touched. The full suite runs once per package, in its Test step.

## Workflow and watcher

- **Workflow:** `ict-caption-gap-build`, run id `wf_3daef78c-fe2`.
- **Script:** `runs\wf\ict-caption-gap-build.js`. `runs/` is git-ignored, so the script is local only.
- **Journal:** `C:\Users\mason\.claude\projects\C--Users-mason-bottrading\82edbfde-6c31-41c0-8a34-6578eb2166b5\subagents\workflows\wf_3daef78c-fe2\journal.jsonl`.
- **Push watcher:** `scripts/push_after_stages.py`.
  - It pushes `mentorship` only after a `test:<package>` result that contains `SUITE GREEN:`.
  - Before every push it runs the secrets/data check on `origin/mentorship..mentorship`.
  - Log: `runs/push_after_stages.log`.
  - Local-only commits, such as this file, go up with the next package push.

## Resume after a usage-limit stop (or any stop)

A weekly-limit stop makes every remaining agent fail at once with "You've hit your weekly limit · resets ...". Nothing bad is committed, but the chunk that was building usually leaves uncommitted work. Keep that work: every prompt tells the agent to finish or redo an interrupted attempt.

1. After the reset, check the state from `C:\Users\mason\bottrading` in Git Bash:
   ```
   git status --short
   git log --oneline -5
   git log -1 --format=%h origin/mentorship
   tail -3 runs/push_after_stages.log
   ```
   Do not reset or stash the uncommitted files.

2. Restart the push watcher in the background:
   ```
   .venv/Scripts/python -u scripts/push_after_stages.py "C:/Users/mason/.claude/projects/C--Users-mason-bottrading/82edbfde-6c31-41c0-8a34-6578eb2166b5/subagents/workflows/wf_3daef78c-fe2/journal.jsonl"
   ```
   On start it logs the stages it already counts as pushed.

3. Resume the workflow. In Claude Code, ask Claude to run:
   ```
   Workflow({scriptPath: "C:\Users\mason\bottrading\runs\wf\ict-caption-gap-build.js",
             resumeFromRunId: "wf_3daef78c-fe2"})
   ```
   - It needs no args, because the package and chunk list is inside the script.
   - Finished agents return from the cache, keyed by their exact prompt. Failed or unfinished agents run again.
   - Do not edit the prompts in the script: any change makes the finished agents re-run.

4. If the script is missing, rebuild it. The scripts in `runs\wf\build\` replay the steps that made it:
   `bash_02.sh` / `bash_03.sh` (chunk list -> `gap_args.json`), `make_gap_wf.py` (template -> script), `bash_07.sh`, `bash_08.sh`, `bash_09.sh` (test-scope edits), `bash_11.sh` (Test step with "SUITE GREEN" and 3 attempts).
   - Run them in that order from `runs\wf\build`.
   - The result must reproduce the original prompts exactly. Check it against an agent transcript in the run folder before resuming.
   - If `runs\wf` is gone too, the steps are in this session's transcript: `C:\Users\mason\.claude\projects\C--Users-mason-bottrading\82edbfde-6c31-41c0-8a34-6578eb2166b5.jsonl`.

5. If a Test step returns without "SUITE GREEN", the workflow re-runs it automatically, up to 3 attempts, and the watcher does not push. If all 3 attempts fail, read the Test agent's answer in the journal, fix the failure, then resume again.

## After the pass

- Restart the backtests on the finished engine.
- Answer the owner questions collected in `build_log.md`.
- Merge PR masonberger4/bottrading#3 when the owner is ready.

Not part of the build, left alone: the Silver Bullet SPY paper bot, `run_studio.py`, `claude_hf record`, and anything under `C:\Users\mason\X`.
