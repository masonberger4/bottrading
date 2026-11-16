<!-- proposal by dreamer at 2026-11-13 06:06:04Z; target: results.md; reason: Q2 results 11-12/13 (replaces unapproved R3); link: cmsg_01FAHERC1Lsrg2bYtrKuRHmP2uMud85T9vhdUjLTfMciK8; status: merged -->
EXACT TEXT for results.md, new sections at end:

## Low trade count funnel (2026-11-11, PR #66, fixed-roll data, ES 5m, 2019-26)
- Defaults: 166 trades, -$490. The "done for the week" rule blocks 1,378 of 2,147 sessions (64%). It stops the week once last week's high, last week's low or the middle of the new-week opening gap is reached, and that gap is only about 5 points, so one of the three is hit on Monday in 383 of 406 weeks. ICT's version (videos 038 and 101) is one called weekly target, and which level counts was never defined, so the engine's version is stricter (our interpretation).
- With the rule off: 899 trades, -$2,106. By setup: PM Silver Bullet -$8.8k, AM -$5.2k, lunch +$5.8k, last hour +$3.1k.

## Weekly-rule variants (2026-11-12, PR #67, ES 5m)
| version | trades | total | 2019-22 | 2023-26 | max DD |
|---|---|---|---|---|---|
| defaults | 166 | -$490 | -$5.9k | +$5.4k | -$9.8k |
| weekly rule on last week's high/low only, AM and PM SB off | 276 | +$7.4k | +$3.8k | +$3.6k | -$11.0k |
| weekly rule off, AM and PM SB off | 664 | +$10.2k | +$9.0k | +$1.2k | -$16.5k |
The setups were switched off in the test script, not in the engine (this also removed the 11 release_ob trades). No defaults changed.

## Three-market baselines (2026-11-13, PR #71, cloud runner, 2019-26)
| variant | ES | NQ | YM | all three |
|---|---|---|---|---|
| defaults | -$0.5k | -$4.3k | -$3.8k | -$8.6k |
| week rule high/low only | +$4.4k | -$8.4k | -$13.6k | -$17.6k |
| same, AM and PM SB off | +$7.4k | -$6.1k | -$8.2k | -$6.9k |
| week rule off | -$2.2k | -$38.4k | -$49.2k | -$89.7k |
| week rule off, AM and PM SB off | +$10.2k | -$28.7k | -$37.1k | -$55.6k |
- Lunch: +$5.8k on ES, -$24.8k on NQ, -$34.5k on YM.
- Of 512 filter combinations on ES, none beats a random day filter, and of the 10 best on 2019-22, 8 lose in 2023-26.
- SIZING CAVEAT: "$1k risk" is not real. The engine caps a position at $400k, so the median trade risks about $340-490. Per unit of risk, the +$10.2k ES variant is slightly negative.

## Engine vs ICT's own video trades (2026-11-13, PR #69)
- 42 dated ICT trades (25 ES, 17 NQ, 2023-26). 38 of the 40 with a readable entry price match our data at his price in his stated minutes; 1 miss is a roll difference (2023-12-08).
- The engine took 0 of 41 under the defaults (the weekly rule had closed the week on 35; holiday-week, holiday-eve, Fed-chair and chop filters stopped the rest) and 4 with the day filters off, with 1 true match (the 2023-05-22 Silver Bullet short).
- Main gaps: the engine never enters on a fair value gap (about half of ICT's entries are a 1-minute gap after a sweep and shift); half the engine's trades are at lunch (ICT: 4 of 41); the afternoon closes once the morning target is hit; big-gap and news rules block mornings he traded; the defaults trade ES only, while he trades NQ in nearly every video from mid-2023. The report lists 7 switches to test, with the 1-minute gap entry and the weekly rule first.
