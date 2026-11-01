---
name: start-laptop-run
description: Use when starting or restarting a long pytest or backtest run on Mase's laptop (MB-Laptop, C:\Users\mason\bottrading) so it survives the Remote Control session.
---

# Start a laptop run detached

Rules: folder C:\Users\mason\bottrading only (never C:\Users\mason\X, no folders outside it). One laptop writer at a time.

1. Check `remote_control_status` and that no other thread is writing to the laptop.
2. Check for an existing run first: `Get-CimInstance Win32_Process | ? { $_.CommandLine -match 'pytest|study|laptop_shard' }`. Never start a duplicate; never run two pytest runs at once (CPU and memory max out).
3. Leave alone: PIDs for ict_fetch transcribe/prep jobs (idle) and the Silver Bullet paper bot instances. Mase runs taskkill himself.
4. Launch detached so ending the session does not kill it: `Start-Process powershell -WindowStyle Minimized` with output to a log under `%TEMP%\bt\`. Use 4 workers (xdist 4 cores), `-v -rf`.
5. Record commit hash, command, log path and PID in the thread.
6. Every 15 min check the log is advancing and restart if stalled (rerun only remaining test IDs, e.g. runs\run_remaining.py). Post status to Mase at least every 30 min, commit and push at least every 30 min, because the RC connection times out ~1h after the session goes quiet.
7. Where the thread cannot copy files to the laptop, kill processes or merge PRs, give Mase the exact line to do it.
