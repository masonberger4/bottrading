# Digest: trade models and setups

Sources: all 218 notes files (001-105 = 2023 playlist, cc01-cc12 = Core Content 2016-17), mentorship_rules.md, strategy.py, levels.py.
Times are New York. "ES pts" means ES handles; 5 ES = 20 NQ (049 ~2:44; 071 ~20:34). Citations use the file ID and the note's timestamp. Pure PD-array definitions are left to the PD-array digest and appear here only as entry rules.

## 1. Rules

### 1.1 Common skeleton ("one setup for life")
- Seven steps [2023]. The bias is what the weekly/daily candle reaches for, and you trade one direction only. Pick a time window and mark that window's high and low pools. Wait for a raid on the pool against the bias (the Judas). Then a structure shift with displacement must leave an FVG. Enter on any PD array (FVG, OB, breaker, OTE, IFVG, turtle soup, wick CE) and target the opposite pool or gap (067 ~12:00-26:00, ~1:30:00; 063 ~12:22; 065a ~2:28:00). [both]: cc01_001 ~02:05 (state -> tool), cc12_004 ~26:28-36:30 (only 3 intraday patterns).
- Pools by time (067 ~0:21:00): previous PM 13:30-16:00, London 02:00-05:00, NY lunch 12:00-13:30, AM 09:30-12:00, and the ORG (prior RTH close to 09:30 open). Priority at 09:30: the previous PM range if price is near it, else London, else the previous AM range. [2023]
- No trade when you can frame both directions (046 ~0:10; 095 ~27:33; 025 ~11:18). No trade when there is no draw, no inefficiency and no displacement (045 ~0:31). [2023]
- Enough room: the framework must offer about 10 ES pts to the draw while aiming for 5 (5.25 after commissions) (024 ~25:26; 046 ~0:32-0:40; 054 ~0:36; 058 ~37:16; 065b ~04:07). Day-trade room 50-60 pips; under 40 pips is only a scalp [fx-only] (cc09_001 ~3:22). [both]
- Time-to-work: once price touches the entry array it should deliver "on this candle or the next", or within 2-3 1m candles (022 ~1:43:27; 031 ~0:24:29; 071 ~32:41; 092 ~1:41:14). 025 ~17:17 allows ~10 min. A touch of the SIBI's far edge gets 2 minutes before you take half or all off (092 ~1:11:05). [2023]
- Abort rules [2023]:
  - A body closes outside the FVG against you and the next candle trades beyond that candle: close at once (045 ~1:19:58).
  - Three stacked PD arrays broken against you: close before the stop (026 ~28:02; 027 ~38:26; 078 ~1:02:38; 098 ~47:00; 105 ~1:21:06).
  - Never widen a stop; never add to a loser (003 ~1:14:05; 044 ~1:13:38; 085 ~13:52).

### 1.2 Market maker buy/sell model (MMBM / MMSM) and the AM reversal model
- Phases (MMBM; MMSM mirrors) [both]: original consolidation, distribution, redistribution, smart money reversal, low-risk buy, reaccumulation (x2), return to the original consolidation's buy side (003 ~1:27:50; 011 ~9:48; 071 ~7:35; 072 ~30:28; 103 ~28:37; 104 ~27:28-53:35; cc07_007 ~17:24 [chart]).
- AM entry version (Ep 03/05/07) [2023]:
  - Context: an HTF draw on the far side (daily VI, REH) and price dropping into a discount array (5m OB / 1m BISI).
  - Trigger: a short-term low is taken, then a short-term high breaks with displacement leaving an FVG (003 ~10:38-16:45; 009 ~1:00-3:00; 034 [chart]).
  - First entry is allowed in the bullish OB BEFORE the MSS (003 ~39:00, 6 lots @10901 with a 17.5-pt stop). Adds go on new FVGs that hold.
  - The MSS swing must be the one that led to the high or low that ran liquidity (010 ~41:31-46:19). Break the parent swing, not minor swings (058 ~41:15). The MSS needs no close; a wick or 1 tick through counts (012 ~30:30; 026 ~1:31:22; 030; 075 ~33:20).
  - Speed check: price must "rip through" the small SIBI high, then must not trade below the lowest open or close of the swing low (009 ~15:51-16:19).
- MMSM stage entries (104 ~31:17-53:35) [2023]:
  - Smart money reversal: sell wicks within 1-2 ticks of the HTF array high. Expert only.
  - Low-risk short: the rally back to the CE of the 60m SIBI after the break. Stop just above the high or the upper-wick CE.
  - 1st-stage distribution: retrace into the bearish breaker.
  - 2nd-stage redistribution: bearish OB MT.
  - Pyramid on buy-side-curve arrays retested from below. Target below the original consolidation low, ~80% off there.
  - If you missed a stage, the next one becomes your first (104 ~37:12).
- Reclaimed blocks [CC]: on the sell side of the curve, mark each down candle that was followed by a bounce. Do not buy them on the way down; buy their retests after the low once higher highs form (cc04_007 ~0:50-5:00) [chart].
- 4h MMSM example (103 ~28:27): sold a 15m bearish breaker and pyramided 5/10/5/5 for ~$51k.

### 1.3 2022 model (and "Model 2022" in the CC as the turtle-soup/OTE short)
- Short [2023]:
  - Buy-side (old high / REH / NWOG / London high) is taken, then displacement breaks a short-term low (MSS).
  - Inside the displacement leg (high -> breaking low), sell the FVG at or above 50% (premium). Never sell the breakout candle (022 ~38:38-47:56; 062 ~34:53; 074 ~26:53; 082 ~4:45; 087 ~5:50; 094 ~4:43; 008 ~2:49 [fx-only]).
  - FVG choice: prefer one aligned with a VI + bearish OB (022 ~55:00). With two FVGs, allow the higher one (042 ~47:20; 082 ~5:31). Otherwise the first FVG above EQ (022 ~1:03:08).
  - The FVG must close, a new candle must open, and price must trade back into it without first taking the low (042 ~34:53).
  - Pyramid only in premium. Past the 25% level of the leg, stop adding and only take partials (022 ~49:26; 025 ~47:56).
  - Stop: just above the bearish OB MT (022 ~59:02, 2 pts), above the FVG candle high (062 ~37:28), or just above the CE of the higher FVG when there are two (069 ~13:46).
  - Target: sell-side below 50% of the range, preferring the larger pool (042 ~1:09:17).
  - Long mirror: sell-side taken, MSS up, buy the FVG (032 ~56:57, last-hour version).
- Three drives ("three Indians") into liquidity that fails, then an MSS, then the 2022-model FVG (or breaker/IFVG) short (093 ~0:10:37; 074 ~32:49). [2023]

### 1.4 Silver Bullet (SB)
- Windows: 10:00-11:00 (AM) and 14:00-15:00 (PM) [2023] (044 ~0:50; 054 ~08:51-14:14; 058; 060 ~56:50; 065a ~55:55). Also London 03:00-04:00 (054; 060; 092 ~20:04). 092 adds 15:00-16:00; 099 ~53:30 adds an optional 07:00-08:30. [fx-only] variants 03:00-05:00 and 07:00-09:00 (065a).
- Setup [2023]:
  - Displacement toward the draw leaves an FVG whose direction faces the trade (a BISI for longs) (044 ~1:06:34).
  - Enter on the retrace into the FVG. Only the ENTRY must be inside the window; the FVG may form earlier (058 ~44:37; 059 ~0:08:56; 060 ~56:50; 065b ~04:48; 054 charts show gaps starting on the 09:55/13:55 bars). The target may print after the window (047 ~08:00; 054 ~11:27).
  - The first FVG in the bias direction during the hour is the entry (048 ~57:36). It must sit beyond the level that needed breaking (048 ~1:34:31).
  - MSS before the FVG is shown in 054/055/058 but never stated as required.
- Evolving SB: if price leaves the first FVG without a retrace, move the limit to the next FVG in the window. Better to miss than chase (057 ~0:02:16; 058 ~46:43). [2023]
- Cancel the order if price trades through the target before the fill (057 ~0:03:35). A shallow 1-tick run under sell-side followed by a retrace into the FVG is wanted (057 ~0:04:18). [2023]
- Room filter: ≥10 ES pts (40 ticks) or ≥15 pips [fx-only] from entry to the draw; take ~5 pts or cover at the old low (054 ~00:36; 058 ~37:16; 059 ~00:10:36; 060 ~50:00). Looser variants: 044 needs >5; 068 and 072 accept 4-5 pts.
- Draws (054 ~04:02-06:50): PDH/PDL; previous session H/L (London H/L for the AM); PWH/PWL; NWOG; OTE; 2022-model confluence. If these are already raided, use an HTF pool or inefficiency.
- Session order: London, else AM, else PM; one fires every day in one market (054 ~18:18; 090 ~2:00:22). If the FVG does not form in your market, do not trade another market (046 ~0:55).
- Entry price: a limit near the FVG's near edge (044; 057), the FVG midpoint as "worst case" (048), or the candle low (055). The sub-minute FVG (30s or lower) inside a 5m breaker/IFVG is also used (092 ~48:52).
- Stops (only 057 states one): 2 pts above entry, ~top of the evolved FVG (057 ~0:06:41). Also "below the candle forming the FVG low and below the OB MT" (090 ~2:14:00) and "below the entry candle" (086 ~11:35).
- Exits (057 ~0:07:35): layered limits at the NWOG high, its 75%/25% and its CE (4/2/4 of 10). Supercharge by aligning with the weekly profile: most at the 60-minute target, 1 runner (048 ~2:02:12).
- Examples:
  - 057: 10 short @4206.25, stop 4208.25, ~+5.2R.
  - 069: 12 short ~4395, covered at the ORG top +8.
  - 060: PM short 4169 -> 4153.75.
  - 063: 15 long @4273.75 +5 @4278.25, exit ~4285-4288.

### 1.5 PM models
- PM last-hour setup (Ep 01) [2023]:
  - Window 15:00-16:00; sweet spot 15:15-15:45. No setup by ~10 min before the close means no trade (001 ~1:00:01).
  - Pre-select an HTF FVG (4h/1h nested) as the last-hour zone [chart].
  - Trigger: 1m bodies refuse to close beyond the 60m FVG edge, then a fast candle leaves a breakaway FVG (001 ~39:03-41:00).
  - Entry at the top of the 1m FVG; adds in the FVG, in the breakaway gap, and on a breaker (001 ~42:19-45:02). Stop just below the FVG candle open, then trailed.
  - One exit at the draw, no intermediate partial (001 ~45:20).
  - He exited at 16:01; exits after 16:00 also in 012 and 032.
- MOC / last-hour macro 15:15-15:45 [2023]: runs to liquidity not yet engaged; no run if the HTF target was already hit (014 ~5:19; 030 ~20:06; 032 ~47:41; 047 ~11:15; 056 ~0:14:57). Variants:
  - 2022 model inside the window: sell-side taken 15:15-15:45, MSS one tick through, buy the VI/OB/FVG, target buy-side, flat by the 16:00 candle (030; 032 ~56:57).
  - Old low tagged, buy it, add on the new FVG (013 ~26:20).
  - With no setup, wait to ~15:40-15:45 and expect a 5-8 pt run (032 ~1:01:00).
  - Don't fade or add in the last ~15 min; close before 16:00 (026 ~1:59:50; 027 ~58:22).
  - Examples 013, 020, 024, 027 (all 15:35-15:57 entries).
- PM session reversal "2:00 macro" (015 ~31:57-36:20) [2023]:
  - Bias bullish, the intraday high taken after lunch. A 1m FVG at the old high can be bought for the run to the HTF objective.
  - Once the objective is hit, the trigger is a short-term-low MSS with price trading DOWN through that FVG (inversion).
  - Short the first return into the inverted FVG. Stop just above its high. Targets: the old daily high and the lunch relative equal lows.
- PM trend (CC index lessons) [CC]:
  - PM session 13:00-16:00. The move usually starts ~14:00 off an OB formed in the AM or at lunch. It continues or reverses the AM (cc10_012 ~00:00:34-00:07:07).
  - If the AM set the day's low, expect the high 15:00-16:00 (cc10_012 ~00:11:27).
  - Index SMT for the PM: lows/highs formed noon-15:00 (cc10_012 ~00:07:25).
  - Hold at least to the 15:00 bond close, ideally 16:00 (cc10_014 ~00:03:01).
- PM framing in 2023 [2023]: the PM starts at 13:30 (13:30 open = PM midnight open; Judas above it into premium, then sell, 010 ~56:30). The 14:00-16:00 sweet spot generally continues the AM (047 ~09:21). Lunch 12:00-13:30 runs the AM traders' stops (046 ~2:03:21; 064 ~1:45:41; 068 ~00:12:42). The PM trader starts ~14:45 (026). If nothing by 14:30, skip the PM (044 ~1:55:03).
- PM long/short off lunch (067 ~0:46:00) [2023]: lunch low taken, MSS + FVG, target the lunch high. The short is the mirror (lunch high into the ORG, 2022-model FVG, target the lunch low).

### 1.6 Power of three, Judas swing, opening prices
- Daily PO3 [both]: a bullish day opens near its low. Buy at or below the midnight open (the 00:00 15m candle open); shorts at or above it (006 ~5:51, ~23:28; 043 ~4:11; 060 ~15:20; cc03_003 ~31:25; cc08_008 ~1:34; cc12_003 ~23:11). The midnight-open line runs 00:00-11:00 (069 ~4:37).
- Three opening prices: midnight (preferred), 08:30, 09:30, plus 13:30 for the PM (010 ~38:31). Weekly versions: the Sunday open and Monday 00:00 (cc08_001 ~22:58-29:03; cc12_003 ~19:03; 048 ~1:00:10). [both]
- Weekly opening-price filter (cc08_001) [CC]:
  - Bearish week: expect an early trade above the week open (weekly Judas), then sell every day below it until an opposing daily PD array is hit.
  - A Thursday cross back through the open against the bias means a likely weekly reversal.
- Judas references [both]:
  - CC: London 00:00-02:00 protraction (cc08_005); NY at 07:00 (cc01_008 ~4:46) or the 08:20 CME open (cc09_006 ~19:07); 09:30 for indices (cc10_011 ~00:02:38).
  - 2023: the 09:30-10:00 opening range is the Judas (042 ~4:29; 062 ~32:00; 069 ~8:38). Wait it out; there is no bias before 10:00 (031; 036; 044; 065b ~04:53; 092 ~1:45:24, "amateur hour").
- News Judas [2023]:
  - Wait for the release. The first pool run is the losing side; buy after the sell stops are taken (064 ~0:52:12; 073 ~10:42, NFP up-down-up).
  - FOMC: 14:00 is a red herring; the real move starts at 14:25-14:30 (021 ~2:40; 065b ~05:30).
  - 105 (NFP Dec 8): bought inside a 4h FVG 45-60 s after 08:30, after the spike up failed to take buy-side.
- ORG repricing macro (069 ~10:06-14:50) [2023]:
  - ORG = prior RTH close (16:14/16:15 candle) to the 09:30 open, with levels at the high, low, CE and quadrants.
  - After the 09:30 Judas away from the ORG, price reprices back into it. Target the ORG near edge.
- Swing PO3 [2023]: if bullish, a tiny-size limit buy at or below the midnight open, aiming for today's high and then the HTF objective (013 ~8:45). The daily swing-short version is in 1.13.

### 1.7 Breaker, unicorn, mitigation and failure-swing entries
- Classic breaker entry [both]:
  - Bullish: low A, high B, a lower low that runs A's sell stops, then a move above B (MSS). Buy the return to the breaker.
  - Bodies should respect the breaker; wicks may poke (033 ~00:57:56; 048 ~1:06:07; cc04_005 ~0:37-7:14; cc05_005 ~09:46-11:24).
  - Stop beyond the sweep extreme (cc05_005 ~11:06).
  - The zone is defined differently across sources (Conflict 3).
- Advanced breaker (070 ~34:59-1:08:31) [2023]:
  - Use only the A->B leg (B -> lower low is "time distortion").
  - With bias on side you may buy inside the A-B leg or on the sell-side run without waiting for the break and retest.
  - Fill at MT needs 1 tick through.
  - Target B + 1x(B-A); further SD only at an HTF level.
  - Best when the lower low also hits an HTF pool. Fine-tune on the 1m last up-close candle.
- Breaker pyramid [2023]: buy the turtle soup low, then add at the breaker retest (cc12_004 ~33:23, pattern 3; 063 ~28:37). 070 scales in early (1, then 3, then 6).
- Unicorn [2023]:
  - An FVG inside the breaker's candle range. Strongest right after a sell-side run at the 09:30 open (007 ~22:39-23:35; mentorship_rules Ep 05).
  - Buy the FVG/CE inside the breaker and add on each new imbalance. Accumulate inside the breaker before the breakout.
  - Example 007: buys 3941-3942, out 3951.5/3956.5.
  - 018 is the same thing pre-open: a 5m FVG overlapping the breaker, may enter the breaker but not below its MT.
  - 101 ~84:31: a breaker with a SIBI inside after a liquidity run, on many TFs. 104 uses "unicorn" for the 2nd-stage redistribution (Conflict 11).
- Reaper (076 ~18:30-22:20) [2023]: a bullish breaker plus an FVG in the discount half of its impulse leg that price cut through on the way to the lower low. After the breaker high is taken, price returns; wicks stab the Reaper, its CE holds and bodies stay above; a reaction candle is the entry. 081 labels a bearish breaker zone "-Reaper".
- Breaker swing point vs failure swing (cc05_005) [CC]:
  - Breaker swing: one more drive takes the short-term high into the key level, then breaks the in-between low. Sell the retest of that breaking point; stop above the new high.
  - Failure swing: a lower high that fails to reach the level, then the break. Sell the retest of the level or the breaking point; stop above the failed high.
  - Both levels must be drawn before price arrives.
- Mitigation block [both]:
  - cc04_004: high, low A, a LOWER high, then a break below A. Sell anywhere in A's last down candle; stop above its high; repeat on each lower leg.
  - 2023: sell zone above the day's opening price; stop above the MT (098 ~46:00).
  - 033 ~01:03 and 041 ~00:00 use the bullish mirror for longs. 075 ~21:40 calls it a target, not an entry (Conflict 12).

### 1.8 OTE
- Anchor [CC]: the impulse leg from a 3-bar swing low to the high, confirmed once a later candle trades lower (the "4th candle").
- Entries [CC]:
  - Buy only below 50%. The OTE zone is 62-79% with 70.5% the sweet spot; 62% is the minimum. Never buy or short AT 50%.
  - Stop beyond the leg's swing low/high. If price never retraces to 50%, there is no trade.
  - Targets: above the old short-term high, or slightly before an opposing OB (cc01_004 ~9:44-53:45; cc01_005 ~2:07-20:47).
- A break of an old low inside the OTE zone is a turtle soup; buy it, and re-buy the next sweep if stopped (cc01_004 ~32:12, ~45:21). [CC]
- Premium/discount gate: the lower third only (cc01_006 ~2:07). Deep discount is 0.2-0.3 and deep premium 0.8-0.9 on the 0/20/30/50/80/90/100 grid (cc06_004 ~31:39). [CC]
- 2023 use [2023]: OTE is one entry option among many (065a ~2:28:00). cc12_004 pattern 1 ("favorite") stacks OTE + FVG + a swept short-term low + bullish OB; target external liquidity (cc12_004 ~26:28; gold example: entry 1278, stop 1274). 061 ~1:34:00: "fib only for premium/discount, never for entries" (Conflict 13).

### 1.9 Turtle soup and liquidity-raid fades
- Definition [both]: a false break beyond an old high/low taken "by a little", then a fast reversal (cc05_004 ~6:45, 20-day breakouts; cc09_005 ~15:30). It needs context: an HTF PD array at the level plus HTF order flow (010 ~63:38; cc02_002 ~3:46; cc09_005 ~03:12-18:56).
- 2023 entry [2023]: no MSS needed. Price takes a predefined external level, with SMT and one PD array (FVG/OB/VI); stop below that array (022 ~2:47:29). Stop at the nearest NWOG/NDOG/ORG below the old lows (038 ~41:58).
- CC buy-limit raid [CC]:
  - With a bullish bias, rest a buy limit at or just below the old low (cc04_011 ~9:45). The FX sweep is 10-20 pips with a 30-50 pip stop; >25 pips below means a real decline.
  - Targets are the opposite pool or an opposing OB/FVG.
  - Friday after a trending week: run both sides (cc04_011 ~17:59).
- CC turtle soup into a daily OB (cc02_001 ~17:41-25:21; cc02_002) [CC]:
  - A 1h sweep of an old low into a daily bullish OB, then a trade back up through the 1h last down candle.
  - Buy limit at that candle's open + spread; stop below the OB candle MT or the sweep low.
  - Half off at 1R, BE after 2R, runner to 5R.
  - Refine the entry on 15m/5m with the same stop logic.
- Pattern 2, external turtle soup (cc12_004 ~29:35) [CC]: price stops short of the expected HTF discount array (a false low) and later drops into it, raiding the sell stops under that false low. Buy there, not the early bounce.
- Reversal raids (cc09_005 ~00:29-34:24) [CC]:
  - PDH/PDL raid only inside an expansion swing in the bias direction, into a discount array (buy below the candle low when an FVG sits just below).
  - Intra-week high/low raid on Tue-Thu into an unmet HTF array; intermediate-term H/L raids in ranges.
  - NY session reversal only when London/NY open reaches an unmet HTF array.
  - London close reversal only when today's range is ≥125-133% of the 5-day ADR.
- Consolidation fades (cc09_004) [CC]: with daily/4h bias, buy below a 1h/15m consolidation low (or a short-term low below EQ). First target is equilibrium, optionally the far extreme.
- Traps [CC]:
  - False flags: sell the first return to the last up candle after a poke above the flag high; stop above the flag high (cc02_007).
  - False breakouts of a consolidation against the bias (cc02_008).
  - Trendline 3rd touch (cc03_007); H&S neckline break (cc03_008); divergence phantoms (cc04_013).
  - All require an HTF bias that opposes the retail pattern.
- Scalps (cc09_003) [CC]:
  - The Asian 20:00-00:00 fade of late-NY highs/lows [fx-only].
  - NY expansion: before 10:00, buy below a 5m short-term low after London posted the daily low while the 5-day ADR is unfilled. Fixed 20-pip target and stop. He says it works on ES/QQQ on 5m.
- Bonds/index opening range [CC]:
  - Bonds: OR 08:00-09:00, a stop run beyond it on lower volume, then a reversal (cc10_006).
  - Indices: OR 09:30-10:30; turtle soup below the OR low later in the morning, target the OR high (cc10_010 ~6:51).

### 1.10 Index SMT entries, sick sister, instrument choice
- AM SMT [CC]: compare relative lows (bullish) or highs (bearish) of ES, NQ and YM from 05:00 (or from London) into 09:30. One index failing to confirm marks the AM trend.
  - Entries: a buy stop above a down-close candle's high, or a turtle soup on the index that made the lower low.
  - Hold to 10:30-11:00. It shows up a few times a week; "if not obvious, it's not there" (cc10_011 ~00:08:01-00:18:36; cc10_014 ~00:01:15).
  - ICT trades only ES off the signal (cc10_012 ~00:10:17).
- Projected-range profiles (cc10_013/014) [CC]: six day templates chosen from daily/4h order flow:
  - Two-session up close / down close.
  - AM rally PM reversal / AM decline PM reversal.
  - The two consolidation profiles.
  - Each session is entered on SMT at a swing. The PM reversal needs a 15m/60m array nested in a 4h/daily array. Consolidation profiles exit ~14:00 because the day drifts back to its equilibrium.
- 2023 use [2023]: SMT is a qualifier, not a signal (031 ~0:44:53; 070 ~21:14; 099 ~55:07). It is used for bias (ES lower low not confirmed by NQ, 022), exits (YM lower low while ES/NQ hold means take most off, 037 ~00:32:56; 046 ~1:02:40), and as a DXY gate (031; 042 ~19:05; 045; 048; 095 ~26:17).
- Sick sister [2023]: compare reference highs at a key time. Count how many each index took; the one that took the fewest is the sick sister. Buy it at deep discount (below 50% + OTE + OB + FVG). Target the highs it failed to take; exit before the final high (053 ~01:56-07:57; 045 ~01:41, buy the laggard NQ at the down-close OB open; 056; 061; 070 "sixth sister").
- Leader instead [2023]: trade the stronger index for longs and the weaker for shorts (003; 065b ~05:38; 079 ~12:50; 090 ~31:01; 086, the index higher in its own premium array). See Conflict 7.
- Day-level SMT [CC]: daily 3-index SMT as a swing/seasonal timing filter (cc10_015; cc11_003).

### 1.11 TGIF
- Context [2023]: Friday only, after a trending, one-sided week that has reached an HTF premium (bullish week) or discount array. Without that, there is no TGIF (066 ~0:01:38; 074 ~24:04; 089 ~00:00:41; 084 ~15:45).
- Zone [2023]: from the week's extreme, retrace 20-30% of the weekly range (week low incl. Sunday 18:00 to the high). 25% is the midpoint; 40%+ is reversal talk (066 ~0:13:42).
- Timing [2023]: assume the weekly high is in by ~13:30. Either the 09:30 Judas or a later climb into lunch/13:30-14:00 makes it; the PM is more likely (066 ~0:15:10). Alternatives: London close 10:00-12:00 (084). Valid once a bearish shift confirms the high (075 ~1:40).
- Entry [2023]: any model; 066 used the PM SB (14:00-15:00 FVG). Sell 15 @15357 NQ, cover 15280 just below sell-side ~15:57 (+77 pts).
- Exit grid [2023]: partial at 20%, more at the upper gradient, most at 25%, then trail (optional, 066 ~0:47:41).
- 089 example: TGIF + 2022 model on NFP Friday, NQ short 10 @15635.25, stop 15647.25, full pull to sell-side.

### 1.12 Ma Deuce (091 ~19:02-26:47) [2023]
- Bearish setup:
  - The HTF expects the daily BISI (one big up-close daily candle) to be re-delivered lower, and price sits in the premium half of that BISI.
  - On the LTF a bullish 1m FVG is broken and inverts.
  - Do not short the first break. Wait until 08:00, then sell the retrace into the inverted FVG; a 2nd rejection or a new small SIBI just before 08:30 is a 2nd entry. The 08:30 release delivers.
- Targets: the daily BISI CE, then its lower quadrant, then the 1h BISI low.
- Stop never stated. The bullish mirror uses a daily SIBI.
- Do not trade an index while it sits inside its daily BISI range (091 ~6:12).

### 1.13 IFVG, immediate rebalance, propulsion, vacuum and void entries
- IFVG [2023]:
  - Validity: price closes through an opposing FVG, a NEW candle opens, trades back in and holds. A spike through and back does not count (048 ~21:32).
  - Entry at its CE or near edge (078 ~50:28; 085 ~27:21 re-entry; 075 ~1:27:00 after a CISD).
  - Allowed depth (102 ~1:09:00): one pass may reach the far edge; partly re-traded means near edge to CE; traded both ways means low edge to CE max.
  - Stop above CE plus 3-4 ES pts; stops <2 pts are too tight except on 15s-1m (102 ~1:40:20).
  - 061 ~2:15:00 signature: an IFVG with a normal FVG below; a body close at the FVG high/CE triggers, then IOFED.
- Immediate rebalance [2023]: a displacement candle whose next candle touches back with no gap. With bias, enter at once with a very tight stop (099 ~3:46; 060 ~07:20; 080; 100 ~44:54). Exit if price retraces above the range EQ (100 ~1:37:18).
- CISD OB [2023]: after the MSS, the first trade above the open of the last down-close candle validates the OB; its low must hold (075 ~1:16:40). Buy at or below EQ of the range from the post-CISD low to the high.
- Propulsion block [CC]: a down-close candle that trades into a prior bullish OB. On return, price should hit its high and leave; losing its MT means wrong, so use an ultra-tight stop (cc04_008; 027 ~11:31; 079).
- Vacuum block [CC]: an event/session gap. Buy a bullish OB inside it (stop below the lowest down candle), or buy the full fill at the pre-gap close (stop below the lowest low). Exit if price closes back below the pre-gap close (cc04_009).
- Liquidity void [CC]: expect a full re-fill, preceded by a stop run. After the fill, sell a limit inside the first body gap (cc04_010).
- Breakaway gap trade [2023]: a gap that leaves an expected level with an MSS. Valid when the retrace leaves part unfilled and makes a new extreme; trail the stop to the gap (062 ~37:02). Retrace at most to half (065b ~04:39).
- Wick-CE trades [2023]: buy at the wick CE when the next candle closed above it, TP ~0.5 pt below the high (100 ~38:13); 09:30 wick-CE long (080).

### 1.14 London/CBDR day-trade models [fx-only, CC]
- CBDR 14:00-20:00, Asian 20:00-00:00, Flout 15:00-00:00 (half-range SDs).
- London protraction is normal (00:00-02:00) or delayed (02:00-03:00). The HOD/LOD sits 1-2 CBDR SDs out when the CBDR is <40 pips and the Asian range 20-30 pips (cc08_003/004/005; cc12_004 ~8:41-15:40).
- Nine London buy setups with fixed pip stops (cc08_007).
- The 0 GMT open entry with a 5-day-ADR stop (cc08_008).
- "Filling the numbers": ~4 levels from entry (cc09_002).
- Bread & butter scalps (cc09_006/007): London close fade 10:30-13:00 after the ADR is met, stop 10 pips beyond the HOD, target 20-30% of the day's range.
- Sentiment effect: buy below the midnight open AND the Asian low into a 15m discount array (cc09_001).
- Index analogues are untested; see Open questions.

### 1.15 Weekly / short-term (OSOK) templates [CC, partly 2023]
- One Shot One Kill: one trade per week targeting the weekly range (cc07_008; cc02_003).
  - From a monthly/weekly PD array, target the opposing array one timeframe lower (cc07_001 ~09:29).
  - Sell a small piece Monday and add if Tue/Wed fail to make a higher high (cc07_008 ~29:33).
  - The weekly high/low forms Mon-Wed about 70% of the time (cc07_008 ~1:35; cc08_001 ~20:43; cc07_006 ~20:45).
  - A Thu/Fri break of the Mon-Wed high means expansion to target (cc07_001 ~42:44).
- Twelve weekly profiles, each with a manipulation template (cc07_002/003):
  - Classic Tuesday/Wednesday low or high of week.
  - Consolidation Thursday reversal (14:00 news).
  - Consolidation midweek rally/decline.
  - Seek & Destroy Friday: avoid.
  - Wednesday weekly reversal.
  - Targets: a PD array one TF lower overlapping a 1.27/1.68 extension or a 100% measured move.
- Intraweek reversal (cc07_007): a Mon/Tue move far beyond the 5-day ADR into an HTF array, then a reversal at the Tue-Wed changeover.
- 2023: the weekly bias is first; one good setup per week (035 ~16:53; 064 ~1:44:34). cc12_003 ~15:40: let Monday go and enter Tuesday off Monday's low (OTE) or Wednesday off Tuesday's low.

### 1.16 Swing / position models [CC]
- Daily-candle entries (cc05_016/017):
  - With monthly/weekly drawing to an array beyond, the daily must CLOSE counter-direction.
  - Then use a buy stop at that candle's open (confirmation) or a buy limit at its close (deeper). Repeat on each new counter candle until the HTF array is reached.
  - Start at ~half size and re-add partials at the same open.
- Stops (cc05_018): beyond the 40-trading-day extreme, tightening to 20 days at 50% or 75% of the move. Never early BE; ≤1% risk.
- Order type by array (cc06_008): stop orders on breakers, mitigation blocks, FVGs and voids; limit orders on OBs, rejection blocks and old highs/lows.
- Million Dollar Swing management (cc06_008):
  - Gates: seasonal / major market / COT / DXY / commodities / OI (needs data: COT, OI, DXY, bonds, commodities).
  - Leave the stop until 1/3 of the distance; at 1/4 take 20-30% off, then BE.
  - Re-add at 50%. Expect one stop run after equilibrium.
  - Targets: 1.27/1.62 extensions at weekly/monthly arrays.
- MWD sequential (cc06_004/005):
  - All three timeframes bullish: buy every daily and 4h discount array.
  - Daily correcting: buy only at weekly arrays.
  - Weekly correcting: buy only at monthly arrays.
  - Execute on 4h; stops beyond the swing liquidity; ≥3:1 to the nearest opposing array (cc06_003 step 12).
  - Failure protocol: next array at 50% size (cc06_003 ~23:24).
- Swing risk (cc06_006): monthly/weekly framed, 4h entry, ~1.5% risk, 5-10R typical.
- Daily swing short (098 ~19:00) [2023]: after a rally into a daily SIBI, put a sell-stop at the next midnight open (placed after 21:00), stop above the FVG-creating candle, no BE or trail, ≤1% risk.
- Stock models (CAN SLIM + stock-vs-index SMT, cc10_015-018, cc11_003): stock-only, out of scope for the bot.

### 1.17 Trade management used across models
- Sizing:
  - 2023 live: 1-2.1% risk on $100k (003 2.1%; 009 1.2-1.3%; 102 1-1.5%).
  - Contracts = 1% / stop in $ (065a ~1:04:00).
  - Size caps 10-15 contracts.
  - After a loss, re-enter at half size (070 ~38:41; cc02_005; cc06_003; 061 ~2:26:40).
- Pyramid:
  - Largest unit first (6/3/2/1, 006 ~51:52; 6/3/1, 021, 050, 060; 5/4/3/2/1, 083/085).
  - No adds after partials (006). No adds past 25% of the leg or past EQ (022; 045; 092).
  - Exceptions: 067 added above first entries; 070 scaled 1/3/6.
- Stops [2023]:
  - Initial: below the FVG candle open / bodies (001); below the MT of the down-close OB nearest the sweep (009); below the sweep low (cc02_002).
  - Never trail into an FVG created right after the MSS (085 ~19:59).
  - Don't move to BE before the first partial (032 ~58:19; 036; 046 ~1:22:00). Ep 03 moved to BE right after the MSS.
- Partials (all [2023]):
  - The bulk at the first liquidity target: 10 of 12 (006); 9 of 14 (009); 80% at the NWOG CE (020); 80/20 on slow days or 50/25/25 normal (036).
  - Always a partial at a wick CE inside the trade range (065b ~03:52:40).
  - -0.5 SD is always the first partial (064 ~1:33:48).
  - Full pull with no partials in strong one-way conditions (076; 089; 102 low-resistance).
- Exit price vs level: see Conflict 8.
- SD projection targets: anchors are ambiguous, see Conflict 9. Projections must line up with a pool, a PD array or time (014; 029; 030; 062 ~42:19; 065b ~03:03).

## 2. Conflicts

1. **AM session window.**
   - A: 08:30-11:00 (mentorship_rules Ep 01; tweets 013; 044 ~0:55:47; 073).
   - B: 09:30-12:00 (013 [chart]; cc10_011; 067 AM pool).
   - C: no entries 09:30-10:00, "amateur hour" (031, 033, 036, 042, 044, 065b, 092). B and C appear more often in later 2023 files.
   - His own entries: 09:37-09:50 in 007, 009, 034, 041 and 053; mostly ≥10:00 from 044 on (Silver Bullet era).
   - Default: AM entries 10:00-11:00 (SB), plus the existing 09:30 sweep model as a separate tagged setup. Parameter: `am=(570,660)` vs `(600,660)`.
2. **PM start and setup time.**
   - A: 14:00-16:00 with entries 15:15-15:45 (001; rules).
   - B: 13:30 (010 PM Judas; 037; 047; 067).
   - C: 13:00 (cc10_012).
   - D: the 14:00 macro / 14:00-15:00 SB (015; 054; 060; 066).
   - His trades: 13:32-13:46 (067); 14:01-14:15 (060, 066, 071, 058); 15:35-15:57 (013, 020, 024, 027).
   - Default: keep 13:30-15:50 but tag sub-setups (pm_sb 14:00-15:00, last_hour 15:15-15:45). Test each separately.
3. **Breaker zone.**
   - A: candle body / highest body (001; 048 ~1:06; 029 ~22:34; 092 ~10:24).
   - B: full range with wicks of the highest up-close candle (031; 032; cc04_005).
   - C: the whole A->B leg (070).
   - D: the single last opposite candle (cc05_014).
   - levels.breakers uses the last up-close candle at/before the swing high (≈B/D).
   - Default: B (matches the most examples); test C.
4. **Entry before vs after the MSS.**
   - A: after the MSS, at the FVG (most 2023 files; strategy.py).
   - B: in the OB before the MSS (003 first entry; 070 inside the A-B leg; 022 turtle soup needs no MSS).
   - His biggest documented AM trade (003) used B.
   - Default: A; test B only when an HTF array and SMT are present.
5. **MSS validity.**
   - A: a body close with displacement (rules Ep 02/05; strategy.py uses a close above the swing high).
   - B: a wick / 1 tick through is enough (012, 026, 030, 075).
   - B appears in 4+ later files.
   - Default: keep the close (fewer false shifts). Test the wick version as a parameter.
6. **Silver Bullet details.**
   - FVG formed inside vs before the window: before allowed in 058/059/060/065b; inside required in 066.
   - Room: 10 pts (054/058/059/060) vs 5 pts (044/068/072).
   - First FVG only (048) vs evolving (057).
   - Default: entry inside the window, FVG from any time after the sweep, ≥10 pts of room to the target, evolving allowed.
7. **Which index to trade.**
   - A: the stronger/leader (003; 065b; 079; 086; 090).
   - B: the laggard / sick sister (045; 048; 053; 056; 061; 070).
   - 099: in a bearish bias, a laggard failing the low is not SMT.
   - The bot can only trade one ETF pair, so treat this as a selection parameter (SPY vs QQQ), not core logic.
8. **Exit vs level.**
   - A: 0.5-1 pt before the level (010; 070 0.25-1.5; 063 a couple of ticks; 101 2 ticks; 102 1-2 ticks).
   - B: just beyond the level (018 level+0.25; 083 0.75-1 beyond; 099 a couple of handles; 105 1-2 ticks beyond for fills; 050/066 1 tick below the low).
   - Rule of thumb from the examples: exits at a PD array (FVG/OB) are placed before it; exits at a liquidity pool (old high/low) are placed just beyond it.
   - Default: exactly that split. The bot currently exits 0.5 pt before every level.
9. **SD projection anchor.**
   - Down-leg into the low (014).
   - Low to the broken high (030; 047; 062).
   - Manipulation leg (092; Ep 06).
   - Breaker A-B leg (070).
   - London low to high [fx] (008).
   - Default for `sd_targets`: the leg from the sweep extreme to the swing high that was broken (= 030/047, which also matches the existing code). Test the 070 A-B leg.
10. **News days.**
    - A: no NFP Friday, no Thu/Fri or Wed PM of NFP week, no FOMC PM (003; 006; 038; 101 for new traders).
    - B: he trades them (021 after 14:45; 065b FOMC 14:25; 071, 088/089 and 105 NFP Friday; 041 and 050 NFP Thursday; 082 FOMC minutes; 097 FOMC day).
    - Every B instance is labelled "experienced only" or a demonstration.
    - Default: keep A. Test the FOMC 14:30+ stage-2 rule separately.
11. **Unicorn.**
    - A: an FVG inside a breaker (007; 101).
    - B: the 2nd-stage redistribution OB (104).
    - Default: A (as coded).
12. **Mitigation block use.**
    - Entry: cc04_004; 033; 041; 098.
    - Target only: 075 ~21:40.
    - Default: tag only.
13. **Fib/OTE for entries.**
    - A: OTE 62-79% as the entry zone (cc01_004/005; cc12_004; 065a).
    - B: fib only for premium/discount, never entries (061).
    - Default: use as a discount filter (entry below 50% of the sweep-to-high leg); test an OTE limit.
14. **Mean threshold.**
    - Wick high-low (002).
    - Body midpoint (009; cc04_003/008; cc06_005; 026).
    - First open to last high for multi-candle OBs (065a).
    - Stops built on MT differ by ~0.5-2 pts. Default: body MT for stops (009 is his own live trade); keep `ob_mt` and add a body variant.
15. **Reversal after a stopped trade.**
    - A: never reverse in the same session (001; rules).
    - B: flip in the same minute when "absolutely offside" (085; 094; cc08_009 next-day flip).
    - Default: A for the bot.
16. **Breakeven.**
    - Right after the MSS / buy-side run (003).
    - After the 1st partial only (032; 036; 046; cc06_008).
    - After 2R (cc02_001).
    - Never early on position trades (cc05_018).
    - strategy.py moves to BE at T1 (= after the 1st partial). Keep.
17. **Pyramid order.**
    - Largest first (006; 050; 060; 083).
    - Rising sizes (070; 067).
    - Default: largest first with `adds=(0.5,0.33)` (as coded).
18. **Hold vs scale.**
    - Hold to time-of-day, no partials (076; cc10_014 PM to 15:00/16:00; 089).
    - Scale at every pool (003; 064; 065a; 071).
    - Also the mentorship_rules "done by 15:00" vs cc10_014 "hold to 15:00-16:00".
    - Default: half at T1 (current). Test a time-held runner to 11:00 (AM) or 16:00 (PM).
19. **Opening range length.**
    - 09:30-10:00 (2023).
    - 09:30-10:30 (cc10_010).
    - The 2023 version is used in many more files.
20. **London close window [fx].** 10:00-12:00 (008; 104) vs 10:00-11:00 (cc01_002) vs 10:30-13:00 for the scalp (cc09_006).

## 3. Bot implications

What strategy.py/levels.py does now: one sweep -> close-through-swing MSS -> FVG limit model for AM 09:30-11:00 and PM 13:30-15:50. Unicorn preferred, midnight/13:30 open gate, OB-MT stop, T1/T2 exits with BE, NFP/FOMC day filter, optional HTF/trail/adds/weekly bias/SD/wick targets, and an SMT tag.

Add (codeable):
1. **Silver Bullet as its own setup** (tag `sb_am` / `sb_pm` / `sb_london` with ES data).
   - Entries only 10:00-11:00 and 14:00-15:00 (03:00-04:00 is possible on ES/NQ data but not tradable on SPY/QQQ).
   - FVG after an MSS toward the draw, room ≥10 ES pts to the first target, evolving FVG allowed.
   - Cancel if the target trades first (already coded).
   - This is the setup he trades most from file 044 on.
2. **Opening-range wait.** A parameter to block AM entries 09:30-10:00 (Conflict 1). Test whether it removes the losing early trades.
3. **Draw-first filter.** Require the T1 target to exist on the draw side and to offer ≥10 pts of room (keep `min_rr`). Only take the side whose pool sits in the daily/weekly bias direction.
   - Bias proxies available from data: weekly-bias rule, previous-day/3-day H/L, NWOG/NDOG, ORG.
4. **ORG levels.** Compute the ORG (prior 16:00/16:15 close to the 09:30 open, CE, quadrants) and add it as a target and pool (067, 069). Also NDOG (17:00 close to 18:00 open) when ES overnight data exists.
5. **Last-hour model as written.**
   - PM entries 15:15-15:45: a sweep of a session low (lunch/PM) then MSS + FVG, target an untaken pool. Already partly covered by the `pm_last_hour` tag.
   - Add: no new entries after 15:45; flatten at 16:00 (present).
6. **2022-model filter.** Require the entry FVG to sit at or above 50% of the displacement leg (short; mirror for longs) and stop pyramiding past 25% of the leg.
7. **Exit placement split.** Exit before PD-array targets (FVG/OB/NWOG CE) and 1 tick beyond liquidity-pool targets (old H/L, REH/REL).
   - The current `exit_before_pts=0.5` everywhere probably misses fills on pool targets; 083/105 show unfilled exits at the exact level.
8. **Abort / time stop.** Close if, within N bars (2-3 1m bars) of the fill, price has not moved toward the target, or a body closes beyond the FVG and the next bar extends.
9. **TGIF (Friday only).** With a one-way week (weekly range ≥ k x average and the close near the extreme), short (long) Friday entries 10:00-15:00 into a target zone of 20-30% retrace of the weekly range. Fully codeable from daily/1m bars.
10. **Ma Deuce (codeable).**
    - Daily BISI = one big daily candle's gap. Price in its premium half.
    - Pre-08:30 inversion of a 1m bullish FVG; sell the retest after 08:00.
    - Needs ES/NQ overnight data, and SPY pre-market fills are thin, so treat it as research only.
11. **IFVG entry type.** An opposing FVG closed through, then a new candle trades back into it. Add as an alternative entry zone (entry at CE) for the existing sweep -> MSS machine.
12. **Index SMT gate.** Currently a tag only. Test it as a filter (ES vs NQ and also YM/DIA). Window 05:00-09:30 for the AM, 12:00-15:00 for the PM (cc10_011/012). Use ES/NQ futures data, not SPY/QQQ, because ETF pre-market is thin.
13. **Re-entry after a loss** at half size on the same side if the draw is untouched (070; 085). Currently: no re-entry after a loss in the same session.

Change:
- **MSS:** keep the body close as default; add `mss="wick"` (Conflict 5).
- **Breaker zone:** the full range of the highest up-close candle in the swing, wicks included (Conflict 3), when testing the unicorn tag.
- **MT stop:** add a body-MT variant (Conflict 14).
- **PM window:** split it into pm_sb (14:00-15:00) and last-hour (15:15-15:45) tags and report each (Conflict 2).

Remove / don't add:
- Nothing in the current code contradicts the core model.
- `weekly_bias` as coded (a strong down day biases the week) is a one-week remark (rules Ep 05). Keep it off by default.

Too discretionary or needs data:
- CBDR/Asian/Flout SD models, London protraction and 0 GMT entries: fx-only and need 24h data plus pip thresholds. ES Globex 1m could test them; out of scope for SPY.
- OSOK weekly templates and the twelve weekly profiles: classification by day of week is too vague. Only "weekly extreme forms Mon-Wed" and "Mon-Wed high/low break on Thu/Fri means expansion" are testable as stats.
- Million Dollar Swing, MWD sequential, mega-trades: need data (COT, OI, DXY, bonds, commodities, seasonal composites). Swing bot only.
- Smart money reversal (selling within 1-2 ticks of an HTF high), the Reaper and "three PD arrays against you": need judgment about which arrays count.
- Sick sister: needs counting "reference highs taken at a key time" with no fixed time or definition; also needs trading the laggard index.
- DXY gate: needs data (DXY intraday). A free daily DXY could serve as a daily filter only.
- Hold-to-time vs scale-out: discretionary by his own account ("in strong conditions"). Run both as parameters.

## 4. Open questions
- Stop placement for the SB, 2022 model, TGIF and Ma Deuce is rarely stated (only 057: 2 pts above entry; 022: above OB MT; 062: above the FVG candle). Which default should the bot use?
- "Displacement" has no size threshold (candle range vs ATR? FVG size?).
- Room to target: 10 pts measured from entry or from the FVG? ES pts → SPY conversion (~1/10) is already assumed in `es_pt`.
- Room filter "≥10, take 5": should the target be the pool (≥10 away) or a fixed +5 pts?
- SB: does the MSS have to occur inside the window? Can the FVG come from the 09:30-10:00 leg (065b says yes)?
- Silver Bullet 15:00-16:00 and 07:00-08:30 windows (092, 099): real windows or one-offs?
- Index SMT: lookback for the compared swing (05:00 low vs post-09:00 low?), wicks or closes, and how close in time the two swings must be.
- Sick sister: which "key time" and which reference highs; how to rank laggard vs leader.
- TGIF: what makes a week "trending" (range vs ADR? close location?) and whether a new Friday extreme cancels it.
- Ma Deuce: stop, size of the daily BISI, and whether the 08:30 release is required.
- IFVG: how many bars may pass between the close-through and the retest.
- Breaker for the unicorn: is the breaker candle the last up-close before the lower low or the highest up-close in the swing?
- Opening range: 09:30-10:00 or 09:30-10:30, and whether entries inside it are banned or just lower probability.
- ORG close: 16:00 vs 16:15, and expiry (3 days, 5 days, or kept indefinitely).
- CC CBDR/Asian/Flout thresholds in ES points (fraction of ADR?).
- Exit "before" vs "beyond" a level: is the PD-array/pool split right, or do the examples just reflect fill luck?
- PM reversal (015): which FVG counts as "at the old high", and how soon after the HTF objective the inversion must happen.
- NFP/FOMC: whether to test the FOMC 14:25-14:30 stage-2 entry (021, 065b) or keep the full-PM block.

## 5 most important findings for the bot
1. From file 044 onward almost every ICT trade is a **Silver Bullet**: an FVG entry 10:00-11:00 or 14:00-15:00 after a sweep and shift, with ≥10 ES pts of room and a ~5-pt-plus target. Add it as its own tagged setup, plus an option that blocks entries 09:30-10:00.
2. The current sweep -> MSS -> FVG engine already matches his MMBM/MMSM and 2022 model. Missing are the **2022-model entry filter** (FVG at/above 50% of the displacement leg, no adds past 25%) and the **ORG/NDOG levels** as pools and targets.
3. **Exits:** he exits just *beyond* liquidity pools and just *before* PD arrays. The bot's uniform 0.5-pt-before rule likely costs fills on pool targets.
4. **Time stops** (move within 2-3 bars) and **abort on a body close through the FVG** are his consistent invalidations. They are cheap to code and test.
5. **TGIF** (Friday 20-30% weekly retrace) and the **last-hour 15:15-15:45 run** are concrete, mechanical models usable on SPY/QQQ. Ma Deuce, SMT/sick sister and the CBDR models need overnight futures or extra data, so treat them as research only.
