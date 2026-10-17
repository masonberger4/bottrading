# Digest: execution

Scope: entry order types, stops, risk per trade, sizing, pyramiding, partials, trailing/breakeven,
minimum R:R, targets, time exits, drawdown rules, reversals after a loss, journaling rules that
imply code. Sources: all 218 notes, `mentorship_rules.md`, `strategy.py`, `levels.py`.
Units: ES points ("handles"); SPY ~ ES/10, NQ ~ 4x ES (049 ~2:44; 071 ~20:34). Times are New York.
Tags: [2023] / [CC] / [both]; [chart] = only visible on charts; [fx-only] = pip sizes or FX sessions
that do not transfer as stated.

## 1. Rules

### A. Entry order types and entry price
- A1. Default entry is a resting limit inside the FVG/PD array, not a breakout chase. Live examples rest the
  limit at the FVG's near edge or one tick past it [both] (001 ~15:24 [chart]; 018 ~0:06; 042 ~45:29;
  057 ~1:16; 058 ~48:13; 066 ~0:44; cc02_002 ~8:13; cc04_003 ~6:38).
- A2. Only two FVG entry prices: CE (50%, "highest probability") or the institutional order flow entry
  drill (IOFED: the FVG-forming candle's extreme or one tick beyond, which "guarantees" a fill) [2023]
  (024 ~23:19). He rarely gets CE fills, so he enters as soon as price trades a little into the FVG
  (035 ~53:42). Quadrant ladder when bullish: buy at the FVG high, then 75%, then CE (030 ~15:46).
- A3. A fill needs price to print at least one tick through the order price (spread). Limits resting
  exactly at a level that only prints to it go unfilled [2023] (042 ~59:04; 060 ~50:00; 070 ~56:01;
  105 ~1:27:00).
- A4. Market orders are used for adds and for scalp entries; exits use resting limits [both]
  (009 add at market [chart]; 020 +5 at market [chart]; 040 [chart]; cc09_006 ~7:06).
- A5. Stop-entry orders [CC]: buy stop at the open of a closed down-close candle (sell stop at an up-close
  candle's open); move it to each new opposite candle if unfilled (cc05_016 ~0:50, ~3:08). Limit
  alternative: buy limit at that candle's close (cc05_017 ~0:50). Order type by PD array: breaker,
  mitigation block, FVG, liquidity void -> stop order; order block, rejection block, beyond an old
  low/high -> limit (cc06_008 ~14:20). A limit can miss; a stop nearly always fills but widens the stop
  (cc05_018 ~4:39). Rejection block: limit at the body trigger, or sell stop below the trigger after a
  poke above it (cc04_006 ~10:43-11:33). Index AM: buy stop above a down-close candle's high, or turtle
  soup limit below the old low (cc10_011 ~15:32).
- A6. Enter on the retrace candle in your favour: buy into down-close candles, sell into up-close candles
  ("market efficiency paradigm") [2023] (009 ~08:11; 042 ~48:56; 037 ~21:10 short needs at least one
  up-close candle).
- A7. Never chase. If price leaves without retracing, let it go; better to miss than chase [both]
  (057 ~2:45; 037 ~21:10; cc01_001 ~10:28; cc06_003 ~13:00).
- A8. "Evolving" FVG: if the first FVG is left untouched and a newer FVG forms inside the same window,
  move the limit to the newer one [2023] (057 ~2:16-5:40).
- A9. Cancel the pending order if price trades through the target before filling [2023] (057 ~3:35).
- A10. Entry must be inside the time window; only the entry, not the exit, must be in it [2023]
  (054 ~11:27; 058 ~44:37; 060 ~56:50).
- A11. Do not enter early when the stop would be too wide; wait for the structural entry [2023]
  (057 ~2:54).
- A12. Split entry so the move is not missed: half at the open price, half at a limit 10-20 pips beyond
  it toward the Judas move [CC][fx-only sizes] (cc08_008 ~18:07).

### B. Stop placement
- B1. Long stop below the mean threshold (MT) of the bullish OB nearest the sweep low; short mirror
  [both] (009 ~04:17 [chart]: stop 4011.50 under the 09:40 candle's body MT; 022 ~59:02: short stop
  4132 just above MT 4131.50; cc02_001 ~22:02; 104 ~45:17).
- B2. Alternative structural stops used live [2023]: just beyond the FVG-forming candle (001 ~37:45;
  013 ~18:13; 015 ~33:56; 060 ~1:23:00; 090 ~2:14:00, below the candle forming the FVG's low and
  below OB MT); below the entry candle (076 ~28:00); 2 pts above the evolved FVG (057 ~6:41); above
  the CE of the longest wick above the FVG (089 ~6:48); below the breaker low, never letting price
  close below breaker MT (018 ~1:22).
- B3. Stop must sit beyond every nearby inefficiency, not just the entry FVG: below any gap under a
  long (027 ~30:20); with two FVGs in the leg, beyond the higher one / its CE (025 ~55:15;
  069 ~13:46; 082 ~5:31); beyond any overshoot wick already printed (081 ~15:47) [2023].
- B4. Don't place the stop just past a level price is allowed to "mohawk" (1-2 tick wick poke), and not
  under a random swing low near equilibrium; those get swept [2023] (078 ~58:00; 075 ~1:25:00;
  038 ~46:16; 096 ~11:53).
- B5. Padding [2023]: one tick beyond the level (010 ~16:01); 3-4 ES handles beyond a CE stop in fast
  markets, stops under 2 handles too tight except on 15s-1m charts (102 ~1:40:20).
- B6. Swing/breaker setups [CC]: stop beyond the swing that already ran the liquidity (cc05_005
  ~11:06, ~24:44; cc02_002 ~6:34; cc06_004 ~21:17 "beyond the sell-side, not right under the level";
  078 ~1:22:14 above the swing high, not just above the FVG [2023]).
- B7. Fixed-distance variants exist [both]: ~12 handles NQ (088 ~0:40 [chart]); 20/30/40-pip tables by
  setup and Asian-low-minus-50%-ADR (cc08_007 ~14:29-16:01) [fx-only]; stop = 5-day ADR from entry
  (cc08_008 ~13:03) [fx-only].
- B8. NFP: stop wider than usual, behind all candle bodies of the HTF array (105 ~0:51) [2023].
- B9. Never widen a stop; if you want to, close instead [both] (003 ~1:14:05; 044 ~1:13:38;
  045 ~1:19:58; 105 ~26:46; cc02_005 ~15:44).

### C. Risk per trade and sizing
- C1. Size = (equity x risk%) / stop distance [both] (065A ~1:04:00; cc02_004 ~18:56).
- C2. Risk observed in 2023 live trades: 1.2% then 1.3% after an add (009 ~05:27 [chart]); 2.1% initial
  6-lot (003 ~39:00 [chart]); 1-1.5% normal (102 ~1:23:50). 2% is too much for new traders (022 ~1:38:24).
- C3. CC risk ladder: 1% default, 0.5% fine, 2% hard max (cc02_004 ~10:40); new traders <= 2% average,
  1.5% starter (cc02_001 ~3:41, ~15:27); scalps 0.5-1%, never > 1% (cc09_006 ~3:54; cc09_007 ~3:20);
  swings ~1.5% (cc06_006 ~17:03); positions <= 1% (cc05_018 ~5:13); conservative base = 30% of equity,
  1% of that (cc05_013 ~4:13, ~6:27).
- C4. Size down sharply when conditions are mixed [2023]: against the macro undertone ~3 contracts
  instead of 20 (022 ~1:38:24); cracked ES/NQ correlation never at standard risk (090 ~35:02);
  low-probability setups minimum size, no pyramiding (045 ~1:01:43); day before CPI/NFP/FOMC smaller
  risk (029 ~5:22; 042 ~3:50); FOMC week trade light (094 ~1:48); August/war smallest leverage (079
  ~8:54; 103 ~32:44).
- C5. Size up only for the strongest arrays: BPR + FVG up to 15-20 contracts vs ~10 on a plain FVG
  (092 ~9:44); up to 5% per entry when within ~20-30 handles of an HTF target (102 ~1:23:50) [2023].
- C6. Contract caps [2023]: max ~6 initial building to 10-16 (010 ~49:51); standard 6 + up to 4 = 10
  (076 ~27:54); funded $150k cap 15 contracts, he used <= 10, $3k daily loss limit (040 ~1:56; 050 ~45:06).
- C7. After a loss: halve size, aim to win back ~50%, then step back up [both] (061 ~2:26:40;
  cc02_005 ~5:20: 2% -> 1% -> 0.5%, keep halving per loss). Never raise size to recover
  (cc02_005 ~15:44; cc06_003 ~23:24). Re-entry after a stop at half size (070 ~38:41).
  Opposite statement: "after a loss on the day, no max size" (010 ~49:51).
- C8. New traders: paper 6 months at realistic size, then 1 micro; ~70% consistency first; drill =
  1 contract, 5-handle risk for 5-handle target (048 ~2:25:35; 042 ~4:49).

### D. Pyramiding / adds
- D1. Sizes decrease: largest first, smaller adds, never a larger add [2023] (006 ~51:52: 6,3,2,1;
  021 ~20:03: 6,3,1, aggressive 6-4-2-1; 050 ~50:05: 6,3,1; 060 ~1:03:00; 026 ~1:44:04: 6 at VI,
  3 at next VI, 1 at wick CE; 083/085 [chart]: 5,4,3,2,1; 009 [chart]: 8, +4, +2).
- D2. If price closes into the FVG instead of rejecting it, add once more at its low end, same size
  as the smallest add [2023] (006 ~51:52).
- D3. Where to add [2023]: retests of new FVGs that hold (003 ~44:20); down-close candles into a bullish
  OB/VI, near the OB MT (009 ~12:07); breaker retests (001 ~44:00; 063 ~28:37); IFVG (083 [chart]);
  next VI (026, 085 ~30:08); lower SIBI by limit (069 ~16:08); mohawk fills (102 ~1:14:30).
- D4. No adds after partials have been taken [2023] (006 ~53:53).
- D5. No adds past equilibrium [both]: stop adding once price passes the 25% line of the displacement leg
  (022 ~49:26); no pyramiding past halfway of the discount half (025 ~47:56); no adds below EQ of the
  implied dealing range (092 ~1:15:24); no adds above EQ of the anticipated range near target (045
  ~1:51:09); adds only while not yet in premium (058 ~43:12); shorts only above EQ of the leg
  (060 ~1:23:00).
- D6. Limit to one add in a plain bullish version: long at the sweep, one add on the FVG retrace, hold
  (031 ~52:22) [2023].
- D7. No pyramiding on NFP (105 ~9:13) or low-probability/decoupled days (045 ~1:01:43) [2023].
- D8. CC adds: start ~half size and build on returns to the same candles (cc05_016 ~13:17); re-add the
  partial size at 50% of the objective after a short-term dip (cc06_008 ~16:20); re-add removed
  partials when price returns to the same open (cc05_016 ~4:37); buy every 4H discount array in the
  impulse range (cc06_003 ~21:43); pattern-3 add at the breaker after a turtle soup, e.g. 20 + 10
  (cc12_004 ~33:23).

### E. Partial profits
- E1. Scale out at each liquidity pool; "running down equity" = take a piece at every new high (long)
  [both] (003 ~1:04:25 one contract at a time; 027 ~43:36; 041 ~1:45; 063 ~26:23 once ~3/4 to
  objective; 065B ~03:07; cc03_003 ~25:06; cc02_003 ~3:36; 071 ~9:13 resting limits at FVG far edge,
  under it, at sell-side).
- E2. Bulk at the first liquidity target [2023]: 10 of 12 (006 ~33:20); plan 9 of 14 (009 [chart]);
  80% at NWOG CE (020 ~4:40); 80% at first threshold on slow/news-ahead days, 50% on normal days with
  25% at CE and 25% runner (036 ~1:01:00); ~80% before the ideal target (102 ~1:31:00); ~80% at the
  consolidation low target (104 ~47:27); 80% off if ADR is reached before 10:00 (cc09_006 ~19:33).
- E3. Smaller first partials also used [both]: 5 of 14 (018 ~4:37); 1/3 at swing projection (041 ~1:16);
  4/2/4 layered limits at NWOG high/75%/CE (057 ~7:35); half at 1R (cc02_001 ~23:16); half at 3R
  (cc02_003 ~2:57); 20-30% at 1/4 of the objective (cc06_008 ~16:20); always something at +20-30 pips
  (cc08_007 ~16:32 [fx-only]); 75-80% after four projection levels fill (cc09_002 ~6:39); 60-80% by the
  5-day ADR projection (cc08_007 ~17:25).
- E4. Mandatory partial levels: a little before the CE of any wick inside the trade's path, "always, without
  exception" (065A ~2:37:30; 065B ~03:52:40; 105 ~9:00); the -0.5 SD projection is always a first
  partial (064 ~1:33:48); most off at -1 SD, flat or tiny runner at -2 SD (065B ~03:03:40); next partial
  halfway between the hit target and the next (026 ~14:57) [2023].
- E5. Full pull (no partials) is allowed in a low-resistance run (fast, nothing in the way) and is a
  stated one-off in 089 ~8:46; take partials in a high-resistance run (102 ~2:15:30); partials only if
  the low breaks without "speed and distance" (092 ~1:28:54) [2023]. Examples: 001 single exit,
  066 full exit, 076 no partials, 085 ~22:24.
- E6. Bank a partial when an SMT/sympathy warning appears: ~50% when the sister index refuses to break
  (046 ~1:02:40); most off and trail when YM diverges (037 ~32:56) [2023].
- E7. Aim to capture 80-85% of the best-case run, scaling out in the 85-100% zone, while price still moves
  your way (013 ~29:22) [2023]. Day trade: aim for 65-70% of the daily range (cc08_001 ~1:53) [CC].

### F. Trailing stops and breakeven
- F1. Breakeven timing, majority view: only after the first partial and after price has expanded
  [both] (032 ~58:19; 046 ~1:22:00; 036 ~42:40; 105 ~10:41 BE + commissions + a little;
  cc06_008 ~16:20 "never before"; cc02_001 ~24:46 after 2R; cc08_007 ~13:57 not before 40-50% of ADR).
- F2. Earlier BE seen in 2023 examples: right after the MSS above short-term highs (003 ~40:15 [chart]);
  when price stalls ("risk removed, free look") (009 ~09:46 [chart]); once on side (020 ~2:12); after
  new sell-side is taken (042 ~55:08 [chart]).
- F3. Trail to structure [2023]: under the first breakaway/protected FVG after the shift (003 ~42:40;
  062 ~37:02); under the measuring gap after two partial rounds (003 ~1:05:00); under each newer FVG
  after each partial (002 ~8:00 [chart]); to a VI low (009 ~10:00); beyond MT of the last up-close
  candle, then above smooth highs, then the rejection block on a closing basis (071 ~14:42-36:57);
  under the breaker low once the structure high breaks (096 ~4:35); after the 80% partial, roll the
  20% runner to the leg's equilibrium, at least BE (036 ~1:01:20); runner stop at half the open profit
  (065A ~2:56:30); trail under the latest swing low at a key level (060 ~1:15:00).
- F4. Don't trail early [2023]: a new FVG may be revisited (029 ~43:40); never trail into or just under
  an FVG created right after an MSS (085 ~19:59); trailing too soon is the main error (085 ~26:46);
  keep the stop below the IFVG so limit adds still fill (067 ~1:19:00); trailed AM stops get run at
  lunch (064 ~1:45:41).
- F5. Day trade vs session trade: a day trade keeps its initial stop (below the 08:30 open / 08:30 wick
  CE) untrailed and pays itself with partials; session trades trail (064 ~1:38:44) [2023]. Position
  trades: no BE early; trail beyond the 40-day (later 20-day) extreme (cc05_018 ~5:52; cc05_013 ~17:36) [CC].

### G. Minimum reward:risk / framework
- G1. Index day trades: the setup needs ~10 handles of room to the draw while aiming to take 5 (5.25 to
  cover costs) [2023] (024 ~25:26; 046 ~32:40; 054 ~0:36 "framework" = best-case delivery, not
  entry-to-exit; 058 ~37:16; 059 ~10:36; 060 ~50:00). Experienced traders may take 5-handle moves
  without it (046 ~34:00). Minimum 4-5 handles (072 ~35:11); >5 handles to the pool (044 ~57:16).
- G2. Scalps are ~1:1 (042 ~4:49 drill; cc09_006 ~3:54; cc09_007 ~3:20) [both].
- G3. CC swing/day frameworks: >= 3:1, aim 5:1 (cc02_004 ~1:51; cc05_013 ~8:21; cc06_002 ~12:34;
  cc06_003 ~22:25 3x to the closest opposing array on any timeframe; cc06_006 ~7:03); look for 3R+
  (cc02_001 ~5:22). Breakeven win-rate table (1-w)/w (cc02_001 ~7:40).
- G4. Skip if the target pool is too close: a second gap just above a liquidity pool is not a target
  (060 ~1:10:30) [2023].

### H. Targets
- H1. Target = the next opposing liquidity (relative equal highs, old highs/lows, PDH/PDL, session
  highs/lows, 3-day liquidity matrix) or the next opposing PD array (FVG, NWOG, ORG, OB) [both]
  (001; 006 ~33:20; 010 ~65:54; 067 ~0:12:00; cc04_002 ~10:00 enter IRL, exit ERL; cc04_011 ~6:42).
- H2. Exit before PD-array targets: 0.5-1 pt before an FVG edge (010 ~58:50); near edge of the hourly FVG,
  not its middle (049 ~5:37); a couple of ticks before the level (063 ~29:41); one tick short (030
  ~24:24); first limit at the old high, next at the SIBI bottom less one tick (037 ~51:12); 80% 1-2 ticks
  before (102 ~1:31:00); 0.25-1.5 handles before (070 ~1:05:36); before an opposing OB (cc01_004 ~36:31;
  cc01_006 ~23:13; cc03_004 ~12:22); exit ~10/15 pips before projections/ADR (cc12_004 ~18:54;
  cc09_007 ~16:11 [fx-only]); round number ahead of the level (cc09_002 ~26:36) [both].
- H3. Exit beyond liquidity-pool targets: one tick below the low for sell-side (050 ~55:20); 0.75-1 pt
  above BSL (083 [chart]); just through REH (001 [chart]; 006 [chart]); partial 1 handle above REH
  (007 ~19:25); allow ~3 handles below a sell-stop pool (059 ~20:38); limit a tick or two beyond to get
  filled (105 ~1:27:00); runner limit at the HTF level plus a couple of handles (099 ~37:51); level +
  0.25 for fees (018 ~2:50) [2023].
- H4. FVG/gap gradients as staged targets: low, 25%, CE, 75%, high; CE is the default session objective
  (029 ~30:44; 055 ~4:50; 091 ~23:31; 101 ~51:58); CE of a weekly gap is enough, far edge is the
  "ringer" (061 ~2:30:15) [2023].
- H5. SD projections as targets [both]: anchors and multiples vary (see Conflict 9). Examples: first SD
  beyond the BSL from several swing lows, cluster = turning point (014 ~2:54); -1/-2 levels must lie
  beyond the pool (030 ~23:31); breaker A-B +1 SD (070 ~37:31); measuring gap -1 SD (062 ~42:19);
  -2/-2.5/-3 on the manipulation leg (092 ~1:21:26); fulcrum -0.5/-1 (090 ~1:29:01); ORG multiples
  (055 ~19:30; 056 ~17:10); CBDR/Asian/flout "four numbers" (cc08_003; cc08_004; cc09_002).
- H6. 5-day ADR as the day's extreme / exit filter [CC] (cc08_001 ~2:13; cc09_006 ~19:23; cc09_007 ~8:32).
- H7. Session target windows: AM objective by 10:30-11:00, PM by 15:00-16:00; target sits at a 15m-60m
  PD array (cc10_014 ~1:32, ~4:15) [CC].

### I. Time-based exits
- I1. Flat before 16:00; don't hold past the close (027 ~58:22); be fully flat once the day's final level
  is hit (026 ~1:24:30); no setup by 10 min before the close -> no trade (001 ~1:00:01) [2023].
- I2. If the target hits by 15:00, be done; the last hour retraces (006 ~41:45) [2023]. MOC: liquidity
  taken before 15:50 -> small flurry then pullback (027 ~50:40); don't add/fade in the last ~15 min
  (026 ~1:59:50).
- I3. AM positions: take the last unit off before noon (lunch retrace) (003 ~1:12:15); close bulk from
  10:00-11:00 (cc12_004 ~8:25); if AM fulfilled the day's range, flat before lunch and skip PM
  (cc10_007 ~9:05); consolidation days done before 11:00 (cc10_008 ~16:59) [both]. Day traders exit by
  14:00 (cc03_001 ~13:12) [CC].
- I4. Session objective hit -> close everything and stop for the day (029 ~1:03:57; 040 ~0:39) [2023].
- I5. Time stops [2023]: price must reach the next reference within 2-3 one-minute candles or cut it
  (022 ~1:43:27; 031 ~24:29); a 1m trade should show movement within ~10 min (025 ~17:17); after
  touching the SIBI far edge, 2 minutes to move back or take half/all off (092 ~1:11:05); after an
  immediate rebalance, expansion on that candle or the next, else exit (092 ~1:41:14); target expected
  "this candle or the very next" (071 ~32:41).
- I6. CC hold-to-time rule: AM trade hold to 10:30-11:00; PM trend trade hold to 15:00 bond close,
  ideally 16:00; consolidation-profile PM exit ~14:00 (cc10_014 ~3:01, ~13:17) [CC].
- I7. No positions across the 17:00-18:00 break or the weekend (101 ~4:27; 103 ~9:31; 065A ~1:40:30) [both].

### J. In-trade abort and drawdown rules
- J1. Abort an FVG entry before the stop: a candle body closes beyond the FVG against you, and the next
  candle trades beyond that candle's extreme -> close for a small loss (045 ~1:19:58) [2023].
- J2. Three PD arrays: if price breaks ~3 successive PD arrays against the trade, close or reduce before
  the stop (026 ~28:02; 027 ~38:26; 078 ~1:02:38; 098 ~47:00 daily-close version); body close below
  the nearest VI + FVG + OB MT -> take half off (045 ~1:49:28); bodies digging into the named OB ->
  exit manually (105 ~1:21:06) [2023].
- J3. Offside test: short should smash through a down-close candle below; if bodies respect its open
  and trade back above, close (085 ~11:18) [2023].
- J4. Exit when price retraces through the MT of the up-close candle that started the leg (026 ~28:28);
  exit an immediate-rebalance short if price retakes the range EQ (100 ~1:37:18); exit when bodies close
  through a bullish FVG's CE (030 ~15:46); propulsion block MT lost -> wrong (cc04_008 ~5:15) [both].
- J5. Uncertain or lethargic mid-trade: cut half; at minimum size, close (100 ~1:02:17; cc03_003 ~13:18);
  lose focus -> close (102 ~1:34:00); meanders in the SIBI instead of rejecting -> close (092 ~1:04:38)
  [both].
- J6. Session stop: three PD arrays in a row fail -> stop for the session (044 ~1:52:49); out of sync ->
  stop after the first profit (081 ~18:58); no re-entry after a winner on the day (095 ~47:08); a few
  trades a month / ~3 per week / one good setup per week (003; 095 ~49:28; 099 ~47:36) [2023].
- J7. Week/month stops: weekly objective delivered -> done for the week (038 ~6:33; 101 ~34:21); Friday
  after all targets met -> no trade (100 ~7:05); August drawdown -> wait until September (079 ~25:43)
  [2023]. Two consecutive failed with-trend signals = trend tiring (cc06_001 ~8:51) [CC].

### K. Reversal and re-entry after a loss
- K1. Lose in the AM -> do not reverse; stop for the morning, wait for PM. Firm for new traders, "never"
  for funded accounts, experienced traders sometimes reverse [2023] (001 ~46:57-48:43).
- K2. Same-direction re-entry is allowed when the idea is intact: next sub-1m signal (060 ~1:22:30);
  same size at the IFVG CE (085 ~27:21); half size (070 ~38:41; cc02_005 ~4:49; cc06_003 ~23:24 next
  array at 50%); short again at the FVG bottom with stop above the high (104 ~45:41); after a valid
  monthly/weekly stop-out take the next setup (cc06_005 ~30:42) [both]. Exception: FOMC, don't re-enter
  if stopped (021 ~43:56).

### L. Journaling/review rules that imply code
- L1. After each close, record how the day traded against the last 3 days' highs/lows (cc09_005 ~14:22;
  010 ~65:54) and each day's range vs the 5-day ADR (cc08_006 ~23:42) [both].
- L2. Log which weekday and kill zone made each weekly high/low (cc01_003 ~16:36) [CC].
- L3. Keep a sorted level list; mark a level done once traded and move to the next (028 ~54:55;
  045 ~6:38; 105 ~29:59) [2023]. Label each PD array with its source timeframe (078 ~27:00).
- L4. Note "day before FOMC/news" conditions in the journal (042 ~3:50) [2023].

## 2. Conflicts

1. **MT for OB stops: body vs full range.** Body: 009 chart (stop under body MT; full-range MT would be
   above the stop), 026 ~58:05, cc04_003 spoken ~9:38, cc04_008 spoken ~1:27, cc06_005 ~5:45, cc07_004
   ~10:02 (6 sources). Full range with wicks: 002 ~3:45 (Ep 02), cc04_003 slide ~2:00, cc04_008 drawing
   ~6:20, 065A ~1:20:40 (4). His only live stop example (009) follows the body. **Default: body MT; test
   full range.** `levels.order_block` currently returns high-low.
2. **FVG entry price: near edge vs CE vs IOFED.** Edge/one tick in: 001, 018, 042, 054, 057, 066 (live
   fills, 6). CE: 007, 024 ("highest probability"), 048 "worst case", 030 ladder (4, mostly words).
   His fills follow the edge. **Default edge (current), test CE and edge+1 tick.**
3. **Limit vs market vs stop orders.** 2023 entries are limits (A1); adds at market; CC uses stop
   orders for breakers/FVGs (cc06_008) and market entries for scalps (cc09_006). **Default limit;
   alternative: stop-entry above the down-close candle (cc10_011).**
4. **First-partial size.** Bulk 80-90% (006, 020, 036 slow days, 102, 104, cc09_006: 6) vs ~half or
   less (036 normal days, 018, 041, 057, cc02_001, cc02_003, cc06_008: 7). Examples split. **Default
   0.5 (current); test 0.8.**
5. **Breakeven timing.** After first partial / after expansion (032, 046, 036, 105, cc06_008, cc02_001,
   cc08_007: 7) vs right after MSS or when stalling (003, 009, 020, 042: 4, all chart examples).
   **Default: BE after T1 (current); test BE after MSS-confirming new high.**
6. **Exit before vs beyond a level.** Before: FVG/PD-array targets (H2, ~12 sources). Beyond: liquidity
   pools (H3, ~9 sources). One exception: 063 exits 2 ticks under an old high. Reconciled by target
   type. **Default: PD-array targets -0.5 pt (current), liquidity targets +1 tick beyond; test uniform
   -0.5.** 018 calls its exit "level + fees" but it sits inside an FVG.
7. **Pyramid order.** Decreasing (D1, 7 sources incl. live fills) vs increasing 1, 3, 6 when entering
   early in a breaker leg (070 ~36:21) and 067's later buys at higher prices [chart]. **Default
   decreasing (0.5, 0.33, 0.17).**
8. **Hold into the close vs done by 15:00.** Done by 15:00 if target hit (006); flat before 16:00 (027);
   day traders out by 14:00 (cc03_001) vs hold PM trend to 15:00-16:00 (cc10_014) and exit ~14:00 only on
   consolidation days. **Default: flatten 16:00 with exits at targets (current); test a 15:00 hard exit.**
9. **SD projection anchor.** Down-leg into the low (014), sweep low to leg high (bot, Ep 06 wording),
   swing high to broken low (047), manipulation leg (092), breaker A-B (070), high to measuring-gap edge
   (062), trigger swing (065A). 014 is the only multi-example quant study. **Default off as targets;
   test 014's "first level beyond the pool" from the down-leg.**
10. **Reversal after a loss.** No reversal (001, kept by bot) vs same-minute flip when offside (083/085,
    094) vs stop above breaker = switch to long bias for the day (042). The flips are small-size and
    discretionary. **Keep no-reversal; test "flip once if the stop-out is in the HTF draw direction".**
11. **Risk %.** 1-1.3% (009), 2.1% (003), 0.5-1% scalps (cc09_006), 1% of a 30% base (cc05_013),
    up to 5% near HTF targets (102). **Default 1% (current).**
12. **Minimum R:R.** 1:1 index scalps with a 10-handle framework (2023, 6 sources) vs >= 3:1 (CC
    swing/day, 6 sources). **Default min_rr 1 plus a 10-pt framework filter; test 2-3.**
13. **Partials vs full pull.** Scale out at each pool (E1) vs full pull in low-resistance runs (E5).
    **Default scale; full pull is too discretionary to switch on automatically.**
14. **Trailing.** Trail under each new FVG (002, 003, 071, 083) vs never trail into a fresh post-MSS FVG,
    day trades untrailed (029, 064, 085). **Default trail off (current); test trailing only after T1 and
    only under FVGs older than the MSS leg.**
15. **No adds after partials (006) vs re-add at 50% of the objective (cc06_008, swing).** Keep the 2023 rule.

## 3. Bot implications (strategy.py / levels.py)

Already matching: limit at FVG edge with strict trade-through fill; cancel if the target trades before
fill (matches 057); one AM + one PM trade; no opposite-direction trade after a loss (001); stop to
breakeven after T1 (majority BE rule); adds only before T1 and capped at 2% total risk (006, 003);
flat by 16:00; 1% risk sizing.

Change / add (each as a Params switch so it can be measured):
- `mt_mode` = body|range in `order_block`/stop calc; default body (Conflict 1).
- `exit_mode` per target type: liquidity levels (pdh/pdl, pmh/pml, rel-eq, am session H/L) exit
  1 tick (0.25 ES pt) beyond; NWOG/FVG targets keep `exit_before_pts` (Conflict 6).
- `partial` test 0.8; `t1` should be the first liquidity pool, T2 the next (already).
- `adds` default (0.5, 0.33, 0.17) and an equilibrium cutoff: no add once price is past 50% of
  entry-to-final-target (D5). Optional D2 add at the FVG low end when a body closes into the FVG.
- `min_draw_pts` = 10: require the farthest qualifying target >= 10 ES pts from entry even if T1 is 5
  (G1). Current min_rr only checks T1.
- Abort rule J1 (body close beyond far FVG edge, then next bar beyond that bar's extreme -> market exit)
  and time stop I5 (no progress of >= X pts within N 1m bars -> exit). Both codeable.
- `am_exit` time (test 11:00, 12:00): close AM leftovers before lunch (I3). Optional `pm_hard_exit`
  15:00 (Conflict 8).
- `be_mode` = after_t1 | after_mss; `trail_mode` = off | fvg_after_t1 (Conflicts 5, 14).
- `loss_halving`: next trade's risk 0.5x after a loss until a win (C7). Optional `skip_pm_after_am_win`
  (cc10_007; 065B "if the AM wins skip the PM").
- `stop_pad_pts`: currently 0.01 SPY ~0.1 ES pt; test 1 tick vs 3 pts (B5).
- Stop beyond all inefficiencies under the entry (B3): take the min of the OB MT and the lowest FVG low
  in the leg below entry, within `max_risk_pts`.
- Logging (L1-L3): record day range / ADR5, which of the last-3-day highs/lows were taken, and the
  timeframe of the entry array on every trade.

Too discretionary to code as stated: "speed and distance" / lethargic delivery (no threshold);
low- vs high-resistance run (could proxy by count of opposing FVGs/swings between entry and target);
"offside" read (J3 is partly codeable); capturing 80-85% of the best case (E7); choosing which wick
CE matters (E4); full pull vs partials (E5); weekly-objective "done for the week" (needs a weekly
draw model first); sentiment and COT-based sizing.

## 4. Open questions
- MT: body or full range when the OB is several candles (bodies-only per cc06_005)?
- Stop: OB MT vs FVG candle vs sweep extreme. No single rule; examples differ by setup. Which to use for
  the Silver Bullet (never stated in 044-059)?
- How many ticks is a "mohawk" (B4) and how much padding beats it (1 tick vs 3-4 handles)?
- Bulk partial fraction: 50% or 80%? And what fraction at a wick CE ("a little")?
- "Expansion" before BE: how many points/what fraction of the target?
- Time stops: 2-3 candles (022/031), ~10 min (025), 2 min after far-edge touch (092). Which window and
  what counts as "progress"?
- 10-handle framework: measured to the first pool, the final draw, or the best-case run through it (054)?
- SPY mapping: 1 ES tick (0.25) is ~0.025 SPY, below SPY's 0.01 tick resolution in practice; use
  $0.02-0.03 for "one tick beyond"?
- Risk after a loss: halve until the next win, or until the loss is recovered (cc02_005 unclear)?
- Same-direction re-entry after a stop: allowed in the same session (060, 085) but the bot blocks it.
  Test one re-entry at half size?
- Contract caps (6 then 10-16) for SPY share sizing: use a max-notional cap only, or a cap on adds count?
- "Done by 15:00 if target hit" vs "hold PM to 16:00": does it depend on day profile (cc10_013/014)?

## Five most important findings for the bot
1. Stop MT: ICT's only live stop example (009) sits under the **body** midpoint of the sweep candle;
   `order_block().mid` uses high-low. Add `mt_mode`, default body.
2. Exit placement depends on target type: exit **before** FVG/PD-array targets but **1 tick beyond**
   liquidity pools (old highs/lows, equal highs/lows). The bot exits 0.5 pt before everything, which
   misses pool fills.
3. Index entries need a ~10-handle "framework" to the draw while taking ~5 (6 sources); the bot only
   checks T1 against `min_rr`. Add `min_draw_pts`.
4. Pyramiding: decreasing 6/3/2/1 sizes, no adds after partials, and **no adds past equilibrium** of the
   entry-to-target range (5 sources). The bot has the first two; add the EQ cutoff.
5. Cheap codeable exits ICT uses live: the FVG abort (body closes beyond the gap, next bar exceeds it),
   a short time stop (2-3 bars / ~10 min without progress) and closing AM leftovers before lunch. Test
   each as a switch; also test 80% first partial vs the current 50%.
