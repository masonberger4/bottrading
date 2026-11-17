# Do ICT's codable bias rules call the day's direction? (2026-11-16)

Option A of PR #82, asked by Mase. Test only: no engine code, default or data changed.

## Answer

No. None of the 30 codable bias rules calls direction better than chance on ES, NQ or YM.

- Chosen on 2019-22: 2 of 60 rule-and-horizon tests pass the usual 5% bar (|t| >= 1.96). About 3 would pass by luck
  alone, and neither comes close to the bar that allows for 60 tries (|t| >= 3.34).
- Checked on 2023-26: both fail. Premium / discount (`pd`) was 3.0 points *worse* than chance in the morning in
  2019-22 and 1.2 points better in 2023-26. Nearest draw (`draw`) was +2.2 points to the close in 2019-22 and +0.1 after.
- Across all 60 tests the edge in one half says nothing about the other half (correlation -0.12). The largest
  |t| anywhere in 2023-26 is 1.72.
- The best hit rate of any full-coverage rule is about 52%, and "always long" gets 52.8% (morning) and 54.5% (to the
  close) in the same period with no skill.
- Against ICT's own 36 dated trade-sides the best rules agree with him 64-68% of the time (`pdhl` 21 of 31,
  `draw_ord` 23 of 36). On 36 trades that is within luck (always long agrees 56%), and those two rules show no edge
  on the market itself.

So, as PR #82 put it: no entry model built on these bias readings can work, because the readings carry no
direction. This closes the fully automatic "ICT daily bias" route. Option B (his calls made before the fact) is the
remaining test of whether his direction has any information.

## What was tested

- Markets and data: ES, NQ, YM, fixed-roll Databento 5m, every trading day 2019-01-02 to 2026-10-16
  (1,001 days in 2019-22, 943 in 2023-26).
- Rules (full list with one-line meanings at the top of `out/report.md`):
  - 20 engine columns, built by the engine's own `htf.table` at the 09:30 cut with default settings
    (engine = branch `mentorship` at 75c9a9b): reaction, draw, premium / discount, combo, flip, ordered draw, daily
    and weekly candle draw, 20-day premium / discount, daily order flow, weekly bias, order-block mean threshold,
    month-week-day, weekly direction, NWOG bias, draw + P/D agree, quarterly shift.
  - 10 simple readings coded in `score.py` from the bars: midnight open, 08:30 open, weekly open, bias plus the
    cheap side of the midnight / 08:30 open, previous candle, previous day's high / low taken or rejected,
    three-way agreement, COT commercials, high / low of week in.
- Outcome: from the 09:30 open to 11:30, and to 16:00. Everything a rule uses is known at 09:30.
- Score: hit rate on the days the rule makes a call, minus the hit rate its long / short mix would get by chance in
  that period (the "edge"). This matters because the market drifts up: without it any long-leaning rule looks skilled.
- Significance: t-stat on the edge over days, with ES, NQ and YM pooled by day (they move together, so they are one
  bet a day, not three).
- Power: with about 1,000 days a half, a real edge of about 3.5 points (53.5% vs 50%) would give a t-stat of about 3
  (one standard error is about 1.1 points). Check: a planted rule that is right 10% more often than a coin scores +4.8 points, t = 4.1; a
  rule that knows the morning scores +24.9, t = 23.9. So the test can see an edge that size; smaller ones could hide.

## Results (pooled, sorted by 2019-22 |t|; all 30 rules, per market and both horizons in `out/report.md`)

09:30 to 11:30:

| rule | 2019-22 hit % | edge | t | 2023-26 hit % | edge | t |
|---|---|---|---|---|---|---|
| pd | 46.2 | -3.0 | -1.99 | 50.6 | +1.2 | +0.96 |
| ob_mt | 48.2 | -2.0 | -1.75 | 51.0 | +0.5 | +0.44 |
| react | 52.3 | +1.5 | +1.53 | 49.3 | -1.6 | -1.04 |
| wo_above | 52.2 | +1.8 | +1.49 | 50.4 | -0.0 | -0.12 |
| pdhl | 52.3 | +1.9 | +1.49 | 50.3 | +0.1 | -0.17 |
| combo | 51.9 | +1.2 | +1.46 | 49.3 | -1.5 | -1.36 |
| always long (reference) | 52.8 | 0.0 | | 52.4 | 0.0 | |

09:30 to 16:00:

| rule | 2019-22 hit % | edge | t | 2023-26 hit % | edge | t |
|---|---|---|---|---|---|---|
| draw | 52.2 | +2.2 | +1.98 | 49.9 | +0.1 | +0.04 |
| pd | 47.5 | -1.4 | -1.24 | 49.7 | +0.5 | +0.37 |
| prev_candle | 48.8 | -1.6 | -1.21 | 50.7 | +0.4 | +0.35 |
| howlow (560 calls) | 46.6 | -2.9 | -1.10 | 45.6 | -4.0 | -1.72 |
| draw_ord | 50.6 | +1.2 | +0.98 | 48.9 | -0.5 | -0.43 |
| always long (reference) | 54.5 | 0.0 | | 53.2 | 0.0 | |

Every other rule is inside |t| < 1.2 in 2019-22.

## Caveats

- Engine columns use default settings. Their many switches were not searched: with no signal in any default
  reading, searching 60+ variants would only find luck.
- "Direction" here is open-to-11:30 and open-to-close. A rule could in principle call a short swing inside the day
  and still fail this; the entry studies (PR #76, #80) already found no move in the trade's direction after entries.
- The 10 simple readings are my coding of rules ICT states in several ways; they are not engine code.
- The seasonal, sentiment and "narrative" inputs are not codable and are not here. That is option B's ground.
- In the pooled tables the edge is weighted by market-day and the t-stat by day, so on thin rules the two can differ
  in sign when both are near zero.

## Files

- `build_tables.py`: builds the 09:30 bias table per market from an engine checkout (about 70 s each).
- `score.py`: outcomes, the 10 simple rules, hit rates, significance, ICT-trade agreement.
- `out/report.md`: every rule, both horizons, both halves, per market. `out/hit_rates.csv`: the same as data.
- Tables: `/mnt/project-files/mentorship/runs/bias_direction_2026-11-16/table_{ES,NQ,YM}.pkl`.

Rerun: `cd <mentorship checkout> && PYTHONPATH=. python <repo>/runs/bias_direction_2026-11-16/build_tables.py TABLES`
then `python runs/bias_direction_2026-11-16/score.py TABLES runs/bias_direction_2026-11-16/out`.
