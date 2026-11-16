# DXY and bond switches vs defaults (2026-11-16)

Mase asked whether the engine uses DXY and bonds, then asked for this backtest. Results only: no engine code or default changed.

## What is on by default

Nothing. At engine 2101d04 (= `mentorship`) every DXY and bond switch is `"off"` (only `dxy_filter="tag"`, a label). That includes
`sym_gate` and `dxy_states`: decisions D1-D3 of 2026-10-31 set the mode they use when on, the defaults were not flipped.

## Runs

Runner `runs/bt/run.py`, 5m, ES + NQ + YM each as the traded market, 2019-26, fixed-roll data copied from the laptop (ES 2021
defaults reproduces the 11-13 run exactly). `$` is at "$1k risk" (the $400k notional cap makes the real risk about $340-490);
R counts each trade in units of its own risk.

| name | switches |
|---|---|
| defaults / wd_off | engine defaults / week rule off (`week_done_on_draw='off'`), for a larger sample |
| dxy / wo_dxy | `sym_gate='scalp', dxy_states='filter', dxy_intrade='bank', dxy_nonconf_exit='after_partial'` (D1-D3) |
| bond / wo_bond | `bond_range='scalp', bond_dir='filter'` (ZN daily, Databento) |
| both / wo_both | all six |

The 1m DXY file ends in 2025, so the DXY switches do nothing in 2026 (identical trades). Choose on 2019-22, check on 2023-25.

## Result, all three markets together (full tables: `summary.txt`, `report.txt`)

Change against the base of each group; t is the paired weekly t-stat of the R difference.

| variant | 2019-22 trades | 2019-22 change | t | 2023-25 trades | 2023-25 change | t |
|---|---|---|---|---|---|---|
| defaults (base) | 278, -$5.9k, -14.3 R | | | 216, -$0.3k, -4.5 R | | |
| dxy | 262 | +$4.4k, +7.3 R | 0.9 | 206 | -$2.6k, -13.4 R | -0.9 |
| bond | 266 | +$0.8k, +4.8 R | 0.6 | 201 | -$1.0k, -3.4 R | -0.3 |
| both | 253 | +$2.4k, +1.4 R | 0.1 | 194 | -$2.9k, -9.5 R | -0.6 |
| wd_off (base) | 1,492, -$53.5k, -202.6 R | | | 1,120, -$40.3k, -161.4 R | | |
| wo_dxy | 1,344 | +$11.8k, +56.5 R | 2.3 | 1,021 | +$0.9k, +5.9 R | 0.2 |
| wo_bond | 1,358 | +$6.4k, +34.9 R | 1.5 | 1,007 | +$4.2k, +21.1 R | 0.9 |
| wo_both | 1,240 | +$12.6k, +65.6 R | 2.2 | 928 | +$6.1k, +38.6 R | 1.2 |

- On defaults the switches touch too few trades to say anything, and the 2019-22 pick (dxy) is worse in 2023-25.
- With the week rule off, DXY looks good in 2019-22 (t 2.3) and does not carry over (t 0.2). "Both" is the 2019-22 pick and stays
  positive in 2023-25, but not significantly (t 1.2), and the set still loses: -137 R then -123 R.
- Most of the gain is fewer trades from a losing set. wo_both drops 17% of the trades; dropping 17% at random would give about
  +34 R (2019-22) and +28 R (2023-25) against the +66 R and +39 R seen. R per trade moves from -0.136 to -0.110 and -0.144 to -0.132.
- By market it is not consistent: bonds help NQ and YM in 2019-22 and hurt ES, then the reverse in 2023-25 (ES +30.8 R, t 4.5,
  one cell of 24); DXY helps NQ in 2019-22 (+26 R) and hurts it in 2023-25 (-18 R).

## Reading

The DXY and bond switches as built do not add a measurable edge. They behave like the other filters in `runs/bt/README.md`: they
skip some losing trades without making the remaining ones profitable. No case for turning them on by default on this evidence.

Trade files: `/mnt/project-files/mentorship/runs/dxy_bond_2026-11-16/trades_and_skips.tgz`. Summary script: `summary.py`.
