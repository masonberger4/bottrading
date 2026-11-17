# Learning how ICT picks days and direction: groundwork (option C of PR #82), 2026-11-16

Asked by Mase ("Start A through E"). PR #82 says option C is only worth doing if A (bias rules against the market) or
B (his calls scored before the fact) finds something, so this is the groundwork: the list of things he cites, a day
table built from them, and a test that is ready to take A's and B's outputs. No engine code, default or data changed.

## What is here

- `FEATURES.md`: what ICT cites when he picks a side and a day, with the digest rule each comes from, the column that
  stands for it, and the ones that cannot be coded.
- `build_days.py`: one row per market per trading day (ES, NQ, YM, 2017-01 to 2026-10, 7,293 rows). 27 signed columns
  (+ = bullish), 25 day columns, 5 outcome columns. Everything is known at 09:30 New York; distances are in ADR units
  (5-day average daily range) so the three markets pool. Standalone, about 40 s. Output: `out/days.csv` (not committed,
  copy at `/mnt/project-files/mentorship/runs/learn_ict_2026-11-16/days.csv`).
- `model.py`: the four tests below. Output: `out/report.txt`.

## First run (built-in columns only, his 41 dated trades as the calls file)

Outcomes are 09:30 to 11:30 and 09:30 to 16:00 in ADR units. ES, NQ and YM on one day are averaged into one
observation before any hit rate or t-stat, because they are nearly the same bet. No entries, stops or costs.

1. **Each signed column alone.** 0 of 27 has |t| > 2 in 2019-22 (1.4 expected by chance). Best in 2023-26: index SMT
   t = +1.7 (+0.7 in 2019-22), overnight raid of yesterday's high or low +1.4 (+0.8). Nothing to build on. Option A will
   say this properly with the engine's own bias columns; this is only a cross-check from simpler definitions.
2. **Direction model on all 52 columns** (fit 2019-22, checked 2023-26). 09:30-11:30: logistic 50.8% of days right,
   t = -0.6; boosted trees 48.4%, t = -1.7 after 71% in the fit years (pure overfit). 09:30-16:00: 51.9% and 52.5%,
   below always-long. The surest fifth of days is no better. So the columns together do not call the side either.
3. **Day model.** Whether the morning will be large is predictable (AUC 0.69: quiet and wide regimes persist). Whether
   it will be one-way is not (AUC 0.48). So the "clear day" he waits for is not visible in these columns at 09:30.
4. **His picks** (32 one-sided market-days from the 41 trades; far too few, run only to prove the pipeline):
   - No column points his way more often than a coin allows (range 33% to 66%, coin band 32% to 68%).
   - A side model predicts 44% of his sides from the other days; always-long gets 56%.
   - A day model separates his days from the other days of the same months with AUC 0.565.
   - Run on 2019-22, which none of his calls touch: his-side model +0.005 ADR a day (t = +0.6); on the fifth of days
     most like his +0.035 ADR (t = +1.8), on the rest +0.005. Not significant, and with 34 positive days it is noise
     until B supplies more.

**Reading:** with the features he names, as far as they can be coded, neither the side nor the one-way day shows up.
That matches PR #82. The pipeline works end to end, so C can be answered in minutes once A and B land.

## Rerun with option A's columns (PR #83), 2026-11-17

A's 30 engine bias columns (`/mnt/project-files/mentorship/runs/bias_direction_2026-11-16/bias_cols.csv`) joined
through `--a-cols`; output `out/report_with_A.txt`. 57 signed columns in all.

- Still 0 of 57 columns with |t| > 2 in 2019-22.
- Direction model, 2023-26: 09:30-11:30 logistic 49.6% (t = -1.3), trees 47.9% (t = -2.5); 09:30-16:00 52.6% and 52.8%,
  level with always-long (52.7%). Adding A's columns makes the fit years look better and the check years no better.
- His picks: side model 56% of 32, exactly what always-long gets. A's `pdhl` points his way on 70% of 27 days, just
  outside the coin band, and A shows it has no edge on the market.
- The +0.035 ADR (t = +1.8) on "days most like his" in the first run is gone: -0.014 (t = -0.8). It was noise.

So A's answer carries over: the side cannot be read from the codable rules, alone or combined, and a model cannot
recover his side from them. C now rests entirely on B. If B's calls made before the fact are not clearly better than
a coin, C should stop here.

## Final rerun with option B's call log, 2026-11-17

All four sets B scored (`/mnt/project-files/mentorship/runs/ict_calls_2026-11-17/calls.csv`, 157 rows: 114 one-sided
calls, 43 stated no-trade days, 145 said before the move, 2023-01 to 2026-09), with A's columns joined. Output
`out/report_calls_all.txt`. 95 one-sided market-days match the day table (the rest are after the data ends on
2026-10-16, or days with opposite calls).

- **His calls do carry something.** On those 95 days the market's 09:30-11:30 move went his way 64% of the time and
  09:30-16:00 61% (B's own scoring at his horizon: 79 of 114). A coin on 95 days stays inside 40% to 60%.
- **The columns do not see what he sees.** Best single column agrees with him 65% of 71 days (`s_wk_iof`), most sit
  at 40% to 62%. The market direction model picks his side on 51% of the days.
- **A model cannot recover his side.** Each day predicted from the others: 56% of 95, where always-short gets 51%.
  That is inside the coin band (plus or minus 10 points).
- **Nor his days.** His call days against his 43 stated no-trade days: AUC 0.506, the same as chance.
- **On the market, the copy of him is worth nothing.** Run on 2019-22 (none of his calls): 49.0% of mornings right
  (t = -0.5), and on the fifth of days most like his 46.7% (t = -1.1). To the close 51.4% (t = +1.1).

**Conclusion: stop option C.** B shows his before-the-fact calls are better than a coin, so there is something in his
read. But it is not in the 57 codable side columns or the 25 day columns: a model trained on them cannot tell which
side he will take or which days he will pass, and the copy has no edge on years he did not call. More of the same
kind of column is unlikely to change that (A's 30 engine columns added nothing). What he uses is either on the
chart in ways we have not coded (the reaction after 09:30, which draw he means that day) or in his head.

What would reopen it: a new kind of input that agrees with his side well outside the coin band on these 95 days
(for example, his stated draw level per day from the transcripts, or intraday columns at his call time instead of
09:30). The pipeline takes it through `--a-cols` in minutes.

Caveats: 95 days is enough to rule out a strong link (a column that agreed with him 70% or more would show), not a
weak one. B's reference times are estimates (plus or minus 15 to 30 minutes), and my outcome windows are fixed
09:30-11:30 and 09:30-16:00, not his horizon.

## How A and B plug in

- **A** (bias rules): a CSV with `day`, `market` (optional) and columns named `s_<name>` (signed, + = bullish) or
  `c_<name>` (unsigned), one row per day, values known by 09:30. Run `model.py --a-cols FILE`; they join the table and
  go through parts 1 to 4 next to the built-in ones.
- **B** (his calls before the fact): a CSV with `date`, `market`, `side` (`long`, `short` or `none` for a stated
  no-trade day), and optionally `before` (1 = said before the move) and `source`. Run `model.py --calls FILE`. With 30 or
  more stated no-trade days the day model uses those as its "no" days instead of every other day of the month.

## What decides whether C goes further

- B gives at least about 150 dated one-sided calls **and** his side beats the market on them by a clear margin. With
  fewer, a side model cannot be told from a coin (the band is about plus or minus 100 / sqrt(n) percentage points).
- Then: the side model must predict his sides from held-out months (part 4b well above always-long), and part 4d
  (the market in years with none of his calls) must be positive in both 2019-20 and 2021-22.
- If A finds a column that holds in both halves, it goes in as `--a-cols` and part 2 is rerun before anything else.

## Caveats

- Simplified definitions: daily bars are 18:00 to 17:00; daily order flow is "closes through the prior day's high minus
  closes through its low over 5 days", not the engine's order-block reading. A's columns are the fuller versions.
- The dollar column ends in 2025 (spot file); PPI dates before 2019 only, so `c_news830` after 2018 is NFP and CPI.
- His 41 trades are shown winners at many times of day, 2023-26. Part 4 treats them as "days and sides he chose",
  which is what B is meant to replace with calls made before the move.
- Reported in ADR, not dollars at $1k risk: there are no trades here, only side and day. Dollars, risk and drawdown
  come back when a side filter is put on an entry (option D).
