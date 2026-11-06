# 2024 Mentorship Lecture 32 (Vo8WKYKtzIU): "CFDs vs futures": small ORG (20 handles) + Friday + after a large range day = hard AM; under 40 handles use other tools or wait for the 10:00 Silver Bullet; extend the previous day's first presented FVG (3-day life), open inside it = it rules the day; short at its high after its CE and a breakaway gap
Recorded Fri Sep 20 2024 after the AM session (review of ~09:29-11:00 ET), MNQ (Dec), US100 CFD comparison, 1m. ~1h09m (CFD legality, prop-firm gambling, influencers; skipped). Captions only.
Source tier: 2024 Mentorship. Live trade this morning (recording shown): MNQ short entered at the high of Thursday's first presented FVG, exit at a discount wick CE ~19,993.75.

## Summary
Friday after a large range day (FOMC follow-through Thursday), with a limp 20-handle discount ORG (settlement ~20,055, open ~20,035 MNQ). ICT stacks the factors: small gap, Friday, large range yesterday = the AM is more challenging for a new trader; stick to time (macros). His threshold: under 40 handles he uses other tools or waits until 10:00 and trades the Silver Bullet. The key lesson: extend each day's first presented FVG (09:31-10:00) to the right; its life cycle is about three days. Today opened inside Thursday's FPFVG, so that gap (not today's small first gap, formed in "time distortion") was the one the algorithm used: price traded both sides of the ORG, hit the CE of Thursday's FPFVG, left a breakaway gap, and he shorted at the high of Thursday's FPFVG, exiting at a discount wick's CE. Late in the day price returned to the first FVG ("true value on the daily range unless it's a trending day").

## Rules
- STACKED HIGH-RESISTANCE FACTORS: small ORG (~20 handles) + Friday + large range day yesterday = AM session harder; stick to time and macros (when volatility is high the macro times aren't required) ~13:00-15:00, ~28:00
- ORG THRESHOLD (adds to ORG-SIZE): "I don't really like less than 40 handles"; under 40 he uses other tools or opts out and waits until 10:00 for the Silver Bullet ~20:00
  - Estimate at 09:29 whether the gap will be wide ~20:00
  - Small ORG = expect them to work both sides of it back and forth ~17:00, ~26:00-27:00
- FIRST PRESENTED FVG (09:31-10:00) LIFE CYCLE (adds to FPFVG-DEF, GAP-LIFE): extend it right; it stays relevant about 3 days (sometimes weeks) ~16:00-19:00
  - If 09:30 opens inside yesterday's FPFVG, that gap governs today; today's first gap (in time distortion) may be unimportant until later ~20:00-25:00
  - Grade it (high, upper quadrant, CE, lower quadrant, low); bearish = once below, it should not return to the upper half ~47:00-48:00
  - Late in the day price returns to the first presented FVG = true value of the daily range, unless it is a trending day ~1:03
- ENTRY (live): after price hit the CE of yesterday's FPFVG and left a breakaway gap below it, short at the high of yesterday's FPFVG ~51:00-52:00
  - Not a breakout trader: don't short the break below; use the gap ~47:00
- EXIT: the CE of a discount wick as the target ~1:02
- TGIF: Friday tends to retrace 20-30% of the weekly range ~31:00 (TGIF-DEPTH)
- CFD / forex charts: always include volume imbalances in the gap (broker pricing differs); futures can be read with or without them ~1:06
- Beginner blanket rules ("don't trade Mondays", "don't trade news") are for new students; experienced traders trade news after the report hits ~28:00-29:00

## Risk / Process [beginner]
- Micros: MNQ $2/handle, NQ $20/handle; funded-account oversizing is gambling ~5:00-7:00
- Journal: did the FPFVG from 2-3 days ago influence today? ~25:00

## Trade examples
- 2024-09-20 AM (live, MNQ): 20-handle discount ORG inside Thursday's FPFVG (09:38 candle on Sep 19); buy-side runs above the ORG high, back to the open twice; break below with a breakaway gap; short at the high of Thursday's FPFVG after its CE was hit; exit ~19,993.75 at a discount wick CE; afternoon rally back into Thursday's FPFVG.

## Definitions
- Breakaway gap: a gap left as price leaves a reference FVG, not revisited.
- Time distortion: the first minutes after the open when price works both sides of a small ORG.

## Open questions / conflict checks
- [conflict check] Under 40 handles = other tools or wait for the 10:00 Silver Bullet: ORG-SIZE card (Silver Bullet itself stays off by owner directive).
- [conflict check] FPFVG relevance ~3 days, extend previous days': GAP-LIFE card.
- [conflict check] Macro times not required in high volatility: MACRO-GRID card.
- [new] `prev_day_fpfvg_priority` (opening inside yesterday's FPFVG makes it the day's reference); default off.
- [new] `fpfvg_extend_3d`; default off.
