# 2024 Mentorship Lecture 03 (ZkLc4-adodg): PM session on no-news days, New Day / New Week Opening Gaps as the draw
Live 2024-08-07 (Wed), ~13:45-15:00 ET, NQ, 1m. ~2h23m. Captions only.
Source tier: 2024 Mentorship. PM rules explicitly "not for Caleb" (he trades AM) = general/experienced content.

## Summary
If the economic calendar has no medium/high-impact news in the morning, the AM tends to be rangy with false breakouts; wait for the PM session, using a PM news driver (here the 13:00 bond auction). Introduces the New Day Opening Gap (NDOG) and New Week Opening Gap (NWOG) as the "black hole" draw that sits above relative equal highs/lows in importance. Live demo short (6 + 4 contracts) from a bearish OB that failed to reach an FVG's CE, into the London low, >100 handles.

## Rules
- NO-NEWS MORNING: if no medium- or high-impact news in the AM session (usually 08:30, sometimes 10:00), expect a lackluster, rangy, false-breakout day that pulls back into the previous day range; look to trade the PM instead ~4:00, ~1:20:00
  - "If there's no data medium impact or high impact in the morning session try to trade the afternoon session" ~1:20:00
  - Cleaner price after NY lunch; sweet spot usually forms 13:30-14:30 ~1:20:00
  - PM structure: be at the charts at 13:30; if nothing 13:30-14:00, PM Silver Bullet 14:00-15:00; if missed, 15:00 to close ~1:26:00
- BOND AUCTION (13:00, medium impact) is a usable PM driver ONLY on days with no morning news ~1:08:30-1:10:00
- Midnight NY = start of the "true day"; algorithm refers to everything since midnight for liquidity/inefficiencies ~16:30
- NEW DAY OPENING GAP (indices): every day except Friday, the 16:59 1m close (17:00 stop) to the 18:00 first 1m open. High = higher of the two, low = lower ~18:00-23:00
  - It belongs to the NEXT day's trading (Tuesday's gap is for Wednesday) ~21:00, ~27:30
  - Life cycle: 5 TRADING days (holiday: skip and add a day); keep 5 on the chart ~23:00-24:00, ~35:30
  - Levels: high, low, consequent encroachment (midpoint); also quadrants 0.25 / 0.75 ~31:00-33:00
  - Not "done" after being filled/traded to; still valid for its life cycle ~35:00
  - ICT personally: logs every NDOG (high, low, CE, date) in a notebook and looks at any within ~150 handles; uses some up to 9 months old when in the narrative (experience) ~25:00, ~36:30
- NEW WEEK OPENING GAP: Friday 17:00 close to Sunday 18:00 open; keep 5 weeks ("general rule"; they work 6-9 months back) ~28:00
  - NWOG > NDOG for swing trades ~44:30
- CE is not equilibrium: CE = midpoint of a gap/inefficiency; equilibrium = midpoint of a delivered trading range ~31:00
- FVG half rule: best SHORTS form in the LOWER half of a SIBI (upper half left open); best LONGS in the UPPER half of a BISI (lower half left open) → breakaway gap → expect large range expansion ~33:30-34:30
- CLUSTER RULE: if most of the last 5 NDOGs (and NWOGs) are above price → expect price to gravitate there; below → down ~38:00-43:00
  - If anticipating a short with gaps above: give the first 30 min (after 07:00/08:00/09:00) a chance to spike up into them, then wait for MSS / breaker / iFVG ~43:00
  - A gap traded into only once is "hot"; very likely revisited ~48:00
  - Not a hard filter on direction: if looking for a long with gaps below, first see if they drop it there ~47:30
- "Engineering liquidity": with an NDOG draw below, relative equal highs formed after 07:00 → expect them run (Judas) before the drop; don't chase the drop ~51:00-56:00
- Draw hierarchy: NDOG/NWOG and relative equal highs/lows > inefficiencies (FVGs) ~1:54:00
- Sell-side delivery vs sell-side liquidity: an FVG has one-sided delivery; resting stops at lows are real liquidity ~1:55:00
- Holding longer: needs a draw beyond the normal range; "to get 10 handles I look for something that can give me 15-20" ~1:26:00
  - NQ size grades: < 50 handles = scout; intermediate swing = 50+; larger = 100+ ~1:12:00
- [beginner] Can't hold yet: partial below the short-term low, close the rest at the London low, tape-read the remainder and journal doubts ~1:40:00
- Before a news release: if price is already displacing toward the liquidity, trade ahead of the news ~1:36:00
- ENTRY (bearish OB that fails CE): price trades up toward an FVG but can't reach its CE and closes → that candle is a bearish OB; enter short when a later candle returns to the candle's low/body bottom ~1:44:00-1:46:00
  - If the candle HAD touched CE: wait for a trade into the upper part of the gap; stop above the CE of the higher FVG ~1:45:00, ~1:48:30
  - With two stacked FVGs, anticipate the higher one unless the lower one fails at CE ~1:47:30
  - Failing to reach CE = strength/weakness signature ~1:44:30, ~1:56:00
- SIX-AND-FOUR: 6 contracts first entry, 4 contracts pyramid; once the pullback fails to reach CE, stop to first entry minus 2 ticks ~1:50:30
- Mohawk = small overshoot outside an FVG, doesn't change anything ~1:52:00
- Model 2022 / OTE used for the post-news retracement ~1:52:30
- London low with relative equal lows (right low higher = high-probability) + day-session low + NDOG below = three draws stacking ~1:28:00, ~1:38:00
- 1m traders get trapped by a single up-close candle at news ~1:58:00

## Process ([beginner])
- Month 1 back-test/journal old data; month 2 tape-read live; month 3 executions ~2:16:00

## Trade examples
- 2024-08-07 NQ (demo): short 6 @ 18,321.25 (OB that failed the FVG CE, ~12:42-13:00), add 4 @ 18,291.25, all 10 off just below London low (~18,2x3); >100 handles on the main piece. Draw: London relative equal lows + NDOG below. Driver: 13:00 bond auction.

## Definitions
- NDOG, NWOG; CE vs equilibrium; breakaway gap (half of FVG left open)
- Engineering liquidity: relative equal highs/lows built against the larger draw

## Open questions / conflict checks
- [conflict check] NWOG kept 5 weeks here vs rulebook 60 trading days (experienced default from 2023 Ep 051). ICT also says they work 6-9 months → 2023 stays
- [conflict check] NDOG: rulebook "day gaps Mon-Thu 5pm-6pm"; life 5 trading days here
- [conflict check] No-news morning → trade PM (rulebook day selection)
- Switches: `no_am_news_trade_pm`, `bond_auction_pm_driver`, `ndog_cluster_bias`, `fvg_half_quality` (longs upper half / shorts lower half), `ob_fails_ce_entry`, `six_four_pyramid`, `ndog_life_days` (5)
