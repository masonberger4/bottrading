# te58 Case Study With NonFarm Payroll & NQ Futures \ 2026-08-07 (hIusATccCcM)
Recorded 2026-08-07 (NFP Friday) / NQ 1m review / 58 min upload, ~14 min speech. Captions only.
Source tier: Trade Executions (2026). 2023 Mentorship wins on conflicts. NQ points.

## Summary
NFP-day case study: define the pre-news dealing range = highest high / lowest low from 07:00 to 08:29 (premarket). Price respected BISI/SIBI gaps whose edges align with gradient levels (quadrants/octants) of that range; long at the CE of a BISI before 8:30, partial just above halfway to the target (29,780 level tweeted Wednesday), then the 08:50-09:10 macro reached -2.0 SD of the pre-news range and reversed (NFP is a two-stage delivery like FOMC). Bearish iFVG and a balanced price range confirm the reversal. Paper trade, 3 contracts.

## Rules
- New/inexperienced traders should not trade Thursday/Friday of the first week of the month (NFP) ~0:00-0:32
- On high-impact 8:30 news days, define the dealing range from 07:00 to 08:29 (highest high, lowest low) before the release ~1:35-3:21
- A small "mohawk" outside a BISI is permissible; bodies must not close beyond it ~3:21-3:44
- Qualify gaps by their alignment with key levels / gradients (quadrants, octants 0.125-0.875) of the dealing range ~3:44-4:35, ~11:28-12:26
- Bodies holding above the CE of a BISI = bullish ~4:35-5:01
- Take the first partial just above halfway (in the premium half) between entry and the draw ~7:17-8:11
- Project standard deviations of the 07:00-08:29 range; -2.0 SD reached at the 08:50-09:10 macro = potential reversal ~8:46-10:32
- NFP is often a two-stage delivery (like FOMC): first run, then reverse for the stops ~10:32-10:55
- Suspension block (bullish) traded through = bearish inversion FVG ~5:57-6:20
- Balanced price range = BISI and SIBI sharing the same range; use the highest high and lowest low of the two ~6:20-6:45
- After the turn, re-anchor the fib on the new dealing range for PD arrays; gaps qualified by octants; institutional order flow entry drill ~10:55-12:26

## Trade examples
- NQ 2026-08-07 NFP: long at BISI CE pre-8:30, partial above 50%, 29,780 hit; 08:50 macro -2 SD reversal into balanced price range ~0:00-13:14

## Definitions
- Octants: 1/8 gradient levels of a dealing range (0.125...0.875)
- Suspension block: (ICT term, not defined here) a block that price later inverts
- Balanced price range: overlapping BISI and SIBI

## Open questions
- 07:00-08:29 pre-news range + SD projection: switch `prenews_range_sd` [new]
- Octant/quadrant gradients to qualify gaps: switch `gap_gradient_qualifier` [new]
- Partial just above 50% of the way to target: switch
- NFP trading [conflict check with rulebook NFP rules]
