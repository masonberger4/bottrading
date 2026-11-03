# 2024 Mentorship Lecture 05 (ul6x6BwOg6M): Asian session NDOG protocol, measured-move targets, RTH gap 70% to mid-gap, TGIF 20-30%
Live 2024-08-09 (Fri), ~08:00-09:45 ET, NQ (+ES, YM glance), 1m / RTH vs ETH. ~1h44m (captions end ~1:43). Captions only.
Source tier: 2024 Mentorship. Asia protocol is "for those who can only trade the evening" (ICT's least favourite session). Announced turtle soup topic was not reached.

## Summary
Reviews ICT's Thursday-evening Asia trade (long 18,559.75 → exit 18,607.5) to give a step-by-step Asia protocol around the 18:00 NDOG: wait for price to leave the gap, take a short-term high, cross back through the gap, take a short-term low → "initial buy-side / sell-side liquidity" set; at 19:00 the retrace into the gap is the trigger. Targets from a measured move of the prior leg (1.0 and 1.5 SD; exit between). Then: London opening range 00:00-00:30, RTH opening gap (16:15 close → 09:30 open) returns to mid-gap ~70% of the time, Friday "TGIF" retrace 20-30% of the weekly range, SMT use (ES vs NQ; Dow only as a caution).

## Rules
- Annotations are for learning; experienced: keep levels on a notepad, chart naked (annotations make you stubborn) ~13:00-17:00
- Weakness signature: in a short, an FVG that price can't even trade to the CE of → expect decisive one-sided move; take the next bearish OB / 15s FVG ~16:30
- Primary bias factors: NWOG and NDOG; bias can be per hour, per session (~3 h), per AM (to noon), per daily range ~18:00
- NDOG CE: annotate if the gap > 20 handles; < 20 eyeball ~20:00, ~32:00
- ASIA PROTOCOL (18:00 NDOG; key window 19:00-21:00 NY) ~32:00-55:00:
  1. Don't trade at the 18:00 open; time must arrive first ~33:00
  2. Price must move away from the NDOG and take a short-term high (or low) ~40:00
  3. Then cross back over the NDOG and take a short-term low (or high) → "initial buy-side liquidity" and "initial sell-side liquidity" for the day are set; these become reference levels ("real support and resistance") ~41:00-46:00
  4. If price just dilly-dallies at 18:00 and doesn't do this → Asia will be dull; skip ~43:00
  5. At 19:00 (Asia key time) the retrace into the NDOG (touch of its high) is the trigger; prior displacement before 19:00 away from the initial sell-side = signature ~46:00-48:00, ~54:00
  6. Entry: below the BODY of the down-close candle (bullish OB) in its discount wick; ICT filled 18,559.75 vs candle close 18,560 ~52:30-54:00
  7. Stop: below the CE of the NDOG; once the relative equal high is taken, stop to break-even, minimum the NDOG high; don't rush the stop ~54:00-55:00
  - Best if the breakaway BISI is NOT revisited at all; a revisit = move deferred, expect chop ~56:00
  - Want "speed and magnitude" through the buy-side ("nitrous") vs a turtle-soup fake-out ~51:00
- TARGETING (measured move): take the leg before the run (high to low), project 1.0 (= full measured move, "low-hanging fruit / no-brainer exit") and 1.5 SD; ICT exits in the "gray area" between 1.0 and 1.5 (ICT ~1.05; exit 18,607.5) ~57:30-1:04:00
  - Measured move target must coincide with running an old high / relative equal highs ~1:04:00
- Bull-flag consolidation after a run is often fake ~1:08:00
- LONDON OPENING RANGE = 00:00-00:30 NY (extend forward; price refers back to it); London delineation 02:00 ~1:07:30, ~1:14:00
- Many good setups form around previous day high/low ~1:15:00
- After missing a reaction: wait for an FVG/VI retest, short there targeting relative equal lows ~1:16:30
- Take ONE good setup then stop ~1:20:30
- RTH vs ETH: switch to regular-trading-hours chart for the 09:30 hour; RTH close = 16:15, open 09:30; this gap is the opening range gap ~1:21:00-1:24:00
- Opening range 09:30-10:00 sets initial buy-side/sell-side like the NDOG protocol; "no 15-minute opening range" ~1:23:00
- RTH GAP RULE: after a large gap (down), even if bearish later, ~70% chance price trades back to MID-GAP (CE) — "there's always a trade available" ~1:25:30
  - Partial closure: price may stop at the initial sell-side reference (from the NDOG protocol) instead of full closure ~1:24:00
- No-news mornings can be aimless/choppy (confirmed) ~1:35:00
- TGIF: after a big one-sided week, Friday tends to retrace 20-30% of the week's range (some rules allow 40%, not taught); shorts can target the 30% level; then often dies out ~1:36:30-1:38:30
- SMT: if long and NQ makes a higher high but ES doesn't → take a partial (more valid); Dow divergence alone → caution only, not a full close; Dow not traded ~1:41:00-1:42:00
- Smooth relative equal highs on ES/YM → expect disruption before any drop ~1:40:00, ~1:42:30
- Risk-off environment (geopolitics): don't hold overnight, don't trade large, fewer trades ~1:36:00

## Trade examples
- 2024-08-08 evening Asia NQ (live with Caleb): long 18,559.75 (bullish OB at 19:00 retrace into NDOG), stop below NDOG CE → BE after relative equal high taken, exit 18,607.5 (between 1.0 and 1.5 SD measured move).
- 2024-08-09 RTH: gap down, price returned to mid-gap then the initial sell-side reference.

## Definitions
- Initial buy-side / sell-side liquidity (first short-term high/low taken around the NDOG after 18:00)
- Measured move; low-hanging-fruit exit
- TGIF (Thank God It's Friday) retracement

## Open questions / conflict checks
- [conflict check] Asia trading vs rulebook default skip (TE te70 also flagged this)
- [conflict check] RTH gap close = 16:15 (rulebook: ES 16:15 ✓; NQ?) and 70% mid-gap stat vs TE te64 "ORG CE by 10:00 ~70%"
- [conflict check] TGIF 20-30% vs rulebook tgif_exits "066" default
- [conflict check] SMT partial rule (NQ HH, ES no HH → partial) vs rulebook "SMT is a qualifier only"
- Switches: `asia_ndog_protocol`, `measured_move_exit` (1.0 / between 1.0-1.5 / 1.5), `org_midgap_target`, `tgif_retrace_pct` (20/30), `smt_partial_es_nq`, `london_or_0000_0030`
