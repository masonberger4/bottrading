# Does the engine take ICT's own trades? (2026-11-13)

Replication check asked by Mase: take the trades ICT himself shows in the videos (dated entries, stops, exits), confirm them
on the bought Databento data, then see what the engine did on those days. Results only; no engine code or default changed.

Engine 0c46ea6 (mentorship branch, same code as 2101d04), ES / NQ 5m databento, fixed-roll data, $1,000 risk. Run in the
cloud on a copy of the laptop's data files; the cloud run reproduces the laptop's `trades_defaults_2023.csv` exactly
(31 trades, same entries, stops, exits and P&L), and the rebuilt bias table equals the laptop's.

Files: `ict_trades.csv` (the 42 ICT trades, `|` separated), `price_check.txt` (each one against raw contract prices),
`compare.csv` (engine vs ICT, one row per trade), `trace_run.py` (one engine year with a per-day setup funnel),
`compare.py`, `check_prices.py`, `out/` (engine trades, skips and per-day funnel for ES 2023, NQ 2023, NQ 2024).

## 1. ICT's trades and the data

42 live or paper trades with a date, a side and prices were found in the notes' "Trade examples" sections: 25 ES
(Jan to Dec 2023) and 17 NQ (2023, 2024, one 2026). Sources: 2023 Mentorship (35), 2024 Mentorship (6), Trade Executions (1).
40 of them have a readable entry price. The 2025 Lectures and 2026 SMC notes carry rules but no "Trade examples" section,
so their live trades are NOT in this sample yet.

Against the unadjusted contract prices: **38 of the 40 priced entries trade at ICT's price inside his stated minutes**, and every
timed exit (46 of 46 outside Dec 8) is there too. The two exceptions:
- **2023-12-08 (NFP, mt23-105): roll mismatch.** ICT is still on ESZ2023 (entries 4569.25 / 4565.75); our fixed-roll
  series moved to ESH2024 on Thu Dec 7 (the CME roll date), about 50 points higher. So the roll fix is right for
  Jun 2023 and Sep 2024 but one day early here; ICT's own roll timing varies (same note as the 2025-06-16 check).
- 2023-05-08 NQ (mt23-053): fills were not legible in the video (~13250-13265); price was 13261-13290 in that window.

## 2. What the engine did

Two engine versions per day: **defaults**, and **open** = the day filters off
(`week_done_on_draw='off', sloppy_tests=(), fed_chair_skip_am=False, skip_holiday_eve=False, holiday_week_skip=False,
skip_post_holiday_am=False`). NQ is run as its own book the way `study._dec_job` runs the partner (the defaults trade ES only).
A match = same direction, entry within about 30 minutes and near ICT's price. N17 (2026) was not run, so 41 trades.

| | ES (25) | NQ (16) | all (41) |
|---|---|---|---|
| defaults: same trade taken | 0 | 0 | **0** |
| open: same trade taken | 2 | 2 | **4** |
| open: same trade, same result | 1 | 0 | **1** |
| open: engine traded the opposite way that morning | 5 (E09, E14-E17) | 0 | 5 |

The four matches with the filters open:
- **E18 2023-05-22 (Silver Bullet short): the one real replication.** ICT short 10:05 @ 4206.25, stop 4208.25, out
  4198 to 4193.5. Engine `am_mm` short 10:05 @ 4205.25, stop 4209.50, out 10:10 at t1+t2, +1.45R. Blocked in the defaults
  by the AM chop veto (`sloppy:chop`).
- E04 2023-01-24: ICT long 09:40-09:46 @ ~4013.5 after the 09:39 low (4009). Engine long 09:35 @ 4015.50, stop 4012.00,
  stopped in the same bar: it bought before the sweep finished.
- N03 2023-05-08: ICT long 09:45-10:00, +60 points. Engine long 10:05 and 10:35, both stopped (stops 3.5 and 8 NQ points).
- N16 2024-12-05: ICT short (stopped the rest at 21,526 after two limit fills at 21,490). Engine short 09:35 and 09:40,
  both stopped inside 5 minutes.

### Why the defaults take none (first blocker per trade)

| blocker | trades | which |
|---|---|---|
| "done for the week" (`week_done`, X15d) | **35** | all except the six below |
| holiday-week stand-aside (`holiday_week_skip`, card B) | 1 | E02 (MLK week, Tue) |
| Fed chair day + holiday week | 1 | E21 (Jun 21 2023, Juneteenth week, Powell) |
| day before a holiday (`skip_holiday_eve`) | 1 | N07 (Fri Sep 1 2023, NFP) |
| AM chop veto (`sloppy_tests` "chop") | 2 | E18, N03 |
| no pre-open setup fired (big opening gap rule `dw_big_org`) | 1 | E07 (09:21 entry) |

ICT traded on 35 days the weekly rule calls finished, which is strong evidence the engine's reading of that rule
(any of last week's high, last week's low, or the opening-gap midpoint) is not how he trades.

### Why it still misses 37 of 41 with the day filters open

1. **Entry model.** The engine's funnel never reaches an FVG entry: `3_fvg` is 0 on every one of these days, and all
   608 trades of the three open runs enter as `lunch_macro` (313) or `ob_pre`, a limit at the order block before the
   break (265). About half of ICT's entries (22 by the note's description) are a 1-minute (or 15 / 30-second) fair value gap after a sweep and a
   shift. The engine also runs on 5-minute bars; ICT's stops here are 2 to 4 ES points off 1m structure.
2. **Time of day.** About half of the engine's trades are the lunch setup (11:50-13:30). ICT has 4 of 41 there.
   His trades: 20 in the AM 09:30-11:30, 7 in the PM / last hour, 6 before 09:30 (07:50-09:21 and 08:30 releases), 1 Asia,
   3 with no time in the notes.
3. **PM closed after the AM delivers** (`objective_done_pm="reversal_only"`, reject `dw_objective_done_pm`): the top
   reject for 26 of the 41 trades. None of ICT's 7 PM trades (E03, E06, E08, E17, E21, N04, N05) is taken.
4. **AM given up after a big gap or big prior day** (`big_day_am_skip`, rejects `dw_big_day_am` / `dw_big_org`):
   E01, E05, E06, E07, E10, E19, N01, N08, N11.
5. **News rules**: `news_judas` (E03, E11, E19, N04, N06) and the two-release gate `two_driver_gate` (E25, N07) keep the
   engine out on release mornings where ICT traded (NFP Dec 8, NFP Sep 1, FOMC Jun 14).
6. **Direction.** On 2023-05-04 ICT was short four times (+$19.9k on the day) while the engine was long twice at
   10:20 and 10:45. On 2023-02-08 the engine was long at 09:35 and ICT short at 10:22 (both won).
7. **Instrument.** From mid-2023 ICT trades NQ in almost every live video (all 6 of the 2024 trades here); the defaults
   trade ES only. Run as its own book with the filters open, NQ loses: 2023 213 trades -$20.1k, 2024 198 trades -$4.3k
   (ES 2023 open: 197 trades +$3.5k, lunch +$7.9k, everything else -$4.4k).
8. **Management** (not scored): ICT pyramids (up to 30 lots on Jun 21 2023), scales out at each liquidity level and
   re-enters after a stop (Aug 18 2023). The engine takes one entry with fixed rungs.

## 3. Caveats

- ICT posts mostly winners (nearly every trade here made money; E22 is the one clear loss), so this shows whether the engine can find his setups,
  not what his win rate is.
- 41 trades on 33 days is a small sample, weighted to Jan-Sep 2023 and to ES. NQ 2025-26 is not covered.
- "Open" turns off six filters at once to see the core setup logic; it's a diagnostic, not a proposed default.
- One reporting bug seen: the `venom` trade on 2023-01-24 is written at 4847.00, the back-adjusted price, while every
  other trade in the file is in raw contract prices (4016.75). P&L is unaffected, the price column is wrong for venom.

## 4. Suggested switches to test (Mase's call, nothing changed)

1. Weekly rule: `week_done_levels=("pwh","pwl")` or off. This check agrees with the 11-12 weekly-rule screen.
2. A 1-minute FVG entry after sweep + shift as the AM / PM entry (`entry_kind` "fvg" on a 1m run), next to `ob_pre`.
   This is the biggest gap between the engine and what ICT does on screen.
3. `objective_done_pm="off"` so the PM and last hour can trade with the day's direction.
4. `big_day_am_skip=False` (or `big_day_am_resume=630`), `news_judas="off"`, `two_driver_gate=False`, each on its own.
5. `sloppy_tests=("big_prev",)` (drop the chop veto), `holiday_week_skip=False` (card A).
6. Roll: let the roll day follow volume inside the roll week instead of a fixed Thursday (Dec 8 2023).
7. Re-run this check after each change: `trace_run.py` + `compare.py` give the match count in about a minute per year.

Next step if wanted: add ICT's 2025-26 NQ live trades from the transcripts and score the engine on a 1-minute run.
