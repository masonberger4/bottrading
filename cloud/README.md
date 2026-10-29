# Cloud backtests

Run Mentorship backtests in a Claude cloud session and split one version list between the laptop
and any number of cloud sessions. A cloud session has 4 cores like the laptop, so each extra
session adds one laptop's worth of speed.

## One-time setup (Mase, in claude.ai)

Project settings, Cloud environment, Add cloud environment:
- Network access: add `hist.databento.com` under Allowed domains (keep "Allow package managers").
- Environment variable: `DATABENTO_API_KEY` = the same key as on the laptop.

Only the first download needs these. After it, the raw bars sit in
`/mnt/project-files/mentorship/data/databento/` and later sessions copy them from there.

## In each cloud session

    bash cloud/setup.sh                    # libraries + bars (from the shared folder)
    python -m cloud.data --quote           # first time only: what the download costs
    python -m cloud.data --buy --end 2026-10-17   # first time only: download, keep a shared copy

## Splitting a run

Every machine uses the same commit, `--tag`, shard count, `--tfs` and `--variants`
(default: every version in `mentorship/study.py` DECISIONS, years 2019-2026).
Jobs are (timeframe, year, version), the same files as `study.main_decisions`, so a stopped run
resumes and caches mix.

    # laptop (merge this branch into mentorship first, or copy the cloud/ folder)
    python -m cloud.run --tag rerun --shard 1/2
    python -m cloud.push_results --tag rerun     # trade CSVs to the backtest-results branch

    # cloud session, checked out at the same mentorship commit
    python -m cloud.run --tag rerun --shard 2/2  # also copies each job to the shared folder

    # anywhere with the repo (normally a cloud session)
    python -m cloud.merge --tag rerun

`--plan` lists a shard's jobs without running them. More cloud sessions: use `--shard 2/3`, `3/3`.
Merge refuses shards from different commits and warns when library versions differ.
It writes `<tag>_trades.csv` and `<tag>_summary.md` ($ at $1k risk, 2019-22 vs 2023-26, years up,
and $ by day type for the defaults and the top five on 2019-22) to
`/mnt/project-files/mentorship/runs/`.
