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
- RC receives only Mase's own typed messages (send_message refused); lines for the laptop must be given to Mase to send (see decisions.md "mentorship-missing-concepts").
- Haiku pass on owner questions was shallow; use Opus for rule decisions (decisions.md "model-choice-for-decisions").
