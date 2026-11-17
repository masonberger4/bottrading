# Narrow NQ morning engine (PR #82 option D), 2026-11-16

Asked by Mase ("Start A through E"). PR #82 framed this option as worth building only once A or B finds direction;
it was built now, with no direction input, so what is measured here is the shell by itself.

## What was built

A new switch in the engine, `Params.narrow` ("off" by default, so nothing changes unless it is set). With
`narrow="am"`, `run_day` runs only this model (`mentorship/narrow.py`) and none of the rulebook setups:

1. 09:30 to 11:30 only. No lunch, no PM, no order-block-before-the-break entry.
2. Sweep: price runs a resting pool by a tick (prior day's high / low, overnight high / low, London high / low).
3. Shift: a 1-minute bar closes through the last swing that formed before the sweep extreme.
4. Gap: the last 1-minute fair value gap of that leg.
5. Entry on the reaction: wait for price to come back into the gap and for a bar to close back out of it in the
   trade's direction, then buy / sell the next bar's open at market. (The old resting limit is a switch.)
6. Stop beyond the sweep extreme, target 2R, flat at 12:00, one trade a day.

Every piece is a switch (`nar_entry`, `nar_stop`, `nar_target`, `nar_be_at`, `nar_pools`, `nar_shift_n`,
`nar_gap_min`, `nar_win`, `nar_flat`, `nar_max_trades`, `nar_bias`); the list is in `narrow.py` and next to the
fields in `strategy.py`. 13 tests in `tests/test_narrow.py` (long, short mirror, stop, noon exit, limit entry, each
switch, and a no-look-ahead check that cuts the day off at the entry bar).

## How it was run

- 1-minute fixed-roll bars, NQ (the target), with ES and YM as a check. $1,000 risk a trade, no sizing cap
  (median risk $981 on NQ, largest $1,000), $5 a side per contract.
- `run.py`: a light runner that calls the same `strategy.run_day` day by day (the narrow mode needs no bias tables, so
  a variant takes seconds). Check: NQ 2024 through the full engine path (`runs/bt/run.py --tf 1`) gives the same 30
  trades and the same $.
- Base settings were fixed before any result was seen. Then 24 one-switch-at-a-time variants. "pick" = for each
  switch, the level with the best 2019-22 R a trade on NQ. 2023-26 was not used to choose anything.
- 2016-18 was also run as a second untouched check. It is kept out of the totals.
- Outputs: `results/summary.txt` (every variant, every market), `results/PICK.txt`, `results/funnel.csv`. Trades:
  `/mnt/project-files/mentorship/runs/nq_am_2026-11-16/trades.tgz`.

## Result

R = average result a trade in units of its own risk (x $1,000 = $ a trade). t under about 2 means it cannot be told
from zero.

| | trades | 2019-22 R (t) | 2023-26 R (t) | 2019-26 total | max drawdown | worst year | 2016-18 R (t) |
|---|---|---|---|---|---|---|---|
| NQ base | 229 | +0.07 (0.7) | +0.12 (1.0) | +$20.2k | -$11.1k (-11.4 R) | -$1.9k | -0.21 (-1.8), 70 trades |
| NQ pick (chosen on 2019-22) | 206 | +0.25 (1.8) | -0.05 (-0.3) | +$24.3k | -$12.6k (-12.7 R) | -$4.0k | +0.04 (0.3) |
| ES base | 239 | +0.08 (0.7) | -0.07 (-0.7) | +$0.1k | -$21.7k | -$12.0k | +0.13 (0.7) |
| YM base | 262 | +0.05 (0.5) | +0.05 (0.5) | +$12.2k | -$15.3k | -$7.8k | -0.24 (-1.6) |
| all three, base | 730 | +0.07 (1.1) | +0.03 (0.4) | +$32.4k | -$20.0k | -$4.4k | -0.13 (-1.5) |
| all three, pick | 629 | +0.13 (1.6) | -0.05 (-0.6) | +$24.4k | -$29.3k | -$11.1k | +0.10 (1.0) |
| all three, resting limit at the gap | 1,205 | -0.04 (-0.8) | -0.05 (-1.0) | -$52.3k | -$60.8k | -$17.1k | +0.02 (0.2) |

Reading:

1. **This is the first shell that is not clearly losing, but it is not an edge.** NQ base is up in both halves
   (+$20k on 229 trades, 6 of 8 years up, still up at twice the costs: +$17.4k), yet the t-stat is 1.1, about 29
   trades a year. A result like this turns up by chance roughly one time in four.
2. **Choosing on 2019-22 does not carry over.** The pick goes from +0.25 R to -0.05 R on NQ in 2023-26, and loses on
   all three markets together there. That is the test Mase set, and it fails.
3. **The second check fails for the base.** 2016-18 on NQ: -0.21 R on 70 trades; 23 of the 25 NQ variants lose
   there. (Caveat: point settings are scaled to 2019-26 prices, so 2016-17 has few trades.)
4. **ES does not confirm it**: zero over 2019-26 and negative in 2023-26 for 24 of 25 variants.
5. **Entry on the reaction beats the resting limit in 2019-26**: on NQ and YM in both halves and on all three
   together (about +0.05 R against -0.05 R a trade). It does not on ES in 2023-26 or in 2016-18, so this is a lean,
   not a finding. It agrees with PR #80.
6. **More trades wash it out.** Adding short-term swing pools gives 3,688 trades at 0.00 R (and -0.20 R in 2016-18).
7. The simple direction filters do not help reliably: the 08:30-open filter is best on NQ (+0.15 R both halves, 154
   trades) but -0.31 R in 2016-18; "with the prior day" is the only one positive in all three periods, on 366 trades
   (t 1.6). Neither is strong enough to act on; both are things option A is already scoring on every day.
8. Where the base result comes from (2019-26, all markets): 329 stops at -1.02 R, 137 targets at +1.98 R, 264 noon
   exits at +0.37 R. Stops are wide (the sweep extreme), so costs are only 0.01 to 0.02 R a trade; that, not a better
   read of direction, is most of the difference from the earlier tight-stop setups.

## What this means

As PR #82 expected, the shell alone has no proven edge. It is now ready for a direction filter: `nar_bias` is the
hook, and any bias that options A or B confirm can be added there and tested in minutes. Nothing here supports
trading it as it stands.

Risk and drawdown, NQ base, 2019-26: $981 median risk a trade, max drawdown -$11.1k (-11.4 R), longest stretch below
a prior equity high 724 days, worst year -$1.9k (2023).

## Caveats

- 25 variants share most of their trades, so "18 of 25 positive in both halves on NQ" is one result seen 25 ways,
  not 25 confirmations.
- Market entry is modelled as the next 1-minute open plus the standard cost. Real slippage at 09:30 to 10:00 on NQ
  can be more than a tick; twice the costs is shown for that reason.
- No news, weekday or weekly-rule filters are applied in this mode.
- NQ and YM point settings are scaled by the price ratio to ES, as in `runs/bt/run.py`.
