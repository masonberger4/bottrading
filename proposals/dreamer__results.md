<!-- proposal by dreamer at 2026-11-11 06:05:48Z; target: results.md; reason: R3 low-trade-count funnel result; link: cmsg_01FAHERC1Lsrg2bYtrKuRHmPCoYsVpFPbTi5peiLE5YCeq; status: open -->
EXACT TEXT for results.md, new section at end:

## Low trade count funnel (2026-11-11, PR #66, fixed-roll data, 2019-26, $ at $1k risk)
- Defaults: 166 trades, -$490. The "done for the week" rule blocks 1,378 of 2,147 sessions (64%). It stops the week once last week's high, last week's low or the middle of the new-week opening gap is reached, and that gap is only about 5 points, so one of the three is hit on Monday in 383 of 406 weeks.
- ICT's version (videos 038 and 101) is one called weekly target in the week's direction, and which level counts was never defined, so the engine's version is stricter than his (our interpretation).
- With the rule off: 899 trades, -$2,106 (2024 alone -$12,844). By setup: PM Silver Bullet -$8.8k, AM -$5.2k, lunch +$5.8k, last hour +$3.1k. 1,524 AM sessions are open but only 132 get an AM trade; most trades are lunch trades (515 of 899).
- Proposed next steps (Mase's call): screen the rule counting only the nearest of last week's high or low (the option already exists in the engine), and find out why the PM Silver Bullet and AM setups lose.
