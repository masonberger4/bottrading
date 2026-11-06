# 2024 Mentorship: DRAFT rules for Mase's review

**Status: DRAFT. Nothing here is wired into the engine and nothing has been backtested.**
Every rule below is DRAFT until Mase accepts it. Built 2026-11-03 from the per-lecture notes in
`mentorship/notes_2024/` (one file per lecture, with ~timestamps). Captions only: frames are on the
laptop, so "this level / that candle" in ICT's speech is resolved from context. Prices quoted from
captions can be garbled; treat them as approximate.

## How to read this

- Source tiers: **2023 Mentorship wins on every conflict.** The 2024 Mentorship (Aug 2024 onward,
  live streams for ICT's son Caleb, NQ) sits below it, alongside Trade Executions / Charter
  (`te_charter_draft_rules.md`, PR #9).
- The 2024 series is taught to a **beginner**. Rules ICT gives "for Caleb" (1% risk, one trade, stop
  after a win, 07:00-only framework) are marked **[beginner]**. The experienced-trader version stays
  the default; beginner rules become switches only.
- Tags (checked by grepping `mentorship_rules.md` on 2026-11-03; the rulebook is large, so a tag
  can be wrong, and each needs Mase's check):
  - **[new]**: term or rule not found in the rulebook.
  - **[in rulebook]**: already there in some form; the draft adds detail only.
  - **[conflict: X]**: differs from rulebook item or owner directive X. Not resolved; the 2023 rule
    stays in force until Mase decides.
  - **[conflict check]**: possibly differs; needs a closer read.
- "Our interpretation" marks places where ICT used judgment or withheld a threshold.
- Lecture refs: L01-L39 = notes `01_*.md`-`39_*.md` (no L15, L30 or L34 yet). Times are New York local.

## Coverage

| Lectures | Dates | Status |
|---|---|---|
| L01-L11, L13 (live) | 2024-08-05 to 08-20 | notes done (captions) |
| L12 (after-close review) | 2024-08-19 | notes done (captions) |
| L14, L16-L25 | 2024-08-22 to 09-09 | notes done (captions; L16 is a Saturday review, L23 an execution video) |
| L15 | 2024-08-23 | **pending**: no captions, needs whisper |
| L26-L29, L31-L33, L35-L38 | 2024-09-11 to 10-01 | notes done (captions; L32 is an after-session review) |
| L39 | 2024-09-02 | notes done (5-min market replay clip, no rules) |
| L30 | 2024-09-18 | no commentary (chart example only, no rules) |
| L34 | 2024-09-24 | **pending**: needs whisper |
| L40-L51 | 2024-10-02 onward | **pending** (handoff `/mnt/project-files/mentorship/handoff_2024m_040.md`) |

**Appending L14-L51:** add a note per lecture in `mentorship/notes_2024/` (same template), then
add bullets under the matching topic in Part A with the lecture ref, new rows to Parts C/D/E, and
update this table. Keep numbering of existing conflicts/switches stable.

---

## Part A. Rules by topic (DRAFT)

### A1. Time windows, sessions, macros
- DRAFT: Time first, then price; always New York local time (L01, L07). [in rulebook]
- DRAFT: AM session starts 07:00 for any market; morning session 07:00-11:00 (technically to
  noon); ICT likes to be done by 10:15-10:30 (L01, L02). [conflict check: rulebook session windows]
- DRAFT: Pre-market range = first 30 min of 07:00, 08:00 or 09:00 (07:00-07:30 etc.); expect a
  move opposite the draw (Judas) inside it (L01, L02). [conflict: TE te58/te60 premarket ranges;
  rulebook N5]
- DRAFT: Opening range = the 30 min after a pre-market range (07:30-08:00, 09:30-10:00); "there is
  no 15-minute opening range" (L01, L05, L10, L11). [in rulebook: 09:30-10:00] [new: 07:30-08:00]
- DRAFT: Hourly macros xx:50-xx:10: price spools to liquidity (short-term high/low) or to an
  inefficiency (FVG); if no FVG use the OB; all three never coexist at one price/time (L07).
  [in rulebook: macros]
- DRAFT: Also 00:00-01:00 and last-hour macros; 90 minutes is only a minimum watch window, no
  "90-minute cycles" (L07). [in rulebook]
- DRAFT: 08:30 spools even without news; news just makes it larger and faster (L04). [new]
- DRAFT: Lunch = 11:30-13:30. At 11:30 look back for the FIRST low (bullish morning) formed AFTER
  10:00; the lunch macro runs the stops under it, then after 13:30 price may resume the morning
  direction (mirror for a bearish morning) (L10, L12). [conflict check: rulebook lunch hour
  12:00-13:00 references; TE te46 lunch macro]
- DRAFT: Last hour: hold runners to at least 15:15 (start of the last-hour macros, four in that
  hour); 15:15-15:45 macro; 15:45-16:00 = market on close, 15 minutes (L11, L12). [conflict:
  owner #1 last hour 15:00-15:50; rulebook 15:45-15:50 macro]
- DRAFT: Clean vs sloppy: clean = impulsive legs leaving one inefficiency, a run to an obvious
  level, a retrace with one FVG. Sloppy = overlapping, back-and-forth; don't push the day (L07, L10).
  [in rulebook: owner #10 sloppy days, pending]

- DRAFT: 14:50-15:10 macro in the PM (L19). [conflict: C26 LAST-HOUR]
- DRAFT: PM session from 13:30; 13:50-14:10 macro (L22, L24). [in rulebook]
- DRAFT: Opening range = 09:30-10:00 (30 min; "15 minutes is not enough"); it sets the initial buy and sell side; SDs of its high-low project the day's highs/lows (L27). [conflict check: OPEN-RANGE-TRADE]
- DRAFT: PM session 13:30-close is "the easiest session for index futures": draw = lunch high/low or day high/low, whichever is obvious; last hour on expansion days makes the new extreme (L27). [conflict check: LAST-HOUR]
- DRAFT: Lunch = 11:30-13:30, two hours (L37). [conflict check: LUNCH-WINDOW]
- DRAFT: Macro times are not required when volatility is high; stick to them when factors stack against you (small ORG, Friday, after a big day) (L32). [conflict check: MACRO-GRID]
- DRAFT: Premarket = before 09:00 (from 07:00); a Fed chair speech in the 09:00-10:00 hour means trade before 08:00 (L37). [conflict check: PREMARKET-ENTRY] [new]

### A2. Day and week selection, news
- DRAFT: CPI/PPI/NFP/FOMC are manually intervened: never trade the release; trading 15-30 min
  after it (even NFP) is fine; afternoons are fine (L06, L07, L08). [conflict check: rulebook N1/N4]
- DRAFT: On those days don't frame initial buy-side/sell-side before the report; relative equal
  highs/lows aren't required: target the liquidity of traders who profited on the news run (L07, L08).
  [new]
- DRAFT: No medium/high-impact AM news → AM tends to be rangy with false breakouts; trade the PM
  (13:30-14:30 sweet spot); the 13:00 bond auction is a usable PM driver only on no-news days (L03).
  [new]
- DRAFT: Monday with no AM news and CPI/PPI later in the week = skittish "seek and destroy"; ONE
  early chance, partials, no re-entry after a stop (L06). [new]
- DRAFT: With big news tomorrow, take trades early (07:00-09:30 window) (L06). [conflict: rulebook
  N5 pre-09:30 entries are test-only switches]
- DRAFT: ICT usually skips Mondays EXCEPT Mondays of NFP week (L06). [conflict: experienced default
  "Mondays traded"]
- DRAFT: Jackson Hole (Wed-Fri) week: treat like NFP week, trade early in the week; expect heavy
  overlapping delivery; take partials early (L11, L12). [new; TE te61-63 has a related rule]
- DRAFT: Problem ("kryptonite") days: one-sided grinding, compressed, stilted after CPI/PPI →
  stand aside; one win on a hard-read day → take it and leave (L07). [in rulebook: owner #10
  pending] (needs a measurable proxy: our interpretation)
- DRAFT: Don't buy premium: after an 08:30 run + gap-up open + initial run to buy-side, wait for a
  discount; early chop after news is a trap (L09). [new]
- DRAFT: If the morning gives nothing, wait until 11:00-11:30 and fade the morning run in the lunch
  macro (L09). [new]
- DRAFT: Fridays: if no money was made in the morning, don't trade the afternoon (L10). [new]
- DRAFT: FOMC two-stage: the move into 14:00, then 14:00-14:30 goes the OPPOSITE way ~70% of the
  time and is larger; hold to ~15:15 (L11). [conflict check: rulebook FOMC handling]

- DRAFT: After a large range day (up or down), beginners skip the AM session and trade the PM from
  13:30; AM arrays get "colored outside the lines" (bodies outside the FVG) (L22). [conflict: C31]
- DRAFT: Friday before a US holiday weekend: no trade (erratic, light volume); no trading the Monday
  holiday or the Tuesday after (L21). [in rulebook: filters.md 1.2; C30 not scored]
- DRAFT: NFP, FOMC, CPI, PPI are manual intervention: don't position ahead; trade 20-30 min after
  (15 if very skilled; NFP 08:45 earliest); look at what the shock left behind (L16, L24, L25).
  [conflict: C33 NEWS-WAIT]
- DRAFT: No-news day = price must be absolutely clean or no trade; in a midweek PPI/CPI week trade
  Monday and Tuesday (L25). [conflict: C36 CPI-WEEK]
- DRAFT: Weekly objective hit (HTF target for the week) = done for the week (L24). [new; C41]
- DRAFT: Jackson Hole week is light; skip the Monday after the Symposium (L14). [new; C43]
- DRAFT: 15m bellwether: mark the 15m relative equal highs/lows before 08:30 and 09:30; the side the
  release takes is a clue for the session (L24). [new]
- DRAFT: Morning after a large range day = high resistance; new traders skip the AM; the day's first low is a suspect trap (L27, L32). [conflict check: AFTER-BIG-DAY]
- DRAFT: Day before FOMC: muddy, morning only, wait for the mohawk past the FVG; FOMC day: inexperienced traders avoid it (L29). [conflict: FOMC-DAY]
- DRAFT: Fed chair speech = manual intervention: no trading during it and 15 min after, until PD arrays book to the tick; afternoon speech = setup must come 09:30-10:30, no PM (L37). [new]
- DRAFT: Wait at least 15 min after any high/medium release (09:45 PMI = wait to 10:00) (L37). [conflict check: NEWS-WAIT]
- DRAFT: ICT always trades the Monday of NFP week; new students skip other Mondays (L37) and Wed-Fri of NFP week (L38). [conflict check: MONDAY, NFP-THU-FRI]
- DRAFT: High vs low resistance liquidity runs: price marking time inside FVGs = high resistance (journal it daily); seek & destroy = every high and low taken, never two in one week; decoupled indices = trade light, expect missed targets (L33, L35, L36, L37). [new]
- DRAFT: Time distortion: tight range, no movement; sit still until 10:00 or the PM release (L32, L33).

### A3. Bias and draw on liquidity
- DRAFT: Smooth vs jagged: price goes to smooth relative equal highs/lows; the jagged side was
  already raided; don't trade into it (L01, L02). [in rulebook: A3 smoothness]
- DRAFT: Primed relative equal highs: the LEFT high slightly above the right one (mirror for lows);
  a right-side wick above with a lower body close still counts (L01, L10, L11). [new]
- DRAFT: Tolerance for "relatively equal": ICT won't say (L01). Our interpretation needed.
- DRAFT: Beginner bias rule: look at pools formed at/after 07:00 (never before); whichever side
  has smooth relative equal highs/lows is the draw; if both, wait for one to be disrupted and work
  to the other; each hourly window passed builds trust (L01, L02, L11). [beginner] [new]
- DRAFT: Session draw is two-sided: mark buy-side and sell-side; the first side taken is the trap,
  the second is the target ("the first shall be last") (L11, L12). [in rulebook: Judas]
- DRAFT: Opening-gap cluster: if most of the last 5 NDOGs (and the NWOGs) are above price, expect
  price to gravitate up (and vice versa); ICT says ~80% for the 08:30 direction (L03, L04). [new]
  - A gap traded into once is "hot" and likely revisited (L03). [new]
  - Sandwiched between two gaps before 08:30 with nothing to lean on → wait (L04). [new]
- DRAFT: Draw hierarchy: NDOG/NWOG and relative equal highs/lows > FVGs (L03). [conflict check]
- DRAFT: Caleb's model (draw): an NDOG/NWOG with relative equal highs just below it (bullish) or
  relative equal lows just above it (bearish) (L13). [new]
- DRAFT: Election-year built-in buy bias; shorting every "broken wing" gets chopped (L09). [new;
  context only]
- DRAFT: Every profitable short was entered in a premium, every long in a discount; weekly prep picks one heaviest-leverage "one shot one kill" idea, other trades are scalps (L37).
- DRAFT: ORG bias: 09:30 above settlement = bearish opening-range bias toward the mid-gap and vice versa (L29, L36).

### A4. Opening gaps and opening ranges
- DRAFT: NDOG = 16:59/17:00 close to the 18:00 first print, every day except Friday; labeled for the
  NEXT trading day; levels high, low, CE, quadrants (L03, L04, L13). [in rulebook: L6]
- DRAFT: NDOG life 5 trading days; NWOG (Fri 17:00 → Sun 18:00) kept 5 weeks as the baseline
  (ICT also uses older ones, 6-9 months) (L03, L08, L13). [conflict: rulebook up to 60 trading
  days; 2023 stays]
- DRAFT: Gaps stay valid after being filled; bodies respect them (L03, L13). [in rulebook]
- DRAFT: CE/quadrants on NDOG/NWOG only when the gap is 20+ handles; smaller, eyeball the CE
  (L04, L05, L11). [conflict check: rulebook A5 quadrants on every gap]
- DRAFT: 6 PM opening price: when the 17:00 close equals the 18:00 open (no NDOG), draw that single
  price; it behaves like an NDOG (L08). [new; rulebook L6 ignores tiny gaps]
- DRAFT: Opening range gap (ORG) = 16:15 RTH settlement to the 09:30 first print; on a gap-up the
  ORG high is the 09:30 open (L05, L09, L10, L11, L13). [in rulebook]
- DRAFT: After a gap-up run, the first "fair value" target is the 09:30 opening price (L09). [new]
- DRAFT: RTH gap returns to mid-gap (CE) ~70% of the time; CE is the highest-probability target;
  a failing gap trades about halfway, fails, then drops (L05, L13). [in rulebook / TE te64]
- DRAFT: Opening range (09:30-10:00) and ORG: mark high, low, CE, quadrants; carry any not fully
  used forward 3 days (L10). [new]
- DRAFT: London opening range = 00:00-00:30 (L05). [new]

- DRAFT: ORG mid-gap is traded to ~70% of the time 09:30-10:00 ("back to 1987 using Globex
  numbers"); after the mid-gap, taking the next low gives ~80% odds of a 3/4 fill (L14, L22, L25).
  [conflict check: C37 ORG-CE-WINDOW; 80% follow-on new]
- DRAFT: Small ORG (under ~20-40 NQ handles; ICT gives "20 to 30" and "30 to 40") = no ORG play,
  wait for 10:00 (L17, L18). [conflict: C22 ORG-SIZE]
- DRAFT: Large premium ORG = "too expensive": don't buy it; frame a short in a premium array between
  a breaker low and the ORG upper quadrant, target the mid-gap, then the lower quadrant (L20, L25).
  [new]
- DRAFT: An NDOG/NWOG inside the ORG beyond the mid-gap is the next target (low-hanging fruit)
  (L22). [new]
- DRAFT: Layered (nested) NDOG/NWOG near price = high-resistance liquidity run (chop, "time
  distortion"); spaced-out gaps = clean runs; slicing through layers = in a hurry to a farther
  draw (L20, L21). [new]
- DRAFT: Event horizon = halfway between the NWOG above and the NDOG below (L16, L21). [in rulebook]
- DRAFT: NWOG lookback up to 60 trading days (5 weeks is the beginner baseline) (L16, L18).
  [conflict: C23 GAP-LIFE]
- DRAFT: ORG mid-gap model: ORG over 40 handles (bigger is better), bias toward the mid-gap, enter the first FVG 09:31-10:00, partial below a short-term low and stop to cover costs, 75-80% off at the mid-gap, rest to full fill (L29). [conflict: OPEN-RANGE-TRADE, ORG-CE-WINDOW]
- DRAFT: ORG size: ~15-20 handles = limp; under 40 = other tools or wait for 10:00; under 75 invites a lethargic morning; very large (several hundred) = let them make the initial high first (L27, L31, L32, L35, L36). [conflict: ORG-SIZE]
- DRAFT: Premarket ORG that shrinks into 09:30 = muddy first 30 minutes (L27). [new]
- DRAFT: After gap closure treat the whole ORG as an FVG; bodies stopping at its quadrant with a small part left open = signature the target gets hit (L36).
- DRAFT: First presented FVG: on 1m it can't be the 09:30 candle (09:31+, L28, L29, L32, L36, L37); on 15s the first gap after the 09:30 minute counts (L35); extend it ~3 days; opening inside yesterday's FPFVG makes that one the day's reference; late-day return to the FPFVG = daily true value unless trending (L32). [conflict: FPFVG-DEF]

### A5. PD arrays and definitions
- DRAFT: CE = midpoint of a gap (FVG, VI, wick, opening gap); mean threshold = midpoint of an order
  block; equilibrium = midpoint of a delivered range (L03, L13). [in rulebook]
- DRAFT: Wick CE: every swing-point wick is treated as a gap; mark its CE and quadrants; can't reach
  the CE → likely the other direction (L08). [in rulebook: A23 / A5]
- DRAFT: FVG annotation: keep the original levels after partial fills; a volume imbalance inside
  the FVG extends it to the body (L01, L02, L06). [conflict check: rulebook A9 / FVG definition]
- DRAFT: FVG half rule: best shorts form in the lower half of a SIBI (upper half left open), best
  longs in the upper half of a BISI → breakaway, range expansion (L03). [in rulebook: A5/A6 reads]
- DRAFT: Breakaway gap = FVG formed as price leaves a consolidation after a stop run; tends to stay
  open (L07, L09). [in rulebook: A6]
- DRAFT: Exhaustion gap = late-run gap price should not return to (L09). [new]
- DRAFT: Inversion FVG: bodies stay inside, wicks may spike ("permissible"); the far half should
  stay open; a full roll-over cancels the idea (L09). [in rulebook: A8]
- DRAFT: Reclaimed FVG: a second return is tradeable if it fails at CE (L04). [conflict check]
- DRAFT: BPR inside an FVG: candle 3's body flush on candle 1's body (no wick between) is the real
  level (L08). [new]; Mohawk = small overshoot from a BPR (L03, L08). [in rulebook]
- DRAFT: An FVG inside an OB's range → use the OB range; ignore the first FVG of a new program still
  inside it (L08). [new]
- DRAFT: Consecutive-candle OB: the opening price of the first candle of a run of same-colour
  candles before displacement is the change in state of delivery; it needs a supporting PD array
  (L07, L08, L12). [in rulebook: A12 `ob_pick` "blend"]
  - Validated when price crosses that open; "I don't need to see it close below it" (L08).
    [conflict check: rulebook close requirements]
  - Bodies stay in the upper half (bullish) / below the MT (bearish) (L07, L08). [in rulebook]
- DRAFT: Bearish OB validated when a later candle closes below its open (L06). [in rulebook]
- DRAFT: Bearish OB that fails to reach an FVG's CE = entry candle (L03). [new]
- DRAFT: Gap + OB: a true opening gap right after a down-close candle when bullish is a strong buy
  (L11). [new]
- DRAFT: Immediate rebalance; balanced price range doesn't need a deep retrace (L02, L04). [in
  rulebook: A7, A11]
- DRAFT: Every PD array has an inversion role; arrays from the buy-side of the curve that converge
  with new sell-side arrays carry the most weight (L02, L08). [in rulebook: A8]
- DRAFT: Turtle soup has two forms only: (1) reversal / change in state of delivery (breakers are
  usually this); (2) entry inside an existing program (every FVG entry is one). Not the Street Smarts
  20-day pattern (L08). [in rulebook]
- DRAFT: Three drives: measure low to the 3rd high; first target 50% of it; objective the low (L07).
  [in rulebook: M2] [new: 50% first target]
- DRAFT: Daily references: previous day high/low, last 3 days' highs/lows, last week's high/low,
  and their quadrants (L07). [in rulebook]

- DRAFT: First presentation FVG = first FVG with its middle candle at 09:31 or later before 10:00;
  carried for a 3-day life (L14, L16, L21); not limited to the 09:30 anchor: any first FVG after a
  time anchor (L24). [conflict: C38 FPFVG-DEF]
- DRAFT: Bearish OB = the whole run of consecutive up-close candles; change of state at the lowest
  open (bullish: highest open of the down-closes); validated when LTF bodies respect it; entry
  range up to its mean threshold (L14, L17, L20, L24). [conflict: C35 OB-CANDLE]
- DRAFT: OB activation by a one-tick breach of that open with no close (L14). [conflict: C21]
- DRAFT: Breaker zone = body, upper half for a bullish breaker (L18). [conflict: C24 BREAKER-ZONE]
- DRAFT: FVG wick tolerance: a wick may extend beyond an FVG by up to one standard deviation of the
  gap's width (L24). [new; C40]
- DRAFT: Immediate rebalance: next candle touches the prior candle's high/low and should go at
  once (L17, L21). [new]
- DRAFT: Balanced price range: no long through it; if reclaimed, stop for the day (L16). [new]
- DRAFT: FVG roles: candle 2 = FVG / trigger, candle 3 = entry candle; grade by quadrants; wicks may pass CE, bodies may not; bullish ideal = one (at most two) candles into the upper half, lower half open (L27, L28, L33, L35, L36). [conflict check: FVG-VALID]
- DRAFT: CE should be hit once and left; a second return = likely failure (L33).
- DRAFT: Wick CE: "opposing premium and discount CEs on wicks" can be a model; bodies building at a wick CE = continuation (L26).
- DRAFT: Volume imbalance = the weakest PD array; real VI has an indecisive candle between bodies (L26, L35).
- DRAFT: OB validated once price crosses its open, no close needed; bullish OB = open to mean threshold (L35, L38). [conflict check: OB-CLOSE]
- DRAFT: Breakaway vs measuring gap (gap at 50% of a leg = equal second leg) (L38). Model 2022: with stacked FVGs expect the higher one first (L31, L38).
- DRAFT: Bearish inversion FVG = an up-close FVG used bearishly; traded back above = reclaimed bullish FVG, not an inversion (L36, L37).
- DRAFT: Indigo entry: OB with a volume imbalance on it trading into a liquidity purge (L38). [new]

### A6. Entries
- DRAFT: IOFED: limit at the near edge of an FVG expected not to fully fill (BISI: its top;
  SIBI: its bottom), within one tick either side (L07/L11 say one tick outside the gap, L10 one
  tick inside); go-to only when ICT says the gap should stay open (breakaway) (L07, L08, L10, L11).
  [in rulebook: A15] [conflict check: the exact tick offset]
  - Caleb's entry technique: buy one tick below the high of a bullish FVG, sell one tick above the
    low of a bearish FVG (L10). [beginner]
  - FVG can be called while candle 2 is still forming (L11). [new]
- DRAFT: The very first FVG prior to a stop run (inside the leg that ran the stops) is the preferred
  entry over the breaker; it becomes the inversion FVG (L02). [new]
- DRAFT: Once bearish, extend only SIBIs and short-term highs (ignore BISIs unless a violent
  reversal) (L02). [new]
- DRAFT: A SIBI already overlapped and respected 2+ times = low probability, no trade (L02). [new]
- DRAFT: OB entry at the open, on an uptick (L06); short at the SIBI low ("lowest threshold") so the
  order fills (L06). [conflict check: owner #11 OB entry before the break]
- DRAFT: Inversion FVG followed by a fresh FVG in the bias direction = "very nice model" (L10). [in
  rulebook: M10]
- DRAFT: Gap-down open: buy at the open toward the ORG CE "with no bias needed" (L13). [conflict:
  rulebook no entries 09:30-10:00 / N8 large ORG]
- DRAFT: NDOG high + 1 tick as the easiest-fill entry; stop below the opening candle / VI (L10). [new]
- DRAFT: Asia NDOG protocol (see A12). [conflict: Asia skipped by default]

- DRAFT: Caleb's model inside the OR: first FVG (09:31-10:00) entry, partial at the mid-gap,
  terminus at an NDOG/NWOG (L14, L22). [conflict: C20 OPEN-RANGE-TRADE] Opposite on L25: sit still
  until 10:00 (beginner exercise).
- DRAFT: Re-entry after a stop-out while the model is intact (market maker sell model): re-enter
  at the inversion FVG and keep pyramiding (L20). [conflict: C27 REENTRY]
- DRAFT: Turtle soup above highs into a bearish OB; entry at the FVG candle high - 1 tick (L23,
  L24). [in rulebook]
- DRAFT: 50/50 rule: if the setup frames both ways, don't trade (L20). [new]
- DRAFT: FVG entry: long at candle 3's low + 1 tick, short at candle 3's high - 1 tick; add at the near quadrant and at CE (L28). Scale in 1 at CE, 1 at the lower quadrant (L27). [new]
- DRAFT: A level is not a setup: need displacement off the PD array first (L33, L36). Caleb's strongest model: buy side and sell side both taken, then the FVG/IFVG (L33).
- DRAFT: Re-entry: failed FVG = inversion at half size (L28); after an inversion is left, one touch, then the next displacement FVG (L31); return to a premium array must be on a new candle (L37). [conflict check: REENTRY]
- DRAFT: Missed entry: drop a timeframe (L29). Limit orders for entries and exits; market orders only to get out (L28, L38).

### A7. Stops and management
- DRAFT: Breaker stop above the HIGHEST high of the consecutive down-close candles (+1-2 ticks)
  (L02). [conflict check: owner #14 full-range breaker]
- DRAFT: OB stop at the OB's mean threshold (L06). [conflict check: rulebook MT/OB stops]
- DRAFT: FVG baseline stop beyond candle 1; tight stop = CE of candle 1's wick + 2 ticks (L08).
  [new: wick-CE+2]
- DRAFT: Bearish OB in a sell program: stop above its high (or wick) + 1 tick; if stopped by a spike
  into the wick's CE, re-enter there (L08). [conflict check: E10 after a loss]
- DRAFT: Kill the trade when a candle CLOSES beyond the stop-reference level, before the stop is hit
  (L07). [new]
- DRAFT: Immediate response: far half of the gap left open → must accelerate; full fill → must give
  speed and large-range candles right away (L08). [new] (our interpretation needed for "immediate")
- DRAFT: Trailing stop below a balanced range / wick CE that price passed through (L11). [new]
- DRAFT: Don't strangle a position by trailing; expect the lunch retrace (L12). [new]
- DRAFT: An open trade can give back 50-60% of unrealized profit normally (L08). [conflict check:
  TE `max_giveback_unrealized`]
- DRAFT: Hard stop, never a mental stop; if distracted, close at least 50% (L04). [in rulebook]

- DRAFT: Stop below the FVG imbalance (middle) candle - 1 tick (conservative: first candle) (L20);
  OB stop above its high + 1 tick (L24). [conflict check: C39 not scored]
- DRAFT: Move the stop to cover costs once price is halfway to the first partial (L20).
  [conflict: C28 STOP-MGMT]
- DRAFT: OSOK: hold a day-of-entry position overnight to a daily FVG CE (L23, L24).
  [conflict: C32 OVERNIGHT-HOLD]
- DRAFT: Stop placement (new card STOP-PLACE with C12, C39): beyond candle 1 (conservative) or candle 2 (max leverage) (L28); above candle 2 if affordable, else candle 3 body / wick CE (L37); one tick past the OB open (L26); 2x the FVG range on high resistance days, CE + 1 tick on low resistance days (L36); beyond the higher stacked FVG's CE (L38). [conflict: STOP-PLACE]
- DRAFT: Break even only after price has run 25% of the way to the target (L26); cover costs once a short-term low breaks (L29). [conflict: STOP-MGMT]
- DRAFT: High resistance: dial back leverage, cut to one contract when you notice it mid-trade, partial every broken low (L36).

### A8. Partials and targets
- DRAFT: Every short-term high broken in a long is a partial candidate; better to take a partial
  than move the stop early ("running down equity") (L13). [in rulebook]
- DRAFT: Private-student rule: a short-term high between entry and target AND beyond 50% of the run
  → partial when price passes it (L10). [new]
- DRAFT: Measured move: project the prior leg 1.0 and 1.5; exit between them; must coincide with an
  old high / relative equal highs (L05). [conflict check: rulebook projections]
- DRAFT: Quarter-range projection: project 25% of the range (swing high to low) beyond the old low =
  low-hanging target (L08). [new]
- DRAFT: Targets beyond relative equal highs/lows: the nearest NDOG/NWOG beyond them, split into
  quadrants; easiest exit = first quadrant + 1 tick (L11). [new]
- DRAFT: Rejection block (extreme body close) as a partial (L08). [in rulebook]
- DRAFT: Minimum move: NQ 10 handles (ICT prefers 15, needs ~20 of room); ES 5 (L07, L10).
  [conflict: owner #2 5 handles minimum room; rulebook L15]
- DRAFT: After the objective (e.g. high of day touched) → done for the day (L02, L04). [in rulebook]
- DRAFT: Take 75-80% off at upside targets before Thursday 13:00 (L10). [new]

- DRAFT: Below a previous-day low, take the partial after the next short-term low (L19).
  [conflict: C25 PARTIAL-TRIGGER]
- DRAFT: Dynamic trailed partial: one contract trailed above each prior 1m candle high (L19). [new]
- DRAFT: Lunch macro target: first high/low after 10:00 (L14); always a retracement against the AM
  move (L24). [conflict: C34 LUNCH-TARGET]
- DRAFT: Prior 3 days' highs/lows and Thu/Fri highs/lows as draws (L18, L19). [new]
- DRAFT: Limit cover a little before the exact target so the full size fills (L24). [new]
- DRAFT: Minimum 20 handles of room (L28, L29, L31). [conflict: MIN-ROOM]
- DRAFT: Scale out at a wick CE ahead of the target; exit ahead of premium levels; finesse for spread (L33, L35, L26). Targets: easiest exit first (first gap, ORG lower quadrant, ORG CE) (L28).
- DRAFT: Multi-contract runner: one contract off each time a new swing high breaks (L38). Decoupled market: majority off at the first target (L37). [conflict check: EXIT-STYLE, PARTIAL-TRIGGER]

### A9. Pyramiding and size
- DRAFT: Six-and-four: 6 first entry, +4 on the pullback; once the pullback fails to reach CE, stop
  to first entry minus 2 ticks (L03). [conflict check: E11/E12, add_ladder 631]
- DRAFT: IOFED ladder: 6 at IOFED, +4 at CE/upper quadrant, +5 one tick below CE (not allowed by
  some prop firms; then single entry and pyramid only at higher arrays) (L07, L08). [conflict check:
  E12 decreasing adds]
- DRAFT: Size with the daily bias: full size with daily order flow while HTF targets remain; 1-4
  contracts counter-trend or late in the move (L12). [new; check owner #12]

- DRAFT: OSOK pyramid windows: same-day adds only in the final hour (14:30-15:00) if the high holds,
  else after midnight (L23). [new; C42]
- DRAFT: Add small (1-2 contracts) at a premium array near a wick CE when already on (L26). Max leverage only on low resistance days (L36).

### A10. Weekly and daily profiles (TGIF)
- DRAFT: TGIF: after a big one-sided week, Friday retraces 20-30% of the week's range; fib low→high
  (up week) with 20/30% levels (L05, L10). [in rulebook: M14] [conflict: tgif_exits "066"]
- DRAFT: TGIF can start Thursday 13:00, measured from the highest high at/after Thursday 13:00, when
  the weekly range is larger than recent weeks (L10). [conflict check: M14 timing]
- DRAFT: Once a 20% weekly retracement prints and you haven't traded → done for the week; if it
  happened Thursday, don't trade Friday; a new high after it = manual intervention (L10). [new]
- DRAFT: Deferred TGIF: if Friday didn't retrace, expect 20-30% on Monday (L06, L10). [new]
- DRAFT: Daily power of three: after a bullish day reaches its objective it retraces 20-30% and
  closes in the upper third; a close on the high hints at a retrace/short tomorrow (L10).
  [conflict check: rulebook power of three]
- DRAFT: TGIF: Friday retraces 20-30% of the weekly range; 20% = first partial, 30% = target; else Monday (L32, L36). [conflict check: TGIF-DEPTH]

### A11. SMT
- DRAFT: Long, NQ makes a higher high and ES doesn't → take a partial; Dow divergence alone → caution
  only (L05). [conflict: rulebook "SMT is a qualifier only"]
- DRAFT: Prefer ES vs NQ; YM is usually the one that "doesn't listen" (L09). [conflict check:
  rulebook ES/NQ/YM matrix]
- DRAFT: SMT matrix 5m/4m/3m/2m/1m for NQ/ES/YM; a qualifier, not a necessity (L04). [in rulebook]

- DRAFT: SMT = waning continuation only; combine with a technical break (L20). [conflict: C29]
- DRAFT: SMT on ES vs NQ; Dow only as an early warning; body SMT (higher wick, lower bodies) counts (L29); want all three indices to agree in a trade (L37). [conflict check: SMT-USE]

### A12. Asia and London
- DRAFT: Asia NDOG protocol (key window 19:00-21:00): don't trade the 18:00 open; price leaves the
  NDOG and takes a short-term high (low), crosses back and takes a short-term low (high) = initial
  buy-side/sell-side; at 19:00 the retrace into the NDOG is the trigger; entry below the body of the
  down-close candle; stop below the NDOG CE; BE after the relative equal high is taken; skip if price
  dawdles at 18:00 (L05). [conflict: Asia skipped by default]
- DRAFT: London range 02:00-05:00; NY first characteristic = re-trade into it (L02). [in rulebook]

### A13. [beginner] process (not engine rules)
- August = journal only; month 1 back-test, month 2 tape-read, month 3 executions (L02, L03).
- One contract; one setup; max 1% risk; stop after a loss; after a winning day close the charts
  (L02, L06, L08, L11). [conflict: owner #12 1.2%/1.3%; E10]
- Graduated holding: close at target → hold through lunch, flat by 13:30 → hold to 15:15 (L11, L12).
- Log "price delivery measurements" (time to target, heat) and tally them daily (L10).
- Draw your model on a napkin: entry, stop, first partial, terminus (L07, L10).
- [beginner] Drill target: one micro, $75-100 then stop (L31); volatility pinball: one contract, limit entry with stop and target, every 15s/1m FVG to an old high/low, log the stats (L38); learn on micros (L28, L31, L32).

---

## Part B. Trade examples (captions; prices approximate)

| Date | Lecture | Trade | Notes |
|---|---|---|---|
| 2024-08-05 | L01 | none | REH 17,820.75 forecast; 09:30 Judas into breaker/FVG near EQ, then the run |
| 2024-08-07 | L03 | short 6 @ 18,321.25, +4 @ 18,291.25 (demo) | OB failed FVG CE; London REL + NDOG draw; >100 handles |
| 2024-08-08 eve | L05 | long 18,559.75 → 18,607.5 (Asia) | NDOG protocol; exit between 1.0 and 1.5 measured move |
| 2024-08-12 | L06 | short from bearish OB, add at SIBI low | partial taken, trailed stop hit; deferred TGIF Monday |
| 2024-08-13 | L07 | none (hindsight long) | IOFED 18,931.00 at 10:52 in 10:50-11:10 macro |
| 2024-08-14 | L08 | none (hindsight short) | CPI; NWOG hit; consecutive-candle OB open crossed |
| 2024-08-15 | L09/L10 | short at lunch high (turtle soup, 15 lots, 5 off) | mentioned in L10 |
| 2024-08-19 | L11/L12 | long IOFED in 10:00 FVG (demo) | 2 handles heat; exit at NWOG lower quadrant + 1 tick |
| 2024-08-20 | L13 | none (hindsight long) | gap-down open → ORG CE, NDOG support, daily VI quadrants |
| 2024-08-21 | L14 | ICT long (inversion FVG buy stop) and short 6 +4 at an OB / NDOG low | "over $177,000" (caption); last 4 stopped on the overlap |
| 2024-08-22 | L14 | none (hindsight short, Caleb's model) | premium ORG, mid-gap hit, inversion entry 19,973.50 (candle high - 1 tick) |
| 2024-08-23 | L16 | short (narrated) | Judas during Powell, turtle soup, bearish OB; draw to a nested NDOG/NWOG |
| 2024-08-26 | L17 | none | small discount ORG (~20 handles), wait to 10:00; immediate rebalance |
| 2024-08-27 | L18 | ICT pre-session short 12 (6 + 6 at wick CE); hindsight AM long | first FVG low held to the tick; 3/4 then full ORG fill |
| 2024-08-28 PM | L19 | none | dynamic trailed partial example; 14:50 macro rally to Tuesday's low |
| 2024-08-29 | L20 | ICT pre-session short, stopped, re-entered at the IFVG | premium ORG "too expensive"; layered gaps; 50/50 = no trade |
| 2024-08-30 | L21 | none | pre-holiday Friday; layered NDOG/NWOG chop |
| 2024-09-04 | L22 | none | after a large range day: sit out the AM; mid-gap then NDOG |
| 2024-09-05/06 | L23, L24 | ICT OSOK short held overnight, 14 contracts covered at the Aug 13 daily FVG | ~$100,000 (caption), "almost 360 handles"; adds after midnight |
| 2024-09-09 | L25 | none | premium ORG into a weekly IFVG; IOFED ~10:30 to the mid-gap |
| 2024-09-11 | L26 | none | CPI day; drop to ORG fill; 1m wick CE ~18,775 then NDOG flush |
| 2024-09-12 | L27 | none | after a large range day; 15-handle ORG; 1h BISI graded |
| 2024-09-16 | L28 | none (drills) | first FVG long ~19,365-19,378, ~3 handles heat; ORG lower quadrant reached |
| 2024-09-17 | L29 | none (framed) | >100-handle premium ORG; FPFVG 09:33 short to mid-gap ~19,728 |
| 2024-09-19 | L31 | short 1 MNQ | several-hundred-handle ORG; first FVG; Model 2022 stab; $75-100 offered |
| 2024-09-20 | L32 | short MNQ | at the high of Thursday's FPFVG after its CE; exit ~19,993.75 wick CE |
| 2024-09-23 | L33 | long (early) | wick CE + IFVG, exit at 0.25 extension; then time distortion, no trades |
| 2024-09-25 | L35 | long | 1m BISI beside yesterday's FPFVG toward the Aug 22 high; scaled out |
| 2024-09-27 | L36 | none (framed) | high resistance; FPFVG low kissed = short; stop 2x FVG; TGIF 20/30% |
| 2024-09-30 | L37 | none (framed) | FPFVG bearish inversion at CE to REL; decoupled ES/YM |
| 2024-09-30 Asia | L38 | long 8 (reviewed) | Indigo entry; one contract off per new swing high |
| 2024-10-01 | L38 | ~10 drills (1 contract) | volatility pinball, wins and losses |

---

## Part C. Conflicts to decide (2023 rule / owner directive stays in force meanwhile)

1. NWOG life 5 weeks and NDOG life 5 days vs rulebook up to 60 trading days (L03, L08, L13).
2. Pre-market range definitions (07:00-07:30 etc.) and a 07:30-08:00 opening range vs TE te58/te60 and rulebook N5 (L01).
3. Gap-down open long toward ORG CE at 09:30 vs rulebook "no trades in 09:30-10:00" and N8 large-ORG wait (L13).
4. Lunch window 11:30-13:30 and the "first low after 10:00" target vs rulebook lunch references (L10, L12).
5. Last-hour macros from 15:15 and MOC 15:45-16:00 vs owner #1 (15:00-15:50) (L11, L12).
6. Minimum move NQ 10 / ES 5 (20 room) vs owner #2 (5 handles minimum room) (L07, L10).
7. TGIF 20-30% exits and Thursday 13:00 start vs tgif_exits "066" and M14 timing (L05, L10).
8. SMT partial on NQ/ES divergence vs "SMT is a qualifier only" (L05).
9. Mondays skipped except NFP week vs "Mondays traded" (L06).
10. Asia NDOG protocol vs Asia skipped by default (L05).
11. Early (07:00-09:30) entries before big news vs N5 pre-09:30 test-only switches (L06).
12. OB entry at the open on an uptick / stop at mean threshold vs owner #11 and rulebook OB stops (L06). Stop part scored on card STOP-PLACE (position A).
13. Breaker stop at the highest high vs owner #14 full-range breaker (L02).
14. OB validation on a cross without a close vs rulebook close requirements (L08).
15. NDOG/NWOG CE and quadrants only when 20+ handles vs rulebook A5 quadrants on every gap (L04, L05, L11).
16. Beginner risk (1%, one trade, stop after a loss) vs owner #12 and "reversing after a loss allowed" (L06, L08).
17. News: trade 15-30 min after the release vs rulebook N1/N4 handling (L08).
18. Pyramid ladders (6/4, 6/4/5) vs E11/E12 and add_ladder 631 (L03, L07).
19. Stand aside until the 10:00 SB when price reaches the NWOG before 09:30 (L04): SB is OFF, so this stays off.
20. First FVG / ORG trades inside 09:30-10:00 (Caleb's model) vs rulebook no trades 09:30-10:00 (L14, L22; L25 the other way). Card OPEN-RANGE-TRADE.
21. OB activation on a one-tick breach with no close (L14). Card OB-CLOSE.
22. Small ORG (under ~20-40 handles) = wait for 10:00 (L17, L18). Card ORG-SIZE (new position D).
23. NWOG/PD array lookback 60 days, 5 weeks only the beginner baseline (L16, L18). Card GAP-LIFE.
24. Breaker = body, upper half (L18) vs owner #14 full range. Card BREAKER-ZONE.
25. Partial below a previous-day low only after the next short-term low (L19). Card PARTIAL-TRIGGER.
26. 14:50-15:10 macro (L19) vs owner #1 15:00-15:50. Card LAST-HOUR.
27. Re-entry after a stop-out while the model holds (L20). Card REENTRY.
28. Stop to cover costs at half the way to the first partial (L20). Card STOP-MGMT (new position F).
29. SMT as waning continuation only (L20). Card SMT-USE.
30. Pre-holiday Friday and the Mon/Tue after a holiday skipped (L21): agrees with filters.md 1.2; not scored.
31. No AM trades after a large range day, trade the PM (L22). Card AFTER-BIG-DAY.
32. OSOK: hold overnight to a daily FVG CE (L23, L24) vs flat by 16:00. New card OVERNIGHT-HOLD.
33. News: trade 15-30 min after NFP/CPI/PPI (L24, L25). Card NEWS-WAIT.
34. Lunch target: first high after 10:00 (L14) vs retracement of the AM move (L24). Card LUNCH-TARGET.
35. OB = the whole consecutive-candle run, open of its extreme candle (L14, L17, L20, L24). Card OB-CANDLE.
36. Trade Mon/Tue before midweek CPI/PPI; no-news days need clean price (L25). Card CPI-WEEK (new position C).
37. ORG mid-gap 70% in the first 30 min (L14, L22, L25). Card ORG-CE-WINDOW.
38. First presentation FVG at 09:31+ with a 3-day life (L16, L21), or after any time anchor (L24). Card FPFVG-DEF (new position D).
39. Stop below the FVG imbalance candle - 1 tick (L20), OB high + 1 tick (L24). Card STOP-PLACE (with 12 and 45).
40. FVG wick tolerance of one standard deviation of its width (L24). Not scored (one source).
41. Done for the week once the weekly objective is hit (L24). Not scored (one source).
42. OSOK pyramid windows: final hour or after midnight (L23). Not scored (one source).
43. Light Jackson Hole week, skip the Monday after the Symposium (L14). Not scored (one source).
44. Break even only after 25% of the target (L26) vs cover costs once a short-term low breaks (L29) vs half way to the first partial (L20). Card STOP-MGMT (new position G).
45. Stop placement, L26-L38: candle 1 / candle 2 (L28), candle 2 or candle 3 body/wick CE (L37), OB open + 1 (L26), 2x FVG range on high resistance days vs CE + 1 on low resistance days (L36), beyond the higher stacked FVG (L38). New card STOP-PLACE (with 12 and 39).
46. ORG size: under 40 = no ORG play / wait for 10:00 (L27, L32), 40+ and bigger is better, under 75 lethargic (L29, L36), very large = wait for the initial high (L31). Card ORG-SIZE (new position E).
47. ORG mid-gap model traded inside 09:31-10:00 (L29, L36). Card OPEN-RANGE-TRADE.
48. Mid-gap 70% by 10:00 (L28, L29). Card ORG-CE-WINDOW.
49. FPFVG at 09:31+ on 1m (L28, L32, L36); first 15s gap after the 09:30 minute (L35). Card FPFVG-DEF (new position E).
50. No AM after a large range day, PM is easiest (L27, L32). Card AFTER-BIG-DAY.
51. FOMC day: avoid (inexperienced); day before = morning only (L29). Card FOMC-DAY (new position D).
52. Fed speech in the 09:00-10:00 hour = trade before 08:00 (L37). Card PREMARKET-ENTRY.
53. Minimum 15 min after any high/medium release (L37). Card NEWS-WAIT.
54. Always trade the NFP-week Monday; new students skip other Mondays (L37). Card MONDAY.
55. New students skip Wed-Fri of NFP week; experienced trade after the release (L38). Card NFP-THU-FRI.
56. Lunch 11:30-13:30 (L37). Card LUNCH-WINDOW.
57. Minimum 20 handles of room (L28, L29, L31). Card MIN-ROOM.
58. Re-entry: half size after a failed FVG (L28); think twice on high resistance days (L36). Card REENTRY.
59. Partials below every broken low (L36, L38); 75-80% at the mid-gap (L29). Card PARTIAL-TRIGGER.
60. Majority off at the first target when decoupled (L37); one contract per new swing high (L38). Card EXIT-STYLE.
61. OB valid once price crosses its open (L38). Card OB-CLOSE.
62. FVG with more than 1-2 candles inside / CE revisited = not valid (L28, L33, L36). Card FVG-VALID.
63. TGIF 20-30%, 20% partial and 30% target (L32, L36). Card TGIF-DEPTH.
64. All three indices should agree; decoupled = low risk (L37). Card SMT-USE.
65. Opening inside yesterday's FPFVG makes it the day's reference (L32). Not scored (one source).
66. Fed chair speech: no trading during it and 15 min after (L37). Not scored (one source).

## Part D. Backtestable switches (all default OFF; DRAFT names)

| Switch | Values | Source |
|---|---|---|
| `smooth_pool_bias` | on/off | L01 |
| `primed_equal_pool` | on/off (left higher than right) | L01, L11 |
| `bias_window_start` | 07:00 / 08:00 / 09:00 | L01, L02 |
| `bias_0700_judas_second_side` | on/off | L11 |
| `pre_window_judas_required` | on/off | L02 |
| `entry_first_fvg_before_stop_run` | on/off | L02 |
| `ifvg_in_stop_leg_over_breaker` | on/off | L02 |
| `one_direction_fvgs_only` | on/off | L02 |
| `skip_overlapped_fvg` | off / 2 respects | L02 |
| `vi_extends_fvg` | on/off | L02 |
| `no_am_news_trade_pm` | on/off | L03 |
| `bond_auction_pm_driver` | on/off | L03 |
| `ndog_cluster_bias` / `gap_cluster_bias_0830` | on/off | L03, L04 |
| `ndog_life_days` / `nwog_life_weeks` | 5 / 60d ; 5 / 60d | L03, L08 |
| `fvg_half_quality` | on/off | L03 |
| `ob_fails_ce_entry` | on/off | L03 |
| `six_four_pyramid` | off / 6-4 / 6-4-5 | L03, L07 |
| `wait_if_sandwiched_between_gaps` | on/off | L04 |
| `reclaimed_fvg_entry` | on/off | L04 |
| `bpr_no_deep_retrace` | on/off | L04 |
| `gap_quadrants_min_handles` | 0 / 20 | L04, L05, L11 |
| `asia_ndog_protocol` | on/off | L05 |
| `measured_move_exit` | 1.0 / 1.0-1.5 / 1.5 | L05 |
| `org_midgap_target` | on/off | L05, L13 |
| `org_ce_open_trade` | on/off | L13 |
| `org_open_price_first_target` | on/off | L09 |
| `tgif_retrace_pct` | 20 / 30 | L05, L10 |
| `tgif_start_thu_1300` | on/off | L10 |
| `stop_week_after_20pct_retrace` | on/off | L10 |
| `skip_friday_if_thu_tgif` | on/off | L10 |
| `tgif_deferred_monday` | on/off | L06 |
| `smt_partial_es_nq` | on/off | L05 |
| `smt_exclude_dow` | on/off | L09 |
| `london_or_0000_0030` | on/off | L05 |
| `pre_news_day_one_chance` | on/off | L06 |
| `early_entries_if_big_news_tomorrow` | on/off | L06 |
| `skip_monday_unless_nfp_week` | on/off | L06 |
| `ob_stop_mean_threshold` | on/off | L06 |
| `short_entry_at_sibi_low` | on/off | L06 |
| `iofed_entry` | on/off | L07, L11 |
| `breakaway_gap_requires_consolidation_stop_run` | on/off | L07 |
| `ob_consecutive_candles_open` / `ob_validate_on_cross_no_close` | on/off | L07, L08 |
| `problem_day_filter` | off / proxy (ours) | L07 |
| `min_target_handles` | NQ 10 / 15, ES 5 | L07, L10 |
| `kill_on_close_beyond_stop_ref` | on/off | L07 |
| `three_drives_target_half` | on/off | L07 |
| `macro_hourly_only` | on/off | L07 |
| `wick_ce_levels` | on/off | L08 |
| `six_pm_open_line` | on/off | L08 |
| `ob_range_over_inside_fvg` | on/off | L08 |
| `bpr_inside_fvg_level` | on/off | L08 |
| `stop_wick_ce_plus2` | on/off | L08 |
| `quarter_range_projection_target` | on/off | L08 |
| `fill_requires_immediate_displacement` | off / N bars (ours) | L08 |
| `no_long_after_gap_up_and_news_run` | on/off | L09 |
| `ifvg_body_inside_rule` | on/off | L09 |
| `lunch_macro_fade_if_no_am_trade` | on/off | L09 |
| `or_quadrants_3day` / `org_quadrants_3day` | on/off | L10 |
| `lunch_macro_first_low_after_1000` | on/off | L10, L12 |
| `partial_at_obstacle_past_50pct` | on/off | L10 |
| `partial_every_broken_high` | on/off | L13 |
| `no_friday_pm_if_flat_am` | on/off | L10 |
| `daily_po3_upper_third` | on/off | L10 |
| `target_first_quadrant_of_next_gap` | on/off | L11 |
| `gap_plus_ob_entry` | on/off | L11 |
| `nwog_ce_min_20_handles` | on/off | L11 |
| `fomc_1430_reversal` | on/off (study) | L11 |
| `stop_trading_after_win_day` | on/off [beginner] | L11 |
| `hold_to_1330_exit` / `hold_runner_to_1515` | on/off | L11, L12 |
| `size_by_daily_bias` | on/off | L12 |
| `draw_gap_with_eq_pool` | on/off | L13 |
| `ndog_valid_after_fill` | on/off | L13 |
| `org_three_quarter_after_low` | on/off | L14 |
| `first_fvg_0930_model` | on/off | L14, L22 |
| `stop_wick_ce_if_rebalance` | on/off | L14 |
| `ob_void_on_rejection_block_take` | on/off | L14 |
| `three_drives_retrace` | on/off | L14 |
| `jackson_hole_week_light` / `skip_monday_if_symposium` | on/off | L14 |
| `pd_array_wider_settlement` | on/off | L14 |
| `london_or_first_fvg` | on/off | L14 |
| `first_fvg_min_0931` | on/off | L16 |
| `event_horizon_target` | on/off | L16, L21 |
| `balanced_range_guard` | on/off | L16 |
| `nested_gap_draw` | on/off | L16 |
| `small_org_wait_1000` | 20 / 30 / 40 handles | L17, L18 |
| `immediate_rebalance_continuation` | on/off | L17 |
| `coin_flip_org_return` | on/off | L17 |
| `accumulation_below_pool` | on/off | L18 |
| `quadrant_range_extension_target` | on/off | L18 |
| `vi_true_range_of_fvg` | on/off | L18 |
| `prior_day_thu_fri_hl_draws` / `prior_3day_hl_liquidity` | on/off | L18, L19 |
| `pdl_partial_after_next_swing` | on/off | L19 |
| `dynamic_trailed_partial_1m` | on/off | L19 |
| `speed_past_mid_range` | on/off | L19 (study) |
| `stop_below_imbalance_candle` | on/off | L20 |
| `cover_costs_at_half_first_partial` | on/off | L20 |
| `no_chase_premium_open` / `no_buy_premium_org` | on/off | L20, L25 |
| `layered_gap_high_resistance` / `layered_gap_congestion_filter` | on/off | L20, L21 |
| `fifty_fifty_no_trade` | on/off | L20 (proxy, ours) |
| `skip_preholiday_friday` / `skip_postholiday_two_days` | on/off | L21 |
| `first_presentation_fvg_life_days` | 3 | L21 |
| `skip_am_after_large_range_day` | on/off | L22 (proxy, ours) |
| `hold_overnight_to_daily_target` | on/off | L23, L24 |
| `pyramid_window_final_hour_or_after_midnight` | on/off | L23 |
| `ob_full_run_stop_high_plus1` | on/off | L24 |
| `fvg_wick_tolerance_1sd` | on/off | L24 |
| `weekly_objective_done` | on/off | L24 |
| `bellwether_15m_news_side` | on/off | L24 (study) |
| `org_upper_quadrant_short_frame` | on/off | L25 |
| `wick_ce_entry` | on/off | L26 |
| `stop_above_ob_open` | on/off | L26 |
| `be_after_25pct_target` | on/off | L26 |
| `fvg_quadrant_grade` | on/off | L27 |
| `scale_in_ce_lowerq` | on/off | L27 |
| `premarket_org_shrink_filter` | on/off | L27 |
| `opening_range_sd_projection` | on/off | L27 |
| `fvg_entry_c3_plus1tick` | on/off | L28 |
| `fvg_far_half_open_filter` | on/off | L28 |
| `min_range_20_handles` | on/off | L28, L29, L31 |
| `org_midgap_model` | on/off (min ORG 40) | L29 |
| `pre_fomc_mohawk_entry` | on/off | L29 |
| `large_org_wait_initial_high` | on/off | L31 |
| `stacked_fvg_higher_first` | on/off | L31, L38 |
| `prev_day_fpfvg_priority` / `fpfvg_extend_3d` | on/off | L32 |
| `ce_single_touch_filter` | on/off | L33 |
| `both_sides_then_fvg` | on/off | L33 |
| `seek_destroy_filter` | on/off | L35 |
| `partial_at_wick_ce_before_target` | on/off | L35 |
| `hrlr_classifier` | on/off | L36 |
| `hrlr_stop_2x_fvg` / `lrlr_stop_ce_plus1` | on/off | L36 |
| `fed_speech_window_block` | on/off | L37 |
| `decoupled_index_filter` | on/off | L37 |
| `reentry_new_candle_only` | on/off | L37 |
| `indigo_entry` | on/off | L38 |
| `scale_out_per_swing_break` | on/off | L38 |
| `measuring_gap_projection` | on/off | L38 |

Per-lecture switch ideas and every [conflict check] are in each note's "Open questions" section.

## Part E. Questions for Mase

1. The 2024 series is taught to a beginner (Caleb). Keep it below the 2023 Mentorship (current
   default), with "for Caleb" rules as beginner switches only?
2. "Problem day" / sloppy-day rules (L07, L10) are discretionary, like owner #10 (pending). Want a
   measurable proxy (ours) for a switch, or leave them out?
3. Several entries are shown on the 15-second chart (IOFED, price delivery continuum, L07-L13).
   Same question as the TE draft: skip sub-minute rules, or buy 15s data later?
4. Asia NDOG protocol (L05): test it as a switch even though Asia is skipped by default?
5. NDOG/NWOG lifetimes (5 days / 5 weeks) are ICT's "baseline for beginners" here; keep the
   rulebook's 60 days as the experienced default?
