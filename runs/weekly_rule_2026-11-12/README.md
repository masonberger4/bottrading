# Weekly-rule screen and why pm_sb / am_mm lose (2026-11-12)

Engine 2101d04 (`.worktrees\scb`, = mentorship), ES 5m databento, fixed-roll data, $1,000 risk, 2019-26. No engine code or
default was changed. Runner: `runs/trade_count_2026-11-11/funnel.py` via `run1.ps1` / `run2.ps1`. Tables: `table.py <variants>`
(`step1_table.txt`), splits: `losers.py` (`losers_wd_off.txt`). Trade files (laptop only): `out/`.

## Step 1: which weekly objective stops the week (X15d, SG-m2024-41)

| variant | switch | trades | $ | 2019-22 | 2023-26 | max DD |
|---|---|---|---|---|---|---|
| defaults | PWH, PWL, NWOG CE, any | 166 | -490 | -5,902 | +5,412 | -9,803 |
| wd_nearest | `week_done_pick="nearest", week_done_levels=("pwh","pwl")` | 383 | -372 | +2,001 | -2,373 | -18,373 |
| wd_pwhl | `week_done_levels=("pwh","pwl")` (any) | 338 | +4,441 | +2,099 | +2,342 | -13,224 |
| wd_off | `week_done_on_draw="off"` | 899 | -2,106 | +4,937 | -7,043 | -20,521 |

By year ($): defaults 459 / -3,444 / 93 / -3,011 / 365 / -1,923 / 5,981 / 989; wd_pwhl 5,246 / -182 / -355 / -2,609 /
-2,091 / -2,545 / 5,332 / 1,646 (2019 ... 2026).

Choosing on 2019-22 picks wd_off, which fails the 2023-26 check (-7,043; 2024 alone -12,844, mostly lunch -9,281).
wd_pwhl (drop the NWOG CE, keep "any" of PWH / PWL) is the only reading positive in both halves. Lunch carries every
version (wd_pwhl: lunch 231 trades / +7,251; everything else -2,810).

## Step 2: why pm_sb and am_mm lose (wd_off, 104 + 125 trades)

- Both are the pre-break OB limit (`entry_kind="ob_pre"`, `entry_style="raid"`), stop at the OB body MT. Median risk is
  2.25-2.5 ES pts (lunch: 6.5). 64-68% of trades are stopped, the median stop-out comes 0-5 min after entry.
- They lose in both halves (pm_sb -4,841 / -3,930, am_mm -1,703 / -3,513) and in every year from 2020 on; only 2019 is up.
- **Wider stops don't fix it** (all on top of wd_off):

| variant | switch | trades | $ | 2019-22 | 2023-26 | pm_sb $ | am_mm $ |
|---|---|---|---|---|---|---|---|
| wd_off | - | 899 | -2,106 | +4,937 | -7,043 | -8,771 | -5,216 |
| off_stop_ext | `ob_stop="ext"` (sweep extreme) | 877 | -9,800 | -1,215 | -8,584 | -10,868 | -5,415 |
| off_stop_wick | `ob_stop_kind="wick"` | 901 | -7,412 | +710 | -8,122 | -10,093 | -5,571 |
| off_mt_close | `mt_break="close"` | 897 | -2,487 | +4,309 | -6,796 | -8,499 | -4,176 |
| off_minrisk4 | `min_risk_pts=4.0` | 615 | -2,010 | +3,328 | -5,338 | -5,919 | -5,584 |

  So the losses are the entries' direction / selection, not stop noise. pm_last_hour uses the same entry and stop and is
  +3,078 (but +4,008 of that is 2020 alone).
- Splits that look different (small samples, not tested, would be data-mining without a source): am_mm with a Judas
  tag -5,791 vs +575 without; am_mm `delivery="up"` -6,331 vs down +1,115; pm_sb on 08:30 / 10:00 news days -5,450 vs
  -3,321 on none; trades against `b_draw` lose more than with it in pm_sb (-6,385 vs -2,386) but both lose.
- Post hoc (removing the rows, not a rerun): wd_pwhl without pm_sb / am_mm = 281 trades, +6,580 (+3,142 / +3,437);
  wd_off without them = 670, +11,881 (+11,481 / +400).

## Step 3: baseline by year

The cards-defaults baseline on the fixed-roll data is the `defaults` row above (PR #66). The only setting that moves it is
the weekly-rule level set (wd_pwhl); its by-year row is above. Stop switches don't move it the right way, so they aren't
carried forward.

## Suggested next steps (Mase's call)

1. Decide the X15d reading: wd_pwhl is the only both-halves-positive one; ICT's own note says one weekly target in the
   week's direction, which none of these fully is.
2. Rerun wd_pwhl (and wd_off) with the AM and PM 14:00-15:00 setups switched off as a real run, not post hoc.
3. Lunch is the engine's edge and it is lumpy (2024 -9.3k with week-done off): look at lunch 2024 before trusting it.
