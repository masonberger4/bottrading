# Single ICT ideas tested on their own, 2026-11-16

Mase (23:55 UTC): start options A to E of PR #82. This is option E: stop coding the whole rulebook and test single
ideas alone. No engine, no engine code or default changed. Silver Bullet was not re-tested.

`ideas.py` (rules and fills, 7 seconds to run), `report.py` (tables), `output.txt` (every table).
Every trade: `/mnt/project-files/mentorship/runs/single_ideas_2026-11-16/trades.parquet` (225,015 rows).

## Result

**No single idea has an edge.** Of 85 variants with enough trades, 14 were positive in 2019-22 and only 2 stayed
positive in 2023-26, both too weak to count (below). Every idea's best 2019-22 pick lost or went flat in 2023-26.

$ at a true $1,000 risk per trade, no size cap, ES + NQ + YM together. "Pick" = the variant with the best 2019-22
t-stat. t counts one day as one result. Max drawdown is all three markets traded together, 2019-26.

| idea | pick (chosen on 2019-22) | 2019-22: trades, avg R, $, t | 2023-26: trades, avg R, $, t | 2023-26 avg R with 1 tick slippage | max drawdown |
|---|---|---|---|---|---|
| Sweep and reverse | Asia high/low swept in the AM, 3R target | 361, +0.12, +$44k, 1.2 | 377, -0.12, -$46k, -1.4 | -0.17 | -$67k |
| Fair value gap | PM gap, entry at the edge, 1R target | 1,303, -0.02, -$23k, -0.5 | 1,216, -0.06, -$77k, -1.7 | -0.08 | -$124k |
| Order block | London, middle of the block, 3R target | 1,709, -0.09, -$145k, -1.7 | 1,685, -0.10, -$161k, -1.9 | -0.12 | -$379k |
| Time window | follow the day's move in the last hour | 2,994, +0.04, +$124k, 1.2 | 2,823, -0.02, -$53k, -0.5 | -0.05 | -$115k |
| Opening gap fade | 09:30 gap, full fill by 10:00 | 2,849, +0.02, +$50k, 1.0 | 2,679, -0.03, -$74k, -1.6 | -0.05 | -$102k |

The average trade of each idea across all its variants (2019-22 / 2023-26): sweep -0.06 / -0.06 R, fair value gap
-0.09 / -0.04 R, order block -0.13 / -0.06 R, time windows -0.01 / -0.02 R, gap fades -0.03 / -0.03 R. Costs are about
0.03 to 0.08 R a trade, so sweeps, gaps and time windows are roughly coin flips that pay the costs. The order block
and the fair value gap limit entries are worse than a coin flip (many variants at t -3 to -5 over the whole period),
which agrees with the engine results.

## What each idea was

One plain rule each (exact rules at the top of `ideas.py`). Patterns on closed 5-minute bars, fills and exits
followed on 1-minute bars, one trade per variant per market per day, costs $5 a side per contract.

- **Sweep and reverse:** a bar trades through a level and closes back inside. Levels: previous day, previous week,
  Asia, London and AM-session highs and lows. Windows: London, AM, PM. Targets 1R, 2R, 3R. 33 variants.
- **Fair value gap:** a three-bar gap after a large bar, limit entry at the gap edge or middle, in the direction of
  the move. 18 variants.
- **Order block:** first close through the latest swing, limit entry at the last opposite bar. 18 variants.
- **Time windows:** fade the morning after lunch, fade London in the NY morning, follow the day in the last hour,
  fade the week on Friday afternoon. 4 variants. The midnight and 08:30 open rules are left to option A.
- **Opening gaps:** fade the evening gap (17:00 close to 18:00 open), the Sunday gap, and the 09:30 gap, to half
  or full fill. 12 variants. The engine's `ndog_scalp` is a different rule and was checked in PR #79.

## The two that were positive in both halves

- **Previous week's high/low swept in the AM, 1R target:** +0.04 R then +0.08 R, but only 218 trades in 8 years and
  t 0.9. With 2R or 3R targets the same sweep loses. Not distinguishable from luck.
- **Trading with the Sunday gap (not an ICT idea):** fading the Sunday gap at the first 18:00 print lost heavily
  (-0.25 R, t -6), so the mirror was added: +0.13 R in 2019-22 (t 2.3), +0.06 R in 2023-26 (t 1.0), +0.03 R with one
  tick of slippage. NQ alone: +0.20 R then +0.11 R. It depends on being filled at the first print of the week: the
  same trade entered at 18:05 gives +0.08 R then -0.05 R. So this is the opening minute moving away from a stale
  first print, not something a market order would capture. Worth a look only with tick data, not worth building on.

## Caveats

- These are simple versions of each idea, with no bias, no news filter and no combination. That is the point of the
  test, but it means a "no" here is a no for the idea alone, not for ICT using it with discretion.
- A stop closer than a typical 5-minute bar is moved out to that distance (so costs do not swamp tiny stops).
- When a stop and target fall in the same minute it counts as a stop. That affects under 1% of trades in most
  variants (up to 3.7% for Sunday gaps); counting them as wins changes no conclusion (`all_avgR_best` in `output.txt`).
- Three trades were checked by hand against the bars (one sweep, one gap, one order block): levels, entry, stop and
  exit all as the rule says.

## What this means

Sweep, fair value gap, order block, time window and opening gap do not carry an edge alone on ES, NQ or YM at
5-minute scale, in either half. Together with the engine results, the codable entry patterns are not where any edge
is. If one exists it is in direction and day selection, which options A and B test.
