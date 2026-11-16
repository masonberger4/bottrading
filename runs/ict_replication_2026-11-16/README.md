# Make the engine take ICT's video trades (2026-11-16)

Follow-up to `runs/ict_replication_2026-11-13` (PR #69: the defaults take 0 of ICT's 41 dated video trades). Mase asked to find
why each trade is missed and add what is missing as switches, then rerun. No default was changed.

Engine: `mentorship` 0c46ea6 plus the two switches below. Data: fixed-roll Databento ES / NQ / YM copied from the laptop.
Runs: ES 2023, NQ 2023, NQ 2024 (the 41 trades; N17 2026 not run), in the cloud, 1-minute bars unless stated, $1k risk, no
sizing cap. The 5m defaults rerun gives the 11-13 trades exactly (31 trades, same entries and stops), before and after the change.

## Result

| run | matched of 41 | on his side that day | opposite trade in his window (chance check) |
|---|---|---|---|
| defaults, 5m (11-13) | 0 | | |
| existing switches opened up, free running (`vf`) | 17 | 39 | 13 |
| same plus the two new switches, free running (`vh`) | 15 | 39 | 13 |
| entry test, order block + FVG entries, before the new switches (`o1`) | 18 | 34 | 1 |
| entry test, order block + FVG entries, with the new switches (`ob`) | **20** | 35 | 1 |
| entry test, FVG entry only, before (`o2`) | 6 | 16 | 1 |
| entry test, FVG entry only, with `mss_on_fvg` and `leg_pd=0` (`o9`) | 12 | 22 | 2 |

Match = same side, inside his stated minutes +/- 30 and within 6 ES / 25 NQ points of his entry (`compare.py`).

- **Free running** is the engine deciding everything. Opened up it does take 15 to 17 of his trades, but it also takes a
  trade the other way in the same minutes and price band on 13, and it trades 9 to 11 times a day and loses
  (`vh`: ES 2023 2,326 trades -539 R; NQ 2023 2,625 trades -409 R; NQ 2024 2,816 trades -223 R). Those matches are mostly chance.
- **Entry test** gives the engine ICT's side and time (the scan runs only on his days, his side, from 45 minutes before his
  entry to 15 after) and asks one thing: does the entry model find his entry? It is a measurement, done in the runner
  (`ICT_ORACLE=1`), not an engine switch and not a strategy. With the new switches it finds **20 of 41**.

So the engine can now reproduce about half of his entries when it is told which way and when. What it cannot do is pick his
side and his moment by itself: the rules that choose direction and session (the locked draw, one trade per session, the weekly
rule) keep it out, and with them off it trades everything.

## Why each trade was missed (per-bar trace, `trace_patch.py` + `why_miss.py`)

Under the defaults, on ES 2023: outside every session window (E07, E11, E12, E14, E16, E25), session closed because the draw
had delivered or the session had its one trade (E01, E06, E08, E09, E22-E24), locked draw on the other side (E05, E13, E15,
E17, E19, E21), no named pool swept on 5m bars (E02, E03, E10, E12). Then, once those are open:

- The "both sides armed, stand aside" rule (`neutral_5050="armed"`) shuts most AM windows when both directions are allowed.
- The FVG entry existed but armed late: it waits for a break of the swing high, and ICT is already filled on the first return
  into the first gap (E02 2023-01-17: gap complete 09:42, his fill 09:43-09:44, engine shift 09:44).
- The "entry in the discount half of the leg" rule (`leg_pd=0.5`) held orders that he took above the leg's midpoint (E02).

Still missed in the entry test (21):
- No order armed on his side in his window (10): E07 (09:21 pre-open), E25 and N07 (NFP at 08:31 / 09:33), N04 (FOMC 14:25),
  N10 (07:47), N12 (Asia 19:00), E16, E17, N02, N05. These are release, pre-market and Asia entries or have no sweep first.
- An order armed, at another price or time (11): E01, E10, E11, E13, E15, E18, E19, E20, E22, E24, N08. Typical gaps: he
  re-enters or pyramids after a first trade (E13, E15, E20, E24), or uses a different gap than the last one after the shift (E18).

## Switches

New (both default to the built behaviour, tests in `tests/test_ict_replication_switches.py`):
- `session_trades` (default 1): fills allowed per session slot. ICT took four shorts on 2023-05-04 and three AM trades inside
  20 minutes on 2023-08-18.
- `mss_on_fvg` (default False): a gap completed wholly after the sweep extreme counts as the shift, so the FVG order arms
  at once. Acts only with `ob_entry` "post_mss" or "both".

Existing switches used (set `vh`, the "ICT replication" set):
```
week_done_on_draw='off', sloppy_tests=(), fed_chair_skip_am=False, skip_holiday_eve=False, holiday_week_skip=False, skip_post_holiday_am=False, ob_entry='both', objective_done_pm='off', big_day_am_skip=False, news_judas='off', two_driver_gate=False, draw_relock=True, pre_0900=True, am=(570,710), lunch=True, draw_lock='off', am_from_0830=True, pool_swings=True, session_trades=4, use_bias=False, ob_valid='any', neutral_5050='off', mss_on_fvg=True, leg_pd=0.0
```
What each does: week rule and day filters off; FVG entry after the shift as well as the order block (`ob_entry`); PM open after the
AM delivers; big-gap, news-judas and two-release rules off; draw lock off (both sides); pre-open 09:00 window, AM from 08:30
to 11:50, lunch session; short-term swing lows as pools; open filter off (`use_bias`); any order block (`ob_valid`); 50/50
stand-aside off; no leg-discount rule.

## Read this before using the set

- It is a replication aid, not a candidate default: free running it loses about 1 R every four trades on all three runs.
- In the free run 80% of trades are the order-block-before-the-break entry, and they carry the loss (ES 2023: 1,616 trades,
  -436 R; FVG entries 618 trades, -100 R).
- ICT posts winners, 41 trades on 33 days, 2023-24 only.
- The full test suite was not run in the cloud (only the new test file); both switches are inert at their defaults and the
  5m defaults run is unchanged.

## Files

`rep_run.py` (runner: `ICT_TRACE=1` per-bar trace, `ICT_ORACLE=1` entry test), `compare.py`, `why_miss.py`, `trace_patch.py`,
`compare_vh.csv`, `compare_ob.csv`, `compare_o9.csv` (one row per ICT trade). Trades, armed orders, funnels and traces:
`/mnt/project-files/mentorship/runs/ict_replication_2026-11-16/outputs.tgz`.

## Suggested next steps (Mase's call)

1. Direction is the gap. Test the engine's direction pick alone against ICT's 41 sides (locked draw, daily bias) before more entry work.
2. Add the missing entry families: the 08:30 release entries (E25, N07), FOMC afternoon (N04), Asia (N12).
3. Audit the order-block entry's same-bar stops (idea 2), since it is 80% of the open set's trades and all of its loss.
