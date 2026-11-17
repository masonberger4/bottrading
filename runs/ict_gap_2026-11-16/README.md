# Why the engine loses while ICT looks profitable, and what to do next (2026-11-16)

Asked by Mase. Analysis and options only: no engine code, default or data changed. Built from the existing results
(`runs/bt/RESULTS_2026-11-16.md`, `RESULTS_1m_2026-11-16.md`, `runs/ict_replication_2026-11-13`, and on `mentorship`
`runs/ict_replication_2026-11-16`), the notes and digests, and the conflict scorecard. One new number is computed here
(section 2, point 4) from `compare_ob.csv`.

## Short answer

1. We are not comparing like with like. The engine has a measured record: 4,908 trades, -0.13 R a trade. ICT has no
   measured record, only a set of trades he chose to show.
2. The part of his trading that the videos show working is the part he does by eye: which way, which day, which moment.
   The part we could code (sweep, shift, gap, order block, time windows) has no edge by itself on 2019-26 data.
3. So more switches on the current engine will not fix it. The next step should measure whether his direction calls
   carry any information at all, before anything else is built.

## 1. Is ICT's success something we can match?

- **The sample is selected.** About 220 videos gave 42 dated trades with prices. 41 of them made money, one clear loss
  (E22). Nobody wins 41 of 42. These are the trades he chose to show, so they say what a good trade of his looks like,
  not how often it happens.
- **Much of it is not real money.** The notes record TradingView "Paper Trading" as the account on several 2023
  trades (for example Jan 6, Jan 24, Jun 2 2023). A few clips show an "AMP Live" connection. There is no statement,
  no full trade log and no audited record anywhere in the corpus. Paper fills also have no queue and no slippage,
  which matters with 2 to 4 point stops.
- **The prices are real.** 38 of 40 priced entries trade at his price in his minutes on our data. So the trades shown
  happened as shown. What cannot be checked is everything not shown.
- **His rules and his trades disagree.** Our weekly rule, taken from his words, would have kept him out of 35 of his
  own 41 trades. He traded NFP, FOMC, holiday weeks and the PM after the AM delivered, all of which he tells
  students to skip. The scorecard has 68 cards where he states two or more positions.

Honest reading: his teaching is a vocabulary and a set of habits, not a tested system. "Matching ICT's success" has
no number to match.

## 2. Where the engine differs from what he does

| | ICT on screen | Engine | Evidence |
|---|---|---|---|
| Direction | Top-down read done by eye: weekly and daily draw, order flow, "narrative". If both sides can be framed he skips. | Locked draw plus bias columns, computed mechanically. | Engine entries show no move in the trade's direction 5 to 60 min later. Free running it takes his trade on 15 of 41 and the opposite trade in the same window on 13. |
| Which days | Trades when the picture is clear, skips the rest, and does not show the skips or the losers. | Trades every day the filters allow. | 2 to 11 trades a day when opened up; he shows about 1 dated trade every 5 videos. |
| Moment and entry | Watches the tape on 15 s to 1 m charts, enters after he sees the reaction, re-enters after a stop. | Resting limit at the order block before the break (80% of trades), or an FVG after the shift. | Limits get filled when price is running through them: 31% of 1m trades are stopped inside 5 minutes (AM 55%). |
| Time of day | 20 of 41 in the AM, 7 PM, 6 before 09:30, 4 at lunch. | About half the trades are lunch. | Replication check 11-13. |
| Market | NQ in almost every live video since mid-2023. | Defaults trade ES. | NQ alone loses too. |
| Management | Pyramids up to 30 lots, scales out at each level, trails. | One entry, fixed rungs. | Not scored. |
| Costs | Paper or unknown. | 0.04 to 0.10 R a trade. | Entry study. |

Four points matter most:

1. **Direction is the gap.** Told his side and time, the engine finds 20 of 41 entries. Left alone it cannot pick the
   side. The bias inputs he lists (seasonals, COT, sentiment, "obvious" arrays, weekly profile) are marked in our own
   digest as too discretionary to code, and the ones we did code (DXY, bonds, premium / discount, reaction bias) show
   no edge.
2. **Selection.** A discretionary trader who waits for the clearest one day in five, and shows the best of those,
   will always look better than a rule that must act on every day.
3. **Our choices.** Defaults were set by video count across 68 conflicts, with 20 ties decided by hand. That picks
   what he says most often, which section 1 shows is not what he does. This is a fair source of mismatch but not of
   the loss: no combination of switches tested is positive in either half.
4. **Even his winning days do not rescue the entry.** New number: in the entry test (his day, his side, his window),
   the engine's 40 fills that match his 20 trades won 16 times and summed to -5.1 R. Its stops there are about the
   same size as his (ES median 2.5 points vs his 3.5). So on days we know went his way, the mechanical entry still
   gets stopped first. The skill is in the timing inside the move, which is the least codable part.

## 3. Options, ranked by expected value for the cost

**A. Test direction alone (recommended first; about a day, cloud, no engine change).**
For every day 2019-26, score each codable ICT bias (daily draw, order flow on the daily, premium / discount, weekly
direction, midnight and 08:30 open rules) against what price did next (09:30 to 11:30 and to the close). Choose on
2019-22, check on 2023-26. Also score them against his 41 sides.
If none beats 50% by a margin that survives the second half, no entry model built on them can work, and that closes
the fully automatic ICT route cheaply. If one does, it becomes the filter everything else hangs on.

**B. Measure his calls made before the fact (about 2 to 3 days of transcript work, cloud, captions already
downloaded).**
The one thing in the videos that is not hindsight: sessions where he states a bias or a target before the move (live
commentary, weekend outlooks, the 2025 Lectures and 2026 SMC live sessions, which are not in the 42 yet). Log every
dated call, including days he says no trade and days he is wrong, then check each against the data.
This gives the first honest hit rate for ICT himself. If it is near 50%, stop. If it is clearly higher, we have a
labelled set of a few hundred days for option C.

**C. Learn his day and side selection (only if B gives a good hit rate and enough days; about a week).**
Fit a small model: which codable features separate the days and sides he chose from the ones he passed on. Test it
on the market, not on his trades. 41 trades is far too few for this; it needs B's larger set. Main risk is
overfitting.

**D. Narrow engine built only from what he does live (about 2 to 3 days; only worth it after A or B finds
direction).**
NQ, 09:30 to 11:30, sweep then shift then 1m gap, entry on the reaction instead of a resting limit, no lunch, no
order-block-before-break entry. By itself this is low value: each of these pieces has already been run and loses
(AM on 1m: -0.21 R). It is the right shell if a direction filter turns up.

**E. Stop the "code the whole rulebook" route and redirect (no cost).**
Two ways: (1) treat ICT ideas as single testable effects and keep only what shows up on its own, the way the
overnight-gap scalp did (weak: +0.45 R on 76 trades, +0.21 R in 2023-26); or (2) pause the ICT track. This is the
fallback if A and B both come back empty.

**Not recommended:** more stop, target or filter switches on the current engine (tested widely, nothing positive in
either half), and Mase supplying the daily direction by hand to the bot (point 4 above: even with the right side the
entries net a loss).

## Suggested order

A, then B. Decide after those two: C and D if either finds direction, E if neither does. Total before the decision
point: about 3 to 4 days of cloud work, no purchases, no laptop time.

## Caveats

- 41 trades on 33 days, 2023-24, mostly ES. Small.
- The -5.1 R figure counts every engine fill that matched one of his trades in the entry test (`compare_ob.csv`,
  starred fills, duplicates removed); several of his trades have more than one matching fill.
- Nothing here proves ICT is unprofitable. It shows his results cannot be verified from the videos and that the
  codable part of the method has not shown an edge.
