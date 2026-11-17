# ES data restore and accuracy audit (2026-11-09)

Laptop, C:\Users\mason\bottrading. All checks are read-only except the CSV restore below.

## 1. ES_1min_dbraw.csv restore

- The file had been cut off mid-row after 6,331 rows (2016-01-03 18:00 to 2016-01-08 08:32, 425,472 bytes, a whole number of 512-byte sectors). Kept as `data/mentorship/ES_1min_dbraw.truncated_2026-11-09.csv`.
- `backup_2026-10-30/ES_1min_dbraw.csv` is an older build (2,727,393 rows, different 2016-18 bars from 58,693 minutes on), so it was not used.
- Rebuilt from `ES_1min_dbraw.parquet` (OHLCV) plus `instrument_id` from `ES_1min_dbmeta.parquet` (`restore_dbraw_csv.py`): 3,793,103 rows, 2016-01-03 18:00 to 2026-10-16 16:59 ET, same header and number format. Its first 425,000 bytes are byte-identical to the truncated file.
- The file's modified time was set back to the parquet's (2026-11-01 14:05:17) so the engine keeps reading the existing parquet unchanged.
- Cause: not provable. Every file in data/mentorship has the same 2026-11-01 14:05:17 time, which fits a bulk copy or move of the data folder that day; the drive had 12.9 GB free the next morning (runs/disk_cleanup_2026-11-02.md). An interrupted write (out of space or killed) is the most likely cause. The engine reads the parquet, which was complete, so no backtest read the truncated rows.

## 2. Audit of the data the engine backtests on (ES, 2016-01-03 to 2026-10-16)

Outputs: `audit.out` (sections A-G), `indep.out` (H, I).

| Check | Result |
|---|---|
| A. Fresh rebuild from the Databento downloads (`databento/ES_ohlcv1m.dbn.zst` + `databento_extra/ES_ohlcv1m_2016-18.dbn.zst`) | Identical to the engine parquet: same 3,793,103 bars, 0.0 difference in every column, same contract per bar, same back-adjusted prices. |
| B. Duplicates / order / NaN | None. 5-minute stamps all on the 5-minute grid. |
| C. Bad prices | No zeros, no high<low, no OHLC inconsistency, every price on the 0.25 tick, no zero-volume bars. All 85 one-minute moves over 1% are real events (Sunday reopens, March 2020, 2022 CPI days, April 2025 tariffs). 3 move-and-revert bars, all real. |
| D. Time zone / DST | Correct. Sunday reopen at 18:00 ET on 553 of 555 Sundays in both EST and EDT. The 09:30 volume surge is at 09:30 ET in both (median 5.6x EDT, 5.2x EST); none at 10:30. vs the Dukascopy CFD, 1-minute return correlation is 0.974 at lag 0 and ~0 at +-1 and +-60 min; no day matches better with a 1-hour shift. The 16:15-16:30 halt is present until mid-2021 (CME removed it then). |
| E. Missing days / gaps | 32 weekdays with no regular session, all full CME holidays (incl. Bush 2018-12-05, Carter 2025-01-09). 91 days fail the engine's 90% rule, all holiday early closes (MLK, Presidents, Memorial, July 3/4, Labor, Thanksgiving + Friday, Juneteenth, Dec 24). 2,688 of 2,783 regular sessions have all 390 minutes; the 4 with 5-20 missing minutes are the March 2020 circuit-breaker halts. 9 overnight gaps over 30 min, real outages (e.g. CME outage 2025-11-28). |
| F. Rollovers | 43 rolls, 44 contracts, never rolls back. Back-adjustment is constant within each contract and matches meta `adj` exactly. See finding 1. |
| G. 5-minute vs fresh resample of 1-minute | Identical (0.0 difference, same 760,505 bars). No 5-minute bar mixes two contracts. |
| H. vs Dukascopy S&P 500 CFD, 1-minute, 2019-2026 (2,000 days) | Median daily 1-minute return correlation 0.993; RTH range ratio median 1.009, no day outside 0.7-1.4; RTH high time within 2 min on 92.5% of days, low 95%. |
| I. vs Yahoo ES=F daily, 2016-2026 (2,684 days) | High and low match within 0.5 pt on ~94% of days. All 114 days more than 5 pt off are explained: 96 roll-week days (Yahoo stays on the expiring contract to expiry) and 18 days after a holiday (Yahoo merges the holiday session). |

## 3. Findings

1. **Rolls are late, and later in recent years.** The series stays on the expiring contract until 3-5 days before expiry (2016-18: Sunday of expiry week; 2019-26: Tuesday 20:00 ET of expiry week, Databento's ES.v.0). By then most volume has moved: on the last session before each roll the series' RTH volume is 12-40% of normal (2024-26: 12-30%). Prices are real trades and track the new contract by a fixed spread, so levels and patterns are close, but these sessions are thin. Touches about 1-3 sessions per quarter, roughly 45-130 of ~2,690 sessions (2-5%). Fixing 2016-18 is free (all outrights are on disk); 2019-26 needs the next contract's bars for those days (a small Databento purchase, Mase's call).
2. **Back-adjusted prices are far from real prices in early years.** The cumulative adjustment is +805.75 pt at 2016-01-03 (adjusted ~2,844 vs real 2,038, about 40% high), shrinking over time. Anything in points (stops, targets, R) is unaffected. Anything in percent of price, or a fixed-point threshold compared across years, is distorted in 2016-22. Whether the engine uses percent-of-price anywhere was not checked.
3. **Roll jumps are large since 2022 (+19 to +74 pt).** Under CONTRACT B (`htf_series="raw"`) the HTF levels come from the unadjusted series; the data carries the exact per-bar `adj` to map them, and `htf.py` maps raw levels by `adj` before use. Data side is correct; the mapping itself is engine logic.
4. **Adjustment includes one bar's move.** Each roll's shift is the new contract's first open minus the old contract's last close, so it absorbs that minute's move (rolls happen at the 18:00-20:00 ET reopen, so typically under 1 pt). Cumulative effect on 2016 levels is a few points at most.
5. **73 single bars stamped 17:00-17:59 ET on weekdays** (mostly May-Aug 2018, a few 2016-17, 2020, 2023), one per day. Pre-open or settlement prints, harmless for the 09:30-16:15 day frames.

Nothing else wrong was found. The minute data the engine trades on matches its Databento source exactly and agrees with two independent vendors.
