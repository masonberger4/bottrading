# laptop_ops.md — laptop and cloud operating rules

## From the old MEMORY.md index
- Laptop: MB-Laptop, folder C:\Users\mason\bottrading only. NEVER use or offer C:\Users\mason\X (Mase, 2026-10-11). "Keep everything inside bottrading folder"; create no folders outside bottrading. Silver Bullet build copy at bottrading\.worktrees\sb-build (gitignored). A separate Silver Bullet paper bot on the laptop restarts at logon by itself.
- Rule: one laptop writer at a time; check remote_control_status before starting another.
- Laptop processes: PIDs 17224 and 516 = ict_fetch transcribe/prep jobs (since 10/25, idle at 0% CPU); the Silver Bullet paper bot is one instance (PIDs 10480, 3108, 13968, 17164). Leave all of them alone. Running two pytest runs at once maxes the CPU and memory; run one at a time.
- MONITORING RULE (Mase, 17:29 UTC 2026-10-30): while laptop work runs, check it's moving every 15 min (restart if stalled) and give Mase a status update every 30 min. Laptop thread keeps this schedule; coordinator relays anything needing Mase.
- LONG-WORK RULE: see decisions.md ACTIVE RULES DIGEST item 3. Who is the current laptop writer: see threads.md.
- RESTART of the backtest screen (laptop thread message cmsg_01FAHERC1Lsrg2bYtrKuRHmP9msWSsCnbp9Bc1ByG8AoG7): runs/laptop_shard.py / laptop_screen.py is resume-safe (skips jobs whose CSV already exists). Restart from a clean checkout of 229c1a5 with MENTORSHIP_SRC=databento, launched detached with Start-Process; leave PIDs 17224 and 516 alone. The backtest-results branch layout differs: cloud has its own layout, laptop uses laptop/shard_laptop/dec_jobs/.
- Laptop Wi-Fi drops (2026-10-29/30); laptop never sleeps, plugged in, no Ethernet port. Thread's session safety rules block it copying files to the laptop, stopping some processes, and merging PRs; Mase does those by hand.
- Cloud thread has 4 cores. cloud/setup.sh rebuilds CSVs from /mnt/project-files/mentorship/data/databento/.
- Working copy on the laptop (branch mentorship). Repo: https://github.com/masonberger4/bottrading (private; branches master, claude-hf, mentorship); the repo can lag the laptop by a build stage.

# Detailed memory files moved here verbatim (one section each)

## mentorship-build-parallel — How the Mentorship build runs in parallel, its current stage, and how to check on the laptop from the cloud
(source: mentorship-build-parallel.md, modified 2026-10-20T15:20:41.951Z)

Setup (2026-10-19): the laptop found testing, not building, was the bottleneck (stage 5's tests took ~3.5 h on 1 core). It uses pytest-xdist on 4 cores from stage 6. The main chain stays in order (they edit the same core functions). The Silver Bullet package (off by default, 448 tests) was built in a side worktree, now bottrading\.worktrees\sb-build (branch sb-build, gitignored, excluded from pytest, data\ linked). Mase: "Keep everything inside bottrading folder", so no folders outside it. Mase chose "Laptop only" for tests (10:00 UTC): don't start cloud threads to build or test stages; the 1,081 caption-gap pass waits until the stages are merged.

State 2026-10-20 ~12:10 UTC: FULL-RULE BUILD DONE. All 9 stages plus Silver Bullet merged and pushed to GitHub as 3fb9cd1 (1,059 tests pass, SB still off by default); watcher stopped, sb-build worktree removed (branch kept). Two SB bias switches (want_all_engines, sb_use_bias) kept as is unless Mase says to fold them. Mase chose "Gap pass, light check" (15:09 UTC Oct 20): the laptop builds the 1,081-spec gap pass now (Mase sends the laptop a start line; never rewrite mentorship history, since the baseline is pinned to 3fb9cd1); ONE fresh cloud thread runs a short 5m ES baseline on 3fb9cd1 (scope in handoff.md, Pending item 1); full 1m and all-version backtests wait for the final engine. I asked the coordinator to start that thread. Gap pass started 15:20 UTC Oct 20: 1,080 specs (1 parked: stocks.py), 32 chunks in 9 packages, sequential (every package edits strategy.py), 9 full-suite runs of ~1.5 h, expect well over a day; where a spec would change an owner default, the default stays and the spec becomes a switch, logged in build_log.md as an owner question; watcher pushes after each package. Resume notes (laptop only): mentorship/digests/RESUME.md.

Checking on the laptop from the cloud: Mase's typed lines are the only way to reach it. `rc_session_status` shows whether the session is connected or parked, and the thread log shows "went offline" events. On 2026-10-19 21:47 UTC the session went offline and took the running build with it (~7 h lost); Mase's next message restarted it and it resumed from the workflow journal. I told Mase to stop the laptop sleeping during the build. To see pushes without the laptop: add_repo masonberger4/bottrading (access read), then github list_commits on branch mentorship, no clone.

Time zones: the laptop reports in ET (UTC-4); only its push log is Pacific. Some laptop commits are signed Opus 5.5, so its session is likely still on Opus.

**Why:** usage and clash risk; Mase declined cloud stage-building earlier (see [[mentorship-usage-preferences]]).

## cloud-backtests — How Mentorship backtests run in cloud sessions and split/merge with the laptop (cloud/ folder, PR #2, data in shared folder)
(source: cloud-backtests.md, modified 2026-10-18T19:24:58.074Z)

Built 2026-10-18 on branch claude/cloud-backtests-3zn59v, PR #2 into mentorship (new files only, cloud/; README there). `python -m cloud.run --tag T --shard i/n` runs every n-th (tf, year, version) job via study._dec_job (same file names as main_decisions); `cloud.push_results` (laptop) pushes job CSVs to branch backtest-results; `cloud.merge --tag T` combines laptop + shared-folder shards, refuses mixed commits, writes /mnt/project-files/mentorship/runs/T_trades.csv and T_summary.md ($ at $1k risk, halves, day type).

Data: raw Databento .dbn.zst kept in /mnt/project-files/mentorship/data/databento/ once downloaded (`python -m cloud.data --quote`, then `--buy --end 2026-10-17`); `bash cloud/setup.sh` installs libs (pandas 2.2.3, numpy 2.1.3) and rebuilds CSVs locally. Needs Mase to add a cloud environment with hist.databento.com allowed and DATABENTO_API_KEY set (asked 2026-10-18; built-in env blocks it, also blocks Yahoo). Cloud containers have 4 cores, 15 GB, same as laptop: speed comes from more sessions.

UPDATE 2026-10-18 19:30 UTC: no key needed for now. A folder thread copied the laptop's raw files to /mnt/project-files/mentorship/data/databento/ (ES/NQ/YM_ohlcv1m.dbn.zst). `bash cloud/setup.sh` rebuilt the CSVs from them in ~4 min: ES/NQ 2.75M 1m bars, YM 2.72M, 2019-01-01 18:00 to 2026-10-16 16:59 ET, 32 contracts. Real smoke run OK (defaults, 2025-26, 5m+1m, ~3 min on 4 cores; 1m 159 trades +$17.1k, 5m 30 trades -$18.4k, label only). Yahoo DXY/TNX dailies are not in the shared folder, so dxy/tnx labels stay blank until copied to data/yahoo/. Env change only needed to re-download.

On mentorship commit e58eed1, 7 of 122 tests fail in the cloud (Zone equality with mt=nan; year_end; sloppy alias), same on pandas 3 and 2.2. See [[mentorship-bot]].

## no-x-folder — Mase doesn't want work done in the C:\Users\mason\X folder on MB-Laptop
(source: no-x-folder.md, modified 2026-10-11T21:13:25.109Z)

Don't use C:\Users\mason\X on Mase's laptop (MB-Laptop) for this project. Mase stopped a Remote Control session started there on 2026-10-11 and said "We don't want to use the X folder", then "I don't want this project affiliated with the X folder at all". The bot's home is now C:\Users\mason\bottrading, a new local git repo.

**Why:** Mase said so directly. They chose C:\Users\mason\bottrading instead.
**How to apply:** Only start a laptop session when Mase asks for one, and don't pass the X folder. Point laptop sessions at C:\Users\mason\bottrading. See [[silver-bullet-bot]].

## ict_fetch pipeline facts (moved from decisions.md; dream Z3, Mase approved 2026-11-04)
ict_fetch pipeline = fetch_win.py -> prep_win.py -> manifest.json -> cloud box /workspace/yt_fetch acks -> sync_tool.py deletes all but DONE and writes SYNCED; fetcher pauses at >8 GB un-acked or low disk; supervisor run_all.py, scheduled task "ICT Fetch" (start.ps1); state in data/ict_fetch_handoff.md. C: 107 GB, ~13 GB free; ict_fetch/out 8.1 GB. .git is 18 MB, so dropping stash@{0} frees little (the earlier 3.4 GB estimate was wrong).
## Moved from the MEMORY.md index 2026-11-13 (Mase approved trimming the index, 2026-11-13 00:52 UTC; entries verbatim as they stood in the index on 2026-11-12)
- LAPTOP SESSION DROPS (Mase 2026-11-09): laptop does NOT sleep; the Claude app's Remote Control session goes offline and restarts only when a thread gets a message. Routine "Hourly laptop session check" (trig_01B2WgPisUYEgUdPvpfAio5s, hourly ~:05-:11 UTC) runs in thread "Add hourly laptop session check" (cmsg_01FAHERC1Lsrg2bYtrKuRHmPDBXsN7nFpUcusSMHygT1Df; keep it open). Threads can't message Mase's laptop sessions, so the check asks the COORDINATOR to send the nudge; coordinator does it with message_thread. Mase 2026-11-11: new laptop approval cards did nothing for him; he prefers REUSING an already-connected laptop thread (message it to wake it) over starting a new laptop thread. 11-12: with the laptop app open (list_devices app_open true) a NEW laptop thread on the pre-approved bottrading folder started with no approval card.
- LAPTOP DISK (2026-11-02): cleanup done. Hibernation OFF. Claude app VM image shows twice but is one copy; leave it. 11-08: laptop test venv had 74+ zeroed files; engine thread reinstalled same package versions.
