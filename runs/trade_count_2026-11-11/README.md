# Why the engine trades so rarely (2026-11-11)

Engine 2101d04 (`.worktrees\scb`, = mentorship), ES 5m databento on the fixed-roll data, $1,000 risk, 2019-26. Nothing in the engine
or its defaults was changed. Scripts: `funnel.py` (runs + skips + strategy.FUNNEL counter), `analyze.py`, `week_done_quick.py`.
Outputs (laptop only): `out/` (2019-26, defaults and week-done off), `out_fn/` (2021 + 2024 with the setup funnel).

## Results

| | trades | $ | 2019-22 | 2023-26 |
|---|---|---|---|---|
| defaults (fixed-roll data) | 166 | -490 | -5,902 | +5,412 |
| defaults, old roll data (handoff) | 168 | +810 | -5,901 | +6,711 |
| week_done_on_draw="off" | 899 | -2,106 | +4,937 | -7,043 |

With week-done off, by setup: lunch 515 / +$5,798, am_mm 125 / -$5,216, pm_sb 104 / -$8,771, pm_last_hour 68 / +$3,078,
pm 23 / +$908, pre7 23 / +$1,101, release_ob 11 / +$1,166, ndog_scalp 17 / -$275, venom 13 / +$105. 2024 alone is -$12,844.

## Funnel

1. **Day level (skips).** In 2,147 sessions under the defaults, `day_week: week_done` kills 1,378 (64%). The next biggest
   day-level kills are the PRE7 chop veto (92, PRE7 window only), the PRE7 holiday-week veto (83), `sloppy: big_prev` (80) and
   `holiday_eve` (64). The holiday-week veto also closes the AM and PM on about 30 sessions a year.
2. **Why week_done bites so hard** (`week_done_quick.py`). X15d stops the week once ANY of last week's high, last week's low
   or this week's NWOG CE is reached. The NWOG is small (median 4.75 pt), so its CE is reached on Monday in 356 of 406 weeks.
   One of the three levels is reached Monday in 383 of 406 weeks. Only 449 of 2,030 Mon-Fri sessions stay open (22%), or 843
   if only PWH / PWL counted.
3. **Session level, with week-done off.** 1,524 AM sessions are open, but only 132 of them get an AM trade (9%). Most trades
   come from the lunch setup.
4. **Setup level** (strategy.FUNNEL, per year, counts are bars, not sessions). The AM model reaches its first step, the
   liquidity sweep (`1_sweep`), ~143 times a year, and the MSS after it (`2_mss`) ~51 times. All models together arm ~300
   orders a year. The biggest per-bar rejections are, in order: `x_dw_objective_done_pm` (N9.3, the PM is done once the
   AM delivered the objective; ~2,200 bars), `x_dw_big_day_am` (N8.4, a big opening-range gap gives up the AM; ~570),
   `x_draw_delivered` (~510), `x_news_judas` (M9; ~300), `x_dw_big_org` (~260), `x_dw_london_adr` (N9.6; 84-309) and
   `x_two_driver` (~125).

## Against ICT's notes

- X15d comes from 038 ~6:33 ("once a weekly objective, the higher-TF draw, is delivered, stop for the week") and 101.
  The note itself says which HTF array counts is not defined (038 line 50). In 038 the objective is one called target in
  the week's direction (the DXY daily VI; ES's 4259 sell-side in 101). Counting any of three levels on both sides, one of
  them a 5-point gap midpoint, is a much stricter reading than that [our reading]. It's also one source only (singles.csv
  m2024-41).
- The "nearest objective" option already exists (`week_done_pick="nearest"`, variant `X15d_week_done_nearest`, PWH / PWL only).

## Suggested next steps (Mase's call)

1. Screen 2019-26 with week-done read as ICT's single weekly draw: `week_done_pick="nearest"` with PWH / PWL only, and
   with the NWOG CE dropped. Compare it with off and with the defaults.
2. The count isn't the only problem: with week-done off the engine trades ~112 a year and loses $2.1k. pm_sb (-$8.8k) and
   am_mm (-$5.2k) lose. Lunch and pm_last_hour make money. Look at those setups before widening anything else.
3. If more AM trades are wanted, the narrowest point is sweep -> MSS (~35% pass). Then N9.3 objective-done-PM and the
   N8.4 big-ORG AM sacrifice.
