# Fixed-roll ES / NQ / YM series (2026-11-10)

Fixes finding 1 of `runs/data_audit_2026-11-09/README.md` (late rolls). New files only: the engine's
`data/mentorship/*.parquet` are unchanged; switching over is Mase's call.

## Output

`data/mentorship/roll_fix_2026-11-10/` (not in git), same names and layout as the engine's files:
`<S>_1min_db`, `<S>_1min_dbmeta` (adj, instrument_id, roll), `<S>_1min_dbraw`, `<S>_5min_db`, `<S>_5min_dbmeta` (.parquet),
2016-01-03 18:00 to 2026-10-16 16:59 ET, 43 rolls and 44 contracts each. To switch, copy them over the engine's parquets
(and regenerate the CSVs if anything reads them).

## Roll rule

Every roll is at 18:00 ET on the CME roll date, the Thursday 8 days before the third-Friday expiry: the session dated
expiry-7 (Friday) onward is on the next contract. It's a calendar rule, so there's no lookahead. On the 2016-18 outrights
(`explore.py`), the next contract's volume first leads in exactly that session (e.g. 2017-03-10: ESH7 572k, ESM7 1.08M).
The old series rolled 3-5 days later.

Sources: 2016-18 all outrights (`databento_extra/<S>_ohlcv1m_2016-18`), 2019-26 `<S>.v.0` plus the next-contract bars
bought 2026-11-10 (`databento_extra/roll_next_2019-26`, $4.12, 93 files, 1,127,719 bars). Back-adjusted with
`databento_extra.adjust_same_bar` (same-minute spread between the two contracts, which also removes audit finding 4's
one-bar move).

## Checks (`check.py`, vs the engine's current files)

| | ES | NQ | YM |
|---|---|---|---|
| Last pre-roll session RTH volume / normal, median (min): old | 0.32 (0.12) | 0.26 (0.12) | 0.28 (0.12) |
| same, new | 1.03 (0.67) | 1.02 (0.71) | 1.04 (0.58) |
| Minutes on a different contract | 118,257 | 120,921 | 90,347 |
| Same-contract minutes, max OHLCV difference | 0.0 | 0.0 | 0.0 |
| Minutes only in old / only in new | 922 / 462 | 1,967 / 1,002 | 5,634 / 6,681 |
| ...of the old-only minutes, inside 09:30-16:15 | 0 | 0 | 36 |
| Cumulative adjustment at 2016 start: old / new (pt) | 805.75 / 792.00 | 3,768.25 / 3,858.00 | 4,811 / 4,305 |

- Minute counts differ only because the two contracts trade in different minutes overnight. The 36 YM RTH minutes are on
  roll Fridays when YMZ6 / YMM6 / YMZ5 had no trade (2026-09-11: 27, 2026-03-13: 7, 2025-09-12: 2). Every session still
  passes the engine's 90% rule.
- **2019-03-13 (Databento: reduced quality):** kept as is. It falls after the March 2019 roll in both series, and the old
  and new bars that day are identical (same contract, 1,364 ES bars, 0.0 difference). The engine already trades on this day,
  so the fix changes nothing there.

## Side finding

`data/mentorship/NQ_1min_dbmeta.parquet` and `YM_1min_dbmeta.parquet` only cover 2019-01-01 onward. Their `_1min_db`
files start in 2016, so 1.03M NQ bars and 1.02M YM bars have no adj / instrument_id (ES meta is complete). The new folder has
full meta for all three.

## Switch (2026-11-11, Mase asked)

`switch.py` moved the engine's old ES / NQ / YM files (`<S>_1min_db`, `_dbmeta`, `_dbraw`, `<S>_5min_db`, `_dbmeta`,
CSV and parquet) to `data/mentorship/backup_pre_rollfix_2026-11-10/` (22 files), wrote the new CSVs in the old layout and
copied the fixed parquets in, newer than the CSVs. `verify_switch.py`: the engine's `load`, `load_meta` and `load_raw`
return the fixed series for 1 and 5 minutes, raw + adj = adjusted, and the session counts match the old files (ES 2,692,
NQ 2,692, YM 2,689). NQ and YM now have full 2016-26 meta and a `_1min_dbraw.parquet`.

To undo: `.venv\Scripts\python.exe runs\roll_fix_2026-11-10\switch.py --undo`.
