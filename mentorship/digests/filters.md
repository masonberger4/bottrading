# Digest: filters (which days and sessions to trade or skip)

Source: all 218 notes in `mentorship/notes/` plus `mentorship_rules.md`, `mentorship/strategy.py` and `mentorship/levels.py`. Times are New York. Citations are `note-id ~mm:ss`. `[2023]` = 2023 playlist (001-105), `[CC]` = Core Content 2016-17, `[both]` = both. `[chart]` = only on charts. `[fx-only]` / `[bonds-only]` = does not transfer to index futures. "needs data: X" = the bot has no feed for X today.

## 1. Rules

### 1.1 Scheduled news

**NFP (Employment Situation)**
- NFP Friday: no live trading. New traders never trade it, and nobody trades the first hour after 08:30. Experienced traders wait out the initial volatility, then trade toward the daily draw. It is one of his two weakest days of the month (with NFP Thursday) (006 ~8:35; 061 ~2:49:35; 078 ~1:10:05; 101 ~25:12; 105 ~11:50, ~1:19:00; cc08_001 ~6:37; cc08_006 ~4:45). [both]
- NFP week: trade Mon, Tue and Wed up to 11:00. No trades Wed PM, Thu or Fri. If nothing was taken by Wed 11:00, you are done for the week. He calls this a training-wheels rule; veterans may trade Thu/Fri (003 ~2:44; 038 ~8:05-9:15; 050 ~20:35; 101 ~25:12-39:39; 041 ~0:37 chart note "sloppy on NFP weeks Thurs & Fri"). [2023]
- Monday of NFP week is always a trading day, even when he would skip other Mondays (100 ~33:00; 101 ~30:41; 105 ~44:25). [2023]
- NFP profile: the side taken first after 08:30 is usually the false run, then the other side, then the real move (up-down-up, down-up-down, or chop). NFP runs both sides (073 ~10:42-11:41; 078 ~1:25:47). [2023]
- On NFP, CPI and FOMC days breakers give poorer rejections, and price may trade through them (073 ~4:36). [2023]
- Don't pyramid on NFP (105 ~9:13, ~35:10). [2023]

**FOMC (rate decision 14:00, press conference 14:30)**
- Don't trade the 14:00 release. 14:00-14:45 is observation only. The 14:00 move is usually fake and the real move starts 14:25-14:30 (003 ~4:02; 021 ~2:40-6:18, ~5:23-5:41; 065B ~5:30-5:43). [2023]
- After 14:45, or in the last hour, "the normal routine kicks in". Even that is a gamble if you can't read it (021 ~5:55, ~27:13). [2023]
- FOMC day AM may be traded if the trending-day recipe holds (§1.3). Never hold into the afternoon release (cc10_009 ~3:48-4:46; cc10_008 ~11:18). [CC]
- FOMC days are also listed flatly as "no setup, sit out, demo only" (cc08_001 ~6:37). [CC]
- If the only high-impact event is a 14:00 FOMC, expect AM consolidation and PM volatility (cc10_008 ~2:56). [CC]
- Day before FOMC: slow, mixed, imprecise trade. Lower expectations and be nimble (042 ~3:50, ~53:27). FOMC week before Wednesday: "fickle", no ES/NQ symmetry. Trade light with no max leverage; clean price returns Thu/Fri (094 ~1:48, ~6:47). [2023]
- Day after FOMC: sit still in the AM session (095 ~51:27). If the FOMC reaction whipsawed both ways, skip the next London open (cc08_006 ~3:36). [both]
- FOMC/NFP Thursday turtle soup: very small size, wait for the knee-jerk, limit below the Mon/Tue low (cc07_003 ~24:00). [CC]

**CPI**
- No position into the 08:30 release and none at it. Stops don't protect because liquidity is pulled (030 ~7:22, ~8:41; 047 ~5:26; 064 ~4:35, ~28:55; 065B ~4:07). [2023]
- CPI is grouped with FOMC/NFP as a no-trade event (021 ~17:37). After the print, trading into remaining liquidity is fine (028 ~3:40; 064 ~4:35). [2023]
- He leaves on CPI mornings at 09:45, so a whole-day skip is our reading (030 open question). [2023]
- Day before CPI: don't trade ahead of it. Expect a quiet "high resistance" day: small risk, bread-and-butter only, then stop (028 ~3:40; 029 ~5:22, ~1:03:57). [2023]

**Other news and events**
- Any high- or medium-impact release: wait at least 30 min after it, then trade only if there is ~10 handles of room (aim for 5) (065B ~5:46). [2023]
- On news, the first liquidity pool run is the losing side: sell-side swept first means the bigger move is to buy-side (064 ~52:12-1:09:53). [2023]
- 10:00 release (PMI etc.): wait for the release, not just the 09:30 open (002 ~0:25). Conflict: 049 shorted NQ at the 10:00 release (049 ~2:27). [2023]
- No 08:30 news ("soft bias" day): wait for 09:30 (007 ~11:14; 019 ~7:57). [2023]
- Two high-impact drivers in one session (e.g. 08:30 + 10:00): stand aside. Expect whipsaw both ways, and don't trade ahead of the second release (100 ~50:59-1:40:56). [2023]
- Ideal: exactly one high- or medium-impact release in the session. Multiple releases means avoid. No news means a "wildcard" day (cc08_006 ~5:59-7:32). [CC]
- Fed chair testimony or speech at 10:00: treat it like a rate decision. No AM trades, no bias, not even demo. Use the chart 5-15 min after it ends to frame the PM, which runs 13:30-16:00 (037 ~3:09-9:17; 038 ~39:59; 067 ~0:34, ~0:57:30). needs data: Fed-speaker calendar. [2023]
- Fed speakers make price wild (027 ~25:43). Monday before testimony days: small ranges, modest targets (036 ~13:30). [2023]
- Bond auctions: the day before can consolidate, and the auction-day AM usually does. Avoid the AM on auction days (cc10_008 ~7:29, ~11:07). needs data: Treasury auction calendar. [CC]
- War/geopolitical shocks: smallest leverage, always a stop, no home runs (092 ~55:59; 103 ~32:44; 102). He stood aside for the 2016 US election (cc04_002 ~23:03; cc04_003 ~32:02). [both]

### 1.2 Holidays, rolls, year turn
- Day before a long weekend or holiday (usually Fri, sometimes Thu): skip it, expect a quiet session. The same applies to US bank holidays and the day before them (cc08_006 ~5:06; cc10_008 ~6:54; cc10_019 ~15:02, ~23:29). [CC]
- Morning after a holiday (e.g. Tuesday after Labor Day): choppy, no bias, no trade. The PM or next day can be traded once ES/NQ move in step again (090 ~8:00, ~51:03-53:00). [2023]
- After a Monday holiday, Tuesday acts like Monday and Wednesday is the likely reversal day (cc09_008 ~55:24). [CC]
- Holiday weeks: the low-volume day distorts the week, so expect cleaner delivery Thu/Fri. This cuts against the NFP-week rule (072 ~3:36). [2023]
- Holiday-shortened Friday/Sunday: ignore that week's NWOG and use the nearest normal one (046 ~0:16; 048 ~2:54). [2023]
- Late December holiday range: trade turtle soups toward FVGs and equal highs/lows (cc04_012 ~7:01). [CC]
- Last trading day of the year: low volatility, expect an inside day; year end reprices to buy-side (001 ~17:01, ~31:47). First trading day of the year: don't rush (002 ~1:58). [2023]
- Rollover week (futures expiry) is more volatile and choppy (093 ~0:32). [2023]

### 1.3 Day type: consolidation vs trend
- Four states: expansion, retracement, reversal, consolidation. Consolidation means no trade; wait for the expansion out of it (cc01_001 ~2:05, ~4:29; cc01_002 ~17:26; cc09_003 ~1:51). [CC]
- Daily chart sideways for days (inside a daily range): expect intraday range-bound back-and-forth with ~5-handle runs. Be surgical, take one win and stop, or sit out (031 ~9:20, ~25:10; 043 ~6:51; 048 ~1:49:49). [2023]
- While price is inside a single daily BISI range where both cases are valid, don't trade that index (091 ~6:12). [2023]
- After a one-way multi-day run into a higher-TF premium array: sloppy session, trade less or not at all (044 ~1:14:47). [2023]
- NWOG regime: price keeps returning to the current week's NWOG = consolidation week, so scalp with small targets and no runners. Price leaves it sharply and doesn't return = trending week (025 ~3:11; 030 ~10:17; 039 ~12:26; 051 ~9:25-13:30). Converging NWOGs point to consolidation (051 ~11:10; 053 ~1:31). [2023]
- Large opening range gap, or a very large prior-day range: first 30-45 min choppy. Sacrifice the AM; 13:30-16:00 is better (033 ~13:27). [2023]
- Prior day's range > 2x the 5-day ADR: skip, expect chop (cc08_006 ~1:22, stated for London). [CC]
- After 3 consecutive up daily closes, no longs on the 4th day (mirror for shorts) (cc08_006 ~2:07). [CC]
- If the previous day did not reach the 5-day ADR, an expansion day (1.5-2x ADR) is due (cc08_006 ~23:33). [CC]
- Contraction precedes expansion:
  - Inside day means a large range the next day (012 ~16:17).
  - Inside week means a large range within 2 candles, else scalp only (103 ~12:53).
  - An inside bar or the smallest range of 3 or 7 days is a setup with no direction (cc06_007 ~21:24).
  - Small ranges precede large ones (cc09_007 ~21:22; cc10_008 ~12:46).
  [both]
- Trending-day recipe needs all three (cc10_009 ~1:17-2:46):
  1. Prior day(s) had small or contracting ranges.
  2. Price just traded into a daily discount/premium array.
  3. High/medium-impact US news at 08:30.
  [CC]
- Consolidation-day predictors (cc10_008 ~1:51-7:47):
  - No NY reports today, with reports later in the week.
  - Price meets a higher-TF PD array or the 50% of a higher-TF swing.
  - Holiday eve.
  - Auction day.
  Same idea: Mon/Tue with no news while the week's news is Wed-Fri (053 ~0:38); a small-range day before Wednesday news (046 ~4:41). [both]
- On a consolidation day (cc10_008 ~9:01-17:19):
  - AM scalps only, and only if the opening range is small.
  - Done by 11:00 (noon at the latest).
  - PM only if the AM has not yet run a stop pool.
  - Expect a trending day soon after.
  [CC]
- "Seek & Destroy" profile: whipsaw runs on both sides, then a reversal. Don't hold trades (024 ~13:57; 044 ~1:36:11). Seek & Destroy weeks (range Mon-Thu, Friday breaks out) come while awaiting rates/NFP and in July-August; avoid them (cc07_002 ~7:42; cc07_003 ~33:00). [both]
- Bonds in a range means every market consolidates; wait for a bond close outside the range (061 ~1:05:42; cc10_008 ~8:47). needs data: ZB daily. [both]
- Multi-asset decoupling: bonds, dollar, commodities and stocks out of sync means small, choppy moves. Size down or stand aside (098 ~55:10; cc10_019 ~4:13-25:03). needs data: DXY, ZB, CRB. [both]

### 1.4 Low-probability conditions (no-trade inside an otherwise valid day)
- 50/50: if you can frame both long and short, don't trade. High probability means the other side can't be argued (022 ~1:42:23; 025 ~11:18; 029 ~56:24; 038 ~48:33; 046 ~0:10:01; 095 ~27:33; 100 ~1:35:38; 101 ~40:33). [2023]
- No clear draw, no inefficiency, no displacement ("spotty" back-and-forth): no trade (045 ~31:22-40:49). Clustered volume imbalances ("porous" price) are low trust (027 ~27:38). [2023]
- ES/NQ/YM not symmetrical (decoupled) means high-resistance runs: patience, scalp only, smaller targets (046 ~1:06; 048 ~11:38; 045 ~1:01:43). SMT on both sides at once with no bias means "do not trade" (090 ~41:00). A trade in the stronger index when correlation is cracked: never at max risk (090 ~35:02). needs data: YM (or DIA). [2023]
- DXY gate: no ES longs while DXY rallies above its dealing-range high; the ES lower low should come with a DXY higher high (031 ~7:54-29:52; 036 ~59:00; 042 ~19:05; 045 ~42:05; 048 ~23:27; 095 ~26:17). needs data: DXY intraday. [2023]
- 10-handle framework: the setup must offer ~10 ES handles from entry to the draw while aiming to capture 5. Below that, observe only; experienced traders may take 5-handle moves (024 ~25:26; 046 ~0:32:40; 054 ~0:36; 058 ~37:16; 059 ~10:36; 060 ~50:00). [2023]
- If the macro window (09:50-10:10 or 10:50-11:10) produces no move toward the draw, close the charts for that session, maybe the day (073 ~30:51). [2023]
- Draw delivered before 09:30: expect a choppy 09:30 open and trade the PM (022 ~1:16:11). [2023]
- Daily objective done before lunch: skip, the lion's share is gone (015 ~16:22). [2023]
- Overnight range too narrow, or the sell-side raid before 09:30 too shallow: no AM trade (015 ~11:58). [2023]
- London already made ~80% of the 5-day ADR (or met it): skip NY (cc08_001 ~13:41). [CC]
- Mon-Wed made 30-50% of the weekly range. If you missed it, don't chase a Thu/Fri move (cc07_006 ~23:35-25:33). [CC]
- Once you see you are in chop, close the trade (022 ~1:52:44). Three PD arrays in a row failing means stop for the session (044 ~1:52:49). [2023]
- Higher-TF targets met (weekly objective delivered) means neutral: stop trading for the week, expect consolidation (038 ~6:33; 061 ~2:33:05; 062 ~11:18; 099 ~15:51; 101 ~34:21; cc10_019 ~15:47). Deep-discount target hit midweek: no heavy new shorts (099 ~15:51). [both]
- After a big draw is delivered and the next move is 50/50: drop the daily bias, wait for Monday, trade from Tuesday, intraday only (077 ~5:50-17:49; 084 ~1:04). [2023]
- Day trades not aligned with daily/weekly/monthly (minimum 4h) PD arrays are not high probability (cc07_007 ~26:34). [CC]
- Before a London trade: CBDR > 50 pips or Asian range > 40 pips, or a sustained trend from 20:00, means poor London (cc08_006 ~8:33-12:51; cc08_007 ~7:24). [CC] [fx-only thresholds]

### 1.5 Seasonal and calendar tendencies
- August is a choppy "meat grinder", especially its last two weeks. Trade small or stand aside; no funded challenges or max leverage; after an August drawdown restart in September (079 ~8:54-25:43; 081; 082 ~2:16; 084 ~2:03, ~28:06; 087 ~1:37). [2023]
- Index seasonal map from the Dow 20-yr seasonal, said to mirror the S&P (cc10_015 ~5:04; cc10_018 slide ~22:40) [CC]:

  | Month | Bias |
  |---|---|
  | Jan | bearish |
  | Feb | bullish |
  | Mar | consolidation |
  | Apr | bullish |
  | May | bearish |
  | Jun | consolidation, ending bearish |
  | Jul | bullish into the mid-year high |
  | Aug | consolidation |
  | Sep | first half bullish, second half bearish |
  | Oct | bullish (Q4 low, late Sep or Oct) |
  | Nov | bullish |
  | Dec | bullish |

  - Mar, Jun and Aug are low-probability months.
  - May-Oct is a "low magnitude" range period: use less leverage.
  - Focus on Feb-May and Oct to year end.
- Intramonth notes:
  - Mar is weak in weeks 2-3, then rallies into month end.
  - Apr is soft early, then rallies mid-to-late month.
  - May sells off into week 3 (cc10_015 ~12:40-15:10).
  - Favor shorts from May into the 1st-2nd week of June; longs from fall to year end and the first week of Feb (050 ~2:20).
  - ES weakness late Apr-May; strong low from the 3rd week of May to the 3rd week of June (074 ~16:54).
  [both]
- Seasonal swing windows: longs Feb-May and Oct-Jan (cc10_016 ~2:11); shorts Jan and May-Aug 1 (cc10_017 ~1:52); buy Feb-May, sell May to mid-Sep, buy mid-Sep/Oct to year end (cc10_018 ~22:25). [CC]
- A seasonal is a road map, never a trigger. Take it only when both seasonal lines (long and short sample) agree and the higher-TF trend already leans that way. A seasonal that fails to appear signals a strong move the other way (065B ~4:41; 074 ~49:22; cc05_010 ~1:10-9:59; cc05_011 ~4:01; cc10_003 ~3:03). [both]
- Quarterly shift: expect a major turn or consolidation every 3-4 months. Use it for bias and position sizing, not timing (cc05_001 ~5:05; cc05_002 ~3:52; cc10_001 ~20:51; cc11_003 ~0:44). [CC]
- Monthly bias routine: run it at the close of the last trading day of each month (cc12_001 ~1:45). [CC]
- No rule was found for month-end, quarter-end or year-end intraday behaviour, beyond the year-end and first-day items in §1.2.

### 1.6 Day of week and week templates
- Sunday open: don't trade it, and set no weekly bias before it. Write if/then gap scenarios and wait for Monday 09:30 (011 ~4:20; 028 ~1:16:09; 084 ~3:21; 102 ~16:20; 103 ~7:22). [2023]
- Mondays:
  - New students don't trade Mondays; study them (065B ~4:12).
  - Outside NFP and FOMC weeks he skips Monday (an accumulation day) unless the setup is obvious, or trades only the Monday PM (101 ~30:53).
  - Monday is typically small range (cc08_001 ~18:52).
  - He usually "lets Monday go" (cc12_003 ~15:40).
  - A big Monday range into a daily premium array is likely the high of the week (cc08_001 ~19:49).
  [both]
- Mon-Wed are the ideal days. The weekly high or low forms Mon-Wed ~70% of the time (cc07_008 ~1:35; cc08_007 ~7:17; cc08_008 ~11:07; cc09_007 ~22:37; cc07_001 ~42:34). Tue and Wed are best, Thu is good but can reverse (cc08_001 ~18:52-22:58). [CC]
- Thursday often makes the opposite end of the weekly range, especially after a one-sided week or once targets are met. Don't fight a sharp Thursday retrace (044 ~16:25; 060 ~1:11:50; 099 ~1:02:09; 100 ~8:24). A Thursday cross back through the weekly open against the bias marks a weekly reversal (cc08_001 ~24:20). [both]
- Friday:
  - Small range unless the weekly objective is unmet (cc08_001 ~18:52).
  - TGIF: after a trending week that reached a higher-TF array, Friday retraces 20-30% of the weekly range (066; 074 ~24:04; 075 ~1:40; 084 ~15:45; 089 ~0:41).
  - Take most profit at the first pool, because the higher-TF target may not come that day (070 ~1:06:37).
  - Friday after a week whose targets were all met: don't trade (100 ~7:05).
  - Don't buy Friday after a strong Thursday (cc09_008 ~41:53).
  - Friday after a trending week: chop and profit taking (cc04_011 ~17:59).
  - Friday after a strong one-sided (down) week: be nimble, expect a small daily range; he sat the day out (023 captions, added 2026-11-06). [2023] **New 2023 evidence**: the earlier 023 notes were chart-only.
  [both]
- No positions over the weekend or across 17:00-18:00. Late in the week, get flat rather than carry a net loss into the weekend (065A ~2:30:30; 101 ~4:27; 103 ~9:31; cc02_005 ~8:05). [both]
- Weekly open filter:
  - The Sunday 18:00 open (or Monday 00:00) is the weekly power-of-three reference. In a bearish week, sell each day while below it; in a bullish week, buy while above it, until an opposing daily PD array is hit (cc08_001 ~22:58-29:03; cc12_003 ~19:03).
  - Best longs below the Sunday open, best shorts above it (048 ~1:00:10).
  [both]

### 1.7 Session-level no-trade windows (filter side only; times belong to the sessions digest)
- Opening range 09:30-10:00: don't trade it; wait out the first 30 min. Take an earlier setup only if it is obvious (030 ~42:16, ~57:24; 031 ~4:52; 036 ~23:30; 042 ~4:29, ~24:45; 044 ~4:54; 065B ~4:53:40; 090 ~49:00; 092 ~1:45:24 "amateur hour"). Exception: price already deep in discount with aligned arrays (053 ~10:03). [2023]
- Skip lunch (new-student rule, 065B ~4:12). Scalps avoid 05:00-07:00 and the period after ~10:00 (cc09_006 ~6:46). [both]
- No setup by ~10 min before the close (15:50): no trade (001 ~1:00:45). Don't add to or fade an all-day move in the last ~15 min (026 ~1:59:50). [2023]
- If the AM wins, skip the PM (065B ~4:12). When the session objective hits, close everything and stop for the day (029 ~1:03:57). If the AM delivered the day's range, go flat before lunch and skip the PM (cc10_007 ~9:05). [both]
- Divided day: a bad AM means come back at 13:45; nothing by 14:30 means skip the PM and the last hour (044 ~1:55:03). [2023]

### 1.8 Frequency and stopping rules
- Goal: one good setup per week ("one shot one kill"), a couple per week at most from one model (003 ~1:05:10; 064 ~1:37:34; cc01_001 ~19:44; cc02_003 ~12:03; cc04_002 ~22:00). [both]
- About 3 trades per week (099 ~47:36). A few trades a month is enough (095 ~49:28). About 10 trades a month (cc02_004 ~14:58). [both]
- Silver Bullet: one AM trade per day (047 ~8:00). [2023]
- Day-trading model: ~2 setups per day (London and NY); scalps 2-3 per day, ~1 per session (cc08_001 ~1:30; cc09_006 ~3:54; cc09_007 ~3:20) [CC]. Don't trade every day; skipping days is part of the model (cc08_004 ~25:39; cc09_001 ~10:12; cc10_009 ~10:45; cc09_008 ~43:07). [CC]
- After a win:
  - Bread-and-butter 5 handles, then stop (046 ~4:41; 044 ~57:16).
  - In a choppy market, one win and stop (031 ~9:20).
  - Conflicted higher-TF picture: one entry, take the winner, stop for the session (091 ~10:44).
  - Out of sync with the market: stop after the first profit (081 ~18:58).
  - No re-entry after a winner on the day (095 ~47:08, stated for his son's micro account).
  [2023]
- After a loss:
  - Lose in the AM: don't reverse; stop for the morning and wait for the PM (001 ~46:57-48:43). [2023]
  - Re-entering the same idea is allowed if it has not unraveled, at half the previous risk; halve again after a second loss (cc02_005 ~3:18-14:18; cc06_003 ~23:24; 070 ~38:41; 060 ~1:22:30; 085 ~27:21). [both]
  - Never raise size to recover a loss. After a loss, halve size, win back 50%, then step back up (061 ~2:26:40; cc02_005 ~15:44). [both]
  - After a loss on the day, no max size (010 ~49:51). [2023]
  - If the planned buy is stopped, the stop-out is the signal: flip and look for the other side the next day (cc09_008 ~36:23). If stopped above the breaker high, the SMT is cancelled; switch to a long bias for the rest of the day (042 ~1:08:19). [both]
- Two consecutive failed with-trend signals warn that an intermediate shift is near (cc06_001 ~8:51). [CC]

## 2. Conflicts

1. **NFP Friday.**
   - A: no live trading (006; 061; 105; cc08_001; cc08_006; rules Ep 03/04).
   - B: he traded it live: 071 NQ PM all day; 088/089 NQ short 09:33 (~$15.4k); 105 ES long 45-60 s after 08:30 (as a demo for students); 078 commentary.
   - Count: A ~7 videos, B 4. His own executions follow B, but he labels each as an exception.
   - Bot default: skip NFP day (as now). Parameter to test: allow trades from 09:30 (or 10:00) on NFP day; 089's entry was after 09:30.
2. **NFP week Thu/Fri.**
   - A: no trades (003; 038; 050; 101).
   - B: he traded NFP Thursday (041 Mar 9 long; 050 May 4 four shorts, +$19.9k) and says veterans may (101).
   - Count: 4 vs 2. Examples follow B, with the caveat "sloppy".
   - Bot default: keep the block; test `nfp_thu=True` on its own.
   - Holiday weeks (072) argue for Thu/Fri; tag them.
3. **FOMC day.**
   - A: whole PM out (rules Ep 03 reading; cc10_008; cc10_009 "never in the afternoon").
   - B: only 14:00-14:45 out, normal routine after 14:45 (021). He traded NQ from ~14:25 (065B). A 097 short was open at 15:15.
   - C: whole day out (cc08_001).
   - D: AM allowed (cc10_009). The day before is slow (042); the day after AM is out (095).
   - Count: A 3, B 3, C 1. His examples follow B.
   - Bot default: keep the FOMC PM block (B's real move usually finishes by 14:45, as on 021) and keep the AM open (D). Test: allow entries from 14:45 or 15:00. Also add a day-after-FOMC AM skip.
4. **CPI day scope.**
   - A: only before/at the release is banned; trading after is fine (028; 064; 065B "wait 30 min").
   - B: CPI grouped with FOMC/NFP as no-trade (021). He never traded a CPI morning on stream.
   - Bot: AM entries start 09:30 > 08:30, so A is already met. Default: allow CPI days; test a `skip_cpi` switch. Test a day-before-CPI skip separately.
5. **Opening range 09:30-10:00.**
   - A: wait it out (030; 031; 036; 042; 044; 065B; 092; Silver Bullet starts 10:00).
   - B: entries in 09:30-10:00: Ep 07 (009) bought at 09:44; 006 at ~09:58; 007 at ~09:46; 034 at ~09:40; 088 at 09:33; 053 in the OR.
   - Count: A ~8 statements, B ~6 executions (mostly early 2023, before the "submit to 30 minutes" teaching).
   - Bot: `strategy.py` opens the AM window at 09:30. Default: keep 09:30 (the backtested AM model is the Ep 07 one). Parameter: `am=(600, 660)` to test the 10:00 start.
6. **Trading before 09:30.**
   - A: wait for 09:30 on no-news and soft-bias days (007; 019; 030).
   - B: he traded 09:21 (018), 07:00-08:30 (032 pre-market short on a choppy day), 07:00-09:00 "allowed" (022), 08:00 Ma Deuce before 08:30 news (091), 08:31 on NFP (105).
   - Bot: SPY has thin pre-market. Default: no pre-09:30 entries.
7. **Reversal after a loss.**
   - A: never reverse after an AM loss (001; rules).
   - B: an "offside" flip in the same minute (085 ~14:09; 083 short-to-long at 10:32; 094 reversed at his stop); 042 says switch bias after a stop. All are small, fast flips when price clearly runs the other way.
   - Count: 1 rule vs 4 examples.
   - Bot default: keep A (`lost_side`). Possible test: allow one opposite-side entry when the loss came from a stop beyond the breaker/sweep extreme.
8. **Monday.**
   - A: skip Mondays or trade only the PM (065B new students; 101; cc12_003; cc08_001 small range).
   - B: Monday of NFP or FOMC week is always traded (100; 101; 105). Many 2023 examples are Mondays: 007 Jan 9, 018/019 Jan 30, 036 Mar 6, 053 May 8, 069 Jun 26.
   - Bot default: trade Mondays. Test a `skip_monday` switch that exempts NFP/FOMC weeks.
9. **January seasonal.**
   - Bearish (cc10_015; cc10_018 slide; cc10_017 short month) vs part of the ideal long window Oct-Jan (cc10_016) and longs through the first week of Feb (050).
   - Bot: no month bias by default; tag the month and measure.
10. **Stop once targets are met vs hold.**
    - A: done once the target is hit (by 15:00 in 006; the session objective in 029; the weekly target in 038/101; done for the week in Ep 08).
    - B: trend profiles hold into 15:00-16:00 (cc10_014 ~3:01); 076 holds without partials.
    - Exit details belong to the exits digest. For filters: default to "one AM and one PM trade per day" (current) and test a "stop for the day after a winning AM" switch (065B).
11. **Frequency.**
    - "One setup per week" (003; cc02_003) vs "two per day" (cc08_001) vs "one AM trade a day" (047).
    - These are different models (weekly OSOK vs day trading). The bot's one-AM, one-PM cap matches the day-trading statements. Test a weekly cap (stop after N wins per week, or after the weekly draw is hit).
12. **News entry timing.**
    - Wait for the release and the real range (006; 002; 065B 30 min) vs enter at the release (049 at 10:00; 105 at 08:31).
    - Bot default: wait (AM starts 10:00 on 10:00-release days, as now).

## 3. Bot implications

What `strategy.py` does now:
- `blocked()`: NFP day; Thu/Fri of NFP week; Wed PM of NFP week; FOMC PM.
- `skip_news`: all 08:30/10:00 release days.
- AM entries start at 10:00 on 10:00-release days.
- One AM and one PM trade per day; no opposite-side trade after a loss.
- `day_type` / `news` tags are recorded.

The tables below say what to add or change. Each item should get a Params switch and a tag, so its effect can be measured; none should be hard-coded.

**Calendar filters (data already in `claude_hf/daytypes` + `mentorship/calendar`)**

| Switch | What it does | Source |
|---|---|---|
| `skip_cpi` | whole-day CPI skip | 021 |
| `skip_pre_cpi`, `skip_pre_fomc` | day before CPI/FOMC: skip, or cut size to 0.5 | 028; 029; 042 |
| `skip_post_fomc_am` | skip the AM after FOMC day | 095 |
| `fomc_pm_from` | test 14:45/15:00 instead of the full PM block | 021 |
| `skip_two_drivers` | an 08:30 and a 10:00 release on the same day; needs the 10:00 tags, which only exist for 2026, so extend `calendar.py` to 2019-2025 for ISM/JOLTS/sentiment | 100 |
| `skip_holiday_eve` | the trading day before a market holiday or long weekend | cc08_006; cc10_008 |
| `skip_post_holiday_am` | the AM after a holiday | 090 |

- Half-day sessions (e.g. day after Thanksgiving, Christmas Eve): flatten early. needs data: early-close list.
- `roll_week` and `opex` tags already exist; report results by tag (093 "choppier").
- August: tag first. Test `skip_august` or half size, possibly only from Aug 15 (079; 084).
- Month table (§1.5): tag each trade with the seasonal bias and compare long vs short expectancy by month before using it. Do not make it a hard filter: ICT says it fails without trend agreement.

**Day-of-week and weekly context (computable from bars)**
- Tag the weekday. Test `skip_monday`, exempting NFP and FOMC weeks.
- NFP week Thursday: keep blocked; test it separately.
- Weekly open: compute the Monday 00:00 open (SPY: Monday's first pre-market bar, as `levels.opens` does for midnight) and, for ES, the Sunday 18:00 open.
  - Test the filter: longs only above it, shorts only below it, until a daily PD array is hit (cc08_001). This mirrors the existing midnight-open `use_bias`.
- TGIF: on Fridays tag whether price is in the 20-30% retrace zone of the week. As a filter: Friday, after a week with range > k x average weekly range, allow only counter-week-direction trades, or skip.

**Day-type filters (computable from daily bars)**
- `adr5`: 5-day average daily range.
  - Skip the day if yesterday's range > 2x `adr5` (cc08_006).
  - Tag "expansion due" when yesterday's range < `adr5`.
- Inside day / inside week, and the smallest range of 3 or 7 days: tag them, and test "trade only the day after contraction" (012; 103; cc06_007; cc10_009).
- Three consecutive same-direction daily closes: block that direction on day 4 (cc08_006). Define a close as close > open, and test close > prior close as well.
- NWOG regime: count returns of price into the current NWOG during the week (039; 051). This needs ES ETH data; SPY can only use the Monday-09:30 variant. When "consolidation", cap targets at T1 (no T2) or skip PM trades.
- Large opening range gap: if |09:30 open - prior close| > k x `adr5`, skip AM entries before 10:30 or skip the AM (033).

**Session-level**
- `am=(600, 660)` variant: no entries before 10:00 (opening range rule).
- `no_pm_after_am_win`: skip the PM after a winning AM (065B; cc10_007).
- `pm_cutoff`: the current 15:50 cutoff already matches 001. Add: no new PM entry after 14:30 if the AM traded and lost (044).
- Macro-no-move filter: if 09:50-10:10 range < k x the ATR of the prior 30 min, end AM scanning (073). Needs a threshold; test k = 0.5-1.

**Frequency and size**
- Weekly cap: `max_trades_week`, `max_wins_week` (003; 099). Optionally stop for the week once a weekly draw (prior week high/low, NWOG) is hit (038; 101).
- After a losing trade: halve `risk_dollars` for the next trade, restoring after a winner or a new equity high (061; cc02_005). Ep 08 (no max size after a loss) agrees.
- The existing `lost_side` rule stays.

**needs data (flag, do not drop)**
- DXY (intraday) for the risk gate.
- YM/DIA for three-index symmetry. We have ES/NQ; add DIA from Alpaca.
- ZB/ZN daily for the bond-range consolidation filter.
- COT and open interest for weekly bias.
- Fed-speaker/testimony calendar.
- Treasury auction calendar.
- Early-close calendar.

**Too discretionary to code as stated**
- "50/50 / can frame the other side": the closest proxy is "both a bullish and a bearish setup armed in the same window", which the state machine could detect (both `Side` objects armed within N bars). That is a reasonable test.
- "Spotty" price, "seek and destroy", "in sync with the market", fading headlines: no measurable definition.
- "HTF targets met": needs a defined weekly draw (prior week high/low, NWOG, daily FVG). A proxy is possible.
- Seasonal agreement with "HTF trend": needs a trend definition. A proxy is the weekly close above or below the 9-18-month midpoint (cc12_001).

## 4. Open questions

1. CPI/FOMC/NFP scope: whole day, the release window, or until the "real range" forms? The minute counts conflict: NFP has none (006), FOMC 14:45 (021), any news 30 min (065B).
2. "Day after FOMC": AM only (095) or the whole day? "Day before holiday": Friday only, or also Thursday before a Friday holiday? How many days count as "post-holiday" (090 implies the AM only)?
3. NFP-week cutoff "Wednesday 11:00": is it the end of the AM session or a hard 11:00? He traded NQ at ~11:30 on an NFP Wednesday (101).
4. Thresholds with no number given:
   - "large range" and "small range" day (the only figures are > 2x ADR5 for skip, < ADR5 for expansion due, and ≥ 1.25x ADR for the London close);
   - "large" opening range gap (033);
   - "consolidating" daily chart (031);
   - NWOG "returns", "sharp move away", "clustered" NWOGs (051);
   - "decoupled" indices (046);
   - macro "no movement" (073);
   - "deep discount" for the size cut (099).
5. Three consecutive closes: close > open, or close > previous close (cc08_006)?
6. ADR window: 5 days including or excluding today? Measured from the open, or from the day's low or high?
7. The month-end / quarter-end / year-end intraday tendencies the task asks about are not taught. Only the quarterly shift, monthly bias timing, and the year-end/first-day items exist. Treat month/quarter turns as tags to measure, not rules.
8. January seasonal sign (conflict 9). Are the Dow-based seasonals valid for SPY/QQQ? This needs our own month-by-month test.
9. The "first liquidity run on news is the losing side" (064) applies to CPI/NFP; does it hold for all 08:30 releases? Is there a time limit for the second run?
10. Weekly reference open for SPY: Monday 04:00 pre-market vs Monday 09:30. For ES: Sunday 18:00 vs Monday 00:00. Which wins when they disagree (cc12_003)?
11. Does "skip Monday" apply to the AM only (101 suggests the Monday PM is acceptable)?
12. After a loss, is re-entry in the same direction limited to the same session? When does halved size return to normal?
13. "Done for the week" trigger: which weekly draw counts as met, and is it touch or close?
14. Rollover-week choppiness (093): the whole roll week or only roll day, and is it also true of SPY (which has no roll)?
