# Handoff: full backtests, laptop + cloud (2026-11-02)

## Code to use
- Branch `mentorship`, commit `229c1a5ddb8082810c4f920a329f5099399b62d7` (merge of PR #6; PR #5 is inside it). Check out that commit on every machine so all shards run the same code.
- Full older suite on this code: 5,205 passed, 3 skipped (the 8 failures found on the way were fixed and rerun 8/8).

## What the runner is
`study.main_decisions(out, workers, tfs, variants, tag)` in `mentorship/study.py`. One job = `(tf, year, variant)`; each job's trades go to `<out>/<tag>_jobs/<tf>m_<year>_<variant>.csv`, and a job whose file exists is skipped, so a run resumes and shards merge by copying the job folders together. `<out>/<tag>_trades.csv` is the concat of the jobs it sees.
- Data: `MENTORSHIP_SRC=databento` (ES / NQ / YM 5m and 1m, 2016-2026; `data/mentorship/*_db.csv/parquet`). Without it the default is `histdata` (SPX / NDX CFDs), which is not what the studies use.
- Years: `main_decisions` runs 2019-2026 (`range(2019, 2027)`). 2016-2018 needs the year list changed (see `runs/news_study.py` for a 2016-2026 runner); the 2016-18 minute history is `data/databento_extra/*_ohlcv1m_2016-18.dbn.zst`, already joined by `databento_data`.
- Timeframes: 5m is the main one; 1m is about 5x slower (the job sort puts 5m first).
- Selection rule: choose on 2019-2022, check on 2023-2026 (DXY rules: 2023-2025, the spot file ends 2025-12-31).
- Python on the laptop: `.venv/Scripts/python.exe`. Launch detached, one run at a time, with progress lines (the connection drops after about an hour of silence).

## Variants
- `DECISIONS` (2,543 names) is everything. New in this build (55 variants) and worth a first pass: `TT-*` (tier/tug), `NEWS-*` (calendar), `CG3b-*`, `CG3c-*`, `CG3d-*`, `CG2-*`, `CG3a-*`, `DXY1-*` to `DXY11-*`. Base comparisons: `current` (the pre-owner engine, pinned by `study.CURRENT`) and `defaults` (`{}`).
- Do not pass `_`-prefixed or locally defined variants to worker processes (a variant must exist in `study.DECISIONS` at import time; workers on Windows re-import the module).

## How to shard
1. Split by variant first (all variants of a year share the cached bias table, built once per process: `_bias_cache(tf, ...)`), then by year if a shard is still too long.
2. Suggested split for the cloud/laptop pair: laptop = `current`, `defaults`, every `CG*`, `TT-*`, `NEWS-*` and `DXY*` variant on 5m, years 2019-2026 (about 55 variants x 8 years = 440 jobs; measured here: 28 five-minute jobs (7 variants x 4 years) took about 1.5 hours with 4 workers, i.e. roughly 3 minutes per job, so about 22 hours for this shard at 4 workers). Cloud = the remaining `DECISIONS` on 5m, split by alphabetical blocks of variant names, then 1m.
3. Each shard writes its own `--out` folder (`runs/mentorship/shard_<n>`); merge by copying `<tag>_jobs/*.csv` into one folder and running `pd.concat` (or rerun `main_decisions` with the same `out`/`tag`: finished jobs are skipped, the concat is rebuilt).
4. Report per variant: trades, net, PF, win rate, max DD, 2019-22 vs 2023-26, against `current` and `defaults` (`mentorship.backtest.stats`).
- Example (laptop, PowerShell, detached; put the call in a script under `runs/`, as `runs/news_study.py` and `runs/tier_tug_cmp.py` do):
  `$env:MENTORSHIP_SRC="databento"; $env:PYTHONPATH="C:\Users\mason\bottrading"; Start-Process .venv\Scripts\python.exe -ArgumentList 'runs\my_shard.py' -RedirectStandardOutput runs\my_shard.out -RedirectStandardError runs\my_shard.err -WindowStyle Hidden`

## Not runnable yet / caveats
- **DXY rules (items 1-11, `DXY*` variants)** read the 1-minute spot DXY file, now on the laptop at `data/dxy/spot_dxy_1m_close_2019-2025_NYtime.csv.gz` (verified 2026-11-01: 14,081,703 bytes, 2,580,881 rows, 2019-01-01 to 2025-12-31, NY time; the loader `dxy.spot_path()` finds it). A cloud shard must copy it from the project library (`mentorship/data/dxy/`) to the same path, otherwise the DXY rules run as "no information" and equal the base. 2023 has about 32k fewer rows than other years (short scattered gaps). The 3a and `sym_gate` hourly rules use Databento DX 1h (on disk, 2019-2026).
- DXY rules have only been tested on synthetic data and a stand-in DXY (the inverse of ES). Treat the first real results as a smoke test, not a verdict.
- Not built: `fx_nonconf_exit` (EURUSD / GBPUSD), `dxy_smt="no_press"`, `udx_shape` bars (HistData UDX not on the laptop), the weekly-OB-open ladder level, `sym_dxy="daily"`, gold leg of the symmetrical gate, the COT extras (3e: waits for the COT loader).
- `news_cal="csv"` (default) and `Q92 ob_need_narrative=False` (default, Mase: more trades). With the Q92 narrative rule on, trades drop sharply (ES 5m Dec 2022 - Jan 2023: 0 vs 20).
- `sick_sister` now defaults to the ICT version when on (08:00 count, two references, consolidation days only); the old values are `study.COVERAGE_OLD` and are merged into `CURRENT` / `PRE_OWNER`.
- Details per stage: `mentorship/digests/build_log.md` (sections "tier_stl_mode / tug_required", "NEWS-csv vs NEWS-legacy", "Coverage gaps 1 and 3b-3d", "Coverage gap 2 and 3a", "DXY intraday rules").
- Leave the ict_fetch PIDs (17224, 516) and the Silver Bullet paper bot (`python -m silver_bullet paper`) alone.
