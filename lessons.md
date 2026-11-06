# lessons.md — stalls, drops, and what fixed them

## From the old MEMORY.md index
- LAPTOP STALL LESSON (2026-10-29): Mase: "I need the work to keep moving." Test runs inside the RC session die when it resets/idles; run suites detached, 4 cores, -v -rf. Watch for duplicate runs.
- RC drops 2026-10-31: session connection times out ~1h after the session goes quiet (Windows logs clean). Laptop threads must post status at least every 30 min during long runs.
- Laptop Wi-Fi drops (2026-10-29/30).
- Running two pytest runs at once maxes the CPU and memory; run one at a time.
- Full backtest list is too big to run blindly (2,543 variants x 8 yrs ~1,000 h): screen on one year first (see decisions.md).

# Detailed memory files moved here verbatim (one section each)

## Laptop test-run lessons (from data-wiring-state, 2026-10-31; also kept in data.md)
- A suite started inside the RC Claude session is its child, so ending the session can kill it. Launch long runs detached (Start-Process powershell, minimized, log under %TEMP%\bt\).
- Check for an existing pytest (Get-CimInstance Win32_Process) before any rerun. Duplicates happened twice from misread checks.
- The xdist tail on test_bias_htf_lookahead variants can crawl on one core. Rerunning just the remaining IDs (runs\run_remaining.py, repo root on sys.path) finished 354 tests in 22 min.
- The RC session goes quiet while waiting and can park when idle; parking did NOT kill the run.
- Mase runs taskkill himself (the laptop is blocked from killing processes).

## Other lessons carried in detailed sections
- 2026-10-19 21:47 UTC the RC session went offline and took the running build (~7 h lost); see laptop_ops.md "mentorship-build-parallel".
- (Updated 2026-11-01, was: RC receives only Mase's typed messages.) Laptop threads are started and instructed through the coordinator (start_remote_control, message_thread). Cloud threads cannot message the laptop directly: ask the coordinator. Pasting lines to Mase is only needed if the laptop thread is unreachable.
- Haiku pass on owner questions was shallow; use Opus for rule decisions (decisions.md "model-choice-for-decisions").

## Added 2026-11-01 from the first dream pass (approved by Mase)
- Two laptop sessions edited the same data-wiring code at once (2026-10-29 08:49-08:59, "Mentorship bot" vs "Wire Databento"); nothing committed, ~10 h of drift until Mase chose a keeper. Rule: before ANY laptop write call remote_control_status; if another writer is active, stop and ask the coordinator (step 1 of the start-laptop-run skill).
- Cloud sessions can push only to their designated branch; other pushes and GitHub API writes return 403, and the file-push tool costs ~25k tokens per 84 KB. The memory-branch thread burned 3 turns finding this (2026-11-01 21:32-21:35). Rule: for anything GitHub-hosted beyond the designated branch, hand Mase the click-by-click steps up front; don't try pushing first.
- Early job-rate estimates were off ~6x: laptop first 30 min = 9 of 1,332 jobs (bias-cache build) vs planned ~3 min/job x 4 workers; cloud estimated 55 jobs/10 min. Rule: quote throughput only after the cache build; give a range and re-estimate at each check-in.

- yt-dlp YouTube bot check (11-03): slow pacing and a JS runtime did NOT clear it; hourly retries failed ~12 h. Use cookies.txt exported from the spare Google account (browser extension), never the main one; the download thread switched its ask from a Chrome profile path to cookies.txt (thread proposal, Mase has not confirmed). If the fetcher state is STOPPED_BLOCKED restart it once by hand. Why: avoids another half-day of waiting. How to apply: ask for the cookies.txt path as soon as the first block appears.
- (2026-11-06) Parallel rule-drafting threads collided when they merged into mentorship. PR #43 (2026 SMC 125-136) duplicated the RESISTANCE-DAY card, reused position letter F on FPFVG-DEF, and had merge conflicts after PRs #41 and #42. Why: each thread started from the same base and named cards and letters on its own. How to apply: before starting parallel draft batches, the coordinator assigns each one its card names and position letters, and each thread merges the latest mentorship and re-runs scorecard.py before opening its PR. (Conflict IDs are numbered per playlist, so they do not clash.)
