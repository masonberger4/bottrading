# How ICT calls the morning's direction, coded and tested (2026-11-17)

Asked by Mase: "focus on how ICT calls the direction of the day and fine-tune the engine to predict that the way ICT
does". Results only: no engine code, default or data changed. Follows PRs #83 (bias rules), #87-#92 (his dated calls),
#93 (no coded column reproduces his side: 56%) and #97 (his calls made money with a plain entry).

## Short answer

1. **What he says he is looking at is nearly always a nearby level, not a bias.** Of his 114 dated calls, 83 are
   same-day calls. The stated target is one of: the half of the opening gap (16 calls), relative equal highs or lows
   (about 20), another intraday pool such as the 08:30 or London high or low (about 20), an old gap level (new day or
   new week opening gap, yesterday's settlement, the midnight open: about 15), and for the rest a daily or weekly
   level. The stated reason is most often "that side has not been taken yet" or "the other side went first".
2. **Coded, those reasons reproduce his side better than anything before, but not well.** Eleven new features, each
   read at his call time. Best single ones: fade the opening gap 76% of 33 calls, fade the 08:30 move 81% of 16, toward
   yesterday's settlement 65% of 83, the side of the overnight range not taken last 63% of 83. A model on all eleven,
   each day predicted from the others, picks his side on 61% to 66% of 83 (PR #93's old columns: 56% of 95). With 83
   calls a coin lands between 39% and 61%.
3. **The new finding: his calls come in two kinds, and only one kind works.** When the coded read agrees with him he
   was right 83% of the time (43 of 52); when it disagrees, 61% (19 of 31). Chance gives a gap that large 3 times in
   100. In money, his side with the plain entry of PR #97 at $1,000 risk:

   | his call is | trades | R a trade (t) | total | max drawdown |
   |---|---|---|---|---|
   | back across the overnight range (price in the far third from his target) | 36 | +0.68 (2.9) | +$24.4k | -$2.0k |
   | from the middle third | 18 | +0.51 (1.6) | +$9.2k | -$3.8k |
   | toward the extreme price is already at (continuation to a daily or weekly level) | 25 | +0.07 (0.3) | +$1.8k | -$5.3k |

   So his edge is in the calls back toward a level inside the range (gap, settlement, equal highs or lows on the far
   side). His continuation calls toward higher-timeframe levels are a coin flip. This fits PRs #87-#92: his day and
   week outlooks were weak, his morning calls strong.
4. **Run on every day, the coded read is not an edge, so the engine still cannot call direction by itself.** The
   read (four features summed) traded every day at 10:00 loses in 2019-22 (NQ -$94k, ES -$131k, t -2.5 and -3.7) and
   makes money in 2023-26 (NQ +$64k, ES +$78k, t about 2). Chosen on 2019-22 it would be traded the other way round
   and then lose in 2023-26. It fails the project test. On his call days in 2023-26 the same read makes +0.51 R a
   trade at 10:00 against +0.06 on the other days: he adds the choice of day and moment.
5. **His opening gap rule alone is the only piece that is positive in both halves, weakly.** Short a gap up and long a
   gap down at the 09:30 open, same stop, 2R, flat 12:00: NQ +$68k (2019-22, max drawdown -$27k) and +$30k (2023-26,
   -$38k); ES +$47k (-$40k) and +$94k (-$18k). About +0.06 R a trade, t 1.6 and 1.8 by day. Positive in 6 of 8 years
   on NQ and 7 of 8 on ES. Too thin and too deep in drawdown to trade as it is. His own claim of "70% for half the gap
   by 10:00" holds only for small gaps: the half gap is reached by 10:00 on about 75% of days with a gap of 0.1 to
   0.2 of the daily range, 40% at 0.35 to 0.6, and 10% above 1.0.

## What this means for the engine

- The gap between the engine and him is now narrower and better described: he trades a return to a nearby untaken
  level, on days and at moments he picks. The level and side can be coded (63% to 66% agreement). The day and moment
  cannot yet.
- The useful rule to carry forward is a filter on *kind of call*, not a new bias: side = toward the untaken level
  across the overnight range; never toward the extreme price already sits at.

## What was built

- `feat.py`: the features, each using only bars before the given minute (1-minute fixed-roll bars, NQ and ES).
  - `s_gap` fade the opening gap until its half is reached; `s_settle` toward yesterday's 16:14 settlement;
    `s_mid_rev` toward the midnight open.
  - `s_req` toward the nearer untouched pair of relative equal highs or lows (5-minute swings, last 3 sessions, within
    0.02 of the 20-day average range); `s_sweep` against the side whose swing was run in the last hour.
  - `s_first` the overnight high or low made last was "taken", so the other one is next; `s_onpos` toward the far half
    of the overnight range.
  - `s_oldgap` toward the nearest untouched new day or new week opening gap; `s_gapcl` the side with more of them.
  - `s_judas` fade the move since 09:30; `s_830fade` fade the 08:30 move.
- `build.py`: every day 2019-26 at 09:30, 09:45 and 10:00 (`out/days.csv`), and his 83 same-day calls at his call time
  (`out/calls_feats.csv`). `gap.py`: his gap rule by gap size (`out/gap.csv`). `analyze.py` writes `out/report.txt`,
  which has every number above.
- Entry for all money numbers: PR #97's plain entry (stop 0.25% of price on NQ, 0.21% on ES, 2R target, flat 12:00,
  stop first when a bar touches both, $1,000 risk, no cap, costs 0.25 NQ / 0.10 ES points).

Data: copy `NQ_1min_db`, `NQ_1min_dbraw`, `ES_1min_db`, `ES_1min_dbraw` (.parquet, from `/mnt/project-files/mentorship/data/fixed_roll_2026-11-10/`) to the `DATA` folder named in `feat.py`; `pip install pyarrow scikit-learn`; then `python build.py; python gap.py; python analyze.py` (about a minute). `out/days.csv` and `out/gap.csv` are rebuilt, not committed.

## Caveats

- The stated targets and reasons come from the call files of PRs #87-#92 (taken from the captions by those threads);
  the transcripts were not re-read here. The counts by kind of target in point 1 are a hand sort.
- 83 calls, all 2023-26, from published videos. The 83% against 61% split has about a 3 in 100 chance of being luck,
  and the "read" was put together after seeing which features leaned his way, so treat it as a lead.
- NQ and ES move together, so the two markets are not two independent tests.
- Call times are estimates (plus or minus 15 to 30 minutes).

## Next steps (Mase's call)

- A. Log more of his calls (Trade Executions and Charter sets, and his X posts) to see whether the two-kinds split
  holds on new calls. This is the cheapest way to confirm or kill point 3.
- B. Add the read to the engine as a direction switch, off by default, and run the narrow morning engine with it. The
  market test above says not to expect an edge in 2019-22.
- C. Work on the missing part, the choice of day and moment, using the 43 stated no-trade days and what he says on
  them (news days, the day after a large range, small gaps, "no bias").
