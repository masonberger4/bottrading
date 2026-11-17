# ICT's calls made before the fact, scored (option B of PR #82). Sets 1 to 4: 2024 Mentorship, 2026 SMC, 2025 Lectures, 2023 Mentorship (2026-11-17)

Asked by Mase ("Start A through E"). Log and results only: no engine code, default or data changed.

## Short answer (Set 1, 2024 Mentorship; Set 2 is in its own section below)

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

No-trade and no-call days are in `nocall_2024.csv`. Aug 13 (PPI) was a strong one-way day he passed on.

Losses and stop-outs he mentions in this set (not scored, he gives no prices in the captions): Aug 15 short (5 of 15
off, rest stopped), Aug 21 (4 of 10 stopped), Aug 29 pre-session short (stopped, re-entered), Sep 17 "pretend" short
(stopped on the balance), Oct 3 (2 runners stopped), Oct 7 London short (balance stopped), Oct 24 two losses
(-$1,200 and -$800, "won it back"), Dec 5 (rest stopped).

## What to make of it

1. Wrong calls cluster where he states a **day or week** direction from the higher timeframe (Sep 30, Oct 15, Oct 17,
   Oct 25). Right calls cluster in **the next 30 to 120 minutes** from a specific intraday picture.
2. Five calls are the opening range gap rule (trade toward the mid-gap after a gap open). That rule is mechanical
   and can be tested on every day 2019-26 without him. 4 of the 5 were right at the horizon, and the mid-gap was
   reached by 10:00 on 2 of the 3 that had that deadline.
3. He stood aside on 13 of 41 live stream days and gave no call on 5. Day selection is a third of the record.

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

## Set 2: 2026 SMC lecture series (added 2026-11-17)

Same method, same scorer. 131 notes read; 40 dated videos carried a call made before the move, 4 were stated
no-trade days, 11 had no call, 2 fall after the NQ file ends (Oct 19 and Oct 28), and the rest are reviews and
lectures recorded after the fact (not scored).

- **42 calls, 30 right at his horizon (71%).** The same guess on neighbouring days wins 48%. About a 0.2% chance of
  that by luck. Counting only calls clearly stated before the move: 26 of 38 (68%).
- **Both sets together: 48 of 67 (72%) against 49% by chance.** Morning-window calls: 41 of 51 (80%).
- Moves are still small: median +0.26% (about 75 NQ points at 2026 prices), mean +0.22%.
- Price targets: 24 given, 19 reached by the deadline (79%).
- Shifting every call time by 15 to 30 minutes either way gives 62% to 71% right (table below), so the edge survives
  the timing uncertainty but is smaller than the headline.
- 30 of the 42 calls came with a trade taken live on the stream (23 right, 77%); the 12 without a trade were 7
  right (58%).

| group | calls | right at the horizon end | same call on other days | first to +0.25% vs -0.25% | mean move | median move |
|---|---|---|---|---|---|---|
| all calls | 42 | 30 (71%) | 48% | 29 of 38 (76%) | +0.22% | +0.26% |
| clearly before the move | 38 | 26 (68%) | 49% | 26 of 34 (76%) | +0.18% | +0.24% |
| up calls | 17 | 13 (76%) | 53% | 9 of 14 (64%) | +0.24% | +0.29% |
| down calls | 25 | 17 (68%) | 45% | 20 of 24 (83%) | +0.20% | +0.23% |
| with a live trade | 30 | 23 (77%) | 49% | 22 of 28 (79%) | +0.24% | +0.26% |
| no trade taken | 12 | 7 (58%) | 46% | 7 of 10 (70%) | +0.16% | +0.23% |
| same-day horizon | 38 | 29 (76%) | 48% | 26 of 34 (76%) | +0.26% | +0.26% |
| morning window only (end by 12:00) | 33 | 26 (79%) | 48% | 23 of 30 (77%) | +0.29% | +0.26% |

| ref shift (min) | calls | right at horizon end | first to +0.25% | right at 16:00 |
|---|---|---|---|---|
| -30 | 38 | 27 (71%) | 22 of 35 | 25 (66%) |
| -15 | 38 | 26 (68%) | 23 of 35 | 22 (58%) |
| 0 | 38 | 29 (76%) | 26 of 34 | 27 (71%) |
| +15 | 38 | 26 (68%) | 20 of 27 | 23 (61%) |
| +30 | 32 | 20 (62%) | 20 of 28 | 22 (69%) |

### Dates were pinned from prices

The playlist is not in date order and many notes had inferred dates. Prices he says out loud were matched against
the NQ 1-minute file (09:30 open, 16:14 settlement, session highs and lows). That confirmed most dates and moved these:

- 006/007: Tue Sep 29 (09:30 open 30,708.75), not Thanksgiving week.
- 018: Thu Sep 3 (opening gap 29,194.25 to 29,249.5), not NFP Friday Sep 4. The recording stops mid-trade and NQ
  then rallied about 200 points against the short.
- 138: Thu Jan 29 (discount open 26,133.5, 09:30 low near 26,122.5), not Jan 8.
- 089: Wed May 13 (08:30 candle high 29,360.75). 027: Tue Aug 25. 055: Tue Jul 21 (the same trade 054 reviews).
  030: Thu Aug 20. 067: Wed Jul 8. 095: Tue Apr 21 (the pre-market short 097 mentions).

### Horizon rules (fixed before scoring)

A deadline he names is used (by 10:00, the first 30 minutes, "until 11:06"). Otherwise: a morning setup or live
morning trade ends 11:30; a pre-market call about the 07:00-09:30 move ends 09:30; an afternoon call or a
whole-day direction ends 16:00; an evening outlook ends the next day 16:00; a weekly outlook ends Friday 16:00.

### The 2026 calls

| date | ref | mkt | side | call | horizon | move his way | result | target | trade shown live |
|---|---|---|---|---|---|---|---|---|---|
| 2026-01-05 | 09:17 | NQ | up | Pre-open long from the pre-market first gap toward the highs above | to 11:30 | +0.29% | right |  | live demo long, half off at the minor buy side |
| 2026-01-29 | 08:34 | NQ | up | Pre-market: the smooth side is up, expects the run into the minor buy side | to 09:30 | -0.18% | wrong |  | none |
| 2026-02-10 | 09:24 | NQ | down | Buy side went first, so the relative equal lows are the next draw | to 11:30 | +0.17% | right | hit | live small entries on the 15s chart |
| 2026-02-11 | 09:37 | NQ | down | NFP Wednesday: premium gap, watching for the half gap by 10:00 | to 10:00 | +0.22% | right | hit | none |
| 2026-02-27 | 08:16 | NQ | down | PPI morning: "I'm bearish, I want to see lower prices" | to 16:00 | -0.34% | wrong |  | none |
| 2026-03-08 | 18:00 | NQ | down | Sunday outlook: NQ is the weak index, bearish | to Friday | -0.71% | wrong |  | none |
| 2026-03-09 | 10:25 | ES | up | ES long from an inversion gap to run the shorts from the open | to 11:30 | +0.68% | right | hit | live paper long, one micro |
| 2026-03-13 | 16:30 | NQ | down | Friday review: "I anticipate and expect a gap lower opening on Sunday", stay heavy | next day | -1.23% | wrong |  | none |
| 2026-03-17 | 09:34 | NQ | down | Tape read, no trade: only interested in the sell side below | to 11:30 | +0.23% | right |  | none |
| 2026-04-06 | 09:50 | NQ | down | Premium gap after Good Friday: reads the run above the highs as a false break back to the gap | to 11:30 | +0.34% | right | hit | none |
| 2026-04-08 | 09:33 | NQ | down | Huge premium gap: the only target this morning is the block low | to 11:30 | +0.56% | right |  | live short, stepped partials |
| 2026-04-10 | 09:40 | NQ | down | CPI Friday: premium gap, still drawing lower to the mid-gap | to 10:00 | -0.05% | wrong | missed by 15.12 | none |
| 2026-04-13 | 09:54 | NQ | up | Neutral at the open, then a long from an inversion gap | to 11:30 | +0.27% | right |  | live long |
| 2026-04-16 | 09:30 | NQ | down | Premium gap after nine up days: short toward the gap in the first 30 minutes | to 10:00 | +0.45% | right | hit | live short, late fill |
| 2026-04-17 | 08:25 | NQ | up | Friday plan: next objective is the all-time high | to 16:00 | +0.88% | right | hit | none |
| 2026-04-21 | 08:10 | NQ | down | Pre-market short after the run stalled just under the all-time high | to 09:30 | +0.26% | right | hit | live short, partials, runner stopped |
| 2026-04-28 | 09:45 | NQ | down | Short at 75% of the opening gap toward the morning lows | to 11:30 | +0.62% | right | hit | live short, target hit |
| 2026-05-13 | 09:46 | NQ | up | Long fading the 08:30 news drop | to 11:30 | +0.49% | right | hit | live long, stopped once, re-entered, last piece stopped |
| 2026-05-26 | 15:15 | ES | up | ES last-hour long into the highs | to 16:00 | +0.19% | right |  | live long |
| 2026-06-08 | 10:05 | NQ | up | Bought under the relative equal lows for a run back up into Friday's gap | to 11:30 | +0.91% | right | hit | live paper long, 20 lots |
| 2026-06-22 | 09:31 | NQ | down | Short at the open "for the stops" | to 11:30 | +0.96% | right |  | live paper short, covered within minutes |
| 2026-06-22 | 09:38 | NQ | up | Then long from a reclaimed gap | to 11:30 | -0.95% | wrong |  | live paper long, closed by accident near target |
| 2026-07-01 | 10:05 | NQ | down | Short in the 09:50-10:10 window at the daily block | to 11:30 | -0.26% | wrong |  | live short |
| 2026-07-02 | 10:15 | NQ | down | Short after the 09:30 run up, read as a false move | to 11:30 | +1.80% | right |  | live short |
| 2026-07-06 | 10:02 | NQ | down | No-bias day: short after the 10:00 news | to 11:30 | -0.29% | wrong |  | live short, $1,800 loss |
| 2026-07-06 | 10:10 | NQ | up | Reversed long after the loss | to 11:30 | +0.23% | right | hit | live long, scaled out |
| 2026-07-07 | 09:27 | NQ | down | Wants the gap to fail and price to run the lows | to 11:30 | +0.93% | right |  | none |
| 2026-07-13 | 09:27 | NQ | up | Mild long bias toward Friday's settlement (he says no hard bias) | to 16:00 | -0.81% | wrong | missed by 296 | live paper probes, one contract |
| 2026-07-14 | 08:00 | NQ | up | CPI pre-market: expects up into Monday's gap | to 16:00 | +0.51% | right | hit | none |
| 2026-07-14 | 10:00 | NQ | down | Short at 10:00 from the prior day's half gap | to 11:30 | -0.35% | wrong | missed by 22.5 | live short, last piece stopped |
| 2026-07-16 | 18:30 | NQ | down | Review: price could gravitate below the daily lows tomorrow, with a Friday caveat | next day | +1.29% | right | hit | none |
| 2026-07-21 | 09:31 | NQ | down | Enormous premium gap: short at the open toward the half gap by 10:00 | to 10:00 | +0.11% | right | missed by 94.75 | live short, stopped, re-entered, net small |
| 2026-08-06 | 07:05 | NQ | up | Pre-market long from a daily inversion gap | to 11:30 | +0.72% | right |  | live long |
| 2026-08-10 | 09:35 | NQ | up | Long near the open to the midnight opening price | to 11:30 | +0.12% | right | hit | live long, 5 of 7 off near target |
| 2026-08-17 | 08:22 | NQ | down | Monday short aiming for the untouched weekly gap | to 11:30 | +0.01% | right | hit | live short, target not reached on the video, small profit |
| 2026-08-25 | 08:22 | NQ | down | Pre-market short after price failed above the weekly gap | to 09:30 | +0.26% | right |  | live short, partials |
| 2026-08-27 | 10:00 | NQ | up | Long in the 09:50-10:10 window after the low was swept | to 11:30 | +0.32% | right |  | live long, 5 of 6 off, runner stopped |
| 2026-09-01 | 09:35 | NQ | up | Huge discount gap: favors longs back up into the gap | to 11:30 | +0.46% | right | hit | live paper longs, one small loss |
| 2026-09-03 | 09:48 | NQ | down | Short looking for a run down through the opening gap | to 11:30 | -0.66% | wrong | missed by 63.75 | live short, recording stops mid-trade |
| 2026-09-04 | 10:40 | NQ | down | NFP Friday short already on, "they're going to come down" | to 11:06 | +0.26% | right | hit | live short, closed by hand about $6,470 |
| 2026-09-08 | 09:31 | NQ | down | Premium gap after Labor Day: short at the opening wick | to 10:00 | +0.53% | right | hit | live paper short, one contract |
| 2026-09-29 | 19:45 | NQ | up | Evening long, expects a move up into Monday's gap | next day | -0.01% | wrong | hit | live evening long, partials, runner stopped |

No-trade, no-call and no-data sessions: `nocall_2026.csv`.

### What Set 2 adds

1. The rate repeats on a second, independent set two years later (71% against 72%), in a market that went both ways.
2. Longer calls are still the weak ones: whole-day, next-day and weekly calls were 3 of 8 right (the weekly outlook
   on Mar 8, the "gap lower on Sunday" call on Mar 13, Feb 27, Jul 13 and Sep 29 were wrong). Morning-window calls
   were 26 of 33.
3. Day selection again: on Mar 27 he declined to short a one-sided Friday that fell another 1.5%.
4. A live trade is the stronger signal (77% against 58% without one), but that group has the selection problem below.

### Extra caveats for Set 2

- **Which sessions get recorded and kept is his choice.** 018 stops mid-trade on a losing day; other losing sessions
  may never have been posted. Live-trade calls are the most exposed to this.
- Call times are still estimates (stream start worked back from clock mentions, price touches and video length).
- Four calls are marked `partly` or `unclear`. Two sessions carry two opposite calls minutes apart (Jun 22, Jul 6);
  both are logged.
- Two ES calls (Mar 9, May 26) are scored on ES.
- A horizon-end result ignores his exit: Jul 1 is scored wrong at 11:30 although the short paid first.

## Set 3: 2025 Lecture Series (added 2026-11-17)

- The 83 videos of the 2025 playlist are mostly after-the-fact reviews. Only **12 dated calls** could be logged
  (Mar 23 to Nov 24 2025, all NQ), plus 6 stated no-trade days and 7 sessions with no usable call.
- **7 of the 12 were right at his horizon (58%); the same guess on neighbouring days wins 50%.** That is not
  distinguishable from luck on its own. Counting only the 10 clearly stated before the move: 6 of 10.
- The split matches Sets 1 and 2. The three morning-window calls were all right (Sep 19 live short, Oct 1 half-gap,
  Nov 24 at the bell). The seven evening, next-day and weekly outlooks went 3 of 7.
- Up calls 4 of 5, down calls 3 of 7. Price targets: 4 given, 2 hit by the deadline.
- Sets 1 to 3 together (2024, 2026, 2025): **55 of 79 right (70%) against 49% for the same guess on other days**; morning-window
  calls 44 of 54 (81%); calls that run to the close or longer 11 of 25.

| date | ref | side | call | target | horizon | move his way | result | trade shown live |
|---|---|---|---|---|---|---|---|---|
| 2025-03-23 | Sun 18:00 | down | Weekly outlook: patch-up rally into the daily volume imbalance, then roll over | below the March lows | to Friday | +2.94% | right | none |
| 2025-03-28 | 16:55 | down | Expects Sunday to open at or below the weekly projection | Sunday open | next day 16:00 | -0.40% | wrong | none |
| 2025-04-04 | 16:45 | down | Expects a gap lower on Sunday and a run below Friday's low | below 17,387.50 | next day 16:00 | -0.25% | wrong | none |
| 2025-04-21 | 16:30 | down | Looking for 17,700 and just below overnight or tomorrow | 17,699.75 | next day 16:00 | -2.67% | wrong | none |
| 2025-04-30 | 16:30 | up | Higher on the daily chart into NFP Friday | daily wick CE, volume imbalance | to Friday | +1.74% | right | none |
| 2025-05-07 | 09:30 | up | FOMC morning: stay away today, but likely up to the relative equal highs | relative equal highs | 3 days | +5.28% | right | none |
| 2025-05-18 | Sun 18:00 | up | Sunday outlook: wants it to stay bullish | 21,941.75 | to Friday | -1.56% | wrong | none |
| 2025-06-20 | 04:50 | down | Pre-market X video: bearish, no new highs before the weekend | new week opening gap | to 16:00 | +0.19% | right | short after 09:30, shown afterwards |
| 2025-09-19 | 10:28 | down | Live short at the reclaimed gap | 24,735 | to 11:30 | +0.27% | right | live short, partials, last two stopped |
| 2025-10-01 | 09:25 | up | Pre-open: push higher, half the discount gap by 10:00 | ORG mid-gap | to 10:00 | +0.01% | right | none |
| 2025-11-14 | 09:00 | down | Daily chart drawing to the relative equal lows | sell side below 24,602 | to 16:00 | -1.57% | wrong | none |
| 2025-11-24 | 09:32 | up | At the bell: upside objective for the morning | hourly balanced price range | to 11:30 | +1.12% | right | none |

Notes on this set:
- **Mar 28 and Apr 4 are scored wrong by the horizon rule but the thing he actually called happened.** Sunday opened
  lower both times (19,319.75 against 19,361.00, and 17,100.00 against 17,483.25) and ran below Friday's low; both
  Mondays then recovered above Friday's last price by 16:00. Scored at the Sunday open they are right, which would
  make the set 9 of 12. The rule was kept the same as Set 2 (C26-08).
- Mar 23 is logged as a down weekly call because the net view was "still lower prices". The first leg he described
  (up into the daily volume imbalance) also happened, Monday to Wednesday, before the drop.
- May 18 is soft: he says the Sunday opening price decides and gives the gap-down scenario too. It gapped down.
- Jun 20 is his own evening report of an X video posted at 04:50, so it is marked `partly` and left out of the
  "clearly before" row. Calls he reports later are more likely to be ones that worked.
- Nov 14: the stream's clock time cannot be recovered from the captions. The call is wrong for any time from 07:00
  to 09:35, so the result does not depend on the guess. May 7's time is also a guess (he says "FOMC later today").
- Dates pinned from prices: Apr 21, Apr 30, May 6-7, May 16-18, Jun 20, Sep 19, Oct 1, Oct 14 all matched the
  1-minute file. No note header was wrong in this set, but 5 dates the notes marked "inferred" are now confirmed.
- Not scoreable: six live or voice-over trade videos from January to April (58, 64, 70, 72, 75, 76) carry no date
  or price in the captions, and the Oct 14 "called the low on X" post has no time. The laptop frames would fix both.
- No-trade days: May 2 (NFP), May 7 (FOMC), May 16, Jun 12 and 13 (CPI/PPI week), Sep 26.

## Set 4: 2023 Mentorship (added 2026-11-17)

Same method, same scorer. 105 notes read (videos 001-105, Jan to Dec 2023). 34 dated videos carried a call made
before the move, 20 days were stated no-trade days, 8 videos had no call that can be scored, and the rest are
reviews and lectures recorded after the fact (not scored). Market is ES unless he was on NQ (7 calls, from July).

- **35 calls, 24 right at his horizon (69%).** The same guess on neighbouring days wins 52%. About a 2% chance of
  that by luck.
- **All four sets together: 79 of 114 (69%) against 50% by chance.** Morning-window calls: 56 of 71 (79%). See `summary_all.md`.
- Sets 1, 2 and 4 together (2024, 2026, 2023): 72 of 102 (71%) against 50% by chance. Morning-window calls: 53 of 68 (78%).
- **The split by horizon is the main finding.** Same-day calls: 17 of 22 (77%). Evening and weekly outlooks:
  7 of 13 (54%), no better than a coin flip, and the misses are large (-0.7% to -2.9%).
- Same-day calls by time: before the open 4 of 4, 09:30 to 12:00 8 of 13, afternoon 5 of 5.
- Moves are small again: median +0.29%, mean +0.26%.
- Price targets: 27 given, 25 reached by the deadline (93%). Three live trades (Jan 17, Mar 9, May 22) reached
  their target and paid, but are scored wrong because price had come back by 11:30.
- 14 calls came with a trade taken live (10 right, 71%); 21 without a trade were 14 right (67%).
- At the 16:00 close instead of his horizon, same-day calls are 11 of 22 (50%). The information is gone by the close,
  as in the other two sets.

| group | calls | right at the horizon end | same call on other days | first to +0.25% vs -0.25% | mean move | median move |
|---|---|---|---|---|---|---|
| all calls | 35 | 24 (69%) | 52% | 23 of 33 (70%) | +0.26% | +0.29% |
| clearly before the move | 34 | 23 (68%) | 52% | 23 of 33 (70%) | +0.27% | +0.31% |
| up calls | 19 | 15 (79%) | 54% | 14 of 19 (74%) | +0.36% | +0.33% |
| down calls | 16 | 9 (56%) | 48% | 9 of 14 (64%) | +0.14% | +0.18% |
| with a live trade | 14 | 10 (71%) | 52% | 13 of 14 (93%) | +0.23% | +0.20% |
| no trade taken | 21 | 14 (67%) | 52% | 10 of 19 (53%) | +0.28% | +0.39% |
| same-day horizon | 22 | 17 (77%) | 52% | 17 of 20 (85%) | +0.32% | +0.27% |
| morning window only (end by 12:00) | 17 | 12 (71%) | 51% | 13 of 15 (87%) | +0.21% | +0.21% |

Price targets: 27 given, 27 not yet reached at the call; of those 25 hit by the deadline (93%). Median distance 0.25%.

How much depends on the estimated call time (same-day calls):

| ref shift (min) | calls | right at horizon end | first to +0.25% | right at 16:00 |
|---|---|---|---|---|
| -30 | 22 | 18 (82%) | 14 of 20 | 13 (59%) |
| -15 | 22 | 19 (86%) | 16 of 21 | 13 (59%) |
| +0 | 22 | 17 (77%) | 17 of 20 | 11 (50%) |
| +15 | 22 | 16 (73%) | 14 of 19 | 10 (45%) |
| +30 | 20 | 13 (65%) | 10 of 14 | 10 (50%) |

### How dates and times were pinned

Every live fill or spoken level was compared with the 1-minute file (entry price at the stated minute, targets,
session highs and lows). All 35 agree with the note headers; no date had to be moved in this set. Two things to know:
- Dec 8: the data file had already rolled to the March 2024 contract (about 48.5 points above his December prices),
  so his 4593.50 target is scored as 4642.
- Evening and weekend outlooks use the 18:00 reopen as the call time. May 24 was recorded from about 16:00, minutes
  before an after-hours earnings jump that closed the gap he named; it is logged at 16:15 and counted right.

### The calls

| date | ref | market | side | call | horizon | move his way | result | trade shown live |
|---|---|---|---|---|---|---|---|---|
| 2023-01-09 | 19:45 | ES | down | Evening review: bearish for the rest of the week | to Friday | -2.86% | wrong | none |
| 2023-01-15 | 18:00 | ES | up | Weekly outlook: wants ES to expand up into 4030 after Friday took 4020 | to Friday | -0.80% | wrong | none |
| 2023-01-17 | 09:44 | ES | up | Live long after the 09:40 sweep of the 09:20 lows, target 4030 | to 11:30 | -0.14% | wrong | live long, 14 lots, out at 4030.75 |
| 2023-01-30 | 09:22 | ES | up | Pre-open long from the 5m gap and breaker toward the 03:00 gap he tweeted | to 11:30 | +0.11% | right | live long, 5 off at 4059.25 |
| 2023-01-31 | 15:38 | ES | up | Last-hour long: market maker buy model into the new week opening gap | to 16:00 | +0.50% | right | live long 25 lots, 80% off at 4080.50 |
| 2023-02-01 | 14:25 | ES | up | FOMC: the 14:30 move is the real one and it should take the buy side | to 16:00 | +1.47% | right | none (FOMC, told students not to trade) |
| 2023-02-07 | 08:50 | ES | down | Pre-market: the overnight short should still reach the 03:00 low | to 09:30 | +0.13% | right | none |
| 2023-02-09 | 14:05 | ES | down | PM: short from the morning still has lower objectives | to 16:00 | +0.47% | right | live short held from the morning, partials 4105.25 and 4103 |
| 2023-02-10 | 15:32 | ES | up | Last hour: long framed off the 1m gap toward the day's high | to 16:00 | +0.16% | right | none (hypothetical long taught live) |
| 2023-02-13 | 09:42 | ES | up | Held the opening gap midpoint, so the morning should run the buy side | to 11:30 | +0.61% | right | none |
| 2023-02-15 | 09:47 | ES | up | Choppy day, but expects the run into the highs at 4136.50 | to 11:30 | +0.21% | right | none (told students to sit on their hands) |
| 2023-02-16 | 10:05 | ES | up | After the sweep of the weekly gap low, wants price back above the breaker and into the buy side | to 11:30 | +0.64% | right | none |
| 2023-02-26 | 18:00 | ES | down | Weekly outlook: ES lower | to Friday | -1.83% | wrong | none |
| 2023-03-06 | 09:33 | ES | up | Slow Monday: grind up to the old opening gap low | to 11:30 | +0.33% | right | none shown |
| 2023-03-09 | 09:37 | ES | up | Long back into the 09:00-09:30 range after the bounce at the opening gap midpoint | to 11:30 | -0.26% | wrong | live long 15 lots, scaled out to 4018.75 (and an 08:30 long in video 040) |
| 2023-03-21 | 10:00 | ES | down | Gap up into a premium: waits 30 minutes, then wants the sell side | to 11:30 | +0.24% | right | live demo short 1 lot at 4023.75 about 10:10, out at 4013.75 |
| 2023-03-30 | 10:06 | ES | down | First Silver Bullet session: short below the bearish breaker | to 11:30 | -0.00% | wrong | none (called, not executed) |
| 2023-04-12 | 18:00 | ES | down | Evening after CPI: lower into tomorrow | next day | -1.35% | wrong | none |
| 2023-04-13 | 09:42 | ES | up | Bullish toward the old new week opening gap | to 11:30 | +0.39% | right | none |
| 2023-05-17 | 18:00 | ES | up | Evening: the weekly candle should expand up by Friday | 2 days | +0.80% | right | none |
| 2023-05-22 | 10:03 | ES | down | Live Silver Bullet short | to 11:30 | -0.16% | wrong | live short 10 lots at 4206.25, all out by 4193.50 |
| 2023-05-24 | 16:15 | ES | up | Evening: price should trade back up through the opening gap tonight | next day | +0.73% | right | none |
| 2023-07-02 | 18:00 | ES | up | Weekly outlook: ES higher through the June 16 high | to Friday | -1.13% | wrong | none |
| 2023-07-07 | 14:38 | NQ | down | PM short from above the 12:30 gap | to 16:00 | +0.83% | right | live sim short 6 lots |
| 2023-07-09 | 18:00 | ES | up | Weekly outlook: ES retraces, then expands up | to Friday | +2.29% | right | none |
| 2023-08-13 | 18:00 | NQ | down | Weekly outlook: NQ lower, with an August chop warning | to Friday | +2.34% | right | none |
| 2023-08-16 | 18:00 | NQ | down | Evening review: NQ should still reach the sell side below | next day | +1.12% | right | none |
| 2023-08-18 | 10:31 | ES | down | Short into the gap below, closed when it stalled | to 11:30 | -0.29% | wrong | live short 5 lots, cut for a small loss |
| 2023-08-18 | 10:33 | ES | up | Reversed long from the sell side toward the buy side | to 11:30 | +0.29% | right | live long, 20 lots out at 4373.50-4373.75 |
| 2023-08-20 | 18:00 | ES | down | Weekly outlook: lower | to Friday | -0.74% | wrong | none |
| 2023-09-01 | 09:34 | NQ | down | NFP Friday short after the buy side run, toward the 08:30 low | to 11:30 | +0.79% | right | live short 10 lots at 15,635.25, about +$15,400 |
| 2023-09-21 | 08:10 | NQ | down | Pre-market Thursday: equities soft into Friday's close | next day | +0.75% | right | none |
| 2023-09-22 | 07:48 | NQ | up | Pre-market long after the run under the 07:30 lows | to 09:30 | +0.10% | right | live paper long, pyramided on the 15s chart |
| 2023-10-22 | 18:00 | NQ | down | Weekly outlook: stays bearish | to Friday | +2.82% | right | none |
| 2023-12-08 | 08:32 | ES | up | NFP: long from the 4h gap after the 08:30 spike and drop | to 11:30 | +0.58% | right | live long 10 lots, average 4567.50 |

### No-trade days (20) and no-call videos (8)

In `nocall_2023.csv`. Four no-trade days also carry a call (Feb 1, 7, 13 and 15), as in
Set 1: he named a side but told students not to trade it. Oct 16-19 are days he sat out because his weekly dollar
filter never triggered (stated before in video 102, confirmed in 103).

### Caveats for this set

- Three recordings are silent or narrated afterwards (Jan 17, Aug 18, Sep 1); the fills on screen are the evidence.
  Feb 7 is marked "not clearly before" because the short leg began overnight.
- Statements are picked from long tape-reading streams. Where he named the same side several times in one session
  only the first is logged; where he flipped (Aug 18) both are.
- Review videos that claim an earlier Twitter call (for example Jan 26, Jun 26, Sep 14) are not scored: the call
  itself is not in the set.
- Horizon choice for pre-market live trades: a scalp closed before the open ends 09:30 (Sep 22); a trade held
  through the open ends 11:30 (Jan 30, Dec 8).

## Files

- `calls_2024.csv`: the log (id, date, source video, ref, side, horizon, target, trade shown, before, evidence, what).
- `nocall_2024.csv`: no-trade and no-call sessions.
- `calls_2024_scored.csv`, `summary_2024.md`, `sens_2024.md`: outputs.
- `score.py`, `sens.py`: scorer and the call-time sensitivity check.
- `calls_2026.csv`, `nocall_2026.csv`, `calls_2026_scored.csv`, `summary_2026.md`, `sens_2026.md`, `summary_all.md`: Set 2; `summary_all.md` is all sets together.
- `calls_2025.csv`, `nocall_2025.csv`, `calls_2025_scored.csv`, `summary_2025.md`, `sens_2025.md`: Set 3 (2025 Lectures).
- `calls_2023.csv`, `nocall_2023.csv`, `calls_2023_scored.csv`, `summary_2023.md`, `sens_2023.md`: Set 4 (2023 Mentorship). `summary_all.md` now covers all four sets.
- `calls_for_option_c.csv`: date, market, side, before, source (also at
  `/mnt/project-files/mentorship/runs/ict_calls_2026-11-17/calls.csv`).

## Not done yet

Trade Executions and Charter. Same method, one
set per thread. Handoff: `/mnt/project-files/mentorship/handoff_ict_calls_2026-11-17b.md`.
