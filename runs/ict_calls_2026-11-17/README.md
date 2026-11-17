# ICT's calls made before the fact, scored (option B of PR #82). Set 1: 2024 Mentorship (2026-11-17)

Asked by Mase ("Start A through E"). Log and results only: no engine code, default or data changed.

## Short answer

- In the 2024 Mentorship live streams (Aug 5 to Oct 28 2024, plus one December outlook) ICT made **25 dated directional
  calls** on NQ and stood aside on **13 stated no-trade days**. 5 more sessions had no call.
- **18 of the 25 calls were right at his own horizon (72%).** The same guess on the neighbouring 80 or so trading days
  wins 49%. Price reached +0.25% in his direction before -0.25% on 18 of the 22 calls where either was reached.
- It is a small sample. 18 of 25 has about a 2% chance of happening by luck, and the plausible range for the true
  rate is roughly 54% to 86%. Counting only calls that are clearly stated before the move: 14 of 20 (70%).
- The information is short-lived. Scored at the 16:00 close instead of his horizon, same-day calls are 14 of 22 (64%,
  not distinguishable from luck). If each call is assumed to come 30 minutes later than estimated, 11 of 18 (61%).
- The moves are small: median +0.28% (about 55 NQ points), mean +0.66% (three days of the August rebound carry it).
- So the first honest number says his **direction for the next one to two hours is probably better than a coin
  flip**, on the days he chooses to speak. That is not the same as a profitable system: PR #82 found that even on
  his day and side the engine's entries lost.

## What counts as a call

A statement, made on a dated live stream before the move, of which way NQ should go next or which level it should
reach, with a horizon (the opening half hour, the morning, the afternoon, the week). Each call has a `ref` time (when
it was in force, New York time) and an `end`. Excluded: trades he says he took before the stream and shows
afterwards, hindsight walk-throughs, and conditional statements ("if it takes this low, then...").

Scoring (`score.py`, NQ 1-minute raw prices, fixed-roll files):
- **right at the horizon end**: price at `end` is beyond price at `ref` in the called direction.
- **first touch**: which came first after `ref`, +0.25% in his direction or -0.25% against.
- **target**: where a price is given or can be computed (ORG mid-gap, 09:30 open, London low), did it trade by the deadline.
- **same call on other days**: the same direction, `ref` and `end` applied to every other session within 60 days.

## Results

| group | calls | right at the horizon end | same call on other days | first to +0.25% vs -0.25% | mean move | median move |
|---|---|---|---|---|---|---|
| all calls | 25 | 18 (72%) | 49% | 18 of 22 (82%) | +0.66% | +0.28% |
| clearly before the move | 20 | 14 (70%) | 49% | 13 of 17 (76%) | +0.58% | +0.25% |
| up calls | 15 | 11 (73%) | 52% | 10 of 13 (77%) | +0.82% | +0.32% |
| down calls | 10 | 7 (70%) | 46% | 8 of 9 (89%) | +0.41% | +0.22% |
| with a live trade | 6 | 5 (83%) | 50% | 5 of 6 (83%) | +0.35% | +0.19% |
| no trade taken | 19 | 13 (68%) | 49% | 13 of 16 (81%) | +0.76% | +0.41% |
| same-day horizon | 22 | 16 (73%) | 50% | 16 of 19 (84%) | +0.46% | +0.27% |
| morning window only (end by 12:00) | 18 | 15 (83%) | 50% | 14 of 15 (93%) | +0.61% | +0.30% |

Price targets: 12 given, 11 not yet reached at the call, 8 of those hit by the deadline (73%), median distance 0.63%.
Misses: Aug 15 (never came back to the open, missed by 115 points), Oct 7 (mid-gap not reached by 10:00, 16 points
short), Oct 17 (Tuesday's high, 64 points short).

How much depends on the estimated call time (same-day calls, `sens.py`):

| ref shift (min) | calls | right at horizon end | first to +0.25% | right at 16:00 |
|---|---|---|---|---|
| -30 | 22 | 16 (73%) | 12 of 19 | 12 (55%) |
| -15 | 22 | 17 (77%) | 14 of 19 | 13 (59%) |
| 0 | 22 | 16 (73%) | 16 of 19 | 14 (64%) |
| +15 | 22 | 15 (68%) | 12 of 19 | 11 (50%) |
| +30 | 18 | 11 (61%) | 9 of 16 | 9 (50%) |

## The calls

| date | ref | side | call | target | horizon | move his way | result | trade shown live |
|---|---|---|---|---|---|---|---|---|
| 2024-08-05 | 08:50 | up | Pre-open: smooth relative equal highs above are the draw | 17,820.75 | to 11:30 | +3.44% | right | none |
| 2024-08-06 | 09:30 | up | Relative equal highs targeted after a disruption lower | highs formed after 07:00 | to 11:30 | +0.59% | right | none |
| 2024-08-07 | 12:45 | down | PM short 18,321.25 toward London lows and the NDOG below | London low | to 16:00 | +1.90% | right | demo short, win |
| 2024-08-08 | 08:25 | up | Gap cluster above price, so the 08:30 run should be up | Wed and Tue NDOGs | to 11:30 | +2.30% | right | none |
| 2024-08-12 | 07:50 | down | Monday should give the retracement Friday did not | TGIF 20-30%, NDOG CE | to 11:30 | +0.14% | right | short, stopped on a trailed stop in profit |
| 2024-08-13 | 12:00 | up | Higher-timeframe objective named on a no-trade day | daily VI CE about 19,160 | 3 days | +3.28% | right | none |
| 2024-08-15 | 10:30 | down | Gap up too rich to buy; price should come back to the 09:30 open | 09:30 open | to 16:00 | -0.58% | wrong | none |
| 2024-08-19 | 10:00 | up | Long after the sell-side sweep into Friday's NDOG | NWOG lower quadrant | to 12:00 | +0.26% | right | long, win |
| 2024-09-06 | 08:25 | up | NFP release more likely to run the buy-side first | minor buy-side | to 09:30 | +0.68% | right | none |
| 2024-09-09 | 10:15 | down | Premium gap too expensive to buy; short framed to the mid-gap | ORG mid-gap | to 11:30 | +0.69% | right | none |
| 2024-09-17 | 09:33 | down | Premium gap over 100 handles, mid-gap by 10:00 | ORG mid-gap | to 10:00 | +0.28% | right | none |
| 2024-09-19 | 09:49 | down | Short at the first presented gap after a very large gap up | retracement | to 11:30 | -0.54% | wrong | micro short, small win |
| 2024-09-23 | 09:35 | up | One early long, then stood aside | 0.25 extension | to 10:30 | +0.24% | right | long, win |
| 2024-09-24 | 09:35 | down | Wants the 20,085 sell-side swept before the 10:00 news | 20,085 | to 10:00 | +0.15% | right | none |
| 2024-09-25 | 09:40 | up | Draw is the Aug 22 daily high | Aug 22 high | to 11:30 | +0.08% | right | long, win |
| 2024-09-27 | 09:50 | down | Lackluster Friday; short framed off the first presented gap | ORG mid-gap | to 11:30 | +0.44% | right | none |
| 2024-09-30 | 10:00 | down | Wants the short of the week | weekly BISI CE | to Friday | -0.11% | wrong | none (first target hit, second failed) |
| 2024-10-01 | 09:30 | down | Drill trades aimed lower | 15m relative equal lows | to 11:30 | +1.77% | right | about ten one-lot drills, wins and losses |
| 2024-10-07 | 09:30 | up | Discount gap, bullish to the mid-gap in the first 30 minutes | 20,179.5 | to 10:00 | -0.13% | wrong | none |
| 2024-10-15 | 09:10 | up | Higher-timeframe bullish, drawing up into the daily SIBI | 20,568 / 20,646.75 | to 16:00 | -1.45% | wrong | none |
| 2024-10-16 | 09:50 | up | NQ should come back up into its range after an unconfirmed lower low | opening range | to 10:30 | +0.41% | right | none |
| 2024-10-17 | 08:30 | up | Bullish, draw to nested relative equal highs and Tuesday's high | 20,659.25 | to 16:00 | -0.75% | wrong | none |
| 2024-10-21 | 09:30 | up | Discount gap, bullish 09:30 to 10:00 until half the gap fills | ORG mid-gap | to 10:00 | +0.32% | right | none |
| 2024-10-25 | 10:00 | up | Bullish, draw to smooth highs in the 20,600s | relative equal highs | to 12:00 | -0.14% | wrong | none |
| 2024-12-01 | Sun 18:00 | up | Weekly outlook: favors higher | 21,580.25 | to Friday | +3.16% | right | none |

No-trade and no-call days are in `nocall_2024.csv`. Three of the no-trade days were strong one-way days he passed on
(Aug 13 PPI, Aug 15, Aug 29).

Losses and stop-outs he mentions in this set (not scored, he gives no prices in the captions): Aug 15 short (5 of 15
off, rest stopped), Aug 21 (4 of 10 stopped), Aug 29 pre-session short (stopped, re-entered), Sep 17 "pretend" short
(stopped on the balance), Oct 3 (2 runners stopped), Oct 7 London short (balance stopped), Oct 24 two losses
(-$1,200 and -$800, "won it back"), Dec 5 (rest stopped).

## What to make of it

1. Wrong calls cluster where he states a **day or week** direction from the higher timeframe (Sep 30, Oct 15, Oct 17,
   Oct 25). Right calls cluster in **the next 30 to 120 minutes** from a specific intraday picture.
2. Six calls are the opening range gap rule (first 30 minutes trade toward the mid-gap). That rule is mechanical
   and can be tested on every day 2019-26 without him. 5 of the 6 were right, and the mid-gap was reached by 10:00 on
   3 of the 4 timed ones.
3. He stood aside on 13 of 44 stream days and gave no call on 5. Day selection is a third of the record.

## Caveats (they matter)

- **Call times are estimates.** The 2024 captions carry almost no clock times or prices (he points at the chart), so
  `ref` comes from the stream's start, bell mentions and the per-video notes. The sensitivity table shows what a
  15 to 30 minute error does. The key frames on the laptop show the chart clock and would fix this.
- **The log leans on the per-video notes**, with caption checks on each call. A check of three no-call sessions found
  soft statements the notes left out (for example Aug 30: "probably won't make a higher high on the week"). If notes
  remember calls that worked better than calls that did not, 72% is too high.
- **25 calls, one market, twelve weeks**, most of it a rising market after the Aug 5 low (up calls 11 of 15, but
  down calls 7 of 10 too).
- "Right at the horizon" ignores his stop. A call can be right at 11:30 and still stop a tight entry first.
- 5 calls are marked `partly` or `unclear` on whether they came before the move; results are shown with and without.

## Files

- `calls_2024.csv`: the log (id, date, source video, ref, side, horizon, target, trade shown, before, evidence, what).
- `nocall_2024.csv`: no-trade and no-call sessions.
- `calls_2024_scored.csv`, `summary_2024.md`, `sens_2024.md`: outputs.
- `score.py`, `sens.py`: scorer and the call-time sensitivity check.
- `calls_for_option_c.csv`: date, market, side, before, source (also at
  `/mnt/project-files/mentorship/runs/ict_calls_2026-11-17/calls.csv`).

## Not done yet

2026 SMC (about 67 live or pre-market sessions, many with dates still to pin), 2023 Mentorship (about 60), 2025
Lectures (about 18 live), Trade Executions and Charter. Same method, about a day each for the first two. Handoff:
`/mnt/project-files/mentorship/handoff_ict_calls_2026-11-17.md`.
