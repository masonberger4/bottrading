# Digest: reference levels, projections and draw-on-liquidity selection

Scope: opening prices, opening gaps (NWOG/NDOG/ORG/vacuum), prior day/week/month and session
highs/lows, IPDA 20/40/60-day ranges, quarterly shifts, CBDR/Asian/Flout standard deviations, ADR,
fib/OTE levels and extensions, equilibrium and quadrants, rounding, and the rules for picking the
next draw on liquidity. Sources: all 218 note files, `mentorship_rules.md`, `strategy.py`, `levels.py`.
Times are New York. "ES pt" = handle. SPY ~ ES/10.

## 1. Rules

### 1a. Opening prices
- Midnight NY open (open of the 00:00 15m candle) is the true daily open. Bullish day: buy at or below it; bearish: sell at or above it. Applies every day [both] (006 ~5:51, ~23:28; 008 ~1:10; 010 ~38:31; 043 ~4:11; cc03_003 ~31:25; cc09_001 ~0:31; mentorship_rules Ep 04).
- Extend the midnight-open line from 00:00 to 11:00 only; any return to it before the objective is met is an entry in bias direction [2023] [chart] (060 ~15:20; 069 ~4:37).
- Secondary opens: 08:30 and 09:30; PM uses 13:30 as its Judas reference [2023] (010 ~38:31, ~56:30; Ep 08). On news days, bodies of the retrace stop at the 08:30 opening price (064 ~55:13) [chart].
- Weekly opening price (Sunday 18:00 open, or Monday 00:00 NY 1h open): bullish week = buy every day while price is above it after an early-week dip below it; bearish = mirror; valid until an opposing daily PD array is hit. A Thursday cross back through it against the bias signals an intra-week reversal [both] (048 ~1:00:10; 051 ~3:01; cc08_001 ~22:58-29:03; cc12_003 ~19:03).
- 0 GMT open (19:00/20:00 ET) as an FX reset: buy at it or 10-20 pips beyond, stop = 5-day ADR [CC] [fx-only] (cc08_008 ~12:49-14:07; cc09_001 ~2:24).
- 08:20 CME open: reference for short-term highs/lows and the NY Judas swing in FX/bond futures [CC] (cc08_002 ~7:22; cc09_006 ~19:07; cc10_006 ~11:33). For ES the 09:30 open replaces it (cc10_011).
- True day: 00:00-15:00 (FX/IPDA) [CC] (cc08_002 ~5:15); index true day 09:30-16:00 [CC] (cc10_010 ~2:51).

### 1b. Opening gaps
**NWOG (new week opening gap)**
- Definition: Friday close at 16:59 (last 1m bar; 16:55 5m bar) to the first tick of Sunday 18:00. Read on 1m/5m ETH, never the daily (settlement differs). High/low labels depend on gap direction [both] (039 ~0:57, ~6:12; 025 ~1:44; 050 ~13:20; 051 ~5:38; 052 ~1:35). Variant: Friday 16:59 close to Monday 09:30 open (039 ~14:41) [2023].
- Levels: high, low, CE (50%); optional 25/75% quarters. Treat as three exact levels, not a zone [2023] (020 ~8:21; 022 ~26:52; 024 ~18:37; 026 ~12:50; 030 ~10:17; 039 ~1:26, ~9:29; 057 ~7:35).
- Never discard after a fill; old NWOGs stay magnets for weeks/months [2023] (037 ~22:17; 039 ~5:26; 050 ~13:20).
- Keep at least 4-5 most recent; maximum = every NWOG in the last 60 days [2023] (030 ~31:43; 039 ~3:49; 050 ~16:01; 051 ~18:00; 092 ~1:57:26).
- Holiday week (short Friday or Sunday session): ignore that week's NWOG, use the nearest normal one in the last 60 days [2023] (046 ~0:16:01; 048 ~2:54).
- Use as targets in order near edge -> CE -> far edge; 80% off at CE in a slow/news-ahead tape, 50% at near edge + 25% at CE on normal days; layered exits at high / 75% / CE [2023] [chart] (020 ~3:50-10:06; 036 ~1:01:00; 057 ~7:35).
- Regime: price keeps returning to the current NWOG = consolidation week (scalp targets); leaves sharply and does not return (one retest allowed) = trending week; clustered/converging NWOGs = consolidation [2023] (025 ~3:01; 030 ~10:17; 039 ~12:26; 051 ~9:25-13:30; 053 ~1:31).
- Chain rule: moving from one NWOG toward the next, reaching 50% of the space between them ("event horizon", near edge to near edge) means the next NWOG will probably be reached [2023] [chart] (037 ~22:46; 051 ~16:51-17:05).
- Bias anchor: below the previous NWOG high = bearish; bullish while above the current NWOG; draw = next NWOG above [2023] (030 ~1:17:31; 036 ~16:00; 058 ~53:46).
- A sell-side run below old lows is expected to stop at the nearest NWOG/NDOG/ORG; same logic sizes a turtle-soup stop [2023] (038 ~41:58, ~45:52).
- Sunday-open scenarios (no bias before the open): bullish = gap up, fill, continue; bearish = gap down, partial fill under half, then lower; if Friday closed far from equilibrium expect a full return to the close, if at equilibrium a partial fill [2023] (011 ~6:20; 028 ~1:09:37-1:16:09; 084 ~3:41).
- Sunday 18:00 opening price alone is a level for the whole week [2023] (051 ~3:01).

**NDOG (new day opening gap)**
- 17:00 ET close to 18:00 ET reopen, Mon-Thu only; high, low and midpoint act as S/R/equilibrium [2023] (031 ~0:13:32; 032 ~3:03; 033 ~0:03:24; 052 ~0:46-2:24; 060 ~37:50).
- Ignore gaps of 1-2 ticks, prefer >1 ES pt; extend the first meaningful one through Friday, discard next week [2023] (052 ~4:03-5:46). Confluence only, never a standalone signal (052 ~6:16).
- Repricing scalp: gap down at 18:00 that has not yet traded to the NDOG high -> expect it to (052 ~8:18) [2023] (overnight only).

**ORG (opening range gap, RTH)**
- Prior RTH close to today's 09:30 open, read on an RTH chart. ES close = 16:15 settlement (16:14 1m close); SPY/equities = 16:00 [2023] (033 ~0:11:36; 043 ~11:47; 059 ~0:13:46; 060 ~30:20; 069 ~10:06; 092 ~1:55:54).
- Levels: high, low, CE, 25/75% quarters; bodies respect them, wicks pierce [2023] (044 ~0:07:12; 060 ~31:00; 068 ~0:09:04; 072 ~25:15; 092 ~1:57). Gap below prior close = "discount ORG", above = "premium ORG" (069 ~10:53).
- 09:30 volatility seeks to reprice to the prior close; expect price to trade back into the ORG unless it acts as a breakaway gap (no traction, keeps going) [2023] (022 ~1:25:02; 033 ~0:14:57; 055 ~20:50; 059 ~0:14:46).
- Bullish + gap up: expect a fill then higher; bearish + gap up: fill is a false run; consolidation after a weekly objective: range inside the gap all day [2023] (055 ~17:50-18:20). Gap into premium: small push higher then back into the gap (042 ~11:20).
- Gap below prior close with no attempt to return within ~30 min = very bearish (mirror for gap up) [2023] (030 ~1:27:01).
- Fill depth: full, half or quarter; a quarter fill that holds shows strength; half-filled gap -> later move into the unfilled half; a breaker inside the gap can stop full closure; full closure not required when heavy order flow sits inside [2023] (036 ~0:53; 058 ~53:24; 068 ~0:11:58; 072 ~31:38).
- Target ladder used: ORG near edge (069 exit at top), CE (041 bounce at CE 3999.00; 068), far edge = prior close (043 "Repriced To ORG Low") [2023] [chart].
- Lifetime: 3 days (060 ~32:40) / 5 trading days (068 ~0:09:49) / indefinitely, ~60 days, dimmed once filled (072 ~24:56; 080 ~3:28; 092 ~1:58) [2023].
- Large ORG or large prior-day range -> first 30-45 min chops; run often starts near 11:00; prefer 13:30-16:00 [2023] (033 ~0:13:27).
- ORG size projected in SD multiples; -11 SD gave the day's high to a tick (056 ~0:17:10); 2 SD near the high (055 ~19:30) [2023] [chart].

**Vacuum block / other gaps**
- Event or session-open gap (prior close to next open): high, low, MT; high probability of a fill. Gap at 08:30/early NY likely fills fully; gap at 10:00-11:00 or later more often stays partly open that day [CC] (cc04_009 ~3:58-10:05).
- RTH gap 16:00 -> 09:30 and the weekend gap are "true liquidity voids" (no prints) [2023] (028 ~0:35:46; 039 ~3:06).

### 1c. Prior-period and session highs/lows
- Liquidity matrix: highs/lows of today, yesterday, day before, plus the 3-day extreme [both] (010 ~65:54; cc09_002 ~0:54; cc09_005 ~14:22).
- PDH/PDL are the first daily targets and the daily raid levels; previous days' highs/lows hold real resting orders [both] (006 ~37:12; cc01_003 ~21:46; cc04_011 ~12:57). Reversal off PDH/PDL only with a HTF PD array at the level and HTF order flow; inside an expansion it is a retracement, not a turn [CC] (cc09_005 ~03:12, ~15:10). Old daily low alone is not an entry (Ep 08; 010 ~63:38).
- Previous week high/low and previous month high/low as targets and partial levels [both] (054 ~4:02; cc04_003 ~0:13:40; cc08_007 ~18:27). Monthly: mark OHLC of the last 3 monthly candles (cc03_004 ~1:46).
- Session ranges as pools (highest high / lowest low inside the window) [2023] (067 ~0:12:40-0:51:40): previous PM 13:30-16:00 (RTH), London 02:00-05:00 (ETH), NY lunch 12:00-13:30, AM 09:30-12:00. Priority at 09:30: previous PM range if near; if already beyond it, London's range; then previous AM (067 ~0:52:30).
- Overnight high (Globex) marked pre-market as near buy-side; older high as far tier [2023] [chart] (023 ~17:00).
- Thursday London and Thursday NY-PM highs as next targets (072); Monday 09:30 low and Sunday 23:50 low as named sell-side targets (082 ~6:43); Friday afternoon highs as buy-side reference (080 ~8:03); prior-day ~10:30 low as sell-side (097) [2023] [chart].
- Lunch: runs the stops of traders right in the AM; target the lunch-hour REL/REH in the PM; or the AM's most recent high; or the first post-news swing low [2023] (015 ~29:22; 025 ~1:00:20; 046 ~2:03:21; 064 ~1:45:41; 075 ~1:10:00; cc10_013 ~00:01:21).
- Mon-Wed range: a break of the Mon-Wed high (bullish) or low (bearish) later in the week = expansion toward the weekly target [CC] (cc07_001 ~42:44).
- Index opening range (OR60 09:30-10:30) tends to hold the day's high or low; a wide OR's opposite end gets run later; turtle soup below the OR low then rally to the OR high [CC] (cc10_010 ~3:07-7:05). Opening range 09:30-10:00: watch which liquidity/FVG it leaves [2023] (031 ~0:04:52; 036 ~0:27:30; 042 ~4:29; 073 ~25:00).
- Last hour: if the AM set the low, the high forms 15:00-16:00 (vice versa) [CC] (cc10_012 ~00:11:27).
- Bond OR 08:00-09:00 is the pool raided at 09:30 [CC] [bonds-only] (cc10_006 ~00:03:46).

### 1d. IPDA data ranges, quarterly shift, open float
- Look back 20/40/60 trading days; 20-day levels most sensitive [both] (015 ~4:25; cc05_001 ~22:42; cc07_004 ~00:04:00; cc09_008 ~6:03). Count from yesterday as day 1, roll daily (cc09_008) vs anchor on the first trading day of the month of the last quarterly shift (cc05_001 ~21:48; cc05_003 ~19:15) [CC].
- In each window mark the highest high (buy stops), lowest low (sell stops), unfilled FVGs/voids and the 50% of consolidations [CC] (cc05_003 ~17:12-28:38; cc05_004 ~1:56).
- If the 20-day low (high) is taken, next target is the 40-day, then 60-day extreme; if all have been run, expect a fast move to the nearest level beyond 60 days [CC] (cc05_003 ~28:38-33:39; cc07_004 ~00:07:00; cc06_008 ~12:40).
- Day trading works inside the 20-day range; move to 40 only when every 20-day PD array has been traded [CC] (cc09_008 ~8:47).
- Price near the 50% of the 20/40/60-day ranges with both sides cleared -> range day until news [CC] (cc05_003 ~1:18:26). 60-day high/low = overbought/oversold (cc05_003 ~1:55:26).
- Bias from which side of the 20/40/60 ranges keeps getting raided [CC] (cc05_004 ~8:51); 20-day breakout failures = turtle soup edge (cc05_004 ~6:45).
- Quarterly shift: a major turn/leg every 3-4 months, lasting 2-3 (max 4) months [both] (084 ~22:12; 098 ~58:30; cc05_001 ~5:05; cc05_002 ~3:52; cc05_018 ~3:32).
- Open float pools: short-term (weekly/monthly) highs/lows, 3-month, 6-month and 12-month highs/lows; buy stops above the last bearish shift's high [CC] (cc05_002 ~2:17-8:12).
- Old PD arrays (FVGs, NWOGs) stay valid for 60 days even after being filled [2023] (051 ~19:34; 065B ~03:58).
- Position trailing stop beyond the 40-day extreme, tighten to 20-day late in the move [CC] (cc05_018 ~5:52).

### 1e. Dealing range, equilibrium, premium/discount, grades
- Equilibrium = 50% of the leg/range; premium above, discount below; buy discount, sell premium [both] (Ep 08; 022 ~00:48:15; cc01_004 ~10:26; cc05_014 ~17:34).
- Intraday leg: after the MSS, sell an FVG at or above 50% of the displacement leg (high to the low that broke); no new shorts/adds once price passes the leg's 25% (midpoint of the discount half) [2023] [chart] (010 ~58:09; 022 ~00:38:38-00:52:23; 025 ~47:56; 060 ~1:23:00; 069 ~13:11; 092 ~1:15:24).
- Dealing range anchor: the swing with the most dynamic move (parent range); energetic swing low, not a rounded bottom; Monday midnight/low to Monday high for the week [2023] (028 ~01:07:00; 044 ~0:40:11; 076 ~20:09).
- Implied dealing range (inception to the not-yet-reached target): 50% = consolidation/time distortion, stop hunts in the lower quarter, surge in the top quarter; no pyramiding past EQ [2023] (045 ~02:57:22; 061 ~1:16:20; 075 ~1:35:00; 092 ~1:15:24; cc06_008 ~26:02).
- Grade any range 0/25/50/75/100; setups form near the grades; grade levels are "mile markers": a level traded straight through usually leads to the next [both] (cc03_001 ~38:04; cc03_003 ~22:00; cc07_005 ~5:15-14:14; cc07_006 ~11:35; 061 ~1:34:00; 070 ~10:57).
- Short-term range (one-shot-one-kill): 60-day highest body to lowest body (wicks ignored), halved, then quartered, then eighths; best longs in the bottom quarter, best shorts in the top quarter, avoid the middle [CC] (cc07_005 ~3:10-24:06). Range EQ itself is a high-probability turn level (cc07_006 ~9:29).
- Thirds stricter than halves: buy only in the lower third (cc01_006 ~2:07) [CC]. Fib expansion levels 0/0.2/0.3/0.5/0.8/0.9/1: 0.3 deep discount, 0.2 deepest, 0.8/0.9 deep premium; no new longs there (cc06_004 ~31:39) [CC].
- OTE 62-79%, 70.5% sweet spot; discount entries below 50%, nothing above 50% is a buy; do not short at 50% itself [CC] (cc01_004 ~23:59; cc01_005 ~3:22-5:31; 053 ~04:47 [2023]).
- Confirm the swing high before measuring: 3-bar swing plus a following lower candle; re-anchor to the parent low if the leg extends without breaking its low [CC] (cc01_004 ~9:44, ~13:55).
- From premium or discount price first seeks equilibrium of the most recent range; an EQ-only target is valid [CC] (cc05_015 ~4:03). Consolidation: fade expansions from EQ, first target back to EQ [CC] (cc09_004 ~0:12:29).
- Consolidation range EQ measured on bodies (cc01_001 ~17:20); fib swings on bodies (058 ~41:54); void EQ on bodies (cc04_004 ~10:17) [both].
- After both news-day pools are taken, price retraces to the CE of the range between them [2023] (064 ~1:10:43).
- TGIF: Friday after a strong one-directional week into a HTF array, retrace 20-30% of the weekly range (week low to high), 25% midpoint; >30-40% is reversal territory [2023] [chart] (066 ~0:13:42-0:25:34; 074 ~24:04; 075 ~1:40:00; 084 ~15:45; 089 ~00:00:41; 098 ~27:45). Week's high assumed in by ~13:30 Friday (066).
- Daily BISI range (high of the next candle, low of the prior candle): CE and lower 25% quadrant are draws; inside it, no trade; above CE = premium (091 ~4:09-17:46) [2023].

### 1f. Levels inside gaps, wicks and blocks
- Every gap/FVG/void is three levels: high, CE, low; CE most likely reaction; a BISI retrace most likely reaches the top or CE, the far edge least likely [both] (022 ~00:09:09; 065A ~1:09:40; 061 ~30:04; 078 ~51:00).
- Quadrants 0/25/50/75/100 on any FVG/gap; bodies respect them; CE = default session objective for a HTF FVG; when bullish, price should hold the upper quarter; use quadrants only on large gaps [2023] [chart] (029 ~30:44-33:00; 030 ~15:46; 035 ~1:04:12; 055 ~4:50; 101 ~51:58).
- First target on a FVG = near edge (FVG beats an overlapping OB); final limit at the near edge of an hourly imbalance; weekly gap CE is a fine target, far edge is the "ringer" [2023] (049 ~00:05:37; 061 ~2:30:15; 065B ~03:02:40).
- Partially traded FVG: the unvisited remainder plus the stops beyond it is the next draw [2023] (038 ~1:11:44). Inner gap inside a larger void: target the inner gap's CE (074 ~22:24).
- FVG need not reach its far edge when the lower TF shows layering or a BPR inside it; expect CE or near edge (058 ~21:40) [2023].
- Wick = gap; wick CE (body edge to extreme) is a target, partial and invalidation level; premium wick (above body) / discount wick (below body) [both] (Ep 08; 012 ~4:12; 028 ~0:15:48; 035 ~24:54; 045 ~0:16:51; 063 ~21:57; 079 ~16:55; 101 ~78:20). Weekly wick CE (011 ~4:41; 047; 070 ~3:11; 077 ~1:18).
- Always take a partial a little before the CE of any wick inside the trade's path; with two wicks use the longer [2023] (065A ~2:37:30; 065B ~03:52:40). After a stop run, a rally should be capped at the run candle's wick CE (072 ~5:27).
- Wick CE strength gauge: bearish retrace that cannot reach the upper wick CE = very bearish, stalling at 25% = weaker still; a real move cuts through a big wick's CE; next candle closing beyond the CE = continuation, close back = revisit; long wick in bias direction often stops dead at its CE; stubby wick: probe to CE first [2023] (025 ~25:37; 028 ~00:14:19-00:27:36; 031 ~0:32:15; 100 ~38:13).
- Wick-CE line on a closing basis: no 1h body close above a daily wick CE for shorts; daily close below a wick CE = deeper retrace [2023] (090 ~14:01; 100 ~6:45).
- Weekly/daily wick quadrants as gates: no trade until a daily close beyond the wick's upper quadrant (102 ~6:45; 103 ~2:29) [2023].
- Stubby-wick candle: use its open instead of its high/low as the level; long wick: use the extreme and the wick CE [2023] (055 ~1:44; 061 ~26:10).
- Rejection block level = highest up-close close (bearish) / lowest down-close close (bullish) of a wicked swing; cover/target just past the bodies, wicks need not be run [both] (015 ~2:15; 035 ~20:15; 059 ~0:09:38; 080 ~5:41; cc04_006 ~9:30-14:38; cc05_014 ~18:38).
- Liquidity sits beyond candle bodies; a sweep need only clear the body cluster [CC] (cc02_008 ~09:03; cc03_002 ~2:01; cc05_004 ~13:35; cc03_004 ~12:22). Relative equal lows: draw the line at the lower low (038 ~43:43) [2023].
- One-tick overshoot ("mohawk") past a level is normal; a level needs one tick through to be "booked" [2023] (038 ~46:16; 042 ~59:04; 050 ~33:20; 065A ~2:53:30).
- Old liquidity pool once run often becomes support/resistance from the other side [2023] (034 ~02:10:00; 072 ~36:02).
- Mean threshold (50%) is the OB/breaker level; CE the gap/wick level [both] (021 ~00:21:06; 069 ~11:30; 086 ~10:58).

### 1g. Projections (standard deviations, extensions, measured moves)
- Intraday SD targets: anchor a fib on a swing whose extreme has been broken; project -0.5, -1, -1.5 ... beyond it [2023] (029 ~21:18; 030 ~23:31; 036 ~0:24:00).
- Anchor variants seen: (a) down-leg into the swing low, 0 at the preceding high, 1 at the low, project above the high, levels up to -4.5 (014 ~01:58-03:46); (b) swing low to the broken high (030 ~23:31; 029); (c) swing high that ran buy-side to the broken low, -3 SD exact low (047 ~10:59); (d) manipulation leg, -2/-2.5/-3 SD where it converges with a PD array (092 ~1:21:26); (e) London manipulation swing low to high, step 1/1.5/2/2.5/3 (008 ~6:45; Ep 06); (f) fulcrum: swing high to the low expected to fail, -0.5/-1 (026 ~9:30; 046 ~0:58; 090 ~1:29); (g) bearish OB candle -1/-2/-3 (027 ~32:40 [chart only]); (h) breaker A-B leg: B + 1x(B-A), further SDs to -7.5 only at HTF confluence (070 ~37:31, ~1:02:49; 074 ~29:57; 076 ~16:36); (i) measuring gap: swing high to the gap's near edge, -1 SD, must agree with a run below an old pool (062 ~42:19-44:46); (j) trigger swing -1..-3 aligned with a time window (065A ~2:22:30) [2023].
- Target selection: skip any SD level at or below the buy-side pool (or a newer higher high); use the first SD beyond it; clusters of first-past-pool levels from several swings (STL/ITL/LTL) within 1-2 ticks = high-probability turn [2023] (014 ~02:54-04:43; 030 ~26:01).
- -0.5 SD is always a first partial; -1 SD = measured move; most off at -1; -2 is very extended (flat or tiny runner) [2023] (064 ~1:33:48; 065B ~03:03:40; 090 ~1:31).
- Measure only after the fulcrum is traded through [2023] (008 ~6:45; 026; 065B).
- Measuring gap ~ half of the move; project the range from the root swing to the gap high above the gap [2023] (003 ~31:35; 011 ~6:37; 061 ~1:22:05; 084 ~28:58).
- 1.27 / 1.62(1.68) extensions or a 100% symmetrical swing, only where they overlap an opposing PD array (one timeframe lower) [CC] (cc06_008 ~28:08; cc07_003 ~00:03:01; cc08_007 ~27:39; cc12_004 ~17:29).
- Measured moves: double top/bottom range projected beyond the double top (cc04_014 ~8:40); sweep-low-to-high leg added to the next sweep low (cc02_008 ~16:41) [CC]; Ep 08 measured move [2023].
- CBDR (14:00-20:00, bodies preferred): stack the range as SD1-SD4 above/below; HOD/LOD in London within SD1-2 (SD3 rare, SD4 news); only if CBDR <40 pips (ideal 20-30) and with a bias [CC] [fx-only] (cc08_003 ~2:00-16:05). Then measure the London Judas extension and stack it from the opposite CBDR edge for the day's other extreme by 10:00-12:00 or 14:00 (cc08_004 ~9:37-14:10).
- Asian range 20:00-00:00: buy below it, Asian high = level 1, stack Asian-range units, expect ~4 levels; ideal Asian range 20-30 pips (cc08_005 ~1:25; cc09_002 ~10:48) [CC] [fx-only].
- Flout: 15:00-00:00 (or CBDR+Asian) range, project HALF-range steps from EQ; short only above flout EQ [CC] [fx-only] (cc09_002 ~11:50-15:10; cc12_004 ~12:56).
- "Filling the numbers": expect ~4 levels (pivots/CBDR/Asian/Flout) from entry; take 75-80% off after four; the HOD/LOD is where projections converge with a HTF PD array and time of day [CC] (cc09_002 ~5:40-7:24, ~17:01).
- Pivots (0 GMT floor pivots with midpoints M0-M5) only for range extent, never entries [CC] [fx-only] (cc09_002 ~1:59-4:36).

### 1h. ADR
- Expected daily range ~ 5-day ADR (5-period ATR); capture 65-70% of it [CC] (cc08_001 ~1:53-2:13; cc08_008 ~22:12).
- NY target = ADR high/low, then next 4h/60m array; ADR reached before 10:00 -> take 80%, keep a runner; skip NY if London already made ~80% of ADR [CC] (cc08_001 ~13:41; cc09_006 ~19:23-20:12; cc09_007 ~8:32).
- Exit a fixed buffer before the ADR level (15 pips FX) [CC] [fx-only] (cc09_007 ~16:11).
- Day after a range >2x ADR5: expect chop; after a day that did not reach ADR: expansion of 1.5-2x due [CC] (cc08_006 ~01:22, ~23:33).
- London-close fade only if today's range >= ~125% ADR5; expect a 20-30% retrace of the day's range [CC] (cc09_005 ~11:16, ~32:26; cc09_006 ~23:06).
- Intraweek reversal tell: Mon/Tue range well above the 5-day ADR into a HTF array [CC] (cc07_007 ~20:45).

### 1i. Rounding / key-level calibration
- Round each PD array to the nearest .10/._5 (FX) level, toward current price: premium arrays above price round DOWN, discount arrays below round UP [CC] [chart] (cc12_001 ~34:00-35:07; cc12_002 ~18:29; cc12_003 ~24:36; cc12_004 ~17:04).
- Projected levels rounded to the nearest 5 or 0, called ~1 pip inside; exit at the round number before a projected level [CC] [fx-only] (cc07_008 ~11:27; cc09_002 ~26:36). Nearby round number may stand in for an exact OB high (15.56 -> 15.60) (cc06_004 ~11:28).
- Institutional levels 00/50/20/80/30/70 [CC] [fx-only] (cc06_002 ~9:28). Index examples only incidental: 3900.50 buy-side "round number" (002 ~2:37), 4100 target (021) [2023].

### 1j. Draw-on-liquidity selection
- Price moves only to (a) run stops above highs/below lows or (b) rebalance an inefficiency (FVG, gap, wick, void, up to ~60 days old); otherwise it consolidates [both] (038 ~47:04-50:00; 050 ~8:01; 061 ~41:29; 098 ~39:50; 102 ~2:05:44; 104 ~14:19; 065A ~46:30).
- Search order: inefficiency first; if none, liquidity (sell-side below an old low when in premium, buy-side above a short-term high when in discount) [2023] (065A ~50:00). Alternatively: spot the obvious liquidity, then the nearest inefficiency just beyond it sets how far the run goes (104 ~16:18). If bullish with no FVG above, target the buy stops (038).
- Narrative decision tree: bullish/bearish, then inefficiency vs liquidity [2023] (015 ~8:07). Decide the draw first, then take only one direction (019 ~13:57; 054 ~7:45).
- Direction from the PD-array matrix: after price reacted at one side's arrays, the other side is the next draw; target = opposing array, ideally one TF lower [CC] (cc06_003 ~0:50; cc07_001 ~09:29; cc07_004 ~00:12:02).
- Matrix order outward from EQ: mitigation block, breaker, liquidity void, FVG, OB, rejection block, old high/low; price meets them nearest first; a breaker in the path usually stops price before arrays beyond it [CC] (cc05_014 ~18:20-26:49; cc05_015 ~1:49; cc09_008 ~9:59). Not every array exists; skip exhausted arrays (already traded into and reacted) and prefer untested ones [CC] (cc07_004 ~00:04:00; cc07_005 ~23:13).
- Nearest pool with the least resistance; low-resistance runs (fast, one-sided leg, few overlapping swings) over high-resistance runs; the broken old low where a fast leg began caps a bullish LRLR [both] (cc01_007 ~5:38-14:38; cc02_008 ~13:07; cc04_002 ~00:12:53; 025 ~15:00; 102 ~2:15:30).
- Enter at internal range liquidity (OB/FVG/void), exit at external range liquidity (stops beyond the range high/low); redefine the range after every swing [CC] (cc04_002 ~00:05:39-00:10:00).
- Prefer the larger pool (REL) over a single low; a 4h REL outranks a nearer 1h REL; target the pool below the leg's equilibrium; or the first imbalance below the sell-side that sits below EQ [2023] (042 ~1:09:17; 049 ~00:03:40; 103 ~29:42).
- Smooth relative equal highs/lows (3-4 touches) get run even under an older higher high; double tops are pools, not S/R [both] (Ep 04; 021 ~00:24:37; 025 ~36:20; 063 ~23:14; cc01_003 ~15:23; cc04_014 ~12:02).
- Silver Bullet draw list: PDH/PDL; previous session H/L (London for AM); PWH/PWL; return to or expansion away from the NWOG; OTE; FVG/BISI/SIBI. If raided earlier, use a HTF pool [2023] (054 ~04:02-06:50). Framework must offer ~10 ES pts best case for a 5-pt take (024 ~25:26; 046 ~0:32:40; 054 ~00:36; 058 ~37:16).
- News days: mark REH, REL and the nearest FVG pre-release; the first pool run is the losing side, the second run is the real move [2023] (064 ~0:20:50, ~0:52:12; 073 ~10:42).
- Lunch macro 11:50-12:10 runs the liquidity protecting the AM move; 10:50-11:10 macro runs untapped liquidity; 14:50-15:10 spools toward un-purged 07:00/08:30/09:30-11:00 lows; MOC macro runs liquidity not engaged that day and does nothing if the HTF target already hit [2023] (022 ~03:06:14; 046 ~2:03:21; 056 ~0:19:08; 075 ~1:45:00).
- If the AM did not reach the draw by lunch, carry it to the PM [2023] (029 ~1:29:48; 031 ~1:04:22). If the session objective hits, stop; if the daily objective completes before lunch, skip (015 ~16:22; 029 ~1:03:57).
- PM profile targets: lunch high/low vs intraday high/low depending on whether the AM swing started at a 4h/daily array [CC] (cc10_013 ~00:07:46-00:13:52; cc10_014).
- PD-array failure: a failed daily discount array points to the next weekly, then monthly array [CC] (cc05_015 ~18:45). Weekly: one premium draw and one discount draw (099 ~33:57) [2023].
- Conditional draws: if price fails to reach the upper pool, switch to the lower; once that is taken the low draw is spent [2023] (080 ~16:58).
- Once a weekly objective is delivered, expect consolidation/retracement and stop trading for the week [2023] (038 ~6:33; 099 ~15:51; 101 ~34:21).
- Keep a written level list sorted by price relative to the open; mark each as done when traded and look to the next untouched [2023] (028 ~0:54:55; 045 ~00:06:38).
- Transpose HTF levels to every lower TF; label by source TF [both] (006 ~2:02; 074 ~7:00; 078 ~27:00; cc02_002 ~2:27).

### 1k. Exit placement relative to a level
- Before the level: never target the exact FVG edge, exit 0.5-1 pt before (Ep 08; 010 ~58:50); limit one tick short (030 ~24:24); a couple of ticks before (063 ~29:41); two ticks below an old high (101 ~88:45); ~10 pips early (cc01_006 ~23:13; cc12_004 ~18:54) [both].
- Beyond the level: +1/4 pt for fees past the FVG edge (018 ~2:50); limit 1 tick below a low (050 ~55:20); 0.75-1 pt above buy-side (083 [chart]); ~3 handles below a 4120 pool (059 ~00:20:38); limit a tick or two beyond because the exact high did not fill (105 ~1:27:00); HTF level plus a couple of handles for the runner (099 ~37:51); rest the limit beyond the target (cc10_008 ~14:20) [both].

## 2. Conflicts

1. **NWOG close time.** A: Friday 16:59 ETH close to Sunday 18:00 (039, 025, 050, 052; 7 sources). B: "Friday 16:00(ish)" (029); Monday-09:30 variant (039 homework). His trades/charts use A (020, 039, 057, 069 shows ORG 4383 != NWOG 4388.50). Bot uses RTH Fri 16:00 -> Mon 09:30 (variant B), only edges. **Default A from ES 1m data, CE added; test B as parameter.**
2. **NWOG count.** 4-5 (039), >=5 (050, 092), last 4 (030), all within 60 days (051). **Default: all within 60 trading days (min 5); test 4.**
3. **NDOG lifetime.** Through Friday, first meaningful only (052) vs 5 trading days (068) vs "all next day" (032). **Default through Friday, all gaps >1 ES pt; test 5-day.**
4. **ORG close.** ES 16:15 settlement (043, 055, 060, 069, 092; 5) vs 16:00 (045, 059, 067; 3). For SPY only 16:00 exists. **Default 16:00 SPY / 16:15 ES; no test needed.**
5. **ORG lifetime.** 3 days (060), 5 days (068), ~60 days/indefinite (072, 080, 092). **Default 5; test 60.**
6. **ORG target.** Near edge (069 exit), CE (041, 068), far edge (043). Trades show all three. **Default staged: near edge partial, CE, prior close.**
7. **Opening range.** 09:30-10:00 (031, 036, 042, 048, 073; many) vs 09:30-10:30 (cc10_010). **Keep both as levels (OR30, OR60); default OR30.**
8. **SD anchor.** Ten anchors listed in 1g. Most frequent in 2023 executions: low-to-broken-high/high-to-broken-low (029, 030, 047, 092). Bot uses sweep-low to leg high (close to that) with k=1-2.5. **Default: keep anchor, extend k to 4.5, use "first level beyond the pool" (014/030); test the 014 down-leg anchor.**
9. **Exit before vs beyond.** 1k. Pattern in his own fills: FVG/PD-array targets exit before (Ep 08, 049 "near edge", 063); liquidity-pool targets fill beyond (050, 083, 105). **Default: PD array -> 0.5 pt before; old high/low pool -> 1-2 ticks beyond; test bot's current 0.5-pt-before for both.**
10. **Discount threshold.** Below 50% (most), lower third (cc01_006), OTE 62-79 (cc01_004), 0.2/0.3 (cc06_004), 25% no-add line (022, 092). **Default <50% of the MSS leg; test OTE 62-79.**
11. **Range anchors: wicks vs bodies.** Wicks (014 "every anchor on the wick", cc01_004/005 charts, 2023 liquidity lines) vs bodies (cc01_001, cc04_004, cc07_005, 058, cc03_002, cc08_003 CBDR). **Default wicks intraday; bodies for HTF 60-day range; parameter.**
12. **Mean threshold.** Wick-to-wick (Ep 02, cc04_003 slide, cc04_008 chart) vs body (009 chart, cc04_003 speech, cc06_005, cc07_004, 026, 100). The 009 stop fits body. **Default body for stops; test wick.**
13. **Liquidity at wicks vs bodies.** 2023 lines sit at wick extremes and need one tick through (038, 042); CC says stops sit beyond bodies and a sweep need not take the wick (cc02_008, cc03_002, cc05_004, cc04_006). **Default: sweep = trade past the wick extreme (current); test "past body cluster" for rejection-block lows.**
14. **PD-array order (void vs FVG).** Slide lists FVG farther than void; speech void then FVG (cc05_014, cc07_004). Not coded; ignore.
15. **Lunch target.** Lunch range extremes (015, 067, cc10_013), AM most recent high (025), first post-news swing low (075), stops of AM-correct traders (046, 064). **Default lunch range H/L (12:00-13:30) as PM sweep/target; test AM most-recent swing.**
16. **AM sweep pool.** Bot: PDL1-3 + premarket + REL. 067 ranks prev PM range, London, prev AM. **Add prev PM 13:30-16:00 range and London 02:00-05:00 (needs data).**
17. **PDH/PDL session.** Bot RTH; ICT true day 00:00-15:00 (cc08_002), FX 0 GMT (cc01_003), daily chart (ETH). **Test ETH day (18:00-17:00) vs RTH when ES data exists.**
18. **IPDA anchor.** Month start of the quarterly shift (cc05_001, cc05_003) vs rolling from yesterday (cc05_004, cc07_004, cc09_008). Later lessons roll. **Default rolling.**
19. **FVG target depth.** Near edge (049, 065B), CE (020, 029), far edge only as "ringer" (061). **Default near edge first, CE second.**
20. **Breaker projection.** B+1x(B-A) (070) vs -1 SD of impulse leg (076) vs -1/-2 (074): same arithmetic (1 range beyond B); fine.
21. **Round numbers.** CC calibrates every level toward price; 2023 never rounds index levels except 007 (CE 3959.75 -> 3959 limit). **Default off; test 1/2.5/5 ES pt calibration toward price.**

## 3. Bot implications

What the bot has now (`strategy.py`, `levels.py`): opens (midnight via SPY 04:00 proxy, 08:30, 09:30, 13:30); PDH/PDL of the last 3 RTH sessions; pre-market H/L (SPY 04:00-09:30); AM-session H/L for the PM; REH/REL from untraded pivots; NWOG edges from RTH Fri close to Mon 09:30 open (last 4, any >=3-day or weekday-wrap gap); optional prior-day wick 50% (`wick_levels`); optional SD from sweep low to leg high (1/1.5/2/2.5); targets merged within 1 ES pt and exited 0.5 ES pt before. FVGs are entries only, never targets.

Add / change (priority order):
1. **NWOG CE and quarters; ORG every day** with high/CE/low/25/75, 5-day expiry, as targets and as sweep levels. ORG costs nothing (SPY 16:00 close, 09:30 open). The bot's NWOG is really the Monday ORG; label it so and add the true NWOG when ES Globex data exists. Add "09:30 seeks prior close" as a draw toward the ORG (055, 069).
2. **FVG targets.** Untouched 15m/60m/daily FVGs (and BPR) beyond price: near edge then CE (049, 065B, 029). The bot already detects HTF FVGs (`htf`); reuse them as targets.
3. **Target hygiene.** Only targets not yet traded through since they formed (028, cc07_004); the bot checks "intact" only for sweep levels.
4. **Wick CE levels.** Make prior daily (and weekly) wick CEs default target/partial candidates (strong 2023 evidence: 010, 013, 029, 038, 093, 105); test multiple days back.
5. **Leg premium/discount filter.** Entry must be at/below 50% of the displacement leg (above for shorts) and no adds past 25% (022, 025, 069, 092). Today only the midnight/13:30 open filter exists.
6. **SD target rule.** k up to 4.5 (and -0.5); target = first SD beyond the nearest pool; drop SD levels below the pool (014, 030).
7. **Exit buffer split** (conflict 9).
8. **Prior week H/L, prior month H/L, 20/40/60-day H/L** as HTF pools; next pool when the 20-day extreme is taken (cc07_004).
9. **Session ranges:** lunch 12:00-13:30 H/L for PM sweeps/targets; prior-day PM 13:30-16:00 H/L for AM sweeps; OR30/OR60 H/L. All computable from SPY RTH.
10. **ADR5:** skip AM entries if the day already used >=80% of ADR5 before entry (cc08_001), add ADR high/low as target; flag days after a >2x ADR day as chop (cc08_006).
11. **TGIF:** Friday PM target zone 20-30% of the weekly range back from the extreme after a trending week (066, 089); test only after a HTF-array hit flag exists.
12. **Calibration rounding** parameter (off by default).
13. Optional: NDOG, London 02:00-05:00 range, overnight high/low, Sunday open, CBDR/Asian/Flout SDs. **needs data: ES/NQ Globex 1m (Sunday 18:00, 17:00-18:00 break, 02:00-05:00)**. CBDR/Asian/Flout and pivots are FX-calibrated (pip thresholds); low priority even with data.

Leave out / too discretionary:
- Choosing "the" wick (063: "not every wick works"), "obvious" draw, "nested" HTF arrays, layering/BPR depth reads, three-PD-array invalidation: no stated selection rule.
- NWOG trending vs consolidation regime ("sharp move away"): no threshold; could be approximated (returns to current NWOG count) but untested.
- Quarterly shift anchoring, monthly/weekly bias checklists, COT/OI/bond triad/rate differentials, seasonals: **needs data: CFTC COT, futures OI, ZB/ZN/ZF, DXY**; they are weekly/daily bias filters, not levels.
- Measuring-gap selection when several FVGs exist (062 open question).

## 4. Open questions

- NWOG: zero-size gap; which side is "near edge" when price is inside; trending/consolidation thresholds; 60 calendar vs trading days.
- NDOG: minimum size for ES/SPY; first meaningful vs all; CE official or not.
- ORG: SPY 16:00 vs ES 16:15; is the target near edge, CE or far edge; how long "trying to return" is checked (30 min?); size threshold for a "large" ORG.
- SD projection: canonical anchor per setup; cap on multiples; tolerance for "cluster" (1-2 ticks?); wick vs body anchors.
- Wick CE: which candles/timeframes count; up-close vs down-close wick measurement (body edge vs open); quarter level from body or extreme.
- Equilibrium: which leg (sweep extreme to MSS swing, or swing high to target); how far above EQ still counts.
- Exit buffer in ES ticks for "before" and "beyond".
- Rounding step for ES/NQ (00/50, 5-pt, 2.5-pt) and whether applied before or after choosing the array edge.
- 20/40/60: trading-day calendar for ES; bodies vs wicks for the window extremes; how to rank windows.
- ADR: anchor (open, day low, London low) and the index equivalent of pip thresholds (fraction of ADR).
- TGIF: 20% vs 30% as target; how to confirm the week's high is in; wick or close range.
- Lunch window: 12:00-13:00 vs 12:00-13:30 vs 11:00-14:00; which lunch extreme the PM runs.
- PDH/PDL session definition (RTH, ETH, midnight-to-15:00).
- When several draws qualify, which first: nearest, larger pool, HTF, or untested inefficiency.
