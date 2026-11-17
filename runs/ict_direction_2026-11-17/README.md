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

## Option C: how he picks the day and the moment (added 2026-11-17, `dayfilter.py`, `out/report_c.txt`)

Mase asked for A, B and C after PR #101. A and B run in their own threads. This is C.

1. **His call days differ from his stated no-trade days in a few plain ways.** 79 call days against 39 no-trade days
   (2023-26). He calls when the night has already moved and there is a gap, and he passes on quiet days:

   | | call days | no-trade days | all other days |
   |---|---|---|---|
   | opening gap, median (share of the daily range) | 0.35 | 0.24 | 0.29 |
   | gap under 0.10 | 11% | 28% | 19% |
   | overnight range, median | 0.75 | 0.57 | 0.65 |
   | Friday | 18% | 33% | 20% |
   | CPI or FOMC day | 4% | 15% | 8% |
   | NFP day | 9% | 8% | 4% |
   | day after a range over 1.5x normal | 11% | 10% | 12% |
   | any of: NFP / CPI / FOMC / PPI, holiday eve, day after a big range, small gap | 33% | 51% | 40% |

   The split is real but soft: these conditions would have kept him out of a third of the days he did call.
   He says "the morning after a large range day" is a skip, but his call days show it as often as any other day.
2. **Those skip conditions help the coded read a little, at 09:30 only.** The read (PR #101) traded at the 09:30
   open, on days with none of the four skip conditions, $1,000 risk:

   | | 2019-22 | 2023-26 |
   |---|---|---|
   | NQ, days he would not skip | 534 trades, +0.06 R, +$32.9k, drawdown -$19.8k | 532, +0.06 R, +$29.9k, -$26.7k |
   | NQ, days he would skip | 346, +0.09 R, +$30.4k, -$14.2k | 325, -0.08 R, -$26.2k, -$36.8k |
   | ES, days he would not skip | 532, +0.08 R, +$41.6k, -$12.5k | 516, +0.17 R, +$86.3k, -$17.1k |
   | ES, days he would skip | 354, -0.06 R, -$19.7k, -$41.2k | 344, -0.01 R, -$3.4k, -$24.3k |

   Positive in all four cells, which nothing else in this study is. By day (both markets averaged): +0.06 R, t 1.3 in
   2019-22 and +0.09 R, t 1.7 in 2023-26; all eight years +0.07 R, t 2.1. It is weak: negative on NQ in 4 of 8 years,
   and it was found after trying about ten conditions, so some of it is selection. The one condition that helps most
   consistently is skipping the day after a big range (those days lose in 7 of 8 market, time and half cells).
3. **At 10:00 nothing rescues it.** With or without the skip conditions the read at 10:00 loses in 2019-22 on both
   markets (t -1.7 to -3.3) and wins in 2023-26.
4. **The "kind of call" split does not carry over to every day.** On his own calls, trades back across the overnight
   range made +0.68 R and trades toward the extreme +0.07 R. On every day the coded read shows no such pattern
   (back across the range at 09:30: NQ +0.00 and -0.04 R, ES -0.03 and +0.11 R). So that split describes *his* calls;
   it is not a market rule. Whatever makes his reversal calls work is in the moment he chooses, and position in the
   overnight range does not capture it.

**Where C leaves it.** His choice of day can be roughly copied (active night, a real gap, not CPI or FOMC, not Friday)
and it adds a little to the read at the open. His choice of moment is still not coded. The best all-days rule so far is
"the read at 09:30 on days he would not skip", about +0.07 R a trade with drawdowns of $12k to $27k: a lead for
thread B to test inside the engine, not something to trade.

## Update 2026-11-17: the two-kinds split on new calls only (option A)

14 more calls were logged (Trade Executions and X posts; `../ict_calls_2026-11-17/README.md`, Set 5). 11 are same-day
calls between 07:00 and 15:00, all made before the read existed, so they are a clean test. `python build.py;
python analyze_new.py` writes `out/report_new.txt`. `analyze.py` still reports on the first 114 calls only.

| on the 11 new same-day calls | new | old (83 calls) |
|---|---|---|
| the read picks his side | 3 of 11 (27%) | 52 of 83 (63%) |
| he is right when the read agrees | 1 of 3 | 43 of 52 (83%) |
| he is right when it disagrees | 7 of 8 | 19 of 31 (61%) |
| back across the overnight range: right, plain entry at $1k risk | 0 of 2; 1 trade, +$0.8k, DD $0 | 30 of 37; 36 trades, +0.68R, +$24.4k, DD -$2.0k |
| from the middle third | 3 of 3; 3 trades, +$4.6k, DD $0 | 14 of 20; 18 trades, +0.51R, +$9.2k, DD -$3.8k |
| toward the extreme price already sits at | 5 of 6; 6 trades, -0.22R, -$1.3k, DD -$3.3k | 18 of 26; 25 trades, +0.07R, +$1.8k, DD -$5.3k |

**Not confirmed.** What the new calls say:

- The read does not reproduce his side on new calls: 3 of 11. If the old 63% were real, 3 or fewer of 11 happens about
  2 times in 100. The four features were picked after seeing the old calls, and this looks like that.
- "Right more often when the read agrees" went the other way (1 of 3 against 7 of 8). With 11 calls that is not
  evidence of the opposite either (15 in 100 by chance).
- By where price sits, the money side still leans the old way: the 6 calls toward the extreme lost money with the
  plain entry (-0.22R a trade) although 5 of 6 were right at his horizon, and the 4 others made +1.35R a trade. Only 2
  of the 11 new calls were back across the overnight range, so that kind was hardly tested.
- All calls together (94 same-day): back across 37 trades +0.68R, +$25.2k, DD -$2.0k; middle 21 trades +0.66R, +$13.8k,
  DD -$2.0k; toward the extreme 31 trades +0.01R, +$0.5k, DD -$8.6k.

So the one part that survives is narrow: **his calls toward the extreme price already sits at do not pay with a plain
entry** (31 trades, about zero). The stronger claim, that a coded read tells his good calls from his bad ones, is not
supported by the new calls. The new set is small, is all 2023-25, and is made of trades he chose to publish, so it
cannot settle it; about 40 more same-day calls would. The cheapest source is the 43 silent Trade Executions videos
(date and often side in the title; the minute needs the frames on the laptop).
