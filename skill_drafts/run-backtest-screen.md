---
name: run-backtest-screen
description: Use when running or extending the Mentorship full backtest screen (study.main_decisions) across laptop and cloud shards.
---

# Run the backtest screen

Facts: runner `study.main_decisions`, `MENTORSHIP_SRC=databento`, all runs on one pinned mentorship commit (check current in /mnt/project-files/memory/results.md). Results at $1k risk, reported by half (2019-22 / 2023-26) and day type. Choose on 2019-22, check on 2023-26.

Plan (Mase, 2026-11-01): the full list is 2,543 variants x 8 yrs, too big (~1,000 h). So:
1. Screen every variant on ONE year (2021), entry/stop/trade-count variants first.
2. Meaningful movers expand to 2019-22.
3. Winners get checked on 2023-26.
4. Little-effect variants are parked.
The laptop holds current + defaults on all years as the baseline.

Sharding: laptop thread runs the first 1,326 variants (`runs\laptop_shard.py`, only laptop writer); cloud thread runs the rest (`python -m cloud.run --tag T --shard i/n`), refuses mixed commits, and merges with `cloud.merge --tag T` into /mnt/project-files/mentorship/runs/T_summary.md. Setup in cloud: `bash cloud/setup.sh` (rebuilds CSVs from /mnt/project-files/mentorship/data/databento/). Use the spot DXY file for ICT levels.

Report: trades, $ total, both halves, win rate; compare to baseline rows in results.md. Append the result to results.md with commit hash and date. Do not re-test Silver Bullet (settled, off by default).
