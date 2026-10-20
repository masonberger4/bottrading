# ICT Mentorship bot: consolidated rulebook

> **Owner corrections 2026-10-18** (`mentorship/digests/owner_directives.md`,
> `owner_directive_specs.md`) override this file where they differ: last hour 15:00-15:50 and the
> 16:15 PM close (#1); 5 handles = minimum room (#2); year end from December's direction (#3,
> pending); news dealing-range wait (#4); bearish unicorn (#5); breaker MT respect (#6); opposing
> HTF FVG = resistance (#7); close (not tighten) before noon (#8); lock one draw per session (#9);
> stand aside on sloppy days (#10, pending); OB entry before the break (#11); 1.2% / 1.3% risk
> (#12); front-month prices (#13); full-range breaker (#14). Built status: `digests/build_log.md`.

## 1. Header

**Scope.** One rulebook for the ICT Mentorship bot (`mentorship/`), covering the 2023 Mentorship
playlist (notes 001-105, with 065 split into 065A/065B) and Core Content Months 01-12 (2016-17,
notes cc01_* to cc12_*). The bot is backtest and paper only. It reads signals from HistData
SPX/NDX 1-minute index CFD bars (New York time; RTH is the focus, but the files also carry
overnight bars, so a real midnight open, London range and overnight high/low can be computed).
It trades SPY/QQQ through Schwab, which cannot trade futures.

**Sources.** Seven topic digests in `mentorship/digests/` (models, pd_arrays, times, filters,
execution, levels, bias), which condense all 218 per-video notes in `mentorship/notes/`, plus the
caption-verified Ep 01-08 rules (Appendix A). Go to the digests for the full source lists per rule
and to the notes for context, charts and trade examples. This file states each rule once.

**Notation.**
- Citations: `(023 ~12:30; cc04_005)` = note file id and approximate video time. "Ep 0x" and
  "rules Ep 0x" refer to Appendix A.
- Tags: **[2023]** = 2023 playlist, **[CC]** = Core Content, **[both]**; **[chart]** = only seen on
  charts; **[fx-only]** / **[bonds-only]** = does not transfer to index futures as stated;
  **{needs: X}** = data the pipeline lacks; **{d: X}** = free daily data exists but is not loaded.
- **Bot:** = what `strategy.py` / `levels.py` / `backtest.py` do today. **D#** = see Decision # in
  section 3. **A#** = definition rule in 2.1. **P1-P3** = proposed change in section 4.
- Units: ICT quotes ES points ("handles"). 5 ES pts = 20 NQ pts, so NQ/NDX thresholds are about 4x
  ES (049 ~2:44; 071 ~20:34). SPX pts are about ES pts; SPY is about SPX/10 (`Params.es_pt`).
  "1 tick" = 0.25 ES pt.
- All times New York local time, daylight saving included. Bars are used only after they close.

---

## 2. Bot rulebook

### 2.1 Definitions: PD arrays and structure

**Swings and liquidity**
- **A1 Swing point** = 3-candle pivot: middle high above both neighbours (low below both); not the
  5-candle Williams fractal (012 ~30:08; 050 ~6:02; cc01_004 ~11:56; cc01_005 ~11:49) [both].
  Hierarchy: STL = plain swing; ITL = low with a higher STL on each side; LTL = low with higher
  ITLs on each side (014 ~0:12; cc05_002 ~20:14) [both]. A swing high is "confirmed" once a later
  candle trades lower (cc01_004 ~9:44) [CC]. Bot: `pivot_n=1` (3-candle, default; 2 = the
  5-candle switch, D17); ITL/LTL tiers `levels.swing_tiers`, MSS reference tier `mss_ref`.
- **A2 Buy-side liquidity (BSL)** = buy stops above old highs and relative equal highs;
  **sell-side (SSL)** = sell stops below old lows and relative equal lows (001 ~13:02; cc01_007
  ~1:09; cc04_011 ~4:11) [both]. A level is "booked" only when price trades 1 tick through it
  (042 ~59:04) [2023]. An imbalance is not liquidity (033 ~24:34) [2023].
- **A3 Relative equal highs/lows (REH/REL)** = 2+ highs (lows) close together; the smoother, the
  stronger the magnet; they get run even under an older higher high (Ep 04; 006 ~26:43; 025
  ~36:20; cc01_003 ~15:23; cc04_014 ~2:17) [both]. Nearly level bodies count even if wicks differ
  (cc05_003 ~1:07:26); draw the REL line at the lower of the two lows (038 ~43:43). ICT never gives
  a tolerance. Bot: `eq_tol_pts=0.5` ES pt, cluster extreme = the pool.
- **A4 Bodies vs wicks.** Bodies mark the real level and "tell the story"; wicks "do the damage".
  A 1-2 tick wick beyond a level ("mohawk") still counts as respect (019 ~14:55; 032 ~9:00; 038
  ~46:16; 042 ~1:07:39; 065A ~2:53:30; 096 ~12:04) [2023]. CC: stops sit beyond the body cluster, a
  sweep need not take the wick (cc02_008 ~9:03; cc03_002 ~2:01; cc05_004 ~13:35) [CC]. Bot: a
  sweep = trade past the wick extreme.

**Gaps**
- **A5 Fair value gap (FVG).** Bullish (BISI) at candle 3: low[c3] > high[c1], zone
  [high c1, low c3]; bearish (SIBI): high[c3] < low[c1]. Known at the close of c3; c2 is the
  displacement candle (001 ~13:02; 024 ~23:22; 056 ~6:08; cc04_012 ~1:52) [both]. Measured on
  wicks (old CC body version cc01_006 is superseded). Bot: `levels.fvgs`, matches.
  - Levels: high, low, CE = 50%, plus 25/75% quadrants on large gaps only (020 ~8:21; 029 ~30:44;
    055 ~4:50; 101 ~51:58) [2023]. CE of a higher-TF FVG is the default session objective (029
    ~44:48).
  - Extend the box to an adjacent volume imbalance; a body gap inside the FVG gives the exact limit
    price (022 ~55:00; 098 ~60:00; cc04_012 ~12:27) [both].
  - Validity: c3 closes, a new candle opens, and price trades back in without first taking the low
    (042 ~34:53). It must sit on the path to the draw (048 ~28:06; 091 ~14:27) [2023].
  - State: a touch = "repriced"; "rebalanced" only after price trades through and leaves; "filled"
    needs bodies through, not wicks (021 ~12:28; 050 ~30:29; cc10_011 ~4:29; cc04_012 ~13:08) [both].
  - Expected reaction: a retrace into a BISI most likely stops at its top or CE; the far edge is
    least likely. When bullish, price should hold the upper quarter (022 ~9:09; 030 ~15:46) [2023].
  - Two FVGs in one leg: the retrace may go to the higher (second) one (042 ~47:20; 082 ~5:31).
    Skip an FVG sitting right above a liquidity pool (060 ~1:10:30) [2023].
  - An FVG overlapping an OB: the FVG near edge comes first (065B ~3:02:40) [2023].
  - Lifetime: extend forward and reuse after fills, up to 60 days back (015 ~22:49; 051 ~19:34;
    065B ~3:58:20) [2023].
- **A6 Gap types** (062 ~43:58) [2023]:
  - Breakaway gap = first FVG leaving a consolidation or expected level after an MSS. It must stay
    at least partly open and may retrace at most to its half; the range it leaves is "protected"
    (001 ~40:03; 002 ~4:35; 003 ~27:46; 062 ~37:02; 065B ~4:39). Fully filled = not breakaway.
  - Measuring gap = FVG near the middle of the move; project swing extreme -> near edge of the gap,
    target -1 SD (003 ~31:35; 011 ~6:37; 061 ~1:22:05; 062 ~42:19).
  - Common gap = ordinary FVG, may be revisited.
- **A7 Immediate rebalance** = the next candle trades straight back to the prior candle's extreme
  with no gap; a strong continuation signature (048 ~39:02; 060 ~7:20; 092 ~1:41:14; 099 ~3:46)
  [2023]. Daily version: the open trades exactly to the prior day's high/low (059 ~4:18) [2023].
- **A8 Inversion FVG (IFVG)** = an FVG that a candle closes beyond; it then acts in the opposite
  role (015 ~21:00; 061 ~19:42; 078 ~53:07; 102 ~1:02:03) [2023].
  - Valid only when a candle closes beyond, a NEW candle opens, trades back into it and it holds; a
    spike through and back does not count (048 ~21:32, ~36:40).
  - Allowed depth: one prior pass -> may reach the far edge; partly re-traded -> near edge to CE;
    traded both ways -> near edge, CE at most (102 ~1:09:00). Bearish IFVG retraces usually stop at
    CE or a little above (078 ~50:28).
  - Bias switch: the same 1m gap is a long target before the HTF array is hit and an IFVG short
    after it (086 ~14:12).
- **A9 Volume imbalance (VI)** = consecutive bodies do not overlap while wicks do; bullish:
  min(o,c)[i] > max(o,c)[i-1] and low[i] <= high[i-1] (003; 009 ~2:16; 022 ~54:26; 090 ~13:01)
  [2023]. Use its low as a stop; it may be touched but not pierced (009 ~13:46). It is dead once a
  later body on its own (or higher) TF closes fully across it (035 ~5:50; 090 ~13:01). VIs are
  "flexible", FVGs strict; clusters of VIs = "porous", low trust (027 ~22:09, ~27:38). Bot:
  `levels.volume_imbalances`, matches.
- **A10 Liquidity void** = a true price gap (high[i-1] < low[i]) and, above all, session/week gaps
  with no prints (NWOG, NDOG, ORG) (001; 003; 028 ~36:17; 039 ~3:06; 074 ~20:51) [2023]. CC's
  "range of one-sided candles" (cc04_010; cc06_003) is treated as a displacement leg whose start is
  a fill target, not as a void [CC].
- **A11 Balanced price range (BPR)** = overlap of a bullish and a bearish FVG (046 ~50:02; 065B
  ~4:21; 104 ~24:35) [2023]. Trading TO it is easy, THROUGH it rare; expect probes; a body close
  through its midpoint = abort (026 ~1:05:53; 065B ~4:28; 100 ~22:07). Bot: `balanced_ranges`,
  unused.

**Blocks**
- **A12 Order block (OB).** Bullish = last down-close candle (or run of consecutive down-close
  candles, blended into one) before the up move that breaks structure; bearish mirror (002 ~4:14;
  029 ~29:28; cc04_003 ~0:35; cc04_008 ~2:39) [both].
  - Anchor: open of the first (highest, for bullish) candle of the run (032 ~52:45; cc05_015
    ~16:46). Sensitive range = high down to open (012 ~5:13; 071 ~35:37; cc06_004 ~18:12). Stubby
    wick -> use the open; long wick -> use the low and the wick CE (055 ~1:44; 061 ~26:10).
  - Validation: 2023 = change in state of delivery (CISD): price first trades through the open of
    the last opposite candle before the MSS, then the OB low must hold (075 ~1:16:40; 078 ~53:53).
    CC = a later candle trades above the OB high (cc04_003 ~0:35).
  - Quality: an FVG right after it; larger body; move away >= 2-3x the OB body (022 ~13:12; 064
    ~50:06; cc04_003 ~26:51). When several down candles are run through, use the original/highest
    (012 ~14:06).
  - **Mean threshold (MT)** = 50% of the OB; bodies must not close through it, wicks may (002
    ~3:45; 036 ~54:00; cc02_004 ~3:28). Measured on bodies or full range: D4. Bot:
    `order_block().mid` = full range.
  - Opposing OBs are targets and profit spots, not counter-trend entries (cc01_004 ~36:31; 065A
    ~1:38) [both]. Once price trades through an opposing OB's MT, its other half should not be
    revisited (065A ~1:39).
- **A13 Breaker.** Bullish: swing low L1, swing high H, lower low L2 that runs L1's sell stops, then
  price breaks above H; the zone is the up-close candle at H. Bearish mirror uses the down-close
  candle at the swing low (001 ~45:02; 007 ~22:46; 012 ~11:07; cc04_005 ~0:37-3:32) [both].
  - Candle: the highest up-close candle in the swing by body (029 ~24:13; 048 ~1:06:07; 096 ~6:42).
    Bot: last up-close candle within `pivot_n` bars before H.
  - Zone extent (body, full range, A-B leg, last candle): D6 (`breaker_zone` range default /
    body / leg / last). MT of the zone should not be closed through (018
    ~1:22; 070 ~56:01).
  - First touch is valid; bodies respect, wicks may poke (022 ~2:47:00; 033 ~57:56).
  - A high-low-higher-high at the wrong time of day is "time distortion", not a breaker (070 ~6:24).
- **A14 Unicorn** = an FVG overlapping the breaker zone; strongest right after a sell-side run at the
  09:30 open (007 ~22:39; 101 ~84:31) [2023]. 104 uses the word for a 2nd-stage redistribution OB;
  ignore that usage. Bot: implemented, preferred FVG.
- **A15 Mitigation block** = the breaker's failure-swing twin: high A, swing low, LOWER high B (no
  stop run above A), break below the swing low; the zone is the last down-close candle in that
  swing low (cc04_004 ~2:42-14:35) [CC]; bullish mirror (033 ~1:03:50) [2023]. Weaker than a
  breaker; ICT uses it more as a target (075 ~21:40). Bot: tag only (P2).
- **A16 Propulsion block** = a down-close candle that trades into an earlier bullish OB and becomes
  the new support; on return price should tag its high and leave; losing its MT = idea wrong
  (cc04_008 ~0:30-5:40; 027 ~11:31; 079 ~10:27) [both].
- **A17 Rejection block** = a swing high of long-upper-wick candles; zone = highest open/close of the
  swing up to the highest wick, any candle colour (cc04_006 ~5:04-10:43) [CC]. 2023 uses only the
  body edge as a level: price running the bodies does the same work as running the wicks (015
  ~2:15; 059 ~10:03; 066 ~40:41). Bot: `rejection_blocks`, unused.
- **A18 Reclaimed OB** = in a market maker model, each down candle on the sell side of the curve
  followed by a bounce; do not buy them on the way down; buy their retests on the buy side of the
  curve after the low (cc04_007 ~0:50-5:00; 104 ~46:56) [both]. Not codeable in real time (needs
  the curve low).

**Structure**
- **A19 Market structure shift (MSS)** = after a sweep, price breaks the swing high (low) that led
  into the sweep extreme, with displacement leaving an FVG (002 ~2:37; 006 ~16:59; 022 ~38:38)
  [2023].
  - Which swing: the one that led to the high that ran liquidity, the parent swing, not a minor
    one (010 ~41:31-46:19; 058 ~41:15). A single short-term break is "aggressive"; with relative
    equal lows, wait for the lower one (044 ~42:55). Bot: the swing high before the sweep extreme.
  - Wick or close: D3. Bot: body close (`c[i] > ref`).
  - Two MSSs, each leaving an open FVG = "on side" (006 ~49:16).
  - Do not trust a shift until the relevant liquidity run has happened (Ep 08).
- **A20 Displacement** = fast, large one-directional candles that leave FVGs (006 ~9:55; cc01_004
  ~6:13). The only number given: the move away >= 2-3x the OB body (cc04_003 ~26:51). "Speed and
  distance": price must rip through the trigger high, the next candle should follow (009 ~15:51;
  027 ~33:57). Bot: displacement = an FVG forms within `fvg_wait` bars of the break.
- **A21 Premium/discount.** Equilibrium (EQ) = 50% of the dealing range; buy below, sell above
  (022 ~48:15; cc01_004 ~10:26; cc05_014 ~17:34) [both].
  - Intraday range after an MSS = the displacement leg (sweep extreme to the high that broke
    structure) (010 ~58:09; 022 ~38:38). Day context = 20-day high/low (cc07_004; cc09_008 ~12:42).
  - Zones: OTE 62-79%, 70.5% sweet spot; strict = lower/upper third; 0.2-0.3 deep discount, 0.8-0.9
    deep premium (cc01_004 ~23:59; cc01_006 ~2:07; cc06_004 ~31:39) [CC]. Threshold: D12.
  - Wicks for intraday legs, bodies for multi-day ranges (014; 058 ~41:54; cc07_005 ~3:10).
  Bot (bias_htf): `day_pd="20d"` / `pd_day_range` / `pd_body_multiday` (bodies for the multi-day range), `pd_zone` half / third / deep / ote with `ote_band`; the pd20 column.
- **A22 PD-array matrix**, outward from EQ: mitigation block, breaker, liquidity void, FVG, OB,
  rejection block, old high/low; discount mirror (cc05_014 ~18:20-29:36; cc07_004 ~1:01) [CC].
  Price meets them nearest first; a breaker in the path usually stops price before the arrays
  beyond it (cc05_014 ~21:04; cc09_008 ~9:59). Skip exhausted arrays, prefer untested (cc07_004
  ~4:00).
- **A23 Wick CE** = 50% from body edge to wick tip; a wick is a gap (012 ~4:14; 021 ~21:06; 028
  ~16:43) [2023]. A long wick in the bias direction often stops dead at its CE; a next-candle close
  beyond the CE = continuation, close back = revisit (025 ~25:37; 100 ~38:13). Bot:
  `wick_midpoints`; `wick_levels` (on) for the prior day, `wick_days` / `wick_weekly` /
  `wick_both` / `wick_session` switches (levels_detectors).
- **A24 Not codeable as stated:** implied FVG (035 ~29:49, named once, never defined); Reaper
  (076 ~18:30); "inducement" (not an ICT term in the notes; the bot's sweep step is the closest
  codeable form).

### 2.2 Bias (higher timeframe)

- **B1 Why price moves.** Price moves only to run liquidity (old or relative equal highs/lows) or to
  rebalance an inefficiency (FVG, VI, gap, wick, void, up to ~60 days old); otherwise it
  consolidates (038 ~47:04; 050 ~8:01; 061 ~41:29; 104 ~14:19; 065A ~46:30) [2023].
- **B2 Draw search order:** inefficiency first; if none, liquidity: from premium, sell-side below an
  old low; from discount, buy-side above a short-term high (065A ~50:00). Beyond the obvious pool,
  the nearest inefficiency sets how far the run goes (104 ~16:18) [2023].
  Bot (bias_htf): `htf.table` columns draw_ord / draw_ord_lvl / draw_ext_lvl (inefficiency first, then P/D liquidity, then the extent); `htf_bias="ordered"`; `draw_lock_pick="ordered"` (and "largest" for B3's largest move); `draw_ext_target` makes the nearest inefficiency beyond a pool the locked target.
- **B3 Bias = direction toward the next draw**, decided before the session; then take ONE
  direction only (019 ~13:57; 054 ~7:45; 067 ~12:00) [2023]. Bias is the direction of the day's
  largest move, not the first move; expect the first delivery against it (068 ~16:30; 082 ~8:02).
  Narrative (how the day trades) is separate from bias (001 ~17:01). Bot: no HTF bias; both sides
  are scanned every session (P3 `htf_bias`).
  Bot (bias_htf): `want_all_engines` (the Silver Bullet / Ma Deuce honour `htf_bias`, each pre-09:30 session reads the table cut at its own lock time), `judas_required` tag / filter (the bias side waits for price delivered against it by `judas_min_pts`), `draw_first="session"` umbrella (L14 / L14a).
- **B4 Bias is a condition, not a trade.** It still needs displacement in its direction, an FVG, a
  retrace into it and a valid time of day; no setup = no trade (063 ~12:22-15:47; cc12_003 ~25:07)
  [both].
- **B5 Timeframe chain.** Weekly direction first, daily is where most work is done; intraday dips in
  a bullish week are buys (064 ~1:44:34; 095 ~12:52; 065A ~46:30) [2023]. Day-trade ideas not
  aligned with daily/weekly/monthly arrays (4h minimum) are not high probability (cc07_007 ~26:34;
  cc09_004) [CC]. Bellwether chart: 15m (013 ~2:36; 065B ~05:01). Top-down sequence on news days:
  daily VI, 60m, 30m, 15m, 5m, 1m (Ep 02).
  Bot (bias_htf): `weekly_gate` (no side against the weekly bias), `news_topdown` (release day: the daily VI sets the side), `bellwether_15m` (the 15m read must not deliver against the side).
- **B6 Institutional order flow (IOF), scored on the daily.** Bullish = down-close candles hold as
  support, up-close candles get run through, every short-term low taken reverses at once; bearish
  mirror (cc12_003 ~11:41; 075 ~1:21:40; 099 ~14:56; 102 ~1:42:05; cc06_002 ~4:53) [both].
  {SPX/NDX daily bars from 1m}
  Bot (bias_htf): `htf.table` column iof (candle respect + pivot raids over `iof_days`), `htf_bias="iof"` / `"combo2"` (react, else IOF, else P/D).
- **B7 Daily OB MT close rule.** Bullish flow is intact while no daily close is below the MT of the
  last daily bullish OB; a close through it is "definitive failure" (058 ~6:01-7:41; 007 ~2:15). A
  daily close below 50% of the last down-close daily candle = high of the week probably in (101
  ~32:58) [2023]. Bot: `weekly_bias` (off) codes Ep 05's one-week case only (strong day, close
  back through 50% of its wick); generalise (P3).
  Bot (bias_htf): `htf_bias="ob_mt"` (the ob_mt state column), `how_rule` (a close below 50% of the last down-close candle = high of the week in; "no_long" blocks longs for the rest of the week).
- **B8 Close-based bias flips** (closes, not wicks) [2023 unless noted]:
  - daily close through the last daily OB MT (B7);
  - bodies closing through three PD arrays against the idea (098 ~47:00; 078 ~1:02:38);
  - weekly close below the low of the last down-close weekly candle -> favour sells (077 ~9:19);
  - daily close above Friday's high / a wick CE / a weekly wick's upper quadrant (077 ~10:53; 098
    ~67:30; 102 ~6:45; 103 ~2:29);
  - Thursday trade back through the weekly open against the bias (cc08_001 ~24:20) [CC];
  - stopped out above a breaker high cancels the SMT idea -> long bias for the rest of that day
    (042 ~1:08:19).
  - Bot: the htf `flip` column (`htf_bias="flip"`, `flip_triggers`): ob_mt (B8a), flip_pd3 (B8b),
    wk_dc (B8c), flip_close_above (B8d, result neutral), flip_thu_wopen (B8e), each applied from
    the next session; B8f is the intraday engine switch `stop_flip` ("breaker" / "smt").
- **B9 Not a flip:** HTF target reached (= neutral, B17); two down days inside a daily uptrend (a
  retracement, cc05_003 ~1:34:51); a failed daily array (look to the next weekly array,
  cc05_015 ~18:45); the counter move after the open (= Judas swing, 013 ~4:52; 082 ~8:02) [both].
  An intraday MSS may need no close (see D3), but bias flips use closes (012 ~30:30; 026; 075).
  Bot (bias_htf): `objective_neutral` (day / week / both: the draw delivered -> neutral), `bias_persist` (an opposite reading must repeat, or a close-based flip agree), `next_array_on_fail` (a failed daily array -> the next weekly array is a re-buy).
- **B10 MWD sequential** [CC]: a timeframe is bullish when a discount array there produced
  displacement. Month+week+day bullish: buy every daily/4h discount array. Day correcting: buy
  daily arrays only inside weekly arrays. Week+day correcting: only at monthly arrays. Only a bearish
  breaker on a timeframe cancels it (cc06_004 ~1:02-14:47; cc06_005 ~0:46). {1m-derived}
  Bot (bias_htf): `htf_bias="mwd"` (month / week / day displacement states, cases A / B / C), `mwd_nest` tag / filter (cases B / C: entries only inside the weekly / monthly arrays).
- **B11 Candle-pattern day context** {1m-derived}: inside day -> large range next (012 ~16:17);
  inside week -> expansion within 2 candles, else scalp only (103 ~12:53); down-close outside day
  -> lower prices until that day's high is taken (081 ~1:31); after 3 consecutive up (down) daily
  closes, no longs (shorts) on day 4 (cc08_006 ~2:07) [CC]; inside bar or smallest range of 3/7
  days -> expansion, no direction (cc06_007 ~21:24) [CC].
- **B12 Intraday power of three (PO3) location.** Bullish day: buy at or below the midnight open
  (open of the 00:00 15m candle); bearish: sell at or above it; best shorts above it and best longs
  below it in both the AM and PM (006 ~5:51, ~23:28; 043 ~4:11; 060 ~15:20; 069 ~8:38; cc03_003
  ~31:25; cc08_002 ~5:15) [both]. The line runs 00:00-11:00 (069 ~4:37). PM uses the 13:30 open
  the same way (010 ~56:30). Bot: `use_bias=True`, midnight = first bar at/after 00:00 (SPY: 04:00
  proxy; the CFD data has a true midnight, P1).
- **B13 Weekly open.** Sunday 18:00 open and/or Monday 00:00 open. Bullish week: best longs below it
  early in the week, then buy each day while above it; bearish mirror; valid until an opposing
  daily PD array is hit (048 ~1:00:10; cc08_001 ~22:58-29:03; cc12_003 ~19:03) [both]. {needs:
  Sunday 18:00 = futures data; Monday 00:00 is in the CFD data}
  Bot (bias_htf): `weekly_open` sun18 / mon00 / either (the week's direction side: longs below the open Mon-Tue, above it from Wednesday; expired at an opposing daily array).
- **B14 NWOG regime.** Price keeps returning to the current NWOG = consolidation week (scalp, small
  targets, no runners); leaves sharply and does not return (one retest allowed) = trending week;
  converging NWOGs = consolidation (025 ~3:11; 030 ~10:17; 039 ~12:26; 051 ~9:25-13:30; 053 ~1:31)
  [2023]. Bias vs NWOG: bullish while above the current NWOG, bearish until back above the NWOG low
  (036 ~16:00; 058 ~53:46).
  Bot (bias_htf): `nwog_regime` (returns to the gap, converging gaps, `nwog_converge_pts`), `nwog_bias` / `htf_bias="nwog"` (hold until reclaim, `nwog_bias_reclaim`).
- **B15 ORG direction tell.** If 09:30 opens below the prior RTH close and makes no attempt back to
  it within ~30 min = very bearish; mirror for a gap up (030 ~1:27:01). Bullish + gap up = fill then
  higher; bearish + gap up = the fill is a false run (055 ~17:50) [2023]. {1m}
- **B16 No bias before the Sunday open.** Write both gap scenarios; if neither plays out, wait for
  Monday 09:30 and trade from Tuesday (028 ~1:09:37-1:16:09; 077 ~7:30; 084 ~3:21; 103 ~7:22)
  [2023].
- **B17 Neutral / no bias** [2023 unless noted]:
  - 50/50: if the concepts can frame the other side, no trade (025 ~11:18; 046 ~0:10; 095 ~27:33;
    100 ~1:35:38; 101 ~40:33).
  - Stuck at a premium array or in chop: wait for 09:30 (010 ~14:05; Ep 08).
  - Weekly/HTF draw delivered -> neutral, stop for the week, expect consolidation, not reversal
    (038 ~6:33; 061 ~2:33:05; 099 ~15:51; 101 ~34:21; cc10_019 ~15:47) [both].
  - Daily chart in a multi-day range = scalping market (031 ~9:20; 043 ~6:51); price inside one daily
    BISI range = don't trade that index (091 ~6:12); after a one-way multi-day run into an HTF
    premium array = sloppy session (044 ~1:14:47).
    Bot (#10, opt-in `sloppy_tests`): "premium_run", "inside_bisi", "fomc_week" (Ep03 00:18:23) [our
    interpretation]; `sloppy_mode` decides tag / stand aside / scalp.
  - Indices decoupled (ES/NQ/YM not in step) = high-resistance runs: scalp or skip; SMT both ways
    with no bias = no trade (045 ~1:01:43; 046 ~1:06; 090 ~41:00) [2023].
  Bot (bias_htf): `neutral_gate` tests (fifty_fifty, premium_chop, draw_delivered, range_market, decoupled) with `neutral_gate_mode` tag / skip / scalp, `neutral_5050` (armed / react), `objective_met_stop` (stand aside once the draw is met), `chop_mode` (Ep 08), `decoupled_mode` and `smt_both` (B17.5), `bias_neutral="scalp"` / `no_narrative_scalp` (Ep 02).
- **B18 SMT** (ES vs NQ vs YM): one index fails to confirm the others' lower low (bullish) or higher
  high (bearish) at a PD array (Ep 03; 022; 065B ~05:04) [both].
  - It is a qualifier, never a signal on its own (031 ~0:44:53; 070 ~21:14; 099 ~55:07). If not
    obvious, it isn't there (cc10_011 ~16:59).
  - Windows: AM 05:00-09:30 or "London into 09:30" (cc10_011 ~8:01; cc10_014 ~1:15); PM 12:00-15:00
    (cc10_012 ~7:25) [CC].
  - Uses: bias, partial exits (sister refuses to break -> bank ~50%, 046 ~1:02:40; YM lower low while
    ES/NQ hold -> most off, 037 ~32:56), instrument choice (D15). Bot: `_smt` tag, two-index (SPX vs
    NDX); YM {needs: DJI 1m}.
- **B19 Intermarket** [2023 unless noted]: DXY up = risk-off; no ES longs while DXY rallies above its
  dealing-range high; an ES lower low should come with a DXY higher high (031 ~7:54-29:52; 036
  ~59:00; 045 ~42:05; 095 ~26:17). {d: DXY daily; intraday needs: DXY 1m}. Bonds and stocks move
  together; bonds in a range -> all markets consolidate (061 ~1:05:42; cc10_008 ~8:47; cc05_009
  ~5:02) [both] {d: FRED yields}.
  Bot (bias_htf): `dxy_gate` (the dollar's prior close above its 20-day high and rising: no longs), `bond_range` (yield range: tag / scalp / skip), `bond_dir`; `intermarket_model` umbrella. Daily files in data/mentorship/yahoo, prior sessions only.
- **B20 COT / OI / sentiment** [CC]: commercials' net vs the midpoint of its 12-month range = buy or
  sell program (cc10_001; cc12_003 ~4:25); OI drop 10-15%+ into HTF support = bullish (cc05_003
  ~58:26; cc12_003 ~10:42); weekly Williams %R extremes (cc12_002 ~12:17). Optional enhancers only
  (cc06_002 ~0:24). {d: CFTC COT; needs: CME OI history}
  Bot (bias_htf): `cot_tag` (files in data/mentorship/cot; none shipped), `oi_tag` (data/mentorship/ES_oi.csv, roll-summed), `wpr_tag` (weekly %R(14) from our bars); `cot_oi_model` umbrella.
- **B21 IPDA data ranges** [CC]: look back 20/40/60 trading days; the high/low of each are the
  near/short/intermediate pools; 20-day most sensitive (015 ~4:25; cc05_004 ~1:56; cc09_008 ~6:03).
  If the 20-day extreme is taken, the 40-day, then 60-day are next (cc05_003 ~28:38; cc07_004).
  Price near EQ of all three with both sides run -> range day until news (cc05_003 ~1:18:26).
  Default: roll daily from yesterday (cc09_008), not anchored on the quarterly shift.
- **B22 Quarterly shift**: a major turn or consolidation every 3-4 months; bias and sizing context,
  not timing (cc05_001 ~5:05; 084 ~22:12; 098 ~58:30) [both].
  Bot (bias_htf): `qshift_tag` / `qshift_size` (60-session turn or consolidation, due 3-4 months later, 252-session trend).
- **B23 Seasonals** (road map, never a trigger; use only when long- and short-sample lines agree and
  HTF trend agrees; a missing seasonal signals strength the other way) (cc05_010; cc05_011; 074
  ~49:22) [both]. Index map (Dow 20-yr, cc10_015 ~5:04): Jan bearish, Feb bullish, Mar
  consolidation, Apr bullish, May bearish, Jun consolidation ending bearish, Jul bullish, Aug
  consolidation, Sep split, Oct-Dec bullish; Mar/Jun/Aug low probability. Sources disagree on
  January and late May (cc10_016; 050 ~2:20; 074 ~16:54). Bot: tag only.

### 2.3 Day selection and news

- **N1 NFP Friday: no live trading.** Nobody trades the first hour after 08:30; experienced traders
  wait out the volatility (Ep 04; 006 ~8:35; 061 ~2:49:35; 105 ~11:50; cc08_001 ~6:37; cc08_006
  ~4:45) [both]. He traded several NFP Fridays live, each labelled an exception (071; 088/089;
  105). Don't pyramid on NFP (105 ~9:13). Bot: `nfp_day` trades the day (owner #4: the 30-minute floor); `nfp_first_hour` (on) drops the
  pre-09:30 windows and Ma Deuce on jobs days, `nfp_no_adds` (on), `nfp_day_from` test, the `nfp` day tag. D8.
- **N2 NFP week**: trade Mon, Tue and Wed until 11:00 (end of the NY AM). No Wed PM, Thu or Fri. If
  nothing is done by Wed 11:00, the week is done. A "training wheels" rule (Ep 03; 038 ~8:05; 101
  ~25:12-39:39) [2023]. Monday of NFP week is always a trading day (100 ~33:00; 101 ~30:41). Bot:
  blocked (`nfp_week_thu_fri`, `nfp_week_wed_pm`), relative to the week's REAL jobs date (calendar.nfp_date: Thursday NFP
  weeks - 2025-07-03 - shift the rule by one day). D8.
- **N3 FOMC** (14:00 statement, 14:30 press conference):
  - Never trade the 14:00 release; 14:00-14:45 is observation only; the 14:00 move is usually fake
    and the real move starts 14:25-14:30; after 14:45 the normal routine applies (Ep 03; 021
    ~2:40-6:18; 065B ~5:30) [2023].
  - CC: never hold into the afternoon release; the AM may be traded if the trending-day recipe holds
    (cc10_009 ~3:48); also listed as "sit out, demo only" (cc08_001 ~6:37) [CC].
  - FOMC-only day: expect AM consolidation, PM volatility (cc10_008 ~2:56).
  - Day before FOMC: slow and imprecise, trade light (042 ~3:50; 094 ~1:48). Day after: sit still
    in the AM (095 ~51:27). Don't re-enter if stopped on FOMC (021 ~43:56).
  - After an FOMC whipsaw (both sides of the 14:00 range taken) skip the next London open (cc08_006 ~3:36).
  - Bot: FOMC PM blocked until `fomc_pm_from` (14:45); AM open (`fomc_am` open / recipe / skip); `fomc_flat` (on) closes anything opened
    before the release at 14:00; `fomc_observe` scans 14:00-14:45 and holds the order; `fomc_judas` (M9.2: the first run in
    14:00-14:30 is the Judas, trade the other side from 14:30); `fomc_pm_block_from`, `sb_fomc_pm`; `fomc_only_am`
    (consolidation scalp / skip); `fomc_eve_risk`, `skip_pre_fomc`, `fomc_after_am_block` / `skip_post_fomc_am`;
    `fomc_no_reentry` (on: a loss ends the FOMC day for every model); `fomc_whipsaw_skip_london`. D8.
- **N4 CPI** (08:30): no position into or at the release; stops don't protect (030 ~7:22; 047 ~5:26;
  064 ~4:35). After the print, trading toward remaining liquidity is fine (028 ~3:40; 064). Day
  before CPI: no trade ahead of it, or small bread-and-butter only (028; 029 ~5:22) [2023]. Bot:
  entries start 09:30 + the dealing range; `pre_flat_0830` also flattens PRE8 / LON / Ma Deuce / London SB before 08:30;
  `pre_cpi` off / small / skip (`skip_pre_cpi`). D9.
- **N5 Other releases** [2023]:
  - After any scheduled release, wait for the news dealing range (post-release manipulation
    high/low) to form, then trade from it toward external liquidity; no fixed minute count (Ep02
    ~0:12-1:01; Ep04 ~28:16-31:26). "~30 min" is NFP-only (Ep04 ~8:23); 065B's blanket 30-minute
    rule is kept only as `news_wait="fixed"`. [owner correction #4] Bot: `news_wait="range"`
    (two-swing formation test, NFP 30-min floor, 90-min cap = [our interpretation]).
  - 09:45/10:00 releases (PMI, ISM): wait for the release, not just the 09:30 open (Ep 02; 002
    ~0:25). Bot: AM starts 10:00 on 10:00-release days.
  - No 08:30 news ("soft bias"): wait for 09:30 (Ep 05; 007 ~11:14; 019 ~7:57).
  - Two drivers in one session (08:30 and 10:00): stand aside or at least don't trade ahead of the
    second; expect whipsaw (100 ~50:59-1:40:56). Ideal = exactly one release in the session
    (cc08_006 ~5:59) [CC]. Bot: `two_driver_gate` (on: no pre-open window ends before the second release; the AM waits for
    its range), `skip_two_drivers`, tag `two_driver`.
  - Fed chair testimony/speech at 10:00: no AM trades, not even demo; use the chart 5-15 min after
    it ends; trade 13:30-16:00 (037 ~3:09; 038 ~39:59; 067 ~0:34). Bot: `fed_chair_skip_am` (on) from calendar.FED_CHAIR (the
    semi-annual testimony days, typed from memory - UNVERIFIED, extend FED_CHAIR_EXTRA).
  - Treasury auction day: avoid the AM (cc10_008 ~7:29) [CC]. Bot: `skip_auction_am` (off) from calendar.is_auction_day (the 3-/10-/30-year
    week rule, approximate; AUCTION_EXTRA / AUCTION_SKIP override).
  - Minor releases: `news_claims` (jobless claims Thursday 08:30, Wednesday before a holiday) and `news_minutes` (FOMC minutes 14:00,
    21 days after the decision) count as releases for the dealing-range wait (off).
- **N6 News delivery profile**: the side taken first after the release is usually false; the
  opposite pool is the real move (up-down-up / down-up-down) (064 ~52:12; 073 ~10:42; 078
  ~1:25:47) [2023]. After both pools are taken, price retraces to the CE between them (064
  ~1:10:43). On NFP/CPI/FOMC days breakers reject poorly (073 ~4:36).
- **N7 Holidays and calendar** [both]:
  - Day before a long weekend/holiday (and bank holidays): skip (cc08_006 ~5:06; cc10_008 ~6:54;
    cc10_019 ~15:02) [CC].
  - Morning after a holiday: choppy, no trade; PM or next day once ES/NQ move in step (090 ~8:00)
    [2023]. After a Monday holiday, Tuesday acts like Monday, Wednesday is the likely reversal day
    (cc09_008 ~55:24).
  - Holiday weeks deliver cleaner Thu/Fri (072 ~3:36) [2023].
  - Last trading day of the year: low volatility, expect an inside day; first trading day: don't
    rush (Ep 01; Ep 02).
  - Futures rollover week: more volatile and choppy (093 ~0:32). Bot: `roll_week` tag (calendar, the data's roll flag, or either: `roll_week_src`), `roll_risk`, `skip_roll_week` (N7.5).
  - August: choppy "meat grinder", trade small or stand aside, especially the last two weeks (079
    ~8:54; 084; 087) [2023].
- **N8 Day type** [both]:
  - Consolidation = no trade; wait for expansion (cc01_001; cc09_003).
  - Trending-day recipe needs all three: small/contracting prior ranges, price just traded into a
    daily PD array, and high/medium 08:30 news (cc10_009 ~1:17-2:46) [CC].
  - Consolidation-day predictors: no NY report today with reports later in the week; price at an
    HTF array or HTF 50%; holiday eve; auction day (cc10_008 ~1:51-7:47; 053 ~0:38). On such days:
    AM scalps only if the opening range is small, done by 11:00, PM only if the AM has not run a
    stop pool (cc10_008 ~9:01-17:19) [CC].
  - Large opening range gap or very large prior-day range: the first 30-45 min chop; sacrifice the
    AM, trade 13:30-16:00 (033 ~13:27) [2023].
  - Prior day's range > 2x the 5-day ADR (ADR5): skip, chop (cc08_006 ~1:22, London); prior day
    under ADR5: expansion of 1.5-2x due (cc08_006 ~23:33) [CC].
  - "Seek & Destroy" (both sides run, then reversal): don't hold trades; such weeks come while
    waiting on rates/NFP and in July-August (024 ~13:57; 044 ~1:36:11; cc07_002 ~7:42).
- **N9 In-day no-trade conditions** [2023]:
  - No clear draw, no inefficiency, no displacement: no trade (045 ~31:22-40:49).
  - Draw delivered before 09:30: choppy 09:30, trade the PM (022 ~1:16:11).
  - Daily objective done before lunch: skip the rest of the day (015 ~16:22).
  - Overnight range too narrow, or the pre-09:30 raid too shallow: no AM trade (015 ~11:58).
  - Macro window (09:50-10:10 or 10:50-11:10) produces no move toward the draw: close the charts
    for that session (073 ~30:51).
  - London already made ~80% of ADR5: skip NY (cc08_001 ~13:41) [CC].
- **N10 Day of week** [both]:
  - Sunday open: don't trade it (011 ~4:20; 028 ~1:16:09; 103).
  - Monday: new students don't trade it (065B ~4:12); outside NFP/FOMC weeks he skips it unless
    obvious, or trades the PM only (101 ~30:53); "let Monday go", enter Tue off Monday's low or
    Wed off Tuesday's low (cc12_003 ~15:40). Many 2023 examples are Mondays (007, 018/019, 036,
    053, 069). D20.
  - Tue and Wed are ideal; Thu good but can reverse and often makes the opposite end of the week
    (cc08_001 ~18:52; 044 ~16:25; 060 ~1:11:50; 099 ~1:02:09). The weekly high/low forms Mon-Wed
    ~70% of the time (cc07_008 ~1:35) [CC]; a Thu/Fri break of the Mon-Wed extreme = expansion to
    target (cc07_001 ~42:44).
  - Friday: small range unless the weekly objective is unmet (cc08_001); take most at the first pool
    because the HTF target may not come (070 ~1:06:37); no trade after a week whose targets were all
    met (100 ~7:05); don't buy Friday after a strong Thursday (cc09_008 ~41:53). TGIF: M14.
  - No positions over the weekend or across 17:00-18:00 (065A ~2:30:30; 101 ~4:27; 103 ~9:31).

### 2.4 Times and sessions

- **T1 Clock.** New York time, daylight saving included; ignore platform GMT dividers (Ep 01;
  023 ~16:40; cc08_002 ~0:31) [both]. Time-based charts only, no Heikin Ashi/range/renko (Ep 03).
  Caution: CC Barchart index/bond charts are Central time (NY = CT + 1h) and some 2016 FX charts are
  MT4 server time, so their clock labels are not NY (cc10_011; cc01_008).
- **T2 Opening prices.** Midnight (true daily open, preferred), 08:30 ("trigger time"), 09:30; 13:30
  for the PM (010 ~38:31, ~56:30; 013 ~4:52) [2023]. After a release, retrace bodies stop at the
  08:30 open (064 ~55:13). 0 GMT open [fx-only] (cc08_008). Bot: `levels.opens`.
- **T3 Kill zones.** London 02:00-05:00 (he uses 01:00-05:00 personally), HOD/LOD usually 02:00-04:00
  (Ep 06; cc08_001; cc08_005 ~3:28); NY 07:00-09:00 (FX) or 07:00-10:00; ICT's futures kill zone
  08:20-11:00 (cc10_007 ~4:35); London close 10:00-12:00 (Ep 06; cc08_002 ~4:32). Asia 20:00-00:00
  is FX only; indices start at midnight (095 ~20:23). For the bot only the London 02:00-05:00
  high/low matters, as a liquidity pool (067).
- **T4 Opening range (OR).** OR = 09:30-10:00 "always"; don't trade it: erratic, the first move is
  often a Judas; bias is read from how it delivers; take an earlier setup only if obvious (029
  ~11:44; 031 ~4:52; 036 ~27:30; 042 ~4:29; 044 ~4:54; 065B ~4:53:40; 092 ~1:45:24 "amateur hour")
  [2023]. Exceptions: entries at 09:37-09:46 with price already deep in discount (034; 041; 053
  ~10:03). CC: OR = 09:30-10:30, tends to hold the HOD or LOD; wide OR -> its opposite end gets run
  (cc10_010 ~3:07-7:05) [CC]. Bot: AM entries from 09:30; `or_no_entry` (orders fill from `or_end`; `or_deep` = the 09:37-09:46
  exception with the entry in the lower quarter of the prior day's range [our interpretation]); `or_bias` (the OR's delivery:
  the first extreme was the Judas / the close vs the midpoint); `or_wide` (trade toward the far end of a wide OR). D1.
- **T5 NY AM session**: 08:30-11:00 (Ep 01; 044 ~55:47), 09:30-12:00 (cc10_011; 067), 08:20-11:00
  (cc10_007). Bot: AM 09:30-11:00 (the release's dealing range on release days); `am_from_0830` opens it at 08:30; `pre_0820` a PRE8
  window 08:20 -> the AM (skipped on 08:30 release days); `ny_kz_futures` the futures kill zone incl. release days. D1.
- **T6 Silver Bullet windows** (one-hour windows) [2023]: AM 10:00-11:00 (every SB video: 044 ~50:05;
  048 ~57:36; 054; 058; 090 ~2:00:22), PM 14:00-15:00 (054 ~12:41; 060 ~56:50; 066 ~42:23),
  London 03:00-04:00 (054 ~08:51; 092 ~20:04). 092/099 also list 15:00-16:00; 099 an optional
  07:00-08:30. The entry must be inside the window; 09:57 or 11:01 is outside the rules (058
  ~44:37); the target may print after it (047; 054 ~11:27). Bot: none (P1 `sb`). D2.
- **T7 Macros** (20-minute timing windows; timing, never direction, 073 ~14:54) [2023]:
  - 09:50-10:10: run to liquidity or an inefficiency; the run only needs to start inside (Ep 07;
    009 ~18:24; 044 ~55:47; 073 ~19:41).
  - 10:50-11:10: run on liquidity not yet taken (022 ~3:06:14; 073 ~27:57).
  - 11:50-12:10 lunch macro: runs toward the liquidity protecting the AM move (046 ~2:03:21; 075
    ~1:10:00).
  - 13:30 (to ~13:35): starts the PM and sets up the 14:00-15:00 SB; trap above lunch REH (067
    ~42:30; 068 ~12:42). "2:00 macro" reversal ~13:39-14:00, only after lunch (015 ~31:57).
  - 14:50-15:10: a swing starts; from premium it seeks discount (043 ~15:37; 075 ~1:45:00).
  - 15:15-15:45 last hour / market-on-close (MOC): runs to liquidity not yet engaged that day; does
    nothing if the HTF target already hit (Ep 01; 014 ~5:19; 030 ~20:06; 032 ~47:41; 056 ~19:08).
    15:00-16:00 holds three macros, usually two occur (022 ~3:16:42).
  - A macro fails when the day's run is already done (030 ~18:26). Bot: `macro` tag 09:50-10:10,
    `pm_last_hour` tag 15:15-15:45; every macro in Trade.macro_wins ("HHMM|...", incl. 13:30 and the 13:39 "2:00 macro");
    `macro_gate` / `macro_only` ("0950" / "all", `macro_by` arm | start) gate orders; `macro_done_skip`, `moc_htf_done`
    (the run / HTF target done: `run_done_adr` x ADR5 or a delivered session draw).
- **T8 Lunch**: 12:00-13:00 (015 ~29:06; 025; 056) or 12:00-13:30 (064 ~1:45:41; 067; 068) or
  11:00-13:00 (cc10_007). Usually a consolidation or retrace; it runs the stops of traders who were
  right in the AM (trailed AM stops) (003 ~1:12:15; 025 ~1:00:20; 046 ~2:03:21; 064). If the AM
  did not reach the draw by lunch, the draw carries to the PM (029 ~1:29:48; 031 ~1:04:22) [2023].
  No new entries at lunch (065B ~4:12). Bot: no entries 11:00-13:30 (holds); `lunch` is a test session (AM model, AM draw carried,
  out by `lunch_exit`), `pm_carry_draw` the AM's undelivered draw as the PM's, `draw_done_skip` no lunch / PM after the AM draw.
- **T9 PM session**: starts 13:30 (013; 031 ~1:04:22; 037; 067 ~42:30), 14:00 (Ep 01; 047 "sweet
  spot"; 056), or 13:00 (cc10_012). The move usually starts ~14:00 off an OB formed in the AM or at
  lunch, continuing or reversing the AM (cc10_012 ~0:34-7:07) [CC]; the 14:00-16:00 sweet spot
  generally continues the AM (047 ~09:21). A short-term high or low almost always forms right after
  lunch (cc10_014 ~6:33). Divided day: bad AM -> come back at 13:45; nothing by 14:30 -> skip the
  PM (044 ~1:55:03). PM session 13:30-16:15 (Ep 08 wins over Ep 01's 14:00-16:00; owner #1).
  Bot: PM entries 13:30-15:50. `pm_skip_after` (nothing by 14:30 -> skip; the last hour stays unless `pm_skip_lh`), `pm_bad_am_start`
  (13:45 after a bad AM), `pm_continue_am` (tag / filter), `pm_ob_entry` (tag / require an AM-OB entry). D7.
- **T10 Last hour** 15:00-16:15. Entries 15:00-15:50 (15:50 = our reading of Ep 01's "10 min
  before", confirmed by the owner); 15:15-15:45 = the typical sweet spot, tag `lh_sweet`;
  `last_hour_strict` switch (Ep 01; 001 ~1:00:45; Ep 08 ~1:05:20) [owner correction #1]. A last-hour run to an old high, old low or imbalance happens
  nearly every day (Ep 01 ~49:28). With no clear setup, wait to 15:40-15:45 and expect a 5-8 (up to
  10) handle run (032 ~1:01:00). Pool taken before 15:50 -> flurry then pullback; an up day rarely
  closes on its high (027 ~50:40) [2023].
- **T11 End of day**: flat before 16:00; don't hold past the close; be flat once the day's final
  level is hit; no overnight or weekend holds (026 ~1:24:30; 027 ~58:22; 101 ~4:27; 103 ~9:31)
  [2023]. (001 exited at 16:01 and 012's run printed just after 16:00.) Don't fade an afternoon
  reversal or add in the last ~15 min (026 ~1:59:50). Bot: flatten at the session close: 16:15
  ES/MES, 16:00 SPY (`session_close`); `flatten=960` switch. Conflicts with the 2023 "flat before
  16:00" videos; the owner directive (#1) wins.
- **T12 When extremes form** (testable stats, not rules): index true-day high or low tends to form
  09:30-10:30, the opposite extreme 15:00-16:00; if the AM set the LOD, expect the HOD 15:00-16:00
  (cc10_011 ~0:52; cc10_012 ~1:08, ~11:27) [CC]. 2023 charts: lows at 09:31-09:40 after the 09:30
  sweep, extremes at 10:00-10:20, last-minute highs (009; 014; 022; 093) [chart].
- **T13 Day templates.** Daily PO3: open, Judas move against the bias, expansion, close near the
  opposite extreme (Ep 04; cc08_008 ~1:34) [both]. CC six index profiles: two-session up/down close,
  AM rally/decline + PM reversal, two consolidation profiles (cc10_013; cc10_014); NFP days are
  "seek and destroy" exceptions [CC]. Classification needs an HTF array map (discretionary).
- **T14 Weekly time**: bulk of the weekly range Tue-Thu; 30-50% done by Wednesday's London close
  (cc12_003 ~13:57; cc07_006 ~23:35); Tuesday London makes the low in ~77% of bullish weeks
  [fx] (cc08_001 ~20:43); bearish week high often Tuesday (070 ~4:23). Test as stats first.

### 2.5 Levels and draw on liquidity

**Pools**
- **L1 Session pools** (highest high / lowest low of each window) [2023] (067 ~12:40-51:40):
  previous PM 13:30-16:00, London 02:00-05:00, NY lunch 12:00-13:30, AM 09:30-12:00, plus the ORG.
  Priority at 09:30: the previous PM range if price is near it; if already beyond, London's range;
  then the previous AM range (067 ~52:30). Bot AM sweep pools: PDL1-3, pre-market low (00:00/04:00
  to 09:30), REL; PM: AM-session H/L. Missing: previous PM range, London range, lunch range (P2).
- **L2 Liquidity matrix**: highs and lows of today, yesterday and the day before, plus the 3-day
  extreme (Ep 08; 010 ~65:54; cc09_005 ~14:22) [both]. PDH/PDL are the first daily targets and
  raid levels (006 ~37:12; cc04_011 ~12:57). An old daily high/low alone is not an entry: it needs a
  PD array there plus time of day (Ep 08; 010 ~63:38). Reversal at PDH/PDL needs an HTF array at
  the level and HTF order flow (cc09_005 ~03:12) [CC]. Bot: pdh1-3/pdl1-3 from RTH bars.
- **L3 Higher pools**: previous week high/low, previous month high/low (054 ~4:02; cc04_003;
  cc08_007 ~18:27); 20/40/60-day highs/lows (B21); overnight (Globex) high as near buy-side (023
  ~17:00); OR30/OR60 high/low (T4). Lunch REL/REH are the PM's targets (015 ~29:22; 067 ~46:00;
  cc10_013).
- **L4 Pool quality**: prefer the larger pool (REL over a single low); a 4h REL outranks a nearer 1h
  REL; target the pool below the leg's equilibrium (042 ~1:09:17; 049 ~3:40; 103 ~29:42) [2023].
  Low-resistance runs (few overlapping swings between price and target) over high-resistance runs
  (cc01_007 ~5:38-14:38; 025 ~15:00; 102 ~2:16) [both]. Fund stops can sit up to ~10 handles beyond
  old highs (027 ~44:20).

**Opening gaps**
- **L5 NWOG** = Friday 16:59 ET close to Sunday 18:00 ET first print, read on 1m/5m, not the daily
  (039 ~0:57-6:40; 025; 050 ~13:20; 051 ~5:38) [2023]. Levels: high, low, CE, optional quarters,
  as exact levels (020 ~8:21; 039 ~1:26). Never discarded after a fill; keep all within the last 60
  days, at least the last 4-5 (039 ~3:49; 051 ~18:00; 092 ~1:57). Holiday-shortened week: ignore it
  and use the nearest normal one (046 ~16:01; 048 ~2:54). Halfway rule: reaching 50% of the space
  between two NWOGs (near edge to near edge) -> expect the next one (037 ~22:46; 051 ~16:51). A
  sell-side run below old lows is expected to stop at the nearest NWOG/NDOG/ORG (038 ~41:58).
  Variant: Friday close to Monday 09:30 (039 ~14:41). Bot: Monday-09:30 variant (RTH Fri close to Mon
  09:30 open), edges only, last 4. {needs: Sunday 18:00 open = futures; check whether the CFD files
  carry Sunday-evening bars} D21.
- **L6 NDOG** = 17:00 close to 18:00 reopen, Mon-Thu; high, low, midpoint; ignore gaps <= ~1 ES
  pt; lifetime through Friday (052 ~0:46-5:46) or 5 trading days (068 ~9:49); confluence only,
  never a standalone signal (052 ~6:16) [2023]. {needs: futures data with the 17:00-18:00 break}
- **L7 Opening range gap (ORG)** = prior RTH close to today's 09:30 open (033 ~11:36; 042 ~11:20;
  069 ~10:06; 092 ~1:55:54) [2023]. ES close = 16:15 settlement in most videos; 16:00 in some; for
  SPX/SPY data use 16:00. Levels: high, 75%, CE, 25%, low; bodies respect them (044 ~7:12; 060
  ~31:00).
  - Behaviour: 09:30 volatility seeks the prior close; expect a trade back into the ORG unless it
    acts as a breakaway gap (033 ~14:57; 055 ~20:50). A quarter fill that holds = strength; half
    filled -> a later move into the unfilled half (036 ~53:00; 058 ~53:24). Direction tell: B15.
  - Target ladder: near edge, CE, far edge (= prior close) (069; 041; 068; 043) [chart].
  - Lifetime: 3 days (060), 5 trading days (068), ~60 days (092). Default 5. Bot: none (P2 `org`).
- **L8 Vacuum block** = the gap between the last close before an event/session open and the first
  open after; gaps at 08:30/early NY usually fill the same day, gaps from 10:00 on tend to stay
  partly open (cc04_009 ~3:58-10:05) [CC].

**Levels inside arrays**
- **L9 FVG targets**: near edge first (an FVG beats an overlapping OB), then CE; CE of a weekly gap
  is enough, the far edge is a "ringer" (049 ~5:37; 061 ~2:30:15; 065B ~3:02:40) [2023]. A partly
  traded FVG's unvisited remainder plus the stops beyond it is the next draw (038 ~1:11:44). An
  unbroken OPPOSING HTF FVG between the entry and the target is resistance: it caps the trade (exit
  before its near edge, no target beyond it, no trade if the room is short) (Ep 02 ~2:15-5:22;
  owner correction #7). Bot: HTF arrays as targets (`htf_targets`); [owner #7 REVISED] the opposing FVG between price
  and the draw is a SPEED BUMP by default (`htf_resist_mode="bump"`: a partial at its near edge, the rest for the draw); `"cap"` = the
  first build (exit before it), `"split"` = cap on 1h+ and bump on 15m and lower. An FVG BEHIND the trade is never a target.
- **L10 Wick CE levels**: prior daily (and weekly) wick CEs are targets, partial levels and
  invalidation levels (Ep 08; 012 ~4:12; 035 ~24:54; 101 ~78:20) [2023]. Bot: `wick_levels`
  (prior day, ON by default - the old "off" note was stale); `wick_days`, `wick_weekly`,
  `wick_both`, `wick_session`, `wick_invalidate`, `wick_partial`, `wick_react` switches (off).
- **L11 Rejection-block level**: cover at the old low's lowest body, not its wick (cc04_006
  ~14:14; 059 ~9:38) [both].

**Projections**
- **L12 Standard-deviation (SD) targets** [2023]: anchor a fib on a swing whose extreme has been
  broken and project -0.5, -1, -1.5 ... beyond it (029 ~21:18; 030 ~23:31). Measure only after the
  fulcrum is traded through (Ep 06; 008 ~6:45; 065B). Use only the first SD level beyond the pool;
  skip levels at or before it; clusters of first-past-pool levels from several swings within 1-2
  ticks = high-probability turn (014 ~2:54-4:43; 030 ~26:01). -0.5 SD is always a first partial,
  -1 SD = measured move (most off), -2 very extended (064 ~1:33:48; 065B ~3:03:40). Projections must
  line up with a pool, a PD array or time (014; 062 ~42:19). Anchor: D23. Bot: `sd_targets` (off),
  sweep low to leg high, k = 1-2.5.
- **L13 Other projections**: breaker A-B leg: B + 1x(B-A) (070 ~37:31); measuring gap (A6); ORG
  size multiples (055 ~19:30; 056 ~17:10); CC 1.27/1.62 extensions only where they overlap an
  opposing PD array (cc06_008 ~28:08) [CC]. CBDR (14:00-20:00), Asian (20:00-00:00) and Flout SDs,
  floor pivots and "filling the numbers" are [fx-only] (cc08_003; cc08_004; cc08_005; cc09_002).

**Draw selection**
- **L14 Choose the draw** [both]:
  - Decide the draw first, then trade only toward it (B3).
  - Enter on internal range liquidity (FVG/OB/void), exit at external range liquidity (beyond the
    range high/low) (cc04_002 ~5:39-10:00) [CC].
  - Direction from the matrix: once price has reacted from one side's arrays, the other side is the
    next draw; the target is the opposing array, ideally one timeframe lower (cc06_003 ~0:50;
    cc07_001 ~9:29) [CC].
  - Only targets not yet traded through since they formed; skip exhausted arrays (028 ~54:55;
    cc07_004 ~4:00). Bot: "intact" is checked for sweep levels only.
  - Conditional draws: if price fails to reach the upper pool, switch to the lower; once taken the
    low draw is spent (080 ~16:58) [2023].
  - Keep a sorted level list; mark each level done when traded and look to the next (028 ~54:55;
    045 ~6:38; 105 ~29:59) [2023].
  - Silver Bullet draw list: PDH/PDL; previous session H/L (London for the AM); PWH/PWL; NWOG; OTE;
    FVGs. If already raided, use an HTF pool (054 ~4:02-6:50) [2023].
  Bot (bias_htf): `draw_first` umbrella, `matrix_tf_lower` (react timeframe, then the opposing array one timeframe lower), `cond_draw` (a failed draw switches the lock once, the failed target spent), conf-target hygiene (`target_hygiene` "htf" also filters the lock's confluence draws).
- **L15 Room ("10-handle framework")**: 5 handles is the MINIMUM room to the draw (10 for new
  traders), not the goal; the target is the draw / PD array (024 ~25:26; 046 ~32:40; 054 ~0:36; 058
  ~37:16; 059 ~10:36; 060 ~50:00; 072 ~35:11) [2023] [owner correction #2, 2026-10-18]. Bot:
  `min_draw_pts=5` measured to the draw's exit price (10 = switch); a fixed +5 rung is the
  `t1_fixed_pts` test switch.
- **L16 ADR5** = 5-day average daily range [CC]: expected day range; aim to capture 65-70% of it;
  ADR reached before 10:00 -> take 80% and keep a runner (cc08_001 ~1:53; cc09_006 ~19:33). Also
  N8 filters. {1m}
- **L17 Rounding**: CC rounds every level toward price to the nearest round number (cc12_001
  ~34:00); 2023 index work does not (007 is the one case). Bot: `round_step_pts` switch (off):
  targets rounded down and limit entries up toward price on the real front-month price (#13
  mapping); stops not rounded.

### 2.6 Models and setups

- **M0 The common skeleton ("one setup for life")** [2023] (067 ~12:00-26:00, ~1:30:00; 063
  ~12:22; 065A ~2:28:00; cc12_004 ~26:28):
  1. Bias = what the weekly/daily candle reaches for; one direction only.
  2. Pick a time window and mark its high and low pools (L1).
  3. Wait for a raid on the pool against the bias (the Judas).
  4. A structure shift with displacement leaves an FVG.
  5. Enter on any PD array (FVG, OB, breaker, OTE, IFVG, turtle soup, wick CE).
  6. Target the opposite pool or gap.
  Not every condition is in the bot (no HTF bias; see P3).
- **M1 AM market maker buy/sell model (MMBM/MMSM)** - the bot's `am_mm` [2023] (Ep 03; Ep 05;
  Ep 07; 003 ~10:38-16:45; 009 ~1:00-16:19):
  - Context: HTF draw on the far side (daily VI, REH); price drops into a discount array (5m OB / 1m
    BISI).
  - Trigger: a short-term low (the pool) is taken, then the swing high that led into the low breaks
    with displacement, leaving an FVG (A19).
  - Speed check: price must "rip through" the small SIBI high; afterwards it must not trade below
    the lowest open or close of the swing low (009 ~15:51-16:19).
  - Entry: limit at the FVG (unicorn FVG preferred, A14). 003 took its first entry in the OB before
    the MSS (D10).
  - Stop: below the MT of the bullish OB nearest the sweep low (009 ~4:17) (E5).
  - Full MM model phases (original consolidation, distribution, smart money reversal, re-accumulation,
    return to the original consolidation's buy side) are context for where you are, not extra
    triggers (003 ~1:27:50; 104 ~27:28-53:35; cc07_007). If you missed a stage, the next one
    becomes your first (104 ~37:12).
- **M2 2022 model** [2023] (022 ~38:38-1:03:08; 042 ~34:53-1:09:17; 062 ~34:53; 074; 082; 087;
  094):
  - Short: buy-side (old high / REH / NWOG / London high) is taken, then displacement breaks a
    short-term low (MSS).
  - Sell an FVG inside the displacement leg (high -> the low that broke) that sits at or above 50%
    of the leg (premium). Never sell the breakout candle itself.
  - FVG choice: one aligned with a VI and bearish OB; with two FVGs the higher one is allowed;
    otherwise the first FVG above EQ (022 ~55:00; 042 ~47:20; 082 ~5:31).
  - The FVG must close, a new candle open, and price trade back in without first taking the low
    (042 ~34:53).
  - Stop: just above the bearish OB MT (022 ~59:02, 2 pts), above the FVG candle high (062 ~37:28),
    or above the CE of the higher of two FVGs (069 ~13:46).
  - Pyramid only in premium; past the leg's 25% level, stop adding and only take partials (022
    ~49:26; 025 ~47:56). Target sell-side below 50% of the range, preferring the larger pool (042
    ~1:09:17). Long = mirror (032 ~56:57).
  - Three drives into failing liquidity, then MSS, then the 2022-model FVG (093 ~10:37; 074 ~32:49).
  - Bot: the sweep -> MSS -> FVG machine matches, minus the leg-premium filter and the 25% add cutoff
    (P1 `leg_pd`). D12.
- **M3 Silver Bullet (SB)** [2023] - his main setup from file 044 on (044; 047; 048; 054; 057; 058;
  059; 060; 063; 065A; 066; 068; 090; 092; 099):
  - Windows: T6. Entry inside the window; the FVG may have formed earlier (D2).
  - In the window, displacement toward the draw leaves an FVG facing the trade (a BISI for longs);
    enter on the retrace into it; target the opposing untapped pool (044 ~1:06:34; 048).
  - The first FVG in the bias direction during the hour is the entry; it must sit beyond the level
    that needed breaking (048 ~57:36, ~1:34:31). An MSS before the FVG is shown (054; 055; 058) but
    never stated as required.
  - Evolving SB: if price leaves the first FVG without a retrace, move the limit to the next FVG in
    the window; better to miss than chase (057 ~2:16; 058 ~46:43).
  - Cancel if price trades through the target before the fill (057 ~3:35). A shallow 1-tick run
    under sell-side before the retrace is wanted (057 ~4:18).
  - Room: >= 10 ES pts to the draw, take ~5 or cover at the old low (054; 058; 059; 060); looser
    variants accept >5 (044) or 4-5 (068; 072).
  - Entry price: limit near the FVG near edge (044; 057), CE as "worst case" (048).
  - Stop (rarely stated): 2 pts above entry / top of the evolved FVG (057 ~6:41); below the candle
    forming the FVG low and below the OB MT (090 ~2:14:00); below the entry candle (086 ~11:35).
  - Session order: London, else AM, else PM; one fires every day in one market; if not in your
    market, don't switch (054 ~18:18; 046 ~55:21; 090). One AM SB trade a day (047 ~8:00).
  - An immediate rebalance seen in 10:00-11:00 -> expect more than 5 handles (048 ~39:02). Bot:
    `sb_rebalance_ext` switch (off): with an A7 immediate rebalance in the window the SB draw must
    be at least that many ES points away [our interpretation of the bar test].
  - Exits: layered limits (057: 4/2/4 of 10 at NWOG high/75%/CE); with the weekly profile aligned,
    most off at target and keep 1 runner (048 ~2:02:12).
- **M4 Breaker and unicorn entries** [both]:
  - Classic: buy the first return to the bullish breaker; bodies respect it; stop beyond the sweep
    extreme (A13; cc05_005 ~11:06).
  - Unicorn: buy the FVG/CE inside the breaker right after a sell-side run at 09:30; add on each new
    imbalance; accumulate inside the breaker before the breakout, not on the breakout (Ep 05; 007
    ~22:39-23:35). 018: may enter the breaker but not below its MT.
  - Advanced (070 ~34:59-1:08:31): use only the A->B leg; with bias on side you may buy inside the
    A-B leg or on the sell-side run without waiting for the break; a fill at MT needs 1 tick through;
    target B + 1x(B-A). Best when the lower low also hits an HTF pool.
  - Pyramid: buy the turtle-soup low, add at the breaker retest (cc12_004 ~33:23; 063 ~28:37).
  - Breaker swing vs failure swing (CC): one more drive into the key level then a break of the
    in-between low (breaker), or a lower high that fails to reach it (failure swing); sell the retest
    of the breaking point; stop above the new/failed high. Both levels must be drawn before price
    arrives (cc05_005) [CC].
- **M5 PM last hour / MOC** [2023]:
  - Ep 01 version: pre-select a nested 4h/1h FVG; in 15:15-15:45, 1m bodies refuse to close beyond
    the 60m FVG edge, then a fast candle leaves a breakaway FVG; buy the top of the 1m FVG; add in
    the FVG, the breakaway gap and on a breaker; stop below the FVG candle open, then trailed; one
    exit at the draw (001 ~39:03-45:20). Price should hold above the midpoint of the 4h FVG (Ep 01
    ~30:48).
  - 2022 model inside the window: sell-side taken 15:15-15:45, MSS one tick through, buy the
    VI/OB/FVG, target buy-side, flat by the 16:00 candle (030; 032 ~56:57).
  - Examples 013, 020, 024, 027: entries 15:35-15:57. Bot: `pm_last_hour` tag only (P2).
- **M6 PM reversal ("2:00 macro")** [2023] (015 ~31:57-36:20): bias bullish and the intraday high
  taken after lunch; once the HTF objective is hit, the trigger is a short-term-low MSS with price
  trading DOWN through the 1m FVG at the old high (inversion); short the first return into that
  IFVG; stop just above its high; targets the old daily high and the lunch REL.
- **M7 PM off lunch** [2023] (067 ~46:00): lunch low taken, MSS + FVG, target the lunch high; short
  mirror (lunch high into the ORG, 2022-model FVG, target the lunch low). PM 13:30 Judas: a rally
  above the 13:30 open into a premium array, then sell (010 ~56:30; Ep 08).
- **M8 ORG repricing** [2023] (069 ~10:06-14:50): after the 09:30 Judas away from the ORG, price
  reprices back into it; target the ORG near edge.
- **M9 News Judas** [2023]: wait for the release; the first pool run is the losing side; buy after
  the sell stops are taken (064 ~52:12; 073 ~10:42). FOMC: the real move starts 14:30 (021; 065B; the 14:25 of the
  coverage notes has no source). Bot: `news_judas` (block = the first run's direction is closed after it; wait = also no entry before a
  run; the reference pools = the high / low of the `news_judas_ref_min` minutes before the release [our interpretation]);
  `fomc_judas` for 14:00.
- **M10 IFVG entry** [2023]: protocol A8; entry at its CE or near edge (078 ~50:28; 085 ~27:21);
  stop above CE plus 3-4 ES pts; stops under 2 pts are too tight except on 15s-1m (102 ~1:40:20).
  061 ~2:15:00 signature: an IFVG with a normal FVG below; a body close at the FVG high/CE triggers.
- **M11 Immediate-rebalance and CISD entries** [2023]: with bias, enter at once after an immediate
  rebalance with a very tight stop; exit if price retraces above the range EQ (099 ~3:46; 100
  ~44:54, ~1:37:18). CISD OB: after the MSS, the first trade above the open of the last down-close
  candle validates the OB; its low must hold; buy at or below EQ of the post-CISD range (075
  ~1:16:40). Wick-CE long: buy at a wick CE when the next candle closed above it, TP ~0.5 pt before
  the high (100 ~38:13).
- **M12 Turtle soup** [both] (bot: `turtle_soup` = "2023" / "cc_limit" / "cc_1h_ob" / "or60" /
  "external", off; `ts_max_pts` / `ts_back_bars` = the M12.5 depth/back test, `ts_gate_mss` puts
  it on the MSS model too; bar mechanics [our interpretation]): a false break beyond an old high/low "by a little", then a fast
  reversal; it needs an HTF PD array at the level and HTF order flow (cc05_004 ~6:45; cc09_005
  ~3:12-18:56; 010 ~63:38).
  - 2023: no MSS needed; price takes a predefined external level with SMT and one PD array; stop
    below that array (022 ~2:47:29) or at the nearest NWOG/NDOG/ORG below the old lows (038 ~41:58).
  - Turtle soup short at an old high: let price spike above, short the failure, target the next
    draw, add on new FVGs/breakers (Ep 08; 010 ~25:13).
  - CC: buy limit at/just below the old low with a bullish bias (cc04_011 ~9:45); 1h sweep into a
    daily bullish OB, buy limit at the 1h last down candle's open, half off at 1R, BE after 2R,
    runner to 5R (cc02_001 ~17:41-25:21) [CC]. Index OR version: turtle soup below the OR60 low
    later in the morning, target the OR high (cc10_010 ~6:51) [CC].
  - External turtle soup (pattern 2): price stops short of the expected HTF discount array (a false
    low), later drops into it; buy there, not the early bounce (cc12_004 ~29:35) [CC].
- **M13 OTE** [CC] (cc01_004 ~9:44-53:45; cc01_005 ~2:07-20:47): impulse leg from a confirmed swing
  low to the high; buy only below 50%; zone 62-79%, sweet spot 70.5%; never AT 50%; stop beyond the
  leg's swing low; no retrace to 50% = no trade; target above the old short-term high or just before
  an opposing OB. 2023 uses OTE as one entry option among many (065A); 061 says fib only for
  premium/discount, never entries. cc12_004 pattern 1 ("favorite"): OTE + FVG + swept short-term
  low + bullish OB, target external liquidity. D12.
- **M14 TGIF** [2023] (066 ~1:38-47:41; 074 ~24:04; 084 ~15:45; 089 ~0:41):
  - Friday only, after a trending one-sided week that reached an HTF premium (bullish week) or
    discount array; without that, no TGIF.
  - Zone: retrace 20-30% of the weekly range (week low incl. Sunday 18:00 to the high) from the
    extreme; 25% = midpoint; 40%+ is reversal talk.
  - Timing: weekly high assumed in by ~13:30; PM more likely (066), or the London close 10:00-12:00
    (084). Valid once a bearish shift confirms the high (075 ~1:40).
  - Entry by any model (066: PM SB); exits partial at 20%, more at the upper gradient, most at 25%.
- **M15 Ma Deuce** [2023] (091 ~19:02-26:47): HTF expects one big up-close daily candle's BISI to be
  re-delivered lower and price sits in its premium half; on the 1m a bullish FVG is broken and
  inverts; don't short the first break; after 08:00 sell the retrace into the IFVG (a 2nd rejection
  or a new small SIBI before 08:30 = 2nd entry); the 08:30 release delivers. Targets: daily BISI CE,
  its lower quadrant, then the 1h BISI low. Stop never stated. Pre-market only (CFD bars have it;
  SPY pre-market fills are thin): research only.
- **M16 Index SMT / sick sister** [both]:
  - CC AM SMT: compare ES/NQ/YM relative lows (bullish) from 05:00 or London into 09:30; entry = buy
    stop above a down-close candle's high, or turtle soup on the index that made the lower low; hold
    to 10:30-11:00; a few times a week (cc10_011 ~8:01-18:36; cc10_014 ~1:15). ICT trades only ES
    off the signal (cc10_012 ~10:17).
  - Sick sister: of the indices, the one that took the fewest reference highs at a key time; buy it
    at deep discount; target the highs it failed to take; exit before the final high (053
    ~1:56-7:57; 045; 056; 061). Which index: D15.
- **M17 Out of scope for the bot**: London/CBDR/Asian/0 GMT day-trade models and FX scalps
  (cc08_003-008; cc09_001-007) [fx-only]; One Shot One Kill weekly templates and the twelve weekly
  profiles (cc07_001-008) except as statistics; swing/position models (MWD execution, Million Dollar
  Swing, daily-candle stop entries, daily swing short 098 ~19:00) - parked with the swing idea;
  stock CAN SLIM models (cc10_015-018).

### 2.7 Entries, stops and sizing

**Entries**
- **E1 Order type**: a resting limit inside the FVG/PD array, never a breakout chase (001; 018;
  042 ~45:29; 057 ~1:16; 066 ~0:44; cc04_003 ~6:38) [both]. Adds and scalps at market; exits on
  resting limits (009; 020; cc09_006 ~7:06). CC alternative: stop orders on breakers, mitigation
  blocks, FVGs and voids; limits on OBs, rejection blocks and old highs/lows (cc06_008 ~14:20); index
  AM buy stop above a down-close candle's high (cc10_011 ~15:32) [CC]. Bot: limit.
- **E2 Entry price**: near edge (live fills: 001; 018; 042; 054; 057; 066), CE ("highest
  probability", rarely filled: 007; 024 ~23:19; 035 ~53:42), or IOFED = the FVG-forming candle's
  extreme or 1 tick past the gap edge, a shallow touch that does not reach CE (003 ~30:30; 006
  ~50:09; 010 ~47:38; 024 ~23:43) [2023]. Ladder when bullish: FVG high, then 75%, then CE (030
  ~15:46). Bot: `entry="edge"` (default) | `"ce"` | `"edge_1tick"` | `"iofed"` (`iofed_ref`) | `"ladder"`
  (`entry_ladder_fracs`; later rungs fill as entry-ladder units); the Silver Bullet has its own `sb_entry`;
  unknown values raise. D11.
- **E3 Fill rule**: a limit fills only if price prints at least 1 tick through it (042 ~59:04; 070
  ~56:01; 105 ~1:27:00) [2023]. Bot: requires low < entry (strict), gap-through fills at the open.
- **E4 Retrace candle**: buy into down-close candles, sell into up-close candles ("market
  efficiency paradigm"); a short needs at least one up-close candle (Ep 07; 009 ~8:11; 037 ~21:10)
  [2023].
- **E5 Don't chase / order hygiene** [2023]: if price leaves without retracing, let it go (057 ~2:45;
  cc01_001 ~10:28); move the limit to a newer FVG in the same window (057); cancel if the target
  trades first (057 ~3:35; bot does); entry must be inside the time window, exit need not (058
  ~44:37); don't enter early when the stop would be too wide (057 ~2:54). Bot: pending orders
  expire after `pending_minutes=30` or at the session end; `evolve_fvg` (a newer untouched FVG replaces
  the order, the sweep stays alive), `wait_structural` (a too-wide stop waits for a newer entry),
  `no_new_extreme` (a new low before the fill cancels), `run_cancel` ("t1" | "last" | "off").

**Stops**
- **E6 Stop placement** (several variants, all [2023] unless noted):
  - Below the MT of the bullish OB nearest the sweep low (009 ~4:17: stop 4011.50 under the 09:40
    candle's body MT; 022 ~59:02 short mirror; cc02_001 ~22:02). MT measure: D4.
  - Just beyond the FVG-forming candle / below the FVG candle open and bodies (Ep 01; 013 ~18:13;
    015 ~33:56; 090 ~2:14:00).
  - Beyond the sweep extreme / the swing that ran the liquidity (cc05_005 ~11:06; cc02_002 ~6:34;
    078 ~1:22:14) [both].
  - Beyond every nearby inefficiency, not just the entry FVG: below any gap under a long; beyond the
    higher of two FVGs; beyond any overshoot wick already printed (025 ~55:15; 027 ~30:20; 069
    ~13:46; 081 ~15:47).
  - Not just past a level price may "mohawk", and not under a random swing low near EQ (075
    ~1:25:00; 078 ~58:00).
  - Padding: 1 tick beyond the level (Ep 08; 010 ~16:01); 3-4 ES pts beyond a CE stop in fast
    markets; under 2 pts is too tight except on 15s-1m charts (102 ~1:40:20). NFP: wider, behind all
    HTF bodies (105 ~0:51).
  - Bot: `stop_mode="ob_mt"` = min(FVG bottom, full-range MT of the last down-close candle between
    sweep-3 and the FVG) minus the pad; risk must be 1-15 ES pts. The pad is ONE TICK by default
    (`stop_tick_pts=0.25`, Ep 08; `stop_pad_ticks` replaces it, `stop_tick_pts=0` restores the old 0.01
    `stop_buffer`). Other modes: `fvg_c1_low`, `fvg_bodies`, `fvg_open`, `fvg_candle`, `ce2`, `sweep`
    (E6c), `ob_mt_pure` (MT - 2 pts); modifiers `stop_all_ineff` (E6d), `ce_stop_pad_pts`,
    `nfp_stop_wide` (E6f), `mohawk_ticks` (A4: a wick may poke, a body close beyond the raw level
    exits), `mt_close_stop` (hard stop at the OB far edge, body close below the MT exits).
- **E7 Never widen a stop; if you want to, close instead** (Ep 03; 044 ~1:13:38; 045 ~1:19:58;
  cc02_005 ~15:44) [both].

**Risk and size**
- **E8 Size** = (equity x risk%) / stop distance (065A ~1:04:00; cc02_004 ~18:56) [both]. Risk 1%
  default (009: 1.2-1.3%; 102: 1-1.5%; cc02_004: 1% default, 2% hard max); 2% is too much for new
  traders (022 ~1:38:24). Default open risk 1.2% of equity at entry (Ep 07 ~5:32 "the goal ...
  percentage-wise") [owner correction #12]. Bot: `risk_pct=0.012`, `risk_basis` fixed|equity; 1% =
  legacy preset.
- **E9 Size down** when conditions are mixed: against the macro undertone, cracked ES/NQ
  correlation, low-probability setups (minimum size, no pyramid), day before CPI/NFP/FOMC, FOMC
  week, August, war shocks (022 ~1:38:24; 029 ~5:22; 042 ~3:50; 045 ~1:01:43; 079; 090 ~35:02;
  094; 103 ~32:44) [2023]. Size up only on the strongest arrays (BPR + FVG) or near an HTF target
  (092 ~9:44; 102 ~1:23:50).
- **E10 After a loss**: halve size, win back ~50%, then step back up; never raise size to recover
  (061 ~2:26:40; cc02_005 ~5:20-15:44; cc06_003 ~23:24) [both]. Ep 08: after a loss on the day, no max
  size (010 ~49:51). Bot: `loss_halving` (halve per loss to `halving_floor`, back to full after
  `winback_frac` of the drawdown is won back; carried across days), `after_loss_mult`,
  `after_loss_adds`, `no_max_after_loss`.
- **E11 Caps**: ~6 contracts initial, building to 10-16 by pyramiding (Ep 08; 010 ~49:51; 076
  ~27:54) [2023]. Max open risk 1.3% including adds (Ep 07 ~8:24, ~19:21); 2% is not stated in Ep
  01-08 (cc02_004 only) [owner correction #12]. Bot: `max_total_risk_pct=0.013`; adds shrink to fit;
  `max_contracts_initial` / `max_contracts_total` (+ `units_per_contract`) cap the contract counts.

**Pyramiding**
- **E12 Adds** [2023]:
  - Sizes decrease: largest unit first, never a larger add (Ep 04; 006 ~51:52: 6/3/2/1; 021; 050;
    060; 083/085: 5/4/3/2/1). Exceptions 067 and 070 (1, 3, 6) when entering early in a breaker leg.
    Bot: `adds=(0.5, 0.33, 0.17)` (fractions of the first unit, Ep 04 pyramid; ON by default - the
    first build of this line said `adds=()` off, which the code never did); `add_points` top | ce | q75.
  - Where: retests of new FVGs that hold; down-close candles into a bullish OB/VI; breaker retests;
    IFVGs; the next VI (003 ~44:20; 009 ~12:07; 001 ~44:00; 026 ~1:44:04; 085 ~30:08).
  - If price closes into the FVG instead of rejecting it, add once more at its low end (006
    ~51:52). Bot: `add_low_end` (= `add_fvg_low_end` = `add_fvg_low`).
  - Owner #7 (revised): an FVG BEHIND the trade that price has already traded through (Ep 02: the 15m
    FVG on the short) is support/resistance and an ADD zone, never a target: `add_arrays=("htf_fvg",)`
    (default; also "vi", "ifvg", "ob", "breaker"), `add_hold`.
  - No adds after partials (006 ~53:53). Bot: adds only before T1.
  - No adds past equilibrium: stop once price passes the 25% line of the displacement leg or EQ of
    the implied range to the target (022 ~49:26; 025 ~47:56; 045 ~1:51:09; 058 ~43:12; 092
    ~1:15:24). Bot: `add_cutoff` (0.25 = the 25% line), `add_cut` ("eq" | "leg75"), `add_cut_ref`.
  - No pyramiding on NFP or on low-probability/decoupled days (105 ~9:13; 045 ~1:01:43). Bot:
    `nfp_no_adds` (default on), `decoupled_no_adds`, `low_prob_no_adds`.

### 2.8 Management and exits

**Targets and partials**
- **X1 Target** = the next opposing liquidity (REH/REL, old highs/lows, PDH/PDL, session H/L,
  3-day matrix) or the next opposing PD array (FVG, NWOG, ORG, OB) (Ep 01;
  006 ~33:20; 010 ~65:54; cc04_002) [both]. Bot: T1 = nearest liquidity target paying >= `min_rr`,
  T2 = the next; merged within 1 ES pt.
- **X2 Exit buffer by target type** [2023]: exit BEFORE PD-array targets (0.5-1 pt before an FVG
  edge, a couple of ticks before; near edge of an hourly FVG, not its middle) (Ep 08; 010 ~58:50;
  030 ~24:24; 049 ~5:37; 063 ~29:41; 070 ~1:05:36; 102 ~1:31:00); exit just BEYOND liquidity-pool
  targets (1 tick below a low; 0.75-1 pt above buy-side; 1 handle above REH; a tick or two beyond to
  get filled) (001; 006; 007 ~19:25; 050 ~55:20; 083; 099 ~37:51; 105 ~1:27:00). Bot: 0.5 ES pt
  before every target. D5.
- **X3 Partials** [2023 unless noted]:
  - Scale out at each liquidity pool ("running down equity"): take a piece at each new high near
    each pool (Ep 03; 003 ~1:04:25; 027 ~43:36; 065B ~3:07).
  - Bulk at the first liquidity target: 10 of 12 (006), 9 of 14 (009), 80% at NWOG CE (020); 80/20
    on slow or news-ahead days, 50/25/25 on normal days (036 ~1:01:00). Smaller first partials also
    used (018 5 of 14; 041 1/3; 057 4/2/4; cc02_001 half at 1R). D13.
  - Always a partial a little before the CE of any wick inside the trade's path; with two wicks use
    the longer (065A ~2:37:30; 065B ~3:52:40; 105 ~9:00).
  - -0.5 SD is always a first partial (064 ~1:33:48). Next partial halfway between the hit target and
    the next (026 ~14:57).
  - Never target the exact low/high of an FVG; a first partial can go at an FVG CE or the top of a
    daily FVG (Ep 08).
  - Full pull without partials in a low-resistance run (fast, nothing in the way); partials in a
    high-resistance run (089 ~8:46; 092 ~1:28:54; 102 ~2:15:30). Discretionary.
  - SMT warning (sister refuses to break) -> bank ~50% (046 ~1:02:40; 037 ~32:56).
  - Aim to capture 80-85% of the best-case run (013 ~29:22).
  - Bot: `partial=0.5` at T1, rest at T2.

**Breakeven and trailing**
- **X4 Breakeven** only after the first partial and after price has expanded (032 ~58:19; 036
  ~42:40; 046 ~1:22:00; 105 ~10:41 BE + commissions; cc06_008 ~16:20; cc02_001 after 2R) [both].
  Earlier BE in some 2023 charts (003 right after the MSS; 009 when stalling; 042) [chart]. Bot:
  `be_on="expansion"` (default: after the first partial and a later close beyond the first target; "t1",
  "after_mss", "stall", "pool" (Ep03.15: the first pool taken) and "off" are switches); the BE level carries
  `be_pad_pts` / `be_cost_pad` (105 ~10:41); a day trade has none. The Silver Bullet and Ma Deuce keep the first build
  (BE the moment their first target / rung is taken) unless `extras_be_on="follow"`: then they follow `be_on` (every
  mode, incl. the pad). D14, X4.
- **X5 Trailing** [2023]:
  - Trail under the first breakaway (protected) FVG after the shift, under the measuring gap after
    two rounds of partials, or under each newer FVG after each partial (003 ~42:40, ~1:05:00; 002
    ~8:00; 062 ~37:02).
  - Don't trail early: a new FVG may be revisited; never trail into or just under an FVG created right
    after the MSS; trailing too soon is the main error (029 ~43:40; 085 ~19:59, ~26:46). Trailed AM
    stops get run at lunch (064 ~1:45:41).
  - A day trade keeps its initial stop (below the 08:30 open / 08:30 wick CE) and pays itself with
    partials; session trades trail (064 ~1:38:44).
  - Bot: `trail=False` (the old trail under every new FVG after the fill, off). Default `ladder_trail="fvg"`: under the
    newest FVG formed since a partial, from `trail_after` rounds of partials (1). Switches: "measuring" (Ep03.20:
    under the measuring gap after two rounds, `trail_after=2`), "hit", "prior", "off"; `trail_first_fvg` (Ep03.10:
    under the first FVG after the shift), `trail_breakaway`, `trail_pad_pts` (X5a); `trade_type="day"` (X5c) =
    initial stop at the 08:30 open / wick CE, no trail, no BE (every stop-raising site goes through `manage.raise_stop`,
    which skips a day trade; an order that cannot get the day stop stays a session trade, funnel `x_day_trade_unavailable`). D14, X5.

**Invalidation and aborts**
- **X6 FVG abort**: a candle body closes beyond the FVG against you AND the next candle trades
  beyond that candle's extreme -> close at once for a small loss (045 ~1:19:58) [2023]. Bot: `fvg_abort` (off),
  `fvg_abort_mode="rule"`: a 5m candle CLOSE beyond the entry FVG's far edge arms it and only the NEXT 5m candle
  trading beyond the armed candle's extreme confirms it (else the arm is cleared); "legacy" = the first build
  (whole-body arm, any later bar confirms). X6.
- **X7 Three-PD-array rule**: list three arrays against the trade; through the first is tolerated,
  the second is a warning, body closes through all three = exit before the stop (026 ~28:02; 027
  ~38:26; 078 ~1:02:38; 098 ~47:00; 105 ~1:21:06) [2023]. Body close below the nearest VI + FVG +
  OB MT -> take half off (045 ~1:49:28). Three arrays in a row failing -> stop for the session (044
  ~1:52:49). Which arrays count is discretionary. Bot: `pd3_exit` (off) lists the nearest `pd3_n` arrays (`pd3_list`:
  FVG / VI / OB MT / breaker) at the fill (`pd3_dynamic` re-reads each bar), tags `pd3_warn` at the second break and
  exits at the third; `pd3_half` (X7b); `session_stop_after_fails` (X7c; main engine, SB and Ma Deuce share it, two-way: `run_day` feeds the extras' closed
  trades back to the main loop). The fixed list is cut to the nearest `pd3_n` and tagged `pd3_n<k>` (`pd3_short` when
  fewer exist: it can never fire).
- **X8 Other invalidations** [both]: bodies close through a bullish FVG's CE -> close early (030
  ~15:46); retrace through the MT of the candle that started the leg (026 ~28:28); immediate-
  rebalance trade back above range EQ (100 ~1:37:18); propulsion-block MT lost (cc04_008 ~5:15); a
  short should smash through the down-close candle below, if bodies respect its open and trade back
  above, close (085 ~11:18); after the trigger, price must not trade below the lowest open/close of
  the swing low (Ep 07; 009 ~15:36); meandering inside the SIBI instead of rejecting -> close (092
  ~1:04:38). Bot (all off): `leg_mt_exit` (X8b), `ir_eq_exit` (X8c), `prop_exit` (X8d = prop_mt_exit), `offside_exit` with
  `offside_level` open / wick_ce (X8e), `meander_bars` (X8g); the CE close-through is `ce_hold`, the swing-low bodies
  `ep07_body_exit` (also on the fill bar, `ep07_body_fixes`). The invalidation exits (X6-X8, X9c) also run in the Silver
  Bullet and Ma Deuce (`invalidations_extras`, default on; each exit is still its own switch).
- **X9 Time stops** [2023]: once price touches the entry array it should deliver on that candle or
  the next, or within 2-3 one-minute candles (022 ~1:43:27; 031 ~24:29; 071 ~32:41; 092 ~1:41:14);
  a 1m trade should show movement within ~10 min (025 ~17:17); after touching the SIBI's far edge,
  2 minutes to move back, else half or all off (092 ~1:11:05). Lethargic delivery -> cut half (CC:
  cc03_003 ~13:18). Bot (off): `time_stop_min` / `time_stop_bars` + `time_stop_ref` pts / leg_high / array_far +
  `time_stop_frac` (0.5 = cut half, once; a remainder at minimum size is closed), also in the Silver Bullet and Ma
  Deuce; `far_edge_min` / `far_edge_frac` (092 ~1:11:05). X9.

**Time exits**
- **X10 AM exits**: CLOSE (not tighten) the last AM unit before noon - "should have peeled the last
  contract off" (Ep 03; 003 ~1:17:26-1:18:44) [owner correction #8; exact 12:00 is our wording];
  CC: close the bulk 10:00-11:00 and hold AM SMT trades to 10:30-11:00 (cc12_004 ~8:25; cc10_014
  ~3:01); AM delivered the day's range -> flat before lunch and skip the PM (cc10_007 ~9:05). Bot:
  `am_exit=720` closes all AM, PRE/NEWS, SB-AM, London-SB and Ma Deuce units at the close of the bar
  ending 12:00 (`am_exit_mode="tighten"` = test only). `am_bulk_t` / `am_bulk_frac` (bulk off 10:00-11:00) and `smt_hold_until` /
  `smt_hold_exit` (hold AM SMT trades to 10:30-11:00) are switches (off). D16.
- **X11 PM exits**: target hit by 15:00 -> be done, the last hour retraces (Ep 04; 006 ~41:45); CC:
  hold PM trend trades to the 15:00 bond close, ideally 16:00; consolidation-profile PM trades exit
  ~14:00 (cc10_014 ~3:01, ~13:17); flat before 16:00 (T11). Bot: `pm_done_by`; `pm_consol_exit=840` (off; the 13:30 cc_profile classifier, no entries after
  it); `late_cutoff=945` (DEFAULT: no adds and no fades from 15:45). D16.
- **X12 Session objective hit** -> close everything and stop for the day (029 ~1:03:57; 040 ~0:39)
  [2023]. Bot: `obj_stop` (off), `obj_source` draw / htf_ce: exits at the objective and ends the day for every setup.

**Session, day and week stops**
- **X13 After a loss**: lose in the AM -> do not reverse; stop for the morning and wait for the PM
  (Ep 01; 001 ~46:57-48:43). Same-direction re-entry of an idea that has not unraveled is allowed at
  half the previous risk (070 ~38:41; 060 ~1:22:30; 085 ~27:21; cc02_005; cc06_003 ~23:24) [both].
  Not on FOMC (021 ~43:56). Bot: one trade per session and no opposite side after a loss
  (`lost_side`); switches: `reverse_in_session`, `lost_side_session`, `loss_ends_morning` (X13a), `reentry_half` +
  `reentry_gate` (X13b: same side, draw not delivered, a restored sweep and an FVG made after the stop, not FOMC),
  `reentry_risk` budget / loss, `reentry_lock_r` / `reentry_target_r` (D18). D18.
- **X14 After a win** [2023]: bread-and-butter 5 handles then stop (044 ~57:16; 046 ~4:41) - test
  switch `day_target_pts`, default off (owner #2: 5 = minimum room, not the goal); in
  chop, one win and stop (031 ~9:20); if the AM wins, skip the PM (065B ~4:12); no re-entry after a
  winner on the day (095 ~47:08). Bot: one AM + one PM trade; switches `chop_one_win` (X14b), `no_trade_after_win`
  (X14d), `done_if_target` (Ep04.13), `day_target_pts` (X14a, off).
- **X15 Frequency**: one good setup per week (Ep 03; 003 ~1:05:10; cc02_003 ~12:03); ~3 trades per
  week (099 ~47:36); one AM SB trade a day (047 ~8:00); CC day-trade model ~2 setups a day
  (cc08_001 ~1:30) [both]. Weekly objective delivered -> done for the week (038 ~6:33; 101
  ~34:21). Bot: `max_trades_week` caps the week in every engine (entry-time order; paper.py reads the week's trades), `week_done_on_draw` / `friday_week_done` end the week when the objective is delivered (off). D19.
- **X16 Journal items that are code**: record each day's range vs ADR5 and which of the last 3
  days' highs/lows were taken (cc08_006 ~23:42; cc09_005 ~14:22; 010 ~65:54); the weekday and
  session that made each weekly high/low (cc01_003 ~16:36); the timeframe of each entry array (078
  ~27:00).

---

## 3. Decisions for Mase

Each item: the question; option A and B with sources and how often each appears; what ICT's own
trades show; the recommended bot default; the parameter to test both. Ordered by expected impact
on the bot.

**1. When can AM entries start: 09:30 or 10:00?**
- A: 09:30. Ep 01 AM session 08:30-11:00; Ep 07 bought at 09:44. About 6 early-2023 executions
  (006, 007, 009, 034, 053, 088).
- B: 10:00. Wait out the 09:30-10:00 opening range ("amateur hour"); about 10 statements (030, 031,
  036, 042, 044, 065B, 092) and every Silver Bullet video.
- His trades: 09:37-09:50 entries in early 2023; mostly 10:00 or later from 044 on.
- Recommended: keep 09:30 for the existing `am_mm` setup (it is the tested baseline and the sweep can
  happen in the OR); test `am=(600, 660)`. The new SB setup (D2) starts at 10:00 by definition.

**2. Add the Silver Bullet as its own setup, and which version?**
- Sub-questions: (a) must the FVG form inside the window (047, 054 words, 066: 3) or only the
  entry (058, 059, 060, 065B and the 047/054 charts: ~6)? (b) room >= 10 ES pts (054, 058, 059, 060)
  or >= 5 (044, 068, 072)? (c) first FVG only (048) or evolving (057)?
- His trades: FVGs mostly start at 09:55-10:05; entries strictly 10:00-11:00 and 14:00-15:00.
- Recommended: entry 10:00-11:00 / 14:00-15:00, FVG formed after the sweep at any time (or from
  09:50), >= 10 ES pts of room to the draw, evolving allowed. Test `sb_fvg_in_window`,
  `sb_room_pts` = 5 vs 10.

**3. Does the MSS need a candle close, or is a wick through enough?**
- A: body close (Ep 01/02 rules; 035 ~42:44). 2 sources.
- B: wick or 1 tick through is enough (012, 026, 030, 035 ~20:15, 075). 5 sources, all later.
- His trades: 030 (15:17, one tick) and 026 shown with a wick break.
- Recommended: keep close as the default because it is the tested baseline and filters false shifts;
  B is what ICT says more often. Test `mss_mode = "close" | "wick"`.

**4. Mean threshold: body midpoint or full high-low?**
- A: full range with wicks (Ep 02; 061; 065A; 086; cc04_003 slide; cc04_008 drawing). ~6.
- B: body open-close midpoint (009 chart; 026; 104; cc04_003 and cc04_008 spoken; cc06_005;
  cc07_004). ~7.
- His trades: the only priced live stop (009) fits the body MT; the full-range MT would sit above
  his stop.
- Recommended: body for stops and invalidation. Test `mt_mode = "body" | "range"` (bot today:
  range).

**5. Exit buffer: before every level, or before arrays and beyond pools?**
- A: exit 0.5-1 pt before (Ep 08; 010; 030; 049; 063; 070; 101; 102). ~12 sources, nearly all
  FVG/OB/PD-array targets.
- B: exit just beyond (1 tick to 1 pt) (001; 006; 007; 018; 050; 059; 083; 099; 105). ~9 sources,
  nearly all old highs/lows and equal highs/lows.
- His trades: 083 and 105 show unfilled exits at the exact pool level.
- Recommended: split by target type: PD arrays -0.5 pt, liquidity pools +1 tick beyond. Test
  `exit_mode = "split" | "before"` (bot today: before for all).

**6. Breaker zone: body, full candle, or the whole A-B leg; and which candle?**
- A: body of the candle (001; 012; 029; 048; 060; 063; 081; cc09_008). ~8.
- B: full range incl. wicks (031; 032; cc04_005). ~4.
- C: the whole A->B leg (070). D: the single last opposite candle (cc05_014).
- Candle: the highest up-close candle in the swing by body (029; 048; 096), not the last one.
- His trades: 007/019/029 zones drawn on bodies; 031/032 on full range.
- Recommended: body of the highest-body candle. Test `breaker_zone = "body" | "range" | "leg"`
  (bot today: full range of the last up-close candle). Affects the unicorn tag only.

**7. PM window: 13:30, 14:00, or separate sub-setups?**
- A: 13:30 start (013; 031; 033; 037; 047; 067; 069; 010 13:30 open). ~7.
- B: 14:00-16:00 (Ep 01; 047 "sweet spot"; 056). 3. C: 13:00 (cc10_012).
- His trades: entries 13:30-14:20 (015, 050, 058, 060, 066, 067, 068, 103) and 15:15-15:57 (001,
  013, 020, 024, 027).
- Recommended: keep 13:30-15:50 and tag `pm_sb` (14:00-15:00) and `pm_last_hour` (15:15-15:45);
  report each. Test `pm=(840, 950)`.

**8. News days: keep the strict blocks?**
- A: no NFP Friday, no NFP-week Wed PM/Thu/Fri, no FOMC PM (Ep 03/04; 006; 038; 101; cc08_001;
  cc10_009). ~7.
- B: he trades them: NFP Friday (071, 088/089, 105), NFP Thursday (041, 050), FOMC from 14:25-14:45
  (021, 065B), FOMC-day 15:15 short (097). Every case is labelled "experienced only" or a demo.
- Recommended: keep A (the bot is the "new trader"). Test separately `fomc_pm_from = 14:45`,
  `nfp_thu = True`, `nfp_day_from = 10:00`. Add `skip_post_fomc_am` (095).

**9. CPI days: trade after the release or skip?**
- A: only the release is off-limits; trading after it is fine (028; 064; 065B 30-min rule).
- B: CPI grouped with FOMC/NFP as no-trade (021). He never traded a CPI morning on stream.
- Recommended: allow (bot entries start 09:30, an hour after the print). Test `skip_cpi` and
  `skip_pre_cpi`.

**10. Enter only after the MSS, or also in the OB before it?**
- A: after the MSS, at the FVG (most 2023 files; bot).
- B: in the OB before the MSS (003 first entry: 6 lots, 17.5-pt stop; 070 inside the A-B leg; 022
  turtle soup needs no MSS).
- His trades: his biggest documented AM trade (003) used B.
- Recommended: B (owner correction #11, Ep 07 ~2:10, ~11:06, ~13:35, ~15:03): a limit at the bodies
  of the bullish OB at the sweep low before the break of the reference high is the DEFAULT
  (`ob_entry="pre_break"`); A (FVG after the MSS) = `ob_entry="post_mss"`; "both" takes either. No
  HTF/SMT gating.

**11. FVG entry price: near edge, CE, or IOFED?**
- Edge / 1 tick in: 001, 018, 042, 054, 057, 066 (live fills, 6). CE: 007, 024, 048, 030 ladder
  (4, mostly words). IOFED: 003, 006, 010, 024.
- His trades: fills mostly at the near edge; "rarely gets CE fills" (035).
- Recommended: edge (current). Test `entry = "ce"` and `"edge_1tick"`.

**12. Premium/discount filter: midnight open, leg equilibrium, or OTE?**
- A: the open as the reference: longs below the midnight (13:30) open (006; 043; 060; 069; cc03_003).
  Bot today.
- B: the displacement leg: the entry FVG at/beyond 50% of the leg; no adds past 25% (2022 model:
  010; 022; 025; 060; 069; 092). ~6.
- C: OTE 62-79% (cc01_004/005; cc12_004); D: lower third (cc01_006). 061 says fib never for entries.
- His trades: 2023 entries mostly just past 50% of the intraday leg.
- Recommended: keep the open filter and add B (`leg_pd=0.5`, `add_cutoff=0.25`). Test
  `leg_pd = 0.62`.

**13. First partial: half or the bulk?**
- A: bulk 80-90% at the first pool (006; 020; 036 slow days; 102; 104; cc09_006). 6.
- B: about half or less (036 normal days; 018; 041; 057; cc02_001; cc02_003; cc06_008). 7.
- His trades: split; 036 gives the rule "80/20 slow or news-ahead, 50/25/25 normal".
- Recommended: 0.5 (current). Test `partial = 0.8`.

**14. When to go to breakeven, and trail or not?**
- BE A: after the first partial and expansion (032; 036; 046; 105; cc06_008; cc02_001; cc08_007). 7.
- BE B: right after the MSS or when stalling (003; 009; 020; 042, chart examples). 4.
- Trail: under each new FVG (002; 003; 071; 083) vs untrailed day trades, never into a fresh
  post-MSS FVG (029; 064; 085).
- Recommended: BE at T1, trail off (current). Test `be_mode = "after_mss"` and
  `trail_mode = "fvg_after_t1"` (only FVGs older than the MSS leg).

**15. Which index to trade when SPX and NDX diverge?**
- A: the stronger one for longs / weaker for shorts (003; 065B; 079; 085; 086; 089; 090; cc10_011).
  ~9.
- B: the laggard "sick sister" that will catch up (045; 048; 053; 056; 061; 070). ~7. ICT: sick
  sister only in consolidation (053 ~8:20).
- His trades: A won in 003, 085, 086, 089; B won in 045, 053, 070.
- Recommended: A (the index that did not make the new extreme at the sweep). Test
  `smt_pick = "laggard"` on consolidation days. Bot today: `combine()` takes the first fill.

**16. AM trades: exit by 11:00/12:00, or hold to 16:00? PM: done by 15:00?**
- AM: last unit off before noon (003), bulk 10:00-11:00 (cc12_004), hold AM SMT to 10:30-11:00
  (cc10_014). No source holds an AM trade into the PM.
- PM: done by 15:00 once the target is hit (006) vs hold PM trends to 15:00-16:00 (cc10_014; 076).
- His trades: AM exits before lunch; PM exits 15:50-16:01.
- Recommended: add `am_exit = 12:00` as default (bot today: AM runners can last to 16:00). Test
  11:00, and `pm_done_by_1500` once T1 has filled.

**17. Swing size for pivots: 3-candle or 5-candle?**
- A: 3-candle (n=1) everywhere in ICT (012; 050; cc01_004; cc01_005 "not the 5-candle fractal").
- B: bot uses n=2.
- Recommended: test `pivot_n = 1`; keep 2 until it is tested because it changes every MSS reference.

**18. After a stop-out: no re-entry, or same-direction re-entry at half size?**
- A: no reversal after an AM loss (Ep 01). Bot also allows no second trade that session.
- B: same-direction re-entry at half risk while the idea is intact (070; 060; 085; cc02_005;
  cc06_003); flips when "offside" (083; 085; 094; 042) are small, fast and discretionary.
- Recommended: keep no reversal. Test `reentry_half` (one same-direction re-entry, half risk, draw
  untouched). Keep FOMC exempt.

**19. Trade frequency: daily caps only, or weekly caps too?**
- One setup per week (003; cc02_003); ~3 per week (099); one AM SB a day (047); 2 a day (cc08_001);
  skip the PM after an AM win (065B; cc10_007).
- Recommended: keep one AM + one PM. Test `no_pm_after_am_win` and `max_trades_week = 3`.

**20. Trade Mondays?**
- A: skip or PM only (065B new students; 101; cc12_003; cc08_001 small range).
- B: Monday of NFP or FOMC week is always traded (100; 101; 105); many 2023 examples are Mondays
  (007; 018/019; 036; 053; 069).
- Recommended: trade Mondays. Test `skip_monday` with the NFP/FOMC-week exemption.

**21. NWOG and ORG definitions and lifetimes.**
- NWOG: Friday 16:59 to Sunday 18:00 on futures (039; 025; 050; 052: 7 sources) vs Friday close to
  Monday 09:30 (039 variant; bot today). Count: all within 60 days (051) vs last 4-5 (039).
- ORG: close 16:15 (ES, 7 videos) vs 16:00 (3); SPX data only has 16:00. Lifetime 3 days (060), 5
  (068), ~60 (092).
- Recommended: label the bot's gap "Monday ORG", add CE; ORG daily from the 16:00 close with a
  5-day life. Use the true NWOG only if the CFD files carry Sunday-evening bars. Test `org_days = 60`.

**22. Midnight open: SPY 04:00 proxy or the real midnight?**
- ICT: the 00:00 15m candle open (006; 069; cc08_002). The bot uses the first bar at/after 00:00,
  which on SPY data is 04:00.
- Recommended: take the midnight open from the SPX/NDX CFD bars (they include overnight) and map it
  to SPY. Test against the 09:30 open (`bias_open = "midnight" | "0930"`).

**23. SD projection anchor.**
- Down-leg into the low (014, the only multi-example study); low to the broken high (029; 030; 047;
  062); manipulation leg (092; Ep 06); breaker A-B (070).
- Recommended: keep the bot's anchor (sweep extreme to the broken swing), extend k to -0.5..-4.5 and
  use only the first level beyond the pool (014/030). Test the 014 down-leg anchor
  (`sd_anchor`).

---

## 4. Proposed bot changes

Each item names the params to add (in `strategy.Params`) and whether it is a **tag** (recorded
and reported per trade, changes nothing), a **filter** (removes trades), or a **change** (alters
entries, stops or exits). Default first, then what to test. Run every switch on the same
2019-2026 SPX/NDX data through `study.py` and report by tag.

### P1 (cheap, high evidence, directly on the existing engine)

1. **MSS mode** - change. `mss_mode="close"|"wick"` in `_scan` (today `c[i] > ref`). D3.
2. **MT measure** - change. `mt_mode="body"|"range"`; `levels.order_block` returns the body
   midpoint as well; stop uses it. Also blend consecutive same-colour candles into one OB and anchor
   on the first candle's open (A12). D4.
3. **Exit buffer by target type** - change. `exit_mode="split"|"before"`, `pool_beyond_pts=0.25`;
   label each target as `pool` (pdh/pdl, pmh/pml, rel-eq, session H/L) or `array` (NWOG/ORG/FVG).
   D5.
4. **Real midnight open** - change. Use the SPX/NDX CFD 00:00 bar for `opens["midnight"]` and the
   pre-market pools; keep the SPY 04:00 proxy as `bias_open_src="spy"` for comparison. D22.
5. **Opening-range wait** - filter. `am=(600, 660)` variant; also `or_no_entry=True` that keeps
   09:30-10:00 sweeps valid but blocks fills before 10:00. D1.
6. **Silver Bullet setup** - change (new setup tag `sb_am`, `sb_pm`). Params `sb=True`,
   `sb_windows=((600,660),(840,900))`, `sb_fvg_in_window=False`, `sb_room_pts=10`,
   `sb_evolve=True`. Same sweep -> MSS -> FVG engine; entry only inside the window; pending order
   cancelled at window end; evolving FVG moves the limit. D2.
7. **Room to the draw** - filter. `min_draw_pts=10`: the farthest qualifying target must be >= 10
   ES pts from entry even when T1 is ~5 (today only `min_rr` on T1). L15.
8. **Leg premium/discount (2022 model)** - filter + change. `leg_pd=0.5`: entry FVG must sit at or
   beyond 50% of the displacement leg (sweep extreme to leg high); `add_cutoff=0.25`: no adds once
   price passes the leg's 25% line. D12.
9. **Aborts and time stop** - change. `fvg_abort=True` (X6: body close beyond the FVG's far edge,
   next bar beyond that bar's extreme -> exit at market); `time_stop_bars=3` with `time_stop_pts`
   (no progress of X ES pts within N 1m bars of the fill -> exit). Test N = 3 and 10. X6, X9.
10. **AM exit time** - change. `am_exit=720` (12:00), test 660; `pm_done_by=900` (exit at 15:00 if
    T1 already filled). D16.
11. **Pivot size** - change. Test `pivot_n=1`. D17.

### P2 (more code, solid rules)

12. **New levels in `levels.py` / `DayCtx`** - change (targets and sweep pools):
    - `org=True`, `org_days=5`: ORG high/75%/CE/25%/low from the prior 16:00 close and 09:30 open
      (L7); as AM sweep level and target ladder near edge -> CE -> prior close.
    - NWOG CE and quarters; relabel the current gap as Monday ORG; true NWOG if Sunday bars exist;
      keep 60 days (L5). D21.
    - Session pools: previous PM 13:30-16:00 H/L and London 02:00-05:00 H/L (CFD overnight bars) as
      AM sweep pools with the 067 priority; lunch 12:00-13:30 H/L as PM sweep/target; OR30/OR60 H/L
      (L1, L3).
    - Previous week H/L, previous month H/L, 20/40/60-day H/L as far targets (L3, B21).
    - FVG targets: untouched 15m/60m/daily FVGs beyond price (near edge then CE), reusing `htf`
      zones; BPR and rejection-block levels (L9, L11).
    - Wick CE levels for several prior days, as partial/target candidates (`wick_levels`
      extended; L10).
    - Target hygiene: only targets not traded through since they formed (L14).
13. **Breaker zone** - change (unicorn tag only). `breaker_zone="body"|"range"|"leg"`; pick the
    highest-body up-close candle in the swing. D6.
14. **IFVG entry type** - change. `ifvg=True`: an opposing FVG closed through, a new candle trades
    back into it; entry at CE; depth rule A8; stop CE + 3 ES pts. As an extra entry zone for the
    existing machine (M10) and for the PM reversal (M6).
15. **Partials, BE, trailing, adds** - change. `partial=0.8` test (D13); `be_mode="t1"|"after_mss"`
    (D14); `trail_mode="off"|"fvg_after_t1"` excluding FVGs from the MSS leg (X5); `adds=(0.5,
    0.33, 0.17)` decreasing plus the `add_cutoff` (E12); optional add at the FVG low end when a body
    closes into it.
16. **Stop beyond nearby inefficiencies** - change. `stop_beyond_gaps=True`: stop = min(OB MT,
    lowest FVG low below entry in the leg), within `max_risk_pts`; `stop_pad_pts` test 1 tick vs 3
    ES pts on CE stops (E6).
17. **Calendar filters** - filters, each off by default, all also recorded as tags:
    `skip_cpi`, `skip_pre_cpi`, `skip_pre_fomc`, `skip_post_fomc_am`, `fomc_pm_from=885` (14:45),
    `nfp_thu`, `nfp_day_from`, `skip_two_drivers` (extend `calendar.py` 10:00 releases to
    2019-2025), `skip_holiday_eve`, `skip_post_holiday_am`, `skip_august` (N1-N7). D8, D9.
18. **Loss handling** - change. `loss_halving=True` (next trade 0.5x risk until a win, E10);
    `reentry_half=True` (X13). D18.
19. **Tags (measurement only)** - weekday; macro windows (10:50-11:10, 11:50-12:10, 13:30-13:40,
    14:50-15:10, 15:45-15:50) beside the existing 09:50-10:10; `pm_sb` sub-window; ADR5 ratio of the
    prior day and of today at entry; inside day/week; 3 same-direction closes; ORG size / ADR5;
    opening-gap "no attempt in 30 min" (B15); month (seasonal map); entry-array timeframe; which of
    the last-3-day highs/lows were taken before entry (X16).

### P3 (needs a model of HTF context, or is research)

20. **Daily bias module** - tag first, then filter. `htf_bias="off"|"tag"|"filter"` computed
    pre-open from daily bars built from the 1m data: daily IOF score (B6), position in the 20-day
    range (B21), last daily/weekly structure break (B10), close-based flips (B7, B8), draw = nearest
    untaken of PDH/PDL, 20/40/60-day H/L, unfilled daily FVG edge/CE, daily wick CE. Output +1/0/-1;
    as a filter, scan only the bias side. Replaces/generalises `weekly_bias` (keep the old switch
    for comparison).
21. **Neutral-day gate** - filter. `neutral_skip`: objective met yesterday, price at EQ of the
    20/40/60-day ranges with both sides run, multi-day range, day after > 2x ADR5, day 4 after 3
    same-direction closes, both sides armed in the same window (the codeable proxy for "50/50")
    (B17, N8).
22. **TGIF** - change (new setup tag `tgif`). Friday, after a week with range >= k x the average
    weekly range and the close near the extreme; counter-week entries 10:00-15:00 targeting the
    20-30% retrace zone (M14). Needs an "HTF array reached" flag to be faithful.
23. **Last-hour and PM models** - change (setup tags). `pm_last_hour` as its own model: sweep of a
    lunch/PM low 15:15-15:45, MSS + FVG, target an untaken pool, no entries after 15:45 (M5); PM
    reversal via IFVG (M6); PM off lunch (M7).
24. **SMT** - filter test and instrument choice. `smt_filter=True` (C2); `smt_pick="leader"|
    "laggard"` in `combine()` (D15); AM window from 05:00 using CFD overnight bars.
25. **Weekly framing** - tags then filters: Monday 00:00 weekly open filter (B13); Thursday-cross
    reversal tag; `skip_monday` (D20); `max_trades_week`, `no_pm_after_am_win` (D19); stop for the
    week once the weekly draw (prior week H/L, NWOG) is hit (X15).
26. **Slow intermarket tags** from free daily data: DXY trend, 10/30-yr yield trend, CFTC COT
    hedging-program state (B19, B20). Tags only.
27. **Research only**: Ma Deuce (pre-market, M15); ORG repricing (M8); news Judas second-run entry
    (M9); turtle soup at OR60 low (M12); statistics tests for T12/T14 (where HOD/LOD and weekly
    extremes form on SPX 2019-2026).

### Too discretionary or needs data (brief)

- **Discretionary**: "obvious" draw and "parent" range choice; high- vs low-resistance runs (proxy:
  count of opposing swings/FVGs between entry and target); full pull vs partials; which wick CE
  matters; three-PD-array exit (which arrays); smart money reversal (selling within 1-2 ticks of
  an HTF high); Reaper; reclaimed blocks (need the curve low in real time); weekly profile and six
  day-profile classification; layering/BPR depth reads; "speed and distance" and lethargic
  delivery (no thresholds); implied FVG (undefined); "seek and destroy" and "in sync" reads.
- **Needs data**: YM/DJI 1m for three-index SMT {d: DJI daily only}; DXY intraday (daily is free);
  ZB/ZN intraday (FRED yields daily are free); CME open interest; Fed-speaker, Treasury-auction and
  early-close calendars; Sunday 18:00 and 17:00-18:00 futures prints for the true NWOG/NDOG (check
  the CFD files first); headlines/sentiment text.
- **FX-only**: CBDR/Asian/Flout projections, London protraction models, 0 GMT entries, pip-sized
  stops and room rules.
- **Undefined thresholds** to choose by test, not by reading: REH/REL tolerance; displacement size;
  minimum FVG size and when quadrants apply; "large" ORG or prior range; macro "no move"; time-stop
  window and "progress"; IFVG retest delay; TGIF "trending week".

---

## Appendix A. Verified rules, 2023 Ep 01-08 (caption-checked, kept verbatim)

All times New York (ET); ICT stresses charts must be set to New York local time, daylight
saving included (Ep 01 ~25:15, Ep 03 ~9:46, Ep 04 ~4:07). ICT trades ES/NQ futures; our bot
trades what Schwab allows (SPY/QQQ) with ES-equivalent targets.

Verified 2026-10-17 against the YouTube auto-captions of playlist PLVgHx4Z63pabpjlduWBaEsn8VMtALhjGV
(captions kept locally in data/mentorship/captions/, not committed). Notation: "~mm:ss"
= approximate time in that video; [corrected] = the earlier note overstated or misstated it;
[added] = in the transcript but missing from the earlier notes.

Episode -> playlist position: Ep 01=#1, Ep 02=#2, Ep 03=#3 (#5 is the same video again),
Ep 04=#6, Ep 05=#7, Ep 06=#8, Ep 07=#9, Ep 08=#10. Playlist #4 (AUbdCTzc19k, "ICT Emini NQ
Futures Market Maker Live Execution", 2 min) has no captions and is not covered. Next new
video: #11 (w0CYBeFTzcM, "ICT Premarket Commentary for Week Ending 01/20/23").

## Ep 01 (XN8tuO4QIRw), Jan 1 2023
Definitions
- Buy-side liquidity: buy stops above old highs / relative equal highs. Sell-side liquidity: below old lows / relative equal lows.
- Fair value gap (FVG): 3-candle pattern, gap between candle 1 high and candle 3 low (bullish = BISI) or candle 1 low and candle 3 high (bearish = SIBI). Consequent encroachment = 50% of the gap. [corrected] Only the bullish form is defined in this video; SIBI is named in Ep 02/03.
- Liquidity void: an actual gap between candles (no overlap at all).
- Balanced price range: an FVG price has passed through both ways; price should not re-enter it.
- Breakaway gap: FVG formed as price accelerates away; expected to stay open (don't expect retrace).
- Breaker: low, high, lower low, then price breaks back above the high (use the candle body, not wick).
- Narrative (how the day trades, what liquidity it aims for) is separate from bias (direction).

Day context
- Low-volatility days (e.g. last trading day of year) -> expect an inside day vs previous day's high/low, framed before the 08:30/09:30 open (~16:42). Monday refers to Friday's range.
- Year end takes its side from December's direction: positions built in December get squared (Dec 2022 down, no Santa rally -> shorts covered -> reprice up to buy stops above 3864). Not always bullish. [owner correction #3; mapping = `year_end_map`, pending owner confirmation - owner_directives.md says Dec up -> bullish, the Ep 01 example runs against December] (~12:04-12:16, ~31:13-35:45). Bot: `year_end` switch, default off until confirmed.

Sessions
- AM session 08:30-11:00. PM session 14:00-16:00; focus on last hour 15:00-16:00.
- PM setup window 15:15-15:45. No setup by ~10 minutes before the close (15:50) -> no trade. [corrected] He says "10 minutes before", not the clock time (~1:00:45).
- Lose in AM -> do NOT reverse; stop for the morning, wait for PM. [corrected] Stated firmly for new traders and "never" for funded accounts; he allows that experienced traders sometimes reverse (~46:57-48:43). The bot keeps the strict rule.
- [added] The last-hour run to an old high, old low or imbalance happens nearly every trading day (~49:28).

PM "last hour" setup (the trade shown)
- Mark draw on liquidity: old high/low, relative equal highs/lows, or an unfilled imbalance. Bullish -> target above; bearish -> below.
- Look for nested FVGs aligned on 4h / 1h / 15m / 5m; price trading back into the higher-TF FVG and holding (bodies refuse to close beyond it).
- [added] Context: in the last hour price should hold above the midpoint of the 4h FVG (~30:48).
- [added] Trigger: bodies refuse to close through the low end of the 60m FVG, then price accelerates away, leaving a breakaway FVG (~39:00-40:00). By about 15:25 the move toward the liquidity should have started (~38:57).
- Entry: at the top of the 1-min bullish FVG (mirror for shorts); can add on retests and on a breaker. (He says he bought the top of the gap; "limit order" is our reading.)
- [added] If price dips back into the breakaway gap, buy it with the stop just below the candle bodies (~42:19).
- Stop: just below the opening of the FVG candle, later below the candle bodies and trailed up (~37:45, ~42:19).
- Target: the liquidity pool (e.g. relative equal highs), with a nearer short-term high as an intermediate target (~42:19). Goal ~5 ES handles. [corrected] The 1-point drawdown was one entry, not described as typical.
- [added] A clean delivery has few, small down-close candles; the speed is in the up-closes (~34:45).
- Chart reference points pulled down to 5m and 1m for execution.

## Ep 02 ES review Jan 3 2023 (GHaD0mebgMU)
- News days: when data drops at 9:45 (PMI), wait for the release, not just the 9:30 open. A Judas swing (fake run into nearby liquidity/imbalance during the news) was expected, then the real move. [corrected] The video only covers the 9:45 release (8:30 is not mentioned), and the expected Judas run did not happen: price failed early, so he waited for the structure shift instead (~0:00, ~7:03).
- AM short setup: run up into buy-side liquidity (old high / round number), then market structure shift (break of a swing low with displacement), then short on retrace into the FVG / bearish order block / breaker. Can add on later FVG retests (three entries in the example).
- Order block: last up-close candle(s) before the down move (bearish OB). Mean threshold = 50% of the OB measured from its high to its low (wicks included); bodies should respect it.
- CE = 50% of FVG; MT = 50% of OB.
- Targets: higher-TF FVGs (15m, 30m) and sell-side liquidity below lows; take partials at each level, hold runners while price stays "heavy" (below the 30m FVG). [corrected] He would "probably" exit if price goes back above that FVG, not specifically on a close (~8:39-9:19).
- If no daily range breakout / no higher-TF daily narrative -> intraday scalping only, small targets.
- First trading day of year: don't rush in.
- [added] Top-down chart sequence: daily volume imbalance, then 60m, 30m, 15m, 5m, 1m (~0:56-2:29). On news days the draw was the daily volume imbalance (~9:19).
- [added] An FVG left open on the way down is a breakaway gap (~4:08).

## Ep 03 NQ trade review Jan 4 2023 (ojy5ApHhEu4)
Day type (important)
- Non-farm payroll (NFP) week: trade only Mon, Tue, and Wed up to the end of the NY AM session. Wed PM, Thu, Fri of NFP week are choppy/imprecise -> no trade.
- FOMC day (2pm release): do not trade the release ("carnival ride"). Standing aside for the whole PM is our reading (~4:02, ~36:56).
Definitions
- Volume imbalance: between two consecutive candle bodies (close to next open) where the only overlap is wicks. Draw on liquidity on the daily chart.
- BISI = bullish FVG (bought for longs, target for shorts); SIBI = bearish FVG.
- Measuring gap: an FVG that stays open mid-move; roughly half of the move -> project the target.
- Institutional order flow entry drill: a shallow dip into an FVG that does not reach 50% (CE), then continuation.
- Rejection block: named as the next draw on liquidity. [corrected] It is not defined in this video; "a level of wicks" was our gloss.
- Reclaimed order block: price leaves an OB and trades back into it as support; normal.
- [added] Order blocks are anchored on the down-close candle: its high or its open (~10:34, ~30:58).
- [added] The first FVG after the shift should act as a breakaway gap and not be fully closed; with price leaving it, the range it leaves is a protected zone, which justifies trailing the stop under it (~27:46, ~29:20, ~41:54).
Instrument selection (SMT / relative strength)
- Compare NQ vs ES on the same timeframe. Trade the stronger one for longs (made the cleaner higher high, cleaner FVG). Divergence between them = SMT.
Market maker buy model (long)
- Higher-TF draw above (daily volume imbalance, relative equal highs). Price drops into a discount (lower half of range) into a 5m order block / 1m BISI.
- Takes a short-term low, then breaks a short-term high (market structure shift in discount) leaving an FVG. [added] In the example the 9:30 open dropped below the lows and the setup formed in 10:30-11:00 (~16:45).
- Entry: long at the FVG (he watched its top for support and added there); stop below. Move stop to breakeven after buy-side is run. Pyramid on retests of new FVGs that hold (up to ~10 contracts, ~2.1% risk of a $100k account).
- Expect stop-run of retail bull-flag stops before continuation.
- [added] After large candles turn into small-range candles, expect large candles in the bias direction next (~45:55).
Exits ("running down equity")
- Scale out one contract at a time as each new high prints near each liquidity pool/target, not all at once. Trail stop below the latest measuring gap after two rounds of partials (~1:05:10); the aim is a "funded" position. Never widen a stop (~1:14:05).
- Final target: higher-TF PD array (daily volume imbalance). Accept getting stopped on the last few units.
- [corrected] Lunch: going into noon usually retraces; he says he should have taken off the last contract before it (~1:18:16). The 12:00-13:00 window and "tighten" are our wording.
- Goal: 1 good setup per week; low-hanging target 5 handles (20 ticks).
- [added] Use time-based charts only (no Heikin Ashi, range or renko bars) (~44:23).

## Ep 04 NFP review Jan 6 2023 (VKkn8uckkW0)
- NFP Friday: no live trading (paper/study only). High-impact news (NFP, FOMC) can overshoot FVGs. [corrected] He ignores the immediate reaction to the 08:30 release and waits for the real range; no fixed minute count (~8:35, ~27:45).
- Midnight NY open (00:00 ET 15m candle open) = the true daily open. Power of three (accumulation, manipulation, distribution):
  - Bullish day: buy at or below the midnight open (worst case near it); expect a fake move against bias, then expansion away and a close near the day's high.
  - Bearish day: mirror (sell at/above midnight open).
- Dealing range: after the news, the high/low of the post-manipulation range is the framework. Expect expansion to external range liquidity (beyond that range's high/low).
- Entry trigger: market structure shift (break of a short-term high) while an FVG/BISI stays open; enter on retrace to order block / FVG near midnight open.
- [added] He wanted two structure shifts, each leaving an open FVG, before calling himself "on side" (~49:29).
- Institutional order flow entry drill = retrace that stops ~1 tick into the FVG. Pyramid: largest size first, smaller adds lower (e.g. 6,3,2,1), never larger adds; no adds after partials have been taken. [added] If price closes into the FVG instead, add again at the FVG's low end (~51:00).
- Smooth/"too clean" relative equal highs or lows are magnets; price will run them.
- Targets in order: nearby relative equal highs, old daily highs (previous days' highs/lows hold real liquidity), then daily volume imbalance. Take the bulk (e.g. 10 of 12) at the first target, rest at next ones.
- If target hit by 15:00, be done; last hour tends to retrace into the range.
- SMT: compare ES vs MES for divergence at lows/highs. [corrected] NQ is not used in this video.

## Ep 05 ES review Jan 9 2023 (bGtQOXrrK9c)
- Bearish breaker: high, low, higher high, then the move back down; mean threshold (50% of the OB/breaker) and CE of FVGs as reaction levels. [corrected] "Break below the low" and "resistance" are implied, not stated (~0:00, ~1:42).
- No 8:30 news -> wait for 9:30 open before acting.
- New Week Opening Gap (NWOG): a target/PD array. [corrected] The definition (Friday close to the Sunday open) is not given in this video.
- "Unicorn" (strongest entry): FVG that sits inside a breaker, right after a run on sell-side (bullish) at the 9:30 open. Buy at FVG/CE inside the breaker; add on each new imbalance.
- Accumulate inside the breaker/consolidation before the breakout, not on the breakout.
- [corrected] The 10-12 handle "bread and butter" move was the pre-9:30 move off the 08:00 order block, not the AM setup; the partial was ~1 handle above the relative equal highs (~14:25-15:15, ~19:09).
- [corrected] Lunch: at noon that day price reversed off the hourly FVG's CE; one observation, not a stated rule (~9:16).
- Market maker sell model: consolidation with sell-side below, rally (bought inside a breaker) into relative equal highs, MSS down, sell when price fails to reach the imbalance's CE, run to sell-side, NWOG, imbalances.
- Weekly bias filter: after the strong down day, favor shorts the rest of the week unless price gets back above 50% of that day's wick on a closing basis (~2:36, ~24:20). [corrected] Stated for that week, not as a general rule.
- Watch one market only (he lost track switching between ES and the US500 CFD).
- [added] The stop was placed just below the FVG's high when he couldn't watch, and it was hit (~19:09).

## Ep 06 Forex review Jan 9 2023 (cxdjcXec3eA) - mostly FX, general timing rules
- Kill zones (NY time): London open 02:00-05:00, NY open 07:00-09:00 (FX), London close 10:00-12:00.
- Trending day template: low of day (bullish) forms in London open, continuation in NY open, high of day forms in London close 10:00-12:00; reversal/end of move often at noon.
- Retracement into a SIBI often stops at CE (50%), not the old lows (S/R fails).
- Projection: anchor fib on the manipulation swing (London low to the high) and project standard deviations 1, 1.5, 2, 2.5, 3... as targets. [corrected] Projections only apply after price takes out that high; the 1.5 SD matched closing prices, not wicks, in the 10:00-12:00 window (~6:01-6:49).
- Correlation: DXY bearish = risk-on (EURUSD up). [corrected] "Indices up" and "optional filter" were our additions.
- [added] The midnight opening price is the reference: if bearish, look for price below it (~0:51).
- [added] Relative equal highs/lows are the preferred liquidity pools (~4:31).

## Ep 07 ES live execution & mean threshold risk (tnxvmHq8xEg)
- Draw on liquidity can be an old daily close (e.g. prior daily close level) = "unrealized premium array" target set before the week.
- AM model: wait for 9:30; sell-side purged (e.g. below 9:20 low at ~9:40), then rally leaves an FVG/volume imbalance; buy inside the FVG near its midpoint.
- Stop: below the mean threshold (50%) of the down-close candle (bullish OB) closest to the sweep low. [corrected] Not the candle nearest under the entry (~4:07). Later trail to the low of the retracement candle once price trades through the bodies of the prior swing high.
- Volume imbalance (gap between one candle's close and next candle's open) should hold; stop at its low.
- Pyramid on down-close candles into bullish OB/volume imbalance; take profit on up-close candles ("market efficiency paradigm": buy down candles, sell up candles).
- Trigger: price must break the high of the small SIBI/swing quickly ("speed and distance"); once broken, expect acceleration to buy-side above recent highs.
- [added] Invalidation: after the trigger, price should not trade below the lowest open or close of the swing low (~15:36).
- Macro: 09:50-10:10 ET often produces a run to liquidity or an inefficiency.
- Exit bulk (e.g. 9 of 14) at the target; risk per trade ~1-1.3% of account.
- Think in 5-handle increments; ~15 handles/day possible.

## Ep 08 ES review Jan 18 2023 (cWekmMLqiNM)
- Daily levels: 50% of a daily candle's wick (high to open / low to open) is a key level; daily FVG edges hit to the tick.
- Neutral bias allowed: when unclear (price stuck at a premium array, choppy consolidation), wait for 9:30 open to reveal direction. Choppy = small 2.5-5 handle scalps. [corrected] Sitting out entirely is advice for seasoned traders; new traders should study the chop (~76:36).
- Three opening prices: midnight (preferred), 08:30, 09:30 (and 13:30 for PM). Bearish: sell above the opening price (premium). [corrected] "Bullish: buy below" is the mirror; only the bearish side is stated here.
- MSS validity: the swing low that counts is the one that led to the high that ran liquidity (e.g. previous day high). Don't trust a shift until the relevant liquidity run happened.
- Bearish order block: series of up-close candles before the drop; price returns exactly to their open, then reprices lower; the next wick stops at the up-close candle's mean threshold.
- PM session uses 13:30 open as a Judas swing reference: rally above 13:30 open into premium/FVG then sell. Last hour 15:00-16:15 setups at old daily highs/lows.
- Equilibrium: after a break of short-term low, look for FVG at or above 50% of the swing (premium) to sell.
- Partials: never target the exact low/high of an FVG; exit 0.5-1 point before. [added] A first partial can go at the FVG's CE or the top of a daily FVG (~58:28, ~68:17).
- Measured move: projection of range high-to-low equal distance as target.
- Liquidity matrix: highs and lows of the last 3 trading days (today, yesterday, day before), plus the 3-day highest high and lowest low = targets/entry framework.
- Old daily low/high alone is not an entry; need a PD array (FVG, OB, breaker) there plus time of day.
- Max size ~6 contracts initial, build to 10-16 via pyramiding within risk. [added] After a loss on the day, no max size (~49:51).
- [corrected] "Done for the week" was a personal remark once the week's expected range was delivered (~78:05), not a stated rule.
- [added] Institutional order flow entry drill only needs price to touch the candle that created the FVG (~47:36).
- [added] Turtle soup plan: let price spike above an old high (buy stops), short the failure, target the next draw, add on new FVGs/breakers (~25:13, ~36:53).
- [added] Multi-timeframe shift: price breaks below 5m equal lows on the 1m chart, then retraces into the 5m FVG to sell (~60:04-61:38).
- [added] Stops about one tick beyond the level (~16:01). He wants ~10 handles of range before engaging fully (~75:10).
