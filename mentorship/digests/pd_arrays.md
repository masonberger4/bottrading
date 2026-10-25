# Digest: PD arrays and structure (pd_arrays)

Sources: all 218 notes (001-105 = 2023 playlist, cc01-cc12 = Core Content 2016-17),
mentorship_rules.md, strategy.py, levels.py. Tags: [2023] / [CC] / [both]; [chart] = only
visible on charts; [fx-only] / [bonds-only] = does not transfer to ES/NQ. "c1/c2/c3" = the
three candles of a gap, oldest first. "Body" = open..close; "range" = high..low.

## 1. Rules (codeable definitions)

### 1.1 Fair value gap (FVG), BISI, SIBI, consequent encroachment
- **Definition.** Bullish FVG (BISI) at bar i: low[c3] > high[c1]; zone = [high[c1], low[c3]]. Bearish FVG (SIBI): high[c3] < low[c1]; zone = [high[c3], low[c1]]. Known at the close of c3. c2 is the displacement candle (up-close for a BISI, down-close for a SIBI) (001 ~13:02; 024 ~23:22; 026 ~1:59:24; 056 ~6:08; 078 ~13:51; cc04_012 ~1:52-4:46) [both].
- **Five levels, not a zone:** high, low, CE = (high+low)/2, plus 25%/75% quadrants on gaps large enough to matter (he skips quadrants on small gaps) (020 ~8:21; 021 ~21:06; 029 ~30:44; 030 ~15:46; 055 ~4:50; 061 ~30:04; 090 ~2:11; 101 ~51:58) [2023]. CE is the default session objective of a higher-TF gap (029 ~44:48).
- **Extend the box over an adjacent volume imbalance** (draw "through the candles" to the body gap) (022 ~55:00; 095 ~4:10; 098 ~60:00; 099 ~26:00) [2023]. A body gap inside the FVG gives the exact limit price (cc04_012 ~12:27) [CC].
- **Expected reaction depth.** Retrace into a BISI most likely stops at its top or CE; the far edge is least likely (022 ~9:09). Bullish: price should hold the upper quarter; close the trade early once bodies trade through CE (030 ~15:46). Bearish: the upper half of a new SIBI should stay open, reaction at 25% or 50% (092 ~59:47) [2023].
- **Institutional order flow entry drill (IOFED):** entry on a partial fill that does not reach CE (003 ~30:30; 029 ~47:49; 047 ~10:29; 056 ~5:44; 091 ~3:07); operational versions: 1 tick past the gap edge (006 ~50:09), touch of the c1 extreme or 1 tick beyond (024 ~23:43), touch of the candle that created the gap (010 ~47:38) [2023].
- **Validity.** Needs a close, a new candle's open, then a trade back into it without first taking the low (042 ~34:53). Not every 3-candle gap counts; it must sit on the path to the draw (048 ~28:06; 091 ~14:27) [2023].
- **State machine.** Touching the edge = "repriced"; "rebalanced" only after price trades through and leaves (021 ~12:28; 032 ~51:23; 050 ~30:29). "Filled" counts only when bodies trade through; wicks alone do not (cc10_011 ~4:29; cc04_012 ~13:08) [both].
- **Abort on an FVG entry:** a body closes beyond the far edge, then the next candle trades beyond that candle's extreme -> exit before the stop (045 ~1:19:58) [2023].
- **Two FVGs in the leg:** allow the retrace into the higher (second) one (042 ~47:20; 082 ~5:31); stop beyond the higher one (025 ~55:15) or just above its CE (069 ~13:46) [2023]. Skip an FVG sitting right above a liquidity pool (060 ~1:10:30).
- **Gap hierarchy** (062 ~43:58) [2023]:
  - Breakaway gap = first FVG leaving a consolidation/expected level after an MSS; must stay at least partly open; may retrace to at most half, less if a BPR sits under it (001 ~40:03; 002 ~4:35; 061 ~1:20:51; 062 ~37:02; 065B ~4:39:20; 075 ~58:00). Fully filled = not breakaway (062 ~37:57).
  - Measuring gap = FVG near the 50% of the implied range; project: fib swing extreme -> near edge of the gap, target -1 SD (003 ~31:35; 011 ~6:37; 061 ~1:22:05; 062 ~42:19). Lower half left open = breakaway, then use as measuring gap (084 ~28:58).
  - Common gap = ordinary FVG, may be revisited repeatedly (062 ~34:53).
- **Immediate vs deferred rebalance:** next candle trades straight back to the prior candle's extreme leaving no gap = immediate rebalance, a strong continuation signature; an FVG is a deferred rebalance (048 ~39:02; 060 ~7:20; 072 ~6:02; 078 ~1:14:47; 092 ~1:41:14; 099 ~3:46; 100 ~44:54) [2023].
- **Lifetime/reuse:** extend gaps forward; reuse after fills; 60-day lookback (015 ~22:49; 047 ~6:31; 051 ~19:34; 065B ~3:58:20; 095 ~34:30) [2023]. Weekly gaps can be invisible on the daily; draw from the higher TF and the actual contract, not the continuous chart (056 ~1:08; 068 ~1:44; 074 ~7:00) [2023].
- **FVG beats an overlapping OB:** first target is the near FVG edge, not the OB MT (065B ~3:02:40) [2023].
- **Body test across 1-4m:** only wicks inside the FVG, bodies outside -> continuation (064 ~1:30:49) [2023].

### 1.2 Inversion FVG (IFVG), reclaimed FVG
- **Definition:** an FVG that price trades through **and closes beyond**, then acts in the opposite role (015 ~21:00; 045 ~2:35:15; 059 ~3:47; 061 ~19:42; 067 ~1:18; 072 ~8:31; 078 ~53:07; 102 ~1:02:03) [2023]. 1h/daily IFVGs used as HTF levels (084 ~11:57; 093 ~1:41).
- **Entry protocol:** a candle closes beyond the gap, a NEW candle opens and trades back into it, the gap holds; a spike through and back inside does not count (048 ~21:32-22:00, ~36:40) [2023].
- **Allowed depth** depends on prior use (102 ~1:09:00-1:14:20): one pass only -> may reach the far edge (+ small mohawk); a later wick already entered part of it -> stop between near edge and CE; traded both ways -> near edge, CE at most. Bearish IFVG retrace usually CE or a bit above, rarely the high (078 ~50:28). 15m bodies must not close back through, else it reverts (084 ~12:00).
- **Stop:** just above CE padded 3-4 ES handles (102 ~1:40:20).
- **Bias switch:** same 1m gap is a long target if the HTF array is not yet reached, an IFVG short once it is (086 ~14:12) [2023].
- Ma Deuce model: bullish 1m FVG in the premium of a daily BISI, broken down; sell its retest only after an 08:00 time gate (091 ~19:02) [2023].
- Reaper IFVG: FVG in the discount half of a bullish breaker's impulse leg, cut through on the way to the lower low, later support at its CE (076 ~18:30) [2023] (discretionary).
- Reclaimed FVG: price breaks above a gap, returns, it holds (026 ~1:09:00; 030 ~1:03:52; 091 ~20:11). Every PD array has an inversion use (068 ~13:39; 035 ~1:02:51) [2023].

### 1.3 Implied FVG
- Named once: "CE of two wicks projected out" (035 ~29:49) [2023]. No definition anywhere else. Not codeable from the notes.

### 1.4 Liquidity void
- Three definitions in use (see Conflicts C4):
  - **True gap** between candles, no price overlap: high[i-1] < low[i] (or the reverse) (001 ~13:02; 003 ~32:50; 019 ~12:40; 077 ~1:59) [2023]. ICT later says the real void is a session/week opening gap with no prints, and a one-sided candle is really a SIBI/BISI (028 ~36:17; 030 ~37:20; 039 ~3:06; 060 ~1:09:40; 068 ~8:24; 074 ~20:51) [2023]. The no-trade sliver between close and next open inside a VI = the void "sweet spot" (061 ~1:55:43).
  - **One-sided range**: the span of consecutive long one-sided candles leaving a consolidation; expected to be fully covered later; fill target = the start of the leg / consolidation edge (cc01_001 ~14:58; cc01_006 ~3:13; cc04_010 ~0:58-6:51; cc04_014 ~3:18; cc06_003 ~2:08) [CC]. Its equilibrium is measured on bodies (cc04_004 ~10:17). On a lower TF a higher-TF FVG appears as a void (cc04_012 ~5:22).
- Voids/FVGs inside a held range get filled ("gap risk") (cc04_002 ~1:40) [CC].

### 1.5 Volume imbalance (VI)
- **Definition:** consecutive bodies do not overlap (not even equal) while wicks overlap; bullish: min(o,c)[i] > max(o,c)[i-1] and low[i] <= high[i-1] (003; 009 ~2:16; 019 ~13:02; 022 ~54:26; 035 ~5:50; 090 ~13:01; 095 ~7:01; 100 ~1:29:27) [2023]. Called a "micro FVG" (050 ~26:43). Can span more than two candles (036 ~22:30). Weekly VI counts even with overlapping wicks (077 ~2:40).
- **Use:** stop at its low; price may touch either edge but not pierce (009 ~13:46); CE as level when not an OB (045 ~2:47:29). VIs are "flexible" (price may chop through), FVGs strict (027 ~22:09); clusters = "porous" price, low trust (027 ~27:38).
- **Rebalanced/dead:** a later body closes fully across it, on the highest TF it formed on; wicks and lower-TF bodies do not count (035 ~5:50; 046 ~22:40; 090 ~13:01). Rebalance needs 1 tick beyond the earlier close (050 ~33:20). A VI can act as a breakaway gap (079 ~14:20; 103 ~25:18) [2023].

### 1.6 Opening gaps (NWOG, NDOG, ORG) and vacuum block
- **NWOG** = Friday 16:59 ET close to Sunday 18:00 ET first tick; high/low labelled by direction; CE = midpoint; optional 25/75% (020 ~4:00; 026 ~12:50; 039 ~0:57-6:40; 050 ~13:20; 051 ~5:38) [2023]. Monday variant: Friday close to Monday 09:30 open (039 ~14:41). Sunday open alone is a level for the week (051 ~3:01; cc08_001 ~22:58).
  - Keep >= 5 (039 ~3:49) up to 60 days (051 ~18:00); filling does not end them (039 ~5:26; 050 ~13:20). Holiday-shortened week: use the nearest normal NWOG (046 ~16:01; 048 ~2:54).
  - Regime: price keeps returning to the current NWOG = consolidation, scalp; leaves and never returns = trending week (025 ~3:01; 030 ~10:17; 039 ~12:26; 051 ~9:25). Halfway rule: reaching 50% of the space between two NWOGs (near edge to near edge) -> expect the next one (037 ~22:46; 051 ~16:51).
- **NDOG** = 17:00 ET close to 18:00 ET reopen, Mon-Thu; levels high/low (+CE implied); ignore gaps <= ~1 handle (032 ~3:03; 033 ~3:24; 052 ~0:46-5:01) [2023]. Lifetime: rest of the week (052 ~5:03) or 5 trading days (068 ~9:49).
- **Opening range gap (ORG)** = prior RTH close to today's 09:30 open; levels high, CE, low (+quarters) (033 ~11:36; 042 ~11:20; 043 ~11:47; 069 ~10:06; 072 ~21:05; 092 ~1:55:54) [2023]. Gap down = "discount ORG", up = "premium ORG" (069 ~10:53).
  - Expect a reach back into it unless it acts as a breakaway (033 ~14:57); 09:30 volatility seeks the prior close (055 ~20:50); "repricing macro" after the Judas swing (069 ~14:50); first 30 min not attempting the close = very directional (030 ~1:27).
  - Fill variants: full, half, quarter; a quarter fill that holds = strength (036 ~53:00); half filled -> later move into the unfilled half (058 ~53:24); a breaker inside stops full closure (072 ~31:38). Projection in gap-size multiples (055 ~19:30; 056 ~17:10).
- **Vacuum block** = gap between the last close before a volatility event/session open and the first open after; treat as a candle with high/low/MT (cc04_009 ~3:58) [CC]. Partial fill can stop at a bullish OB inside the gap (higher of the two down candles before it), leaving a smaller FVG; full fill = back to the pre-gap up candle's close, which must then hold (cc04_009 ~7:03-14:26). Gap at 08:30/early NY likely fills same day; 10:00+ gaps tend to stay partly open (cc04_009 ~8:25).

### 1.7 Balanced price range (BPR)
- **Definition (codeable):** overlap of a bullish and a bearish FVG (single pass each way, 1-2 large candles); measured from the higher of the two candles' lows to the lower of their highs; midpoint = "equilibrium" (046 ~50:02; 065B ~4:21:20; 104 ~24:35) [2023]. Older wording: an FVG price has passed through both ways (001 ~15:01; 010 ~48:20; 026 ~1:58:05) [both].
- **Behaviour:** trading TO it is easy, THROUGH it rare; expect several probes (100 ~22:07); "brick wall" (046 ~50:02; 082 ~3:55); may be revisited to its MT (bodies), a return to the far edge means bail (026 ~1:05:53); a body close through the midpoint = abort (065B ~4:28:00). Stop can sit beyond it (075 ~54:20; 085 ~16:32) [2023].
- **Repriced vs balanced:** a single pass only reprices; balanced after price returns to the other edge, fails, and leaves (055 ~15:05; 056 ~7:24). A daily candle chopping inside a weekly FVG is not a BPR; HTF bodies must close across (061 ~40:26) [2023].

### 1.8 Order block (OB), mean threshold
- **Definition:** bullish OB = last down-close candle (or series) before the up move that breaks structure; bearish = last up-close candle(s) before the down move (002 ~4:14; 018 ~6:02; 043 ~18:23; cc01_001 ~12:15; cc04_002 ~10:00; cc04_003 ~0:35) [both].
- **Series = one OB:** consecutive same-colour candles blend into one block (029 ~29:28; 032 ~23:06; 033 ~1:03:02; 071 ~35:30; cc03_004 ~4:46; cc04_003 ~31:02; cc04_008 ~2:39) [both]. Reference = open of the first (highest for bullish) candle (032 ~52:45; cc05_015 ~16:46: highest open, or last open for a tighter stop). A small candle whose body sits inside a bigger one is not its own OB (cc06_005 ~19:02).
- **Levels:** bullish OB sensitive range = high down to open (012 ~5:13; 020 ~6:05; 071 ~35:37; 073 ~11:47; cc02_001 ~18:00; cc03_008 ~8:30); entry at the open/top of body (003 ~10:34; cc04_003 ~1:36; cc04_014 ~3:54); cc06_004 ~18:12: exact prices = high (fair) and open (conservative). Stubby wick -> use open; long wick -> low and wick CE (061 ~26:10; 055 ~1:44).
- **Validation:** a later candle trades above the bullish OB's high (cc04_003 ~0:35; cc03_004 ~14:13; cc02_002 ~6:13; cc03_007 ~22:13) [CC]; 2023 version: first trade through the open of the first down-close candle = change in state of delivery (CISD); the OB low must then hold (032 ~52:45; 075 ~1:16:40; 078 ~53:53) [2023].
- **Quality filters:** an FVG after it (022 ~13:12; 064 ~50:06; 084 ~19:14); larger body preferred (064 ~50:06; cc04_003 ~0:35); move away >= 2-3x the OB body height (cc04_003 ~26:51); when several down candles are run through, use the original/highest one (012 ~14:06); if one candle of the series sits inside an FVG, use the last one outside it (065B ~4:03); must sit where the narrative says (059 ~18:58; 065A ~1:12:00; 085 ~40:02; 102 ~1:42:05) [both].
- **Mean threshold (MT)** = 50% of the OB; bodies must not close through it, wicks may (002 ~3:45; 036 ~54:00; 104 ~49:40; cc02_004 ~3:28; cc03_002 ~4:58). Measurement conflict in C1. Daily: close below MT of the last down-close daily OB = high of week probably in (101 ~32:58); bullish flow intact only above the last daily bullish OB MT (058 ~6:01).
- After price trades through the MT of an opposing OB, its other half should not be revisited (065A ~1:39). An OB whose MT has been traded both sides is ignored for MT (cc09_008 ~14:37).
- **Stop:** below MT (009 ~4:17; cc02_001 ~22:02) or below the OB low / sweep low (cc02_005 ~4:49; cc04_003 ~10:39); short mirror above MT (022 ~59:02; 071 ~14:42).
- **Opposing OBs are targets/profit spots, not counter-trend entries** (cc01_004 ~36:31; cc04_003 ~24:49; 065A ~1:38) [both]. A newer, higher down candle moves the OB up (cc04_003 ~27:51).

### 1.9 Breaker
- **Bullish:** swing low L1, swing high H, lower low L2 (runs sell stops under L1), then price breaks above H; zone = the up-close candle at H (001 ~45:02; 006 ~48:01; 007 ~22:46; 012 ~11:07; 019 ~11:20; cc04_005 ~0:37-2:31) [both]. Bearish mirror: H1, swing low L, higher high H2, break below L; zone = down-close candle at L (007 ~0:12; 043 ~2:44; 056 ~12:35; 103 ~26:03; cc04_005 ~2:45-3:32).
- **Candle choice:** the highest up-close candle in the swing high, by body (029 ~24:13; 048 ~1:06:07; 096 ~6:42); highest close (032 ~39:52); biggest body/lowest close for bearish (081 ~11:48; cc09_008 ~9:59) [both].
- **Zone extent:** see C2 (body vs full range). MT = 50% of the zone, should not be closed through (018 ~1:22; 056 ~13:27; 070 ~56:01).
- **Entry:** first touch, even in the same candle, is valid (022 ~2:47:00); bodies respect, wicks may poke (033 ~57:56; 031 ~59:25); look for an FVG/VI inside it (031 ~1:02:02; 032 ~42:02). FVG inside breaker = **unicorn** (007 ~22:55; 101 ~84:31).
- **A-B leg:** use only the A->B leg; target B + 1x(B-A); may enter inside the leg before the break (070 ~35:00-47:46; 074 ~29:57; 076 ~16:36) [2023].
- A wrong-time high-low-higher-high is time distortion, not a breaker (070 ~6:24). If a candle closes beyond the zone, allow a reach into the next premium array but expect a close back inside (081 ~14:28).

### 1.10 Mitigation block
- **Bearish:** high A, swing low, LOWER high B (failure swing, no stop run above A), then break below the swing low; mitigation block = last down-close candle in that swing low; sell the return; zone = whole candle incl. wicks, stop above its high; bodies must not be violated on the retest (cc04_004 ~2:42-14:35) [CC]. Bullish: low, high, higher low, break of the high (033 ~1:03:50; 065A ~2:52:00) [2023].
- The **only** difference from a breaker is whether the swing ran stops (cc04_004; cc04_005; cc05_005 ~1:46) [CC]. "Breakers are mitigation blocks by default" (078 ~13:16; cc04_005 ~0:20).
- Weaker than a breaker, can be traded through; ICT uses it more as a target (075 ~21:40) [2023]. Nearest array to equilibrium in the PD matrix (cc05_014 ~7:33).

### 1.11 Propulsion block
- A down-close candle (bullish) that trades down into an earlier bullish OB; it becomes the new support; on return price should tag its high (1-2 ticks under) and leave; must not close through its MT; losing MT = idea wrong (cc04_008 ~0:30-5:40; 027 ~11:31; 019 ~10:03; 075 ~28:00; 079 ~10:27) [both]. Levels: wick high down to open (073 ~2:20; 078 ~29:14). Bearish mirror (cc04_008 ~5:45). A second candle going past the first's midpoint with an FVG nearby is more prone to fail (079 ~11:39).

### 1.12 Rejection block
- **Bearish:** swing high made by one or more long-upper-wick candles; zone = highest open/close of any candle in the swing (trigger) up to the highest wick; candle colour irrelevant; price only needs to trade above the highest body (no higher high) (cc04_006 ~5:04-10:43) [CC]. Bullish mirror: lowest open/close down to lowest wick (cc04_006 ~12:16).
- **Usage as a single level** [2023]: the highest up-close close before a high (015 ~2:15; 030 ~1:04:40; 066 ~39:31) or lowest down-close close at a low (059 ~9:20; 067 ~1:05:30; 080 ~5:41; 090 ~31:01); the level running the bodies does the same work as running the wicks (066 ~40:41; 059 ~10:03).
- Entry: sell limit at the trigger (stop above wick high) or sell-stop below the trigger after a probe above it (cc04_006 ~10:43-11:33). Target use: cover at the old low's lowest body, not the wick (cc04_006 ~14:14).

### 1.13 Reclaimed order block
- 2023 loose usage: price leaves an OB and returns into it as support (003 ~54:36; 006 ~50:03; 011 ~9:21) [2023].
- CC precise usage: in a market maker buy model, each down candle on the sell side of the curve followed by a small bounce; do not buy them on the way down; after the low, buy the return to them on the buy side of the curve (cc04_007 ~2:37-5:00) [CC]; sell model mirror; buy-side-curve arrays act as resistance on the sell side (104 ~46:56).

### 1.14 Market structure shift / BOS / change in state of delivery
- **MSS:** after a sweep, price breaks the swing low (high) that started the leg into the sweep, with displacement, leaving an FVG (002 ~2:37; 006 ~16:59; 022 ~38:38) [2023]. "BOS" is not a separate term in the notes; "market structure breaking point" (cc05_005 ~9:50) is the same point.
- **Wick vs close:** a wick/1-tick pierce counts, no close needed (012 ~30:30; 026 ~1:31:22; 030 ~20:06; 035 ~20:15; 075 ~33:20) [2023] vs body break (001 rules; 035 ~42:44 "close below = breaker") - see C3.
- **Which swing:** the swing that led to the high that ran liquidity / the parent swing, not a minor one (010 ~41:31; 058 ~41:15); a single short-term low break is "aggressive", with relative equal lows wait for the lower one (044 ~42:55); MSS need not take the most recent low if price already failed above the midnight open (069 ~14:41); relative equal lows need not be swept first (019 ~8:31) [2023].
- Two MSS, each leaving an open FVG = "on side" (006 ~49:16) [2023].
- **CISD:** first trade through the opening price of the last opposite candle before the MSS (075 ~1:16:40); an OB "is a change in the state of delivery" (032 ~23:06; 058 ~32:02; 064 ~50:06; 092 ~2:02:31) [2023].
- **Breaker swing vs failure swing:** the only two institutional turns; enter on the retest of the breaking point; stop beyond the swing that ran/failed at liquidity (cc05_005 ~1:46-25:40) [CC].
- **Confirmed high:** 3-candle swing high plus a following candle trading lower (cc01_004 ~9:44) [CC].

### 1.15 Swing points
- 3-candle pivot: middle candle high above both neighbours (012 ~30:08; 050 ~6:02; cc01_004 ~11:56; cc01_005 ~11:49: "not the 5-candle Williams fractal") [both].
- Hierarchy: STL = plain swing; ITL = low with a higher STL each side; LTL = low with higher ITLs each side (014 ~0:12; cc05_002 ~20:14) [both].
- Bodies mark the real level: relative equal lows/highs by bodies (075 ~34:00; 095 ~50:20; cc05_003 ~1:07:26); liquidity sits beyond the cluster of bodies, not necessarily the wick (cc02_008 ~9:03; cc03_002 ~2:01; cc05_004 ~13:35) [both]. A low whose bodies were not exceeded by later lows is the real pool (050 ~56:33).

### 1.16 Displacement
- Fast, large one-directional candles away from a level; leaves FVGs (cc01_004 ~6:13; cc04_003 ~0:04:37; cc06_003 ~4:39; 006 ~9:55 "caffeine bar") [both]. Only quantitative test: move >= 2-3x the OB body (cc04_003 ~26:51). "Speed and distance" through a trigger high (009 ~15:51); next candle should "rip" (027 ~33:57) [2023].

### 1.17 Premium, discount, equilibrium
- EQ = 50% of the dealing range; above premium (sell), below discount (buy) (022 ~48:15; cc01_004 ~10:26; cc01_005 ~3:47; cc05_014 ~17:34) [both].
- **Range choice:** the most recent impulsive swing (cc01_004; cc01_005 ~2:07); the energetic swing low, not a rounded bottom (044 ~40:11); the "parent" most dynamic swing (028 ~1:07:00); the implied range from inception to the target (045 ~2:57:22; 061 ~1:16:20; 092 ~1:16:00); intraday after MSS: the swing high->low of the displacement leg (022 ~38:38; 010 ~58:09); the OB candle's high-low after an MSS (064 ~55:46); 20-day high/low for daily work (cc07_004 ~7:00; cc09_008 ~12:46), 60-day body range for short-term (cc07_005 ~3:10) [both].
- **Zones:** strict = lower/upper third (cc01_006 ~2:07); OTE 62-79%, 70.5% sweet spot (cc01_004 ~23:59; cc01_005 ~5:31); FE 20/30 (deep discount) and 80/90 (cc06_004 ~31:39); recursive halves/quadrants/eighths (cc07_005 ~5:15) [CC].
- **Rules:** sell FVGs at or above 50% of the leg (010 ~58:09; 022 ~38:38; 069 ~13:11); don't short at exactly 50% (cc01_005 ~3:22); no adds past the 25% level of the leg / below EQ of the implied range (022 ~49:26; 025 ~47:56; 045 ~1:51:09; 058 ~43:12; 092 ~1:15:24); from P/D, price first rebalances to EQ (cc05_015 ~4:03) [both].

### 1.18 PD array matrix ordering
- From EQ outward, premium: mitigation block, bearish breaker, liquidity void, FVG, bearish OB, rejection block, old high/low. Discount mirror: mitigation block, bullish breaker, liquidity void, FVG, bullish OB, rejection block, old low/high (cc05_014 ~18:20-29:36; cc05_015 ~1:49; cc06_003 ~3:49; cc07_001 ~6:05; cc07_004 ~1:01) [CC].
- Price meets them nearest-first; a **breaker takes precedence** and usually stops price before the arrays beyond it (cc05_014 ~21:04; cc09_008 ~9:59). Without a breaker, expect the void and gap to fill on the way to the OB (cc05_014 ~28:47).
- Exhausted (already traded and reacted) arrays are skipped; untested ones preferred (cc07_004 ~4:00; cc07_005 ~23:13). Old low can act as premium when price is far above it (cc05_014 ~23:22).
- Failure cascade: daily array fails -> next weekly, then monthly; a stop-out into a weekly OB is a re-buy (cc05_015 ~18:45; cc06_003 ~23:24) [CC].
- **Three-PD-array rule:** list three arrays against the trade; through the first = tolerated, second = warning, all three (body closes) = exit even before the stop (026 ~28:02; 027 ~38:26; 044 ~1:52:49; 045 ~1:49:28; 078 ~1:02:38; 098 ~47:00; 105 ~1:21:06) [2023].
- Price moves only to take liquidity or to reach an inefficiency; otherwise it consolidates (038 ~47:04; 050 ~8:01; 061 ~41:29; 067 ~1:29:00; 104 ~14:19) [2023].

### 1.19 Buy-side / sell-side liquidity
- BSL = buy stops above old highs / relative equal highs; SSL = sell stops below old lows (001 ~13:02; cc01_007 ~1:09; cc04_011 ~4:11) [both].
- Booking a level needs one tick through (042 ~59:04); exit just beyond a pool (050 ~55:20; 083 ~8:00; 099 ~37:51); fund stops can sit up to ~10 handles beyond old highs (027 ~44:20) [2023].
- Named pools: previous 3 days' highs/lows (010 ~65:54); session ranges: prior PM 13:30-16:00, London 02:00-05:00, lunch 12:00-13:30, AM 09:30-12:00 (067 ~12:40-51:40); 20/40/60-day highs/lows (cc05_004 ~1:56; cc07_004) [both]. 4h equal lows outrank nearer 1h equal lows (103 ~29:42).
- ERL (beyond range high/low) vs IRL (FVG/void/OB inside): enter on IRL, exit on ERL (cc04_002 ~0:50-18:58) [CC].
- Low- vs high-resistance liquidity run: few overlapping swings between price and target vs many; take only the former (cc01_007 ~5:38-14:38; 022 ~1:48:52; 025 ~15:00; 102 ~2:16) [both].
- An imbalance is not liquidity (033 ~24:34) [2023].

### 1.20 Relative equal highs/lows
- Two or more highs (lows) close together = BSL (SSL), magnets, "smooth edges made jagged" (006 ~26:43; 025 ~36:20; 033 ~56:12; cc01_003 ~15:23; cc04_014 ~2:17) [both]. Bodies nearly level count even if wicks differ (cc05_003 ~1:07:26); draw the line at the lower of two lows (038 ~43:43). No tolerance is ever given.
- Repeated marginal failing highs = engineered buy-side (028 ~1:24:53; 035 ~49:36; 080 ~15:50 triple top "poison"). Equal highs under an untraded HTF array = partial, not reversal (061 ~2:19:50); fade them only when neutral AND a premium array sits just above (cc09_005 ~20:00).
- Double top measured move: (top - low between peaks) projected beyond the top = stop-run objective (cc04_014 ~8:40) [CC].

### 1.21 Inducement
- Not an ICT term in any note. Closest concepts: priming (021 ~25:37; 032 ~56:22), engineered liquidity (cc01_004 ~46:45; 035 ~49:36), Judas swing / protraction (cc01_008; 082 ~1:03), offset distribution/accumulation (cc09_006 ~1:59; cc09_007 ~0:41), false flags / trendline phantoms / H&S traps (cc02_007; cc03_007; cc03_008). Codeable form = "sweep of a short-term pool against the bias before the move" (already the bot's sweep step).

### 1.22 Tolerances that apply to all arrays
- "Mohawk": a 1-2 tick wick past a level is still respect (038 ~46:16; 042 ~1:07:39; 065A ~2:53:30; 096 ~12:04); bodies tell the story, wicks do the damage (019 ~14:55; 032 ~9:00; 045 ~1:06:21; 074 ~26:05) [2023].
- Wicks are gaps: wick CE = 50% from body edge to wick tip (028 ~16:43; 012 ~4:14; 021 ~21:06; 022 ~1:13:58); partial at a wick CE "always" (065A ~2:37:30; 065B ~3:52:40); body close beyond a wick CE = warning (065B ~4:18:20; 100 ~38:13; 105 ~14:01) [2023].

## 2. Conflicts

- **C1 OB mean threshold: wicks vs bodies.** A: full high-low (002 ~3:45; 061 ~51:40; 065A ~1:20:40; 086 ~10:58; cc04_003 slide ~2:00; cc04_008 chart ~6:20) ~6. B: body open-close (009 chart ~4:17; 026 ~58:05; 104 ~49:40; cc04_003 spoken ~9:38; cc04_008 spoken ~1:27; cc06_005 ~5:45; cc07_004 ~10:02) ~7. Trade examples: the only priced stop (009) fits the body MT; 022 (MT 4131.50) is not resolvable. **Default: body MT for stops/invalidation** (more specific, matches the one priced trade). Param `mt_mode = body|range`.
- **C2 Breaker zone: body vs full range.** A: bodies (001 ~44:00; 012 ~11:07; 029 ~22:34; 048 ~1:06:07; 060 ~26:40; 063 ~3:49; 081 ~11:48; cc09_008 ~9:59) ~8. B: full candle incl. wicks (031 ~59:25; 032 ~39:52; cc04_005 ~9:16; 070 box to B's wick) ~4. Examples: 007/019/029 zones drawn on bodies; 031/032 on full range. **Default: zone = body of the chosen candle, invalidation = body close beyond it**; param `breaker_zone = body|range`. Also break condition (C3) and 070's "enter inside A-B without waiting for the break" (test as `breaker_early`).
- **C3 MSS: wick vs close.** A: wick/1 tick is enough (012; 026; 030; 035 ~20:15; 075) 5. B: close/body (001 rules; 035 ~42:44 close -> breaker; strategy.py). Examples: 030 (15:17 one tick) and 026 shown with wick. **Default: wick (trade-through)**; param `mss_mode = wick|close` (bot currently `close`).
- **C4 Liquidity void.** A: true no-overlap gap (001; 003; 019; 077) / session gap only (028; 030; 039; 060; 068; 074) [2023]. B: range of one-sided candles (cc01_001; cc01_006; cc04_010; cc04_014; cc06_003) [CC]. 2023 explicitly calls B a misnomer (028 ~36:17; 074 ~21:33). **Default: true gap (high/low non-overlap) + session gaps (NWOG/NDOG/ORG)**; treat B as "displacement leg" for fill targets only.
- **C5 BPR re-entry.** A: price should not re-enter (001 rules; 077 mild). B: may revisit to MT (026), several probes (100), trades to its edges/CE (062 ~3:44). Examples show revisits (077 revisited and rejected). **Default: BPR is a level; invalidation = body close through its midpoint (065B).**
- **C6 FVG measurement.** A: 3-candle wicks (most, incl. cc04_012). B: bodies between last up candle low and first up candle high (cc01_006 ~3:51); cc02_004/cc02_005 use "FVG" for an OB high-to-open zone. **Default A**; B is old terminology.
- **C7 OB anchor and validation.** Open (003; cc04_003; cc04_014; 098) vs high (003 10864.75 example; 012) vs low (cc03_001 bearish OB line at the candle low ~28:00) vs full range (levels.py). Validation: trade above the high (CC) vs trade through the open (2023 CISD). Examples (009, 020, 096) enter at/near the high-to-open area. **Default: zone = high..open (bullish), MT = body midpoint, validated when price trades above the open after the MSS**; params for `ob_anchor`.
- **C8 Rejection block.** Range from extreme body to extreme wick (cc04_006; cc05_014; cc06_003; levels.py) vs single close level (015; 030; 059; 067; 080; 090; cc12_001). These are the same zone's trigger edge; bearish candle choice varies (highest up-close close vs highest body of any colour). **Default cc04_006 (any colour, extreme body to extreme wick, trigger = body edge).**
- **C9 Propulsion block.** A: candle trading into a prior OB (cc04_008; 027; 073; 075; 078; 079) ~6. B: down candle whose high is taken by the next candle making a higher high (cc09_008 ~14:47) 1. **Default A.**
- **C10 Bearish breaker candle.** Down-close at the swing low (007; 043; 103; cc04_005) vs up-close candles at the low (042 ~46:29) 1. **Default down-close.**
- **C11 Unicorn.** FVG inside a breaker (007; 101) vs 2nd-stage redistribution (104 ~41:02). **Default 007.**
- **C12 ORG close and lifetime.** Close = 16:14 1m close / 16:15 (043; 044; 060; 069) vs 16:00 (045; 059; 067). Lifetime 3 days (060), 5 days (068), ~60 days (092), indefinite (072). For SPY the 16:00 close is the only option. **Default: SPY 16:00 close, ES 16:15; expire after 5 trading days**; param.
- **C13 Swing size.** ICT: 3-candle (n=1) everywhere; bot: n=2. **Test n=1 vs n=2.**
- **C14 Exit vs level.** Before an FVG edge (010 ~58:50; 056; cc01_006) vs one tick inside the FVG (018 ~2:50) vs beyond a liquidity pool (050; 083; 099; 105 ~1:27). Reconciles as: FVG/OB targets -> exit before; liquidity pools -> through by a tick or two. **Default that split.**
- **C15 IFVG definition.** One close through (most) vs "passed through twice" (058 ~4:51). **Default one close + new-candle return (048).**
- **C16 Equilibrium anchors.** Wicks (cc01_004 chart; 014; 044) vs bodies (cc01_001 ~17:20; cc07_005; 058 ~41:54; 063 ~3:49). **Default wicks for intraday legs, bodies for multi-day ranges** (param).
- **C17 FVG entry level.** Near edge (001 first entry; 054 examples; strategy default) vs CE (024 ~23:19; 007 ~22:39; 009) vs IOFED (035 ~53:42 "rarely gets CE fills"). Examples mostly fill near the near edge. **Keep `entry=edge`, test `ce` and `iofed`.**
- **C18 PD matrix order** cc06_006 (OB, void, OTE, FVG, false break, rejection, old high) vs cc05_014/cc06_003/cc07_001/cc07_004. **Default cc05_014.**

## 3. Bot implications (levels.py / strategy.py)

Exists and matches:
- `fvgs` = correct 3-candle wick definition, known at c3. `Zone.mid` = CE. Entry `edge|ce` matches C17.
- `volume_imbalances` = matches (bodies strictly apart, wicks overlapping).
- `balanced_ranges` = overlap of opposite FVGs (065B definition). Unused by strategy.
- `rejection_blocks` = body extreme to wick extreme of a pivot and neighbours (cc04_006). Unused.
- `breakers` = low/high/lower-low, body close above H, zone = last up-close candle before H. Used for "unicorn" overlap.
- `equal_levels` returns the lower of equal lows (038). MSS reference = swing that led into the sweep (010/058).

Change:
1. `mss_mode` param, default wick (C3). Currently `c[i] > ref`.
2. `pivots(n=1)` test (C13); n=2 drops 3-candle swings ICT uses.
3. `order_block`: (a) blend consecutive same-colour candles, (b) zone high..open with body MT (C1/C7), (c) optional filters: FVG adjacent, largest body, displacement >= 2x body. Stop uses `ob.mid`, which is the full-range MT now.
4. `breakers`: param zone body vs range (C2); choose the highest-body up-close candle in the swing, not the last one in a fixed n window.
5. Add FVG state tracking per bar: open / repriced (wick touch) / rebalanced (body through and left) / inverted (body close beyond + new candle returns). Needed for IFVG, breakaway test and the "bodies through CE = exit" rule (030).
6. Add FVG quadrants and VI-extension of FVG boxes (098/099).

Add (codeable):
- **IFVG** entries/targets (048 protocol; 102 depth rule).
- **Mitigation block** (failure swing variant of `breakers`: B < A, no sweep) and **propulsion block** (down-close candle whose range enters a prior bullish OB; invalidation = body close through its MT).
- **Gaps:** NDOG (needs ES data; SPY has no 17-18 break), ORG with CE/quarters (SPY 16:00 -> 09:30; 5-day expiry), true liquidity voids, vacuum block = ORG on news days. NWOG currently stored as (Fri close, Mon RTH open) = 039's Monday variant; add CE and keep 60 days.
- **Wick CE** intraday (only daily `wick_midpoints` exists) as partial-exit and invalidation level.
- **Targets from the PD matrix:** strategy targets are liquidity only (pdh/pdl, pre-market, rel eq, NWOG, AM range). Add opposing FVG near edge / CE, BPR, rejection blocks, ORG CE; order nearest-first with breaker precedence.
- **Premium/discount of the dealing range** (displacement leg high->low, EQ) as entry filter and add cutoff (25% level); currently only the midnight/13:30 open is used.
- **Three-PD-array exit** (opposing arrays broken by body closes -> exit before stop).
- **Exit rule split** (C14): FVG target -> exit_before; pool target -> 1 tick through. Currently `exit_before_pts` applies to all.

Too discretionary to code (why): implied FVG (undefined); Reaper IFVG (needs "retail idea luring traders"); "layering" (058, no count given); "narrative decides which OB" (048/065A); high/low-resistance runs (qualitative overlap); time distortion; reclaimed blocks of the opposite MM-model leg (needs the curve extreme in real time, 104 open question); rejection block "long wick" threshold.

## 4. Open questions
- MT body vs range, breaker body vs range, MSS wick vs close: settle by backtest (C1-C3).
- Relative equal highs/lows tolerance (ticks, % ATR, time apart) is never given.
- How large must a gap be for quadrants to matter (only "10 pips FX", 101); minimum FVG size for ES/SPY.
- IFVG: what counts as "a later candle already traded into part of it" (102); which TF's close counts (048, 5m vs 1m).
- Breakaway gap: how much must stay open; how long to wait before "qualified" (062).
- Which leg defines the dealing range for P/D intraday (last displacement leg vs implied range to the target vs day range).
- ORG/NDOG lifetime (3, 5, 60 days, week) and ORG close time per instrument.
- Displacement threshold beyond cc04_003's 2-3x OB body.
- Rejection block: what is a "long wick"; how many candles form the swing.
- Propulsion block: which candle's MT, body or range.
- Mitigation block vs breaker: close or wick break of the swing low; first swing low candle or lowest one.
- Implied FVG definition (035 only names it).
- PD array matrix: is "nearest first" by price distance or by matrix rank when both exist.
- "Three PD arrays" exit: which arrays and which TF.
