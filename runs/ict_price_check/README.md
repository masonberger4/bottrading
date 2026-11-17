# Our price data vs what ICT shows on his charts (2026-11-09)

Laptop, C:\Users\mason\bottrading. Read-only check of the engine's Databento data against prices visible in ICT's videos.

## Method

- 24 dated videos, 2022-12 to 2026-09: 2023 Mentorship, Trade Executions, 2024 Mentorship, 2025 Lectures, 2026 SMC. ES first (33 checks), plus MES (3) and NQ (11).
- From each chart frame I read the contract, timeframe, recording clock (bottom right, ET), and either the TradingView OHLC header of the live or hovered bar, or price labels ICT drew on swing highs/lows (midnight open, buyside/sellside, ORG). Caption checks used levels he states (e.g. "3876 and a quarter buy stops").
- Compared with the **unadjusted** contract price for the same minute: `data/mentorship/ES_1min_dbraw.parquet` for ES; for NQ, the engine parquet minus the per-bar `adj` from the meta parquet. `lk.py` looks up a bar or range and `find.py` finds a bar by its OHLC. All 47 checks are in `results.csv`.

## Result

| | Checks | Result |
|---|---|---|
| Exact match (every price read equal to ours) | 35 | 0.00 difference |
| Match within 0.25-0.5 | 7 | MES vs ES book (2), one NQ 1h open off by one tick, one 15-second axis read, and 3 spoken levels where ICT drops the half point ("3814" for 3814.50) |
| Miss | 5 | all late roll, 2 videos, 45-62 points |

**Misses: all late roll.**
- 2023-06-13 (CPI): ICT is on ESU2023 and our series is still on ESM2023 until 20:00 ET that day. Live price, CPI spike high and spike low are 45-46 points lower in ours, which is the +45.25 roll spread.
- 2024-09-17: ICT is on ESZ2024 and we're still on ESU2024 until 20:00 ET. The 10:08 high and 09:54 low have the same shape and timing, offset by -61.25 to -61.5 (roll spread +61.50).
- Both are inside the roll window yesterday's audit flagged (Finding 1). This adds that ICT trades the next contract on those days, so those sessions are wrong in absolute price for ICT-style levels, not only thin. On 2025-06-16 (also before our roll) ICT was still on NQM2025 and matched exactly, so his own roll timing varies.

**Ruled out:**
- Timezone: every bar matched at the same ET clock minute, in EST and EDT (Jan, Mar, Jun, Sep, Dec).
- Bad bars: none.
- Wrong contract outside roll weeks: none. TradingView's "B-ADJ" continuous chart (2026) equals the front contract on current dates and matched exactly.
- Back-adjustment: the engine's adjusted prices sit above ICT's by `adj` for that contract (e.g. +850.75 in Jan 2023, +671.75 in Jan 2024, +67.00 in Aug 2026). That is expected. Point distances are unaffected, but any absolute level typed in from a video has to be compared with raw prices or shifted by `adj`.

## Notes for rule building

- ICT's opening range gap uses the **16:14 close**: his "ORG low 4004.25" on 2023-03-27 is our 16:14 close, while our 16:00 close is 4002.00.
- A video's title or upload date can be a day after the session it shows. For example, SMC 2026 #37, uploaded 08-12, shows 08-11.
- Micro (MES) prices differ from ES by 0.25-0.5 at extremes.

## Fix

Rolling 2019-26 on the CME roll date (8 days before expiry) instead of Databento's ES.v.0 Tuesday would remove all 5 misses. That needs the next contract's bars for the roll weeks, the small Databento purchase from the audit (Mase's call). 2016-18 can be fixed for free from the outrights on disk.
