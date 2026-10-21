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
  - Caption-gap fix (A1-impulse-swing-unit; cc01_008 ~1:52): the unit is the IMPULSE swing - a clear one-directional leg between alternating swing extremes; keep only clear swings (item 54's test: >= 60% of bars in the direction, or a displacement FVG inside, or >= 1x ATR). The fib reference is the active parent leg, not the latest minor leg (FX only: protraction-time manipulation legs). Bot: `levels.impulse_legs` / `leg_is_impulsive` (helper, no switch; the A21 `leg_anchor="energetic"` anchor uses the same test).
- **A2 Buy-side liquidity (BSL)** = buy stops above old highs and relative equal highs;
  **sell-side (SSL)** = sell stops below old lows and relative equal lows (001 ~13:02; cc01_007
  ~1:09; cc04_011 ~4:11) [both]. A level is "booked" only when price trades 1 tick through it
  (042 ~59:04) [2023]. An imbalance is not liquidity (033 ~24:34) [2023].
  - Caption-gap fix (A2-which-old-high; 002 ~0:34): the active buy-side pool = the first earlier HTF (daily) swing high above today's high so far, walking back from the newest to the oldest swing high; the sell side mirrors it below today's low. Bot: `active_old_pool` (off) = pools old_hi / old_lo (targets, sweep pools, lock candidates).
  - Caption-gap fix (A2-round-number-pool; 002 ~2:37): a round 00 handle above (below) price acts as buy-side (sell-side); a sweep = trading through it. Use it as CONFLUENCE for the sweep step alongside an old high / low (within 1 ES pt [our interpretation]), never on its own. Bot: `round_pool_mode` "pool" (the built standalone round pools, owner #13) / "confluence" (a handle is kept only with an old high / low (daily, prior week / month, the active old pool), a rel-eq or an engineered pool within `round_conf_pts`; tag `round_conf`) / "tag_only".
  - Caption-gap fix (A2-open-float; 033 ~24:26, cc05_002 ~1:10, cc09_004 ~4:02): open float = all resting stop orders around price, not only at old highs / lows - possibly just beyond price. After a down move the short-term highs (REH) formed during the decline hold shorts' trailed stops: when price is denied continuation (a small, choppy range: no new low for `float_denied_bars` = 20 bars with a range under `float_denied_adr` = 0.3 x ADR5 [our interpretation]) the draw is the nearest such pool above; mirror. In a consolidation the pools sit just beyond its high / low and at its internal highs / lows, heavier with duration (L4; day-trade consolidations are brief). Bot: `open_float_pools` (off; the duration weight is not built).
  - Caption-gap fix (A2-delivery-vs-liquidity; 104 ~11:24: "buy side delivery is the actual animated movement of price"): buy-side DELIVERY = a leg moving higher, sell-side delivery = a leg moving lower; buy-side / sell-side LIQUIDITY = the static stop pools (above). The MM sell model: buy-side delivery runs into BSL (REH), then sell-side delivery runs to the new SSL engineered below the rally's lows. Bot: `Trade.delivery` ("up" / "down" = the last displacement leg, always tagged), `mm_ssl_target` (off; with `mmxm_ctx` the draw is the far end of the delivery leg - side space: the highest high of the leg from `leg_origin` into the sweep extreme).
- **A3 Relative equal highs/lows (REH/REL)** = 2+ highs (lows) close together; the smoother, the
  stronger the magnet; they get run even under an older higher high (Ep 04; 006 ~26:43; 025
  ~36:20; cc01_003 ~15:23; cc04_014 ~2:17) [both]. Nearly level bodies count even if wicks differ
  (cc05_003 ~1:07:26); draw the REL line at the lower of the two lows (038 ~43:43). ICT never gives
  a tolerance. Bot: `eq_tol_pts=0.5` ES pt, cluster extreme = the pool.
  - Caption-gap fix (A3-diagonal-support-is-liquidity; 045 ~26:02, cc03_007 ~2:12/~23:18): never use a diagonal trendline or a pattern breakout as S/R, bias, entry or stop. A smooth diagonal run of higher lows (lower highs) on the execution TF = retail stops beneath (above): expect a spike through it; a trendline/pattern break against daily order flow is a trap. Bot: `diag_pools` (off; >= `diag_min_swings` = 3 swings within the REL tolerance of one line [our interpretation]) = a sweep pool of kind "diag" at the extrapolated line.
  - Caption-gap fix (A3-engineered-liquidity; 035 ~49:54): engineered buy-side = an old swing high H1, a later LOWER high H2 that falls short of it (within `eng_short_pts` = 3 ES pts [our interpretation]), then price drops away (a swing low below the low between them): the new shorts' buy stops rest above H2 and H1, so the pool is above H1; rank it higher with more time between H1 and H2 and with an FVG above H1. Mirror for sell-side. Bot: `engineered_pools` (off; 15m / 1h / daily swings; counts like a rel-eq pool under `eq_pref` in the sweep pick and the draw, higher score first among engineered sweeps; the FVG bonus uses an opposing FVG known by the pool's creation bar; a sweep of one is tagged `engineered`).
  - Caption-gap fix (A3-clean-high; cc01_003 ~15:33): a clean high = swing high H1, price trades away for a while, then H2 within the tolerance of H1 (slightly below OR ABOVE); buy stops sit above max(H1, H2). The two swings must be separated (>= `eq_min_sep_bars` bars; two adjacent equal bars are one swing) [our interpretation]. Bot: `eq_min_sep_bars` (0 = the old rule; 3 to test), the pool is the cluster's most extreme price and a slightly higher second high no longer spends the first.
- **A4 Bodies vs wicks.** Bodies mark the real level and "tell the story"; wicks "do the damage".
  A 1-2 tick wick beyond a level ("mohawk") still counts as respect (019 ~14:55; 032 ~9:00; 038
  ~46:16; 042 ~1:07:39; 065A ~2:53:30; 096 ~12:04) [2023]. CC: stops sit beyond the body cluster, a
  sweep need not take the wick (cc02_008 ~9:03; cc03_002 ~2:01; cc05_004 ~13:35) [CC]. Bot: a
  sweep = trade past the wick extreme.

**Gaps**
  - Caption-gap fix (A4-wick-poke-vi-invalidation; 090 ~1:05:53: "if it goes back above this high here ... I'm not interested"): after a wick-only poke through a daily / 4h level (no body close beyond) keep the idea and record H = the poke extreme; a trade back beyond H cancels the AM orders of that side; re-evaluate at the 13:30 PM session. Mirror. Bot: `poke_high_cancel` (off; same-side 4h / D arrays of the Confluence object; the PM is not gated).
  - Caption-gap fix (A4-ltf-body-qualification; 104 ~21:53, ~34:55: "only the candlesticks wicks are piercing it"): a 60m FVG reached by a run is a qualified reversal level when the 15m (also 5m) BODIES stay inside it / do not close beyond its far edge, even if wicks pierce by more than the 1-2 tick mohawk; then expect delivery toward the opposing draw. Bot: `htf_body_qual` (off; the zones of `htf_entry_arrays` count as fresh while the 5m / 15m bodies since they formed hold above the far edge; the turtle-soup external array is NOT covered).
  - Caption-gap fix (A4-sweep-body-cluster; cc03_002 ~11:36: "we only need it to reach below the bodies of the candle", cc02_007 ~21:51): decision `sweep_ref`: "wick" (as built) / "body" (the relative-equal-low pool is a cluster of 2+ candles whose BODIES end at about the same price; the line is the lowest body, a sweep needs a low below it). Daily context: a run below a body-low cluster that is the first return to the zone in ~1.5-2 months (30-45 sessions [our interpretation]) is HTF accumulation - on the LTF ignore the bearish continuation patterns there and buy after a swing high forms and breaks. Bot: `sweep_ref` ("wick"), `daily_first_return` (off; a TAG on the order only - the LTF behaviour change is NOT built), `daily_first_days` (30).
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
  - Caption-gap fix (X-efficient-delivery-two-pass; 026 ~1:58:21, 050 ~30:29, 061 ~1:35:24): track `up_pass` / `down_pass` on every gap band (FVG, VI, NDOG, NWOG, wick area, void) on its own TF, wicks counting. No pass = open draw; one pass = one-sided (still a target and S/R, the missing side is the next delivery); both = efficient, not a target; NDOG / NWOG stay as references. A band crossed several times (>= `shield_passes` = 3 [our interpretation]) shields the arrays beyond it. Bot: `two_pass_state` (off; intraday bands, HTF bands are not judged yet).
  - Caption-gap fix (A5-caffeine-bar-bisi; 006 ~12:34): a bullish FVG whose c2 is ONE large displacement candle (range >= 2x the mean of the prior 20 bars [our interpretation]) is a significant array; on a normal day any trade below its low (c1 high) kills it; on NFP / FOMC days price can overshoot, so validity is not judged then. Bot: `single_bar_fvg_strict` (off).
  - Caption-gap fix (A5-broken-fvg-reclaim; 027 ~22:24, 091 ~20:18): a broken bullish FVG is invalid; it is reclaimed as a bullish discount array only if price first moved away below it (a swing beyond), later came back and closed above its high, and the bias is bullish (not in premium); chop across it does not reclaim (the "or above CE" variant is removed); in bearish / premium context it is an IFVG (A8). Bot: `fvg_reclaim` (off).
  - Caption-gap fix (A11-htf-gap-own-tf; 061 ~40:20; conflict 078 ~1:13:50): an FVG on timeframe T stays inefficient (an open draw) until bodies on T or higher close across it; ignore LTF oscillation inside it when deciding filled / balanced / BPR. 078 lets 4h back-and-forth balance part of a daily gap. Bot: `balance_tf` "own" (default, the spec: only closes of the array's own timeframe retire it) / "legacy" (the earlier build: a weekly array is retired by DAILY closes) / "next_lower" (4h for a daily array, daily for a weekly one).
  - Caption-gap fix (A5-vi-extended-ce; 098 ~1:09:26/~1:09:42): when an FVG's forming candles include a VI on the far side - including a wick-only link - extend the zone to the VI's far body edge; CE = the midpoint of (near edge, extended far edge); allow a small overshoot (~2 pts on ES weekly). Bot: `fvg_vi_extend` (the extension) with `fvg_vi_extend_ce` (True: the CE follows the extended zone and a wick-linked VI extends it too - a fix, not a behaviour switch).
  - Caption-gap fix (A5-twice-traded-not-fvg; cc05_015 ~11:38): an OB's wick zone that another candle has traded through ("closed in") is not a gap; only one-sided zones count as gaps (A5's strict wick-based FVG already excludes them). Anchor on the OB open (A12-open-vs-wick-gap-criterion, same switch `ob_anchor_rule`).
  - Caption-gap fix (A24-implied-fvg-defined; 035 ~29:49): implied FVG = the range between the CEs (A23) of two wicks, extended forward and used like an FVG; trading through it in the bias direction = strong continuation. [our interpretation] the wicks are c1 and c3 facing a large c2 whose wicks overlap (no true FVG): bullish = c1 upper-wick CE to c3 lower-wick CE. Low confidence (a single mention). Bot: `implied_fvg` (already built, A24.1; `levels.implied_fvgs`).
  - Caption-gap fix (BH-premium-FVG-CE-vs-far-edge-trap; 062 ~15:56: "if it does and it starts to sell off this is a trap"): expected reaction - a retrace into a bearish (premium) FVG that holds at or below the CE and then breaks down into a new SIBI expects the sell-side low to be taken; a retrace to the FVG's FAR (high) edge that then sells off is a trap: the sell side holds and price runs buy-side instead - no short, a neutral zone; mirror for a BISI. Bot: `far_edge_trap` (off; the 60m FVG's far edge = its top - 10% of its height [our interpretation]; a retrace held at or under the CE is tagged `ce_hold`).
  - Caption-gap fix (A5-short-into-htf-sibi; 035 ~1:05:16: "I don't want to see it go above the halfway point"): a daily SIBI above price, quartered: the valid short zone is its low up to its CE (best where a 60m / 15m bearish FVG sits in the lowest 25%); enter on the LTF FVG with SMT confirmation (035: index vs DXY; ES / NQ SMT is the substitute [our interpretation]); if price trades above the daily CE before the entry, skip; if already short, a body close above the CE is an exit warning. Bot: `htf_sibi_short_zone` (off; tags `htf_sibi`, `sibi_q1`; exit level `htf_sibi_ce`), `htf_sibi_need_smt` (off). The BISI long is the mirror.
  - Caption-gap fix (A5-premium-half-daily-fvg; 012 ~18:02: "I want to see the majority of the reactions in the upper portion"): inside a large daily BISI, continuation longs come from the upper half; lower-half imbalances should stay open; fills of them or a close below the CE downgrade the setup (expect chop / consolidation, wait). Mirror for a daily SIBI. Bot: `dfvg_half` ("off" / "tag" -> lv_tag `dfvg_lower_half` / "skip" -> reject; the sweep extreme must be at / above the CE less a tick, and no 15m / 1h body may have closed below it today), `dfvg_large_pts` (15, "large" [our interpretation]).
- **A6 Gap types** (062 ~43:58) [2023]:
  - Breakaway gap = first FVG leaving a consolidation or expected level after an MSS. It must stay
    at least partly open and may retrace at most to its half; the range it leaves is "protected"
    (001 ~40:03; 002 ~4:35; 003 ~27:46; 062 ~37:02; 065B ~4:39). Fully filled = not breakaway.
  - Measuring gap = FVG near the middle of the move; project swing extreme -> near edge of the gap,
    target -1 SD (003 ~31:35; 011 ~6:37; 061 ~1:22:05; 062 ~42:19).
  - Common gap = ordinary FVG, may be revisited.
  - Caption-gap fix (A6-breakaway-identification; 001 ~42:50, 062 ~34:53, 060 ~1:14:06): a breakaway candidate needs HTF context (price leaves a pre-marked level expected to hold: an HTF FVG edge held by bodies, a BPR, an HTF level respected earlier in the week); no context = common gap. Forms: the first FVG as price accelerates away from the held level (with or without an MSS, 001); the SIBI of the SECOND MSS (the first MSS's FVG is a common gap, 062); the FVG after a blow-off run through the target pool is LIKE a breakaway (060, an analogue). If price returns into it, trade it with the stop beyond the candle bodies; a body close beyond its CE = not breakaway, exit. Bot: `breakaway_def` = "first_after_mss" (default) / "context" (`breakaway_ctx_pts`) / "second_mss".
  - Caption-gap fix (A6-breakaway-depth-qualification; 062 ~37:12/~39:01, 065 ~4:39:02, 075 ~1:39:36, 084 ~29:16, cc04_009 ~13:37): replace "at most half" with the switch `bk_depth`: "ce" (A6: at most 50%) / "any_open" (062, cc04_009: any portion left open, then a move away = breakaway; a full fill = not breakaway). State machine: candidate -> retraced (price trades into the gap, far edge untouched) -> QUALIFIED when price then trades beyond the highest high (lowest low) since the gap formed with the far edge still untouched; only a qualified gap is a protected / trail level. A BPR directly beyond the gap limits the retrace to the near side of the CE (065; past it = downgrade, cancel adds). Conflict: A6 vs 062 vs 065 vs 075 vs cc04_009. Not built: the IFVG-as-breakaway measuring target (084) and the 075 close-into-it variant. Bot: `bk_depth`, `bk_state` (the machine gates trail_breakaway / ladder_trail "breakaway" and tags bk_<state>; a qualified gap that is LATER filled to its far edge / CE is dead again), `bk_bpr_ce`.
  - Caption-gap fix (A6-gap-hierarchy-common; 062 ~39:41/~43:58, cc04_010 ~12:25): for each swing away from an expected HTF level (2 MSSs, 062): breakaway = the gap that leaves the level and stays partly open (trail level); measuring = the gap near the middle that holds on the retrace (projection source); other FVGs = common (may be retested many times and act as S/R after being traded through; bodies at or beyond the edge with wicks piercing = respected). Partials, adds and trails reference breakaway / measuring gaps (062 ~44:40). Naming conflict: 062 "common" = an ordinary FVG, cc04_010 "common gap" = a BODY gap (bearish: open[i] < close[i-1] with no range closing the space; zone [open[i], close[i-1]]; expect bodies to close it) - tag separately. "Never trail behind a common gap" is an extrapolation, a switch. Bot: `gap_classes` (tags gap_<class>, cc_common), `trail_skip_common` (off).
- **A7 Immediate rebalance** (A7-immediate-rebalance-definition; 059 ~4:16, 060 ~7:29, 061 ~1:23:38, 078 ~1:15:05, 100 ~44:46, 099 ~1:04:01) [2023]; switch `ir_def`:
  - `a7` (first built): the next candle trades straight back to the prior candle's extreme with no gap; a strong continuation signature (048 ~39:02; 060 ~7:20; 092 ~1:41:14; 099 ~3:46). Daily version: the open trades exactly to the prior day's high / low (059 ~4:18).
  - `open_space` (the 059 family; "it doesn't mean it's the previous day immediately to the left"): candle i+1 (or i+2) trades down to the high of the most recent candle that bounds the open space (yesterday's if it overlaps, otherwise the older candle) - within a tick up to a ~1-2 tick overshoot (`ir_overshoot_ticks`), no body close through - then reverses in the bias direction. Stopping short = a breakaway gap (060). [our interpretation] the bounding candle = the most recent earlier candle whose high lies below every low since it.
  - `zero_width` (100): in a displacement leg take c1, c2, c3 with c2 a large bias-direction candle (body >= `ir_body_mult` = 1.5x the mean body of the last 20 bars [our interpretation]); it counts when high[c3] == low[c1] to the tick (bearish) or low[c3] == high[c1] (bullish).
  - Both modes: need a known draw in that direction (the bias); tag `fast delivery expected` (`ir_fast_<mode>`); the level is a PD array on that TF; with bias, enter or add with a tight stop beyond c3's extreme; first partial at the nearest opposing pool; exit on a retrace back through the range EQ (X8). Conflict: A7 (yesterday, exact, next candle) vs the 059 family vs 100. Bot: `ir_def` ("a7" default), `ir_overshoot_ticks`, `ir_body_mult`; `ir_entries` (M11a) enters at once.
  - Caption-gap fix (A7-immediate-rebalance-gates; 059 ~4:50, 060 ~7:29, 080 ~9:41: "the immediate rebalance isn't going to help you all that much"): an immediate rebalance is a continuation trigger only if (a) the draw / HTF bias was known beforehand and points its way and (b) it prints in a window where volatility is expected ([our interpretation] the macro window or an am / pm session); otherwise do not act on it (also M11). Bot: `ir_need_draw`, `ir_need_window` (both True; they gate only the opt-in IR paths `ir_entries` and `sb_rebalance_ext`, never the default engine).
- **A8 Inversion FVG (IFVG)** = an FVG that a candle closes beyond; it then acts in the opposite
  role (015 ~21:00; 061 ~19:42; 078 ~53:07; 102 ~1:02:03) [2023].
  - Valid only when a candle closes beyond, a NEW candle opens, trades back into it and it holds; a
    spike through and back does not count (048 ~21:32, ~36:40).
  - Allowed depth: one prior pass -> may reach the far edge; partly re-traded -> near edge to CE;
    traded both ways -> near edge, CE at most (102 ~1:09:00). Bearish IFVG retraces usually stop at
    CE or a little above (078 ~50:28).
  - Bias switch: the same 1m gap is a long target before the HTF array is hit and an IFVG short
    after it (086 ~14:12).
  - Caption-gap fix (A8-inversion-any-pd-array; 090 ~2:11:45, 068 ~13:37, 086 ~11:30, 035 ~1:02:55): any PD array (FVG, OB, breaker, VI, ORG, NWOG) whose body closes through it is inverted with the opposite role, stored as THREE prices only (high, low, MT / CE: OB per D4, breaker 50% of high-low). An OB closed below: expect resistance at its low and MT, shorts once displacement lower follows; a body close back through the MT invalidates the new role. Bot: `inversions` (empty; subset of ob / breaker / vi / org / nwog) = entry arrays (support role) and targets (resistance role).
  - Caption-gap fix (BH-A8-opposing-FVG-inversion-confirms; 015 ~26:19, 061 ~46:50 / ~2:33:50: "if a market closes above a fair value gap that you think should be bearish that's not a good shorting opportunity"): narrative gate - while the HTF draw is bullish and unmet, a close above a bearish FVG is not a short but a candidate IFVG; longs are confirmed only when price comes back into it, it holds as support (the validity test above) and rallies, followed by a normal entry pattern (e.g. breaker + FVG) toward the draw; without both the close-through and the hold there is no trade. The role switch after the draw is hit stays as above (086). Mirror. Bot: `ifvg_narrative` (off): "block" (an entry inside an FVG already closed through against the draw is rejected, `x_inverted_against_draw`) / "require" (block, and a with-draw entry also needs the bearish FVG formed today closed through, retested and held before its MSS, `x_ifvg_narrative`).
  - Caption-gap fix (A8-ifvg-narrative-liquidity-run; 078 ~51:00, 084 ~19:43, 073 ~12:56: "an inversion fair value gap is narrative based"): a bullish IFVG needs (a) the HTF bias bullish (a discount array reached), (b) an old low carrying sell-side taken inside or just beyond the bearish FVG (prefer the FVG whose range contains it) and (c) an MSS closing back above the FVG high; do not short the bearish FVG overhead once sell-side is taken and a bullish array held. Without (a) it is just an FVG in its original direction. Bot: `ifvg_need_run` (off; `x_ifvg_no_bias` / `x_ifvg_no_run`; pool within one gap height beyond the FVG [our interpretation]), `ifvg_over_pool_pref` (off).
  - Caption-gap fix (A8-ifvg-stacked-tails-exclusion; 090 ~21:24: "I like to see these things fail"): a bearish FVG closed through upward acts as IFVG support, but not if a cluster of long lower tails sits just below it - those tail lows are run first; the IFVG is valid only after that. Mirror. Bot: `ifvg_tails_block` (off), `tails_tol_ticks` (3; cluster = 2+ candles whose lower wicks (>= their body) end within the tolerance, lows within one gap height below the IFVG [our interpretation]).
  - Caption-gap fix (A8-ifvg-before-pool; 102 ~1:08:45: "because that sell side's still there"): a bearish IFVG (from a failed BISI) is armed only while the nearest swing low below has not been traded through; taken before the return = cancel (the draw is spent). Mirror. Bot: `ifvg_pool_intact` (off; the nearest swing extreme beyond the zone, known at the inversion).
  - Caption-gap fix (A8-ifvg-depth-tolerances; 102 ~1:11:04, ~1:55:46: "only be high probability if it stayed below consequent encroachment"): replace "near edge to CE" by three cases for a failed bullish FVG [L, H] (short side): (a) partly re-traded (a candle printed low W inside the gap) - after the close below L the retrace should stop at L, the CE or W (cap = min(CE, W)) with a small mohawk (2 ticks); the upper portion toward H = skip; (b) no prior re-trade: the retrace may go to H; (c) traded H -> past the CE and closed below: valid only while highs stay <= CE + 1 tick, stop just above the CE. Mirror. Bot: `ifvg_depth` False / True (the first build: far edge when untouched, else CE) / "w_cap" (cases a / b / c; `x_ifvg_depth` on a too deep retrace).
- **A9 Volume imbalance (VI)** = consecutive bodies do not overlap while wicks do; bullish:
  min(o,c)[i] > max(o,c)[i-1] and low[i] <= high[i-1] (003; 009 ~2:16; 022 ~54:26; 090 ~13:01)
  [2023]. Use its low as a stop; it may be touched but not pierced (009 ~13:46). It is dead once a
  later body on its own (or higher) TF closes fully across it (035 ~5:50; 090 ~13:01). VIs are
  "flexible", FVGs strict; clusters of VIs = "porous", low trust (027 ~22:09, ~27:38). Bot:
  `levels.volume_imbalances`, matches.
  - Caption-gap fix (A9-vi-definition-no-wick-condition; 009 ~7:18, 036 ~22:55, 027 ~22:24): the wick-overlap condition is removed - a VI is bodies only: bullish min(o,c)[i] > max(o,c)[i-1] across a run of candles, zone [max body of the earlier candle(s), min body of the later]; if the wicks do not overlap either it is also a liquidity void. Bot: `vi_wick_overlap` (True = the old rule), `vi_multi` (False).
  - Caption-gap fix (A9-vi-delivery-state; 035 ~21:01, 046 ~28:33, 050 ~33:20, 077 ~3:23): states on the parent TF (the highest TF on which the VI exists): reached (a later wick through to the far edge by a tick), target_hit (a later body overlaps), dead (a body lays over the whole zone: `vi_dead_rule` "full_span" 046 / 090, or any overlap 035). Until dead an open daily / weekly VI is a two-sided draw, revisited many times; wicks never change state. Bot: `vi_dead_rule`, `vi_two_sided_draw`.
  - Caption-gap fix (A9-daily-vi-forward-levels; 025 ~23:19, 007 ~3:40/~8:59): mark each daily VI on its own (both body edges + midpoint), never merge; extend through the rest of the week like NWOG edges; a VI above price that is reached becomes a support candidate on a later retrace from above, best with an hourly FVG (mirror for resistance); invalid on a 60m body close beyond its far edge [our interpretation]. The role follows the VI's own direction; a long's targets are only the resistance-role VIs, the support-role one is the entry array. Bot: `vi_flip_support` (targets, off), `vi_flip_entries` (entry array, off).
  - Caption-gap fix (A9-vi-breakaway; 079 ~14:20, 103 ~25:18): a VI on the candle(s) leaving a consolidation, right after an MSS, or inside a displacement leg beyond the current retrace limit, in the bias direction, is a breakaway VI: excluded from retrace targets and entry zones, bodies are expected not to close across it, the range it leaves is protected. A body close through it weakens the bias; a later full body across it = it was not breakaway. Context tests are [our interpretation] (cons_n = 6 flat bars; the leg's 50%). Bot: `vi_breakaway` (off; entry zones only).
- **A10 Liquidity void** = a true price gap (high[i-1] < low[i]) and, above all, session/week gaps
  with no prints (NWOG, NDOG, ORG) (001; 003; 028 ~36:17; 039 ~3:06; 074 ~20:51) [2023]. CC's
  "range of one-sided candles" (cc04_010; cc06_003) is treated as a displacement leg whose start is
  a fill target, not as a void [CC].
  - Caption-gap fix (new-single-candle-daily-inefficiency; 091 ~25:37): single-pass inefficiency = a large up-close candle whose range (low to high) no other candle has traded through (M15 uses it). Levels at 0 / 25 / 50 / 75 / 100%. Until price trades back down through it, flag "needs sell-side delivery": expect the CE, then the lower quadrant; fuller targets: LTF BISI lows inside it, the candle low is the extreme case. Mirror. [our interpretation] large = range >= 1.5x the mean of the prior 20; untouched = none of the 5 bars before it printed above its low. Bot: `single_pass_draw` (off; daily bars as typ "spr" arrays: a draw at the CE below / above price).
- **A11 Balanced price range (BPR)** = overlap of a bullish and a bearish FVG (046 ~50:02; 065B
  ~4:21; 104 ~24:35) [2023]. Trading TO it is easy, THROUGH it rare; expect probes; a body close
  through its midpoint = abort (026 ~1:05:53; 065B ~4:28; 100 ~22:07). Bot: `balanced_ranges`,
  unused.
  - Caption-gap fix (A11-bpr-one-pass-definition; 001 ~15:17, 003 ~29:37, 032 ~51:23, 056 ~7:24, 075 ~54:50): `bpr_def` "overlap" (Type 1, above) / "single_range" (Type 2) / "both". Type 2 = a gap Z (FVG, void, or two adjacent candles' overlap) that price crossed fully one way and then fully the other in one pass, then left; a touch is repricing, not balancing (032). Balanced once a later bar's range lies fully beyond Z on the far side [our interpretation]; a bullish BPR below price is support, a bearish one above is resistance; a long's stop may sit below its low; a body close below EQ or the low = idea wrong. Do not reuse a spent gap in its original direction. Continuation trigger (056): a retrace into a bullish FVG to at least its CE, then a trade above its high = permission toward the next buy-side draw; trail (003): stop to lo - 1 tick once a new bullish FVG forms above hi. Open SIBIs above are valid targets. Conflict: 010 counts a touched SIBI as balanced, 032 needs a trade-through; 101 rejects the term for a daily FX FVG (terminology only). Re-cite 046 ~50:02 as Type 2. Bot: `bpr_def`, `bpr2_two_candle`, `bpr2_trail`, `bpr2_cont_trigger` (the trigger is a tag).
  - Caption-gap fix (A11-balanced-range-body-filled; 098 ~34:57/~1:00:35, 099 ~11:14): midpoint naming: bodies cover the zone height (OB or a two-way range) = equilibrium (EQ); no bodies (FVG / VI / void / wick) = CE. A body-filled balanced range = several consecutive overlapping candles that traded both ways, then left by displacement; on a return price is REDELIVERED, not rebalanced: expect a slowdown at its edge / EQ and do not target its far side without fresh displacement. Keep the A11 BPR separate; tag this `balanced_range` with an EQ. [our interpretation] >= 3 candles, >= 50% overlap. Conflict: A11 FVG-overlap vs the body-filled range. Bot: `balanced_range` (off).

**Blocks**
  - Caption-gap fix (A11-bpr-levels-ce-rejection; 062 ~3:47, 082 ~3:55, 077 ~13:48: "hits it like a brick wall"): a BPR (also one built from a single-candle BISI + SIBI, `bpr_def`) has the levels high, CE, low, extended right indefinitely; bearish: sell at the CE on each revisit from below, stop above the high, valid while no body closes above the CE; once price has left, the far edge is the invalidation. Mirror. Bot: `entry_arrays` + "bpr_ce" (a limit at the CE on every revisit, once per retest; exit on a body close under the CE).
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
  - Caption-gap fix (A12-ob-candle-selection; 012 ~14:06, cc04_003 ~1:00, cc03_004 ~10:30, cc06_005 ~19:10, 065 ~1:21:02, 032 ~53:04): candle selection is a listed decision `ob_pick`: "blend" (a consecutive run blended; level = open of the first candle), "original" (the first / highest candle of the run, 012), "largest_body" (the lowest down candle at or through HTF support S, tie-break on the largest body), "blend_in_htf" (blend only when the whole run lies inside a pre-called HTF array; MT = (low first + high last) / 2). All modes skip a last candle whose body sits inside the previous same-colour body and is clearly smaller (`ob_skip_encapsulated`, cc06_005). Bot: entry OBs only (HTF-array OBs unchanged).
  - Caption-gap fix (A12-consolidation-ob-open-level; 008 ~4:09, one EUR/USD 1h example): on 1h, the last down-close candle before a consolidation range (bullish context): extend its OPEN right as support; pullbacks there are long areas; mirror = the open of the last up-close candle before the range. Bot: `cons_ob_open` (off).
  - Caption-gap fix (A12-mt-all-blocks-ce-all-gaps; 021 ~21:06): MT = 50% of the block applies to mitigation blocks too (A15 gains an MT per D4) and the "bodies must not close through MT" invalidation (E6 / X8) applies to them; CE is explicit for VIs and voids (A9 / A10). Bot: `mit_mt_invalid` (off).
  - Caption-gap fix (A12-open-vs-wick-gap-criterion; cc05_015 ~11:32, cc04_013 ~16:17): if the range between an OB candle's body and its wick extreme has been traded through at least twice ("closed in", no FVG remains) anchor on the body: level = the open, zone = the body, a small probe beyond the open allowed (~5 pips), invalidation = a trade beyond the body midpoint; if the wick area still holds an untraded gap use the wick extreme / gap; otherwise the stubby / long rule above. [our interpretation] the "twice" count = the candle itself plus one other bar overlapping the wick area (the displacement candle leaving it excluded). Bot: `ob_anchor_rule` "wick_len" (as built) / "gap_presence" (entry price of the pre-break OB and the anchor-open entry), `ob_anchor_passes`. Same switch as A5-twice-traded-not-fvg.
  - Caption-gap fix (A12-tf-relative-ob; 079 ~15:06): if the HTF swing-extreme candle has the "wrong" colour, look inside it on a lower TF: the last up-close LTF bar (bearish OB; mirror) at or before the bar holding the extreme, labelled at the HTF location (open, MT, high); it gains weight when it is also the high of an inefficiency (not built). Bot: `htf_ob_ltf_drill` (off; daily -> 1h in the bias table).
  - Caption-gap fix (A12-void-up-down-ob; cc02_007 ~13:33): on 4h and higher, a one-sided rally (void up: >= 3 up-close bars, no overlap) followed immediately by a one-sided drop (void down) through the same range = ONE bearish OB with MT = 50%; a later rally into it in daily premium is a short zone. Bullish mirror. The LTF refinement (the last up candles' body range and its 50% EQ, cc02_007 ~14:00-15:00) is not built. Bot: `void_rt_ob` (off; bias table and Confluence arrays of 4h and above).
  - Caption-gap fix (A12-entry-ob-outside-fvg; 065 ~4:04:05: "we have to use the out outside of the range"): after an MSS walk back from the displacement; an up-close candle breaks a run of down-close candles (a change in the state of delivery). Ignore the down-close candles inside the FVG / shaded zone; the entry OB is the last (lowest) down-close candle OUTSIDE the FVG - use its range for the entry, bodies should hold it - and the open where the up-close candle broke the run is the CISD reference [our interpretation]. Bearish = mirror. Bot: `ob_outside_fvg` (off): `levels.order_block_blend(outside=)` in `_ob_at_low`, the FVG-path OB and `mss_cisd`. Review fix: also in the OB-at-low reads of the DISPLACEMENT and FVG-choice setups (setups.ob_low).
  - Caption-gap fix (A12-range-internal-ignore; 064 ~56:17, 066 ~32:01: "all of these candles in between are all time distortion"): after an MSS plus the return to the OB defines a dealing range (064: post-OB candle high to the OB low; 066: sweep high to the post-displacement low) ignore all FVGs, OBs and structure made by candles strictly inside it, keep the setup armed through any number of retests (especially over lunch), valid while no body closes below the OB MT / the invalidation extreme; a trade beyond the far extreme = expansion toward the first draw. Bot: `range_lock` (off; the order rests with no `pending_minutes` expiry and is cancelled by a body close under the OB MT / the low; wicks inside the range arm nothing).
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
  - Caption-gap fix (A13-breaker-candle-selection; 015 ~21:17, 032 ~41:26, 043 ~18:03, 060 ~26:39, 063 ~3:49, 081 ~12:52): replace "by body" with the switch `breaker_candle`: "last" (015, 043) / "extreme_close" (032, 063, 081; bearish = the lowest close among the down-close candles at the swing low) / "extreme_body" (029 / 048 / 096; ties to the biggest body); never by largest body alone (032). The swing pattern must hold on bodies, wick-only extremes are discarded (060, 081: `breaker_body_swing`). Owner question: the spec lists "last" as the bot default; the built behaviour (extreme close) stays the default. A weekly breaker: find the candle on the daily (063).
  - Caption-gap fix (A13-breaker-zone-extent / D6; 025 ~12:13, 032, 042 ~46:29/~58:37, 044 ~37:47, 070 ~46:45, 072, 078, 084): the swing is the outer H1-L-H2 (ignore minor highs inside); zone options body / range / `blend` (the union of the consecutive candles at the swing, 025 / 044 / 042) / `leg_disruptor` (070: from the opposite candle that disrupts the A->B run to B; the whole-leg reading is dropped from 042). A 1-tick overshoot of the zone high still counts (042 ~58:37). Bot: `breaker_zone` gains "blend" and "leg_disruptor".
  - Caption-gap fix (new-time-distortion; 060 ~24:12, 100 ~42:21, 075 ~1:40:05: "it's being held for a news event ... being held for a session close"): time distortion generalises beyond the 10:00-12:00 FVG hold: no swing / MSS / breaker / FVG signal and no direction is read (a) while bodies stay inside an FVG for several bars (5+) during 10:00-12:00 with only wicks poking out (the FVG stays valid; expect continuation toward the original draw), (b) in sub-5m consolidation in the 15 minutes before a scheduled high-impact release, (c) on bars after 16:00, (d) in the chop between the lunch macro and 14:00 (12:10-14:00). Liquidity seeking resumes in market hours / macros. Bot: `time_distortion`, `td_lunch`, `td_fvg_hold` (off, on, off): `levels.time_distortion_mask` filters the MSS reference swing, the break bar and the entry FVGs; the FVG-hold applies to the single-bar-FVG wick rule. Review fix: with `time_distortion` every Side drops the swing points and zones (FVGs, inverted FVGs, VIs, mitigation / propulsion sources, breakers, HTF-bar zones) defined on a masked bar, so pools, relative equals, MSS references, entry zones and the Silver Bullet arrays never read them; a pool run in a masked bar starts no sweep and an order-block candle of a masked bar is no OB; `td_fvg_hold` works for any gap (needs the session extreme to be set before the gap) and tags td_hold.
  - Caption-gap fix (A13-breaker-needs-rebalance-and-fvg; cc04_005 ~4:31 / ~6:42, 001 ~45:39 / ~56:19): a bullish breaker is confirmed only when the break above H is a fast repricing / range expansion right after the sell-stop run ("repricing lower after buy stops are taken that is a confirmation"). "Leaving" is measured as a close above the BODY high of the breaker candle; price should not trade back into the rebalanced range. Bearish mirror. Bot: `breaker_needs_disp` (off; the break leg leaves an FVG within `breaker_disp_bars` = 3 bars of the break [our interpretation of the speed window]), `breaker_break_ref` "wick" (as built) / "body_high"; a CLOSE back through the displacement FVG undoes the repricing ("price should not trade back into the rebalanced range", [our interpretation]: a full return, not the retest of the breaker inside the gap's span).
  - Caption-gap fix (A13-breaker-close-vs-wick; 035 ~42:44: "you won't need to think about coming back up into here"): after high-low-higher-high, if a candle BODY closes below the swing low, mark the bearish breaker - the retrace stops at the breaker, no need to wait for the higher imbalance; if the low is only wicked through it is an MSS without a breaker and the FVG / imbalance above is the entry. Bullish mirror. Bot: `breaker_by_close` (off; the breaking bar itself is judged, a later close does not turn a wick break into a breaker; the breaker is taken first).
  - Caption-gap fix (A13-breaker-lifetime; 043 ~4:43 / ~16:07, 015 ~22:43: "extended it throughout the day to the last hour"): replace "first touch is valid" with a day lifetime: a breaker zone is extended to at least the 16:00 close and stays eligible for repeat retests that day, the PM last hour included; a later stop hunt that forms a newer low-high-low on top of it does not replace the original; entries may accumulate inside it without waiting for a break and retest; invalidation per the breaker MT rule. Bot: `breaker_day_life` (off; a remembered, alive breaker that price retested and left again arms a resting limit at its top once per retest), `breaker_keep_original` (off), `breaker_accumulate` (off; one order may accumulate inside an alive breaker - a limit at its CE while a close sits in the zone - without a break and retest [our interpretation]).
- **A14 Unicorn** = an FVG overlapping the breaker zone; strongest right after a sell-side run at the
  09:30 open (007 ~22:39; 101 ~84:31) [2023]. 104 uses the word for a 2nd-stage redistribution OB;
  ignore that usage. Bot: implemented, preferred FVG.
- **A15 Mitigation block** = the breaker's failure-swing twin: high A, swing low, LOWER high B (no
  stop run above A), break below the swing low; the zone is the last down-close candle in that
  swing low (cc04_004 ~2:42-14:35) [CC]; bullish mirror (033 ~1:03:50) [2023]. Weaker than a
  breaker; ICT uses it more as a target (075 ~21:40). Bot: tag only (P2).
  - Caption-gap fix (A15-stoprun-variant; cc03_002 ~19:11; conflict cc04_004): two definitions. cc04_004 (above): a failure swing, no stop run, the last down-close candle. cc03_002 (bullish): U = the last up-close candle before a down leg that runs a prior low's sell stops; price later trades back above U; zone = U's high down to U's body top (the upper wick; optionally the body); buy the first return, expect explosive expansion; bearish mirror. [our interpretation] "trades back above" = a close above U's high; stop below U's body. Bot: `mit_def` "a15" (default) / "stoprun".
  - Caption-gap fix (M4-failure-swing-no-new-extreme; cc05_005 ~19:40): the failure swing (also M4) is bearish: H1 reaches, touches or trades through key resistance K; price drops to swing low L; it retraces to H2 < H1 (no new higher high); trade the break below L or its retest. K's position relative to H1 / H2 is irrelevant (drop "fails to reach the level"). It is the fallback when the preferred breaker (a run above H1) does not happen. Bullish mirror. Bot: `fs_def` "m4" (as built: B fails to reach K) / "no_new_extreme".
  - Caption-gap fix (A15-mitigation-block-entry; 033 ~1:04:05, 041, cc04_004 ~4:37 / ~5:01 / ~13:51, cc06_005 ~12:22 vs 075 ~22:10): CONFLICT - 033 / 041 / cc04_004 / cc06_005 trade a mitigation block as an ENTRY, 075 treats it as a target only (it can be traded through; a weekly one acts as a draw). Switch `mitigation_entry`. Entry use requires order flow and narrative in the trade direction, ideally stacked with other arrays (FVG low, OB open; 033), and ranks below breakers. Bearish (cc04_004): after the break below the swing low (no expiry) the zone is the full range of the last down-close candle at that low; sell anywhere in it, stop above the candle's high. Bullish mirror (033): low, high, higher low; target the nearby buy side (~5 handles). Bot: `mitigation_entry` (off; a resting limit in the day's alive block once per retest), `mit_entry_px` "near" / "mid". `mit_preopen` (off; the 041 up-close candles of the 09:00-09:30 consolidation, range <= 0.25 x ADR5, as one more bullish block [our interpretation], tag `mit_preopen`). NOT built: the cc06_005 4h block in premium (the day holds three 4h bars and the 4h arrays carry no mitigation source).
  - Caption-gap fix (X3-a15-mitblock-bear-context; cc04_004 ~6:44: "there's an unrealized lower support level for sell side liquidity that has not been tapped"): take a bearish mitigation block only when the longer-term (HTF) expectation is lower and untapped sell-side liquidity (a lower HTF support level) remains below; target that level. Mirror for bullish. Bot: `mit_needs_bias` (off; the bias must be the block's way and an untaken daily pool / daily array lies beyond; its level is the target).
- **A16 Propulsion block** = a down-close candle that trades into an earlier bullish OB and becomes
  the new support; on return price should tag its high and leave; losing its MT = idea wrong
  (cc04_008 ~0:30-5:40; 027 ~11:31; 079 ~10:27) [both].
  - Caption-gap fix (A16-propulsion-context-sequence; cc04_008 ~3:58, cc09_008 ~14:45): `pb_def`: "cc04_008" = bullish context, a bullish OB, confirmed when a later candle trades above its highest high, price moves higher, then a later down-close candle trades back into the OB and is the PB at its close; "cc09_008" (looser) = a down-close candle adjacent to the prior OB followed by a higher high, level = its open, valid once a later candle trades above its high. Prefer the separated case [our interpretation]. Bot: `pb_def` ("a16" = as built).
- **A17 Rejection block** = a swing high of long-upper-wick candles; zone = highest open/close of the
  swing up to the highest wick, any candle colour (cc04_006 ~5:04-10:43) [CC]. 2023 uses only the
  body edge as a level: price running the bodies does the same work as running the wicks (015
  ~2:15; 059 ~10:03; 066 ~40:41). Bot: `rejection_blocks`, unused.
  - Caption-gap fix (A17-rejection-block-levels; 015 ~2:18, 038 ~4:15, 059 ~10:11, 080 ~5:41, 090 ~34:21, cc04_006): bearish RB (a target when bullish) from the swing-high candles on the trading TF: level1 = max close of the up-close candles (`rb_level` "close", 2023) or max(open, close) of any candle ("open_close", cc04_006); W = the highest high; level2 = wick CE = (level1 + W) / 2; valid only if wicks extend beyond the body; targets in order level1, level2, W; as an entry price may trade a little through level1, level2 should hold, stop beyond W [our interpretation]. Bullish mirror. Bot: `rb_level`, `rb_ce_level` (adds level2 and W to the rung ladder).
  - Caption-gap fix (A17-rejection-block-short-protocol; 035 ~23:08): bearish RB short - (1) the level is the CLOSE of the candle that made an old (daily) swing high; (2) price trades to and through it (high > level); (3) a 1m / 5m short-term swing low (3-candle pivot) is traded through by a WICK - no close beyond it is required; (4) a bearish FVG forms above the pierced low inside the down leg; (5) enter at the FVG per M2 (limit at the near edge, stop above the FVG / OB MT, target sell-side). If the HTF bias opposes the trade, do not take it - the level is then only a partial-profit target for trades in the bias direction. Bullish = mirror. Bot: `rb_pools` (off): the untaken daily RB closes are sweep pools (`rb<n>`), the MSS after their sweep uses a wick pierce, against the bias they are `_targets` rungs only. Review fix: the closes are the typ "rb" arrays of `htf._arrays(rb=True)` (levels.rejection_blocks, `rb_level` "close"); `htf.table(rb_closes=True)` lists the nearest untaken ones as rb_up / rb_dn without touching the bias columns, and `ld4.rb_build` reads the same arrays.
  - Caption-gap fix (A17-index-or-rejection-block; cc10_010 ~9:03: "the lowest close down close candle"): opening-range variant - bullish: among the down-close candles inside the 09:30-10:30 range the one with the lowest close; level = its close, zone down to the OR60 low; on a later-morning return go long if the bar's low holds above the OR60 low, invalid below. Bearish (NQ example): the LAST up-close candle inside the range (just below a pre-OR bearish OB); level = its close; invalid above the OR60 high. Conflicts with the long-wick swing definition above. Bot: `or_rb` (off), `or_rb_from` (630), `or_rb_bear` ("last" / "highest_close" [our interpretation]); before 12:00.
- **A18 Reclaimed OB** = in a market maker model, each down candle on the sell side of the curve
  followed by a bounce; do not buy them on the way down; buy their retests on the buy side of the
  curve after the low (cc04_007 ~0:50-5:00; 104 ~46:56) [both]. Codeable with a confirmation lag (needs
  the curve low; see the caption-gap fix below).

**Structure**
  - Caption-gap fix (A18-reclaimed-ob-codeable; 006 ~49:57 / ~55:24, cc04_007 ~4:07 / ~5:05 / ~8:38): A18 IS codeable with a confirmation lag (drop "not codeable"). Switch `reclaimed_def`: "loose" (006 / Ep 02: an OB that price leaves, re-trades and leaves again; the next return is an ordinary A12 retest entry) / "strict" (cc04_007: while price falls to HTF support record each down-close candle followed by a short-term bounce; once price reaches HTF support and breaks the latest short-term high (MSS), fix the curve low and buy retraces into each recorded block above it). Stop below the curve low or the block MT (ours); one entry per block on its first retrace [our interpretation]; bearish mirror. Bot: `reclaimed_def` ("strict" default), tag `reclaimed_strict` / `reclaimed_loose` (`levels.reclaimed_obs_loose`).
  - Caption-gap fix (A18-traded-through-ok; cc04_007 ~9:45: "it trades through it but we see a climax high"): reclaimed-OB candidates on the buy (sell) side of the curve stay valid even when price trades or closes through them before the curve extreme - the A12 MT invalidation does not apply to them; they become entry levels only after the extreme forms. Bot: already so (`levels.reclaimed_obs` reads no close before the extreme; test added).
- **A19 Market structure shift (MSS)** = after a sweep, price breaks the swing high (low) that led
  into the sweep extreme, with displacement leaving an FVG (002 ~2:37; 006 ~16:59; 022 ~38:38)
  [2023].
  - Which swing: the one that led to the high that ran liquidity, the parent swing, not a minor
    one (010 ~41:31-46:19; 058 ~41:15). A single short-term break is "aggressive"; with relative
    equal lows, wait for the lower one (044 ~42:55). Bot: the swing high before the sweep extreme.
  - Wick or close: D3. Bot: body close (`c[i] > ref`).
  - Two MSSs, each leaving an open FVG = "on side" (006 ~49:16).
  - Do not trust a shift until the relevant liquidity run has happened (Ep 08).
  - Caption-gap fix (A19-break-against-htf-stop-run; 102 ~39:11, cc09_004 ~9:01, cc02_008 ~0:58, 020 ~0:28 / ~7:36: "it's not a breaker it's just a speed bump"): count an intraday MSS or breaker only when it agrees with the HTF (daily / 4h) order flow and draw. A break of a short-term low while HTF flow is bullish is a sell-stop run: arm longs. A bearish-breaker shape below an untaken upside draw is a speed bump - do not short it. False breakouts of a consolidation come against the primary trend (M12: in bearish markets fade breaks above the range, in bullish markets fade breaks below). The A19 FVG requirement stays. Bot: `mss_requires_htf_agreement` (off; the bias column is the HTF flow, a neutral bias counts [our interpretation]), `stoprun_rearm` (off; the counter-HTF break arms the OPPOSITE side's sweep of the stops it ran). In the main loop the side against the bias is never scanned, so `sm2.against_bias_break` looks for that break there: the first close beyond the newest confirmed swing of the against-bias Side while the bias flows the other way.
  - Caption-gap fix (A19-mss-when-raid-missing; 010 ~41:31: "I wanted this one to break down more specifically"): define the expected raid level R before the session (010: the prior day's high). R taken: the MSS reference is the short-term swing that started the leg into the raid; a displacement body close beyond it = MSS. R NOT taken: a break of a short-term swing inside the range is not an MSS, even with an FVG; the reference is the swing that launched the leg making the session extreme and only a displacement break of it counts. Mirror. Bot: `mss_ref_raid` (off), `raid_level` ("pdh": the prior day's low for a long / high for a short, [our interpretation]); `Ep08.4 leg_origin` is the swing; `x_raid_not_taken_no_disp`.
  - Caption-gap fix (A19-mss-no-rel-sweep-with-htf-draw; 019 ~8:34 / ~9:25, 044 ~42:55: "why didn't it go below that it doesn't need to"): with no pre-set HTF draw prefer waiting for the lower REL to be run (044; the short-term-high break is allowed but "aggressive"); with a pre-session draw in direction D (019: NWOG above) an MSS needs only a short-term swing low taken plus a displacement break of the short-term high that leaves an FVG - the REL need not be swept. Bot: `mss_eq_wait_unless_draw` (off; waives `mss_eq_wait` when the session draw is locked in the trade's direction).
  - Caption-gap fix (A19-reh-short-term-low-trap; 029 ~48:29: "what do they see that as a market structure shift"): long bias, the HTF objective above not yet reached, the last two swing highs relatively equal: a break of the short-term low under them is NOT a bearish MSS - it is bait that builds buy-side above the REH. Targets REH then the HTF objective; entry long on the retrace into the nearest bullish FVG below (a retrace that fails to reach the CE = strength / IOFED); invalidate on a body close under that FVG's low [our interpretation]. Mirror. Bot: `reh_trap` (off; the against-bias order is rejected `x_reh_trap`).
  - Caption-gap fix (A19-second-mss-no-new-low; 069 ~14:41: "it didn't need to for me to enter"): after a valid bearish MSS, if the retrace makes a LOWER high (the pre-MSS high is not pierced) a later displacement down that leaves FVG(s) is a valid entry leg even without breaking the latest low; stop just above the CE of the higher FVG when there are two (or above the lower high). Mirror. Bot: `mss_rearm_lower_high` (off; the swept side stays armed while the sweep extreme holds, a newer displacement FVG re-arms; stop mode `ce2` is the two-FVG stop).
  - Caption-gap fix (N-micro-structure-regime; 024 ~10:08: "when the market is moving when it's dynamic"; cross-reference N8 / N9): inside a small intraday consolidation (a narrow range since 09:30, >= 2 alternating short-term runs, no displacement) reject 1m / sub-1m MSS signals - read the structure on a higher timeframe (5m; [our interpretation] of "zoom out") and wait for the next window; accept 1m triggers only when the preceding leg is displacement. Bot: `micro_regime` (off; range < `micro_range_adr` = 0.25 x ADR5 [our interpretation]; then the MSS reference is the 5m swing, i.e. `mss_ref_tf` 5).
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
  - Caption-gap fix (A21-dealing-range-energetic-swing; 028 ~1:07:33, 044 ~40:26, cc01_005, cc04_002 ~18:44): the low is the most recent 3-candle swing low followed by displacement (consecutive same-direction candles leaving >= 1 FVG within N bars); if two are close take the one with more bars clustered around it; skip older rounded lows and pivots inside a consolidation (anchor where the impulse departs; an inner swing low of a tight chop is skipped); impulsive leg = >= 60% of bars in direction and / or a displacement FVG and / or >= 1x ATR(14) [our thresholds]; range = that low to the leg high (wicks), EQ 50%; sub-ranges do not override it; MSS reference stays per A19. Bot: `leg_anchor` = "mss_leg" (default) / "energetic" (leg_pd, leg depth, the OTE band).
  - Caption-gap fix (A21-consolidation-range-def; cc01_001 ~11:50/~17:54): a consolidation range is defined by BODIES: high = max body, low = min body over the range candles; EQ = the midpoint; it needs a clear high and low. ICT's check yourself: the EQ is touched or crossed from both sides several times while price stays in the range ([our interpretation] >= 2 touches each side). Impulse legs keep the wick rule above. Bot: `consol_body_range` (False: opt-in, so the N8 `consol_pools` range keeps the wick range of the chop test until the delivery-state package exists), `consol_eq_touches` (2); the B21 daily consolidations always use the body box.
  - Caption-gap fix (A21-pre-trigger-dealing-range; 048 ~1:20:40: "I don't care how much time it spends inside"): range high = the latest 3-candle swing high before the retrace, range low = the low of the bar that tapped the bullish breaker; while inside no action, however long it chops - time does not invalidate; invalid if price trades deeper than the breaker; trigger = an up-close body above the bearish FVG in the upper half that also takes out the internal highs (the MSS), then the first bullish FVG / immediate rebalance on 1m, preferably 10:00-11:00. Bot: `breaker_range_hold` (off; a breaker order rests with no expiry and is cancelled by a trade under the breaker low; the range construction itself is the ordinary breaker + MSS flow).
- **A22 PD-array matrix**, outward from EQ: mitigation block, breaker, liquidity void, FVG, OB,
  rejection block, old high/low; discount mirror (cc05_014 ~18:20-29:36; cc07_004 ~1:01) [CC].
  Price meets them nearest first; a breaker in the path usually stops price before the arrays
  beyond it (cc05_014 ~21:04; cc09_008 ~9:59). Skip exhausted arrays, prefer untested (cc07_004
  ~4:00).
  - Caption-gap fix (A22-htf-definition-nested-arrays; cc10_013 ~8:17 / ~13:44, cc10_014 ~11:08: "nested ideas of premium array would be our catalyst"): a NESTED array = a 15 / 60m PD array overlapping a 4h or daily array of the same polarity. PM reversal: if the AM move stopped at a nested (HTF) array expect the PM to fade it; if at an un-nested 15 / 60m array expect continuation. HTF set per filter: reversal {4h, D, W+}; consolidation profiles {1h, 4h+}. Bot: `pm_rev_nested` (off; any price overlap [our interpretation]; blocks `pm_reversal` without the nested array and without a Confluence object).
- **A23 Wick CE** = 50% from body edge to wick tip; a wick is a gap (012 ~4:14; 021 ~21:06; 028
  ~16:43) [2023]. A long wick in the bias direction often stops dead at its CE; a next-candle close
  beyond the CE = continuation, close back = revisit (025 ~25:37; 100 ~38:13). Bot:
  `wick_midpoints`; `wick_levels` (on) for the prior day, `wick_days` / `wick_weekly` /
  `wick_both` / `wick_session` switches (levels_detectors).
  - Caption-gap fix (A23-wick-quarter-strength; 025 ~34:43, 028 ~15:24-16:43, 103 ~24:07/~27:23, 065 ~4:19:02, 075 ~1:05:07, 072 ~5:27): re-cite 028 (not 025) for the CE stop. Quarters / gradients: q25 (25% from the body edge), CE, q75. A retrace into an upper wick used as resistance: turns at q25 = very bearish; at CE = normal; overshoots CE but stays <= q75 = still valid (103); trades through q75 or a body closes above CE = failed [our tiers]. Heavy bearish stance: q25 is the reaction / entry level (025 / 028). Bias line (065 / 075, lower wick 1h+): bullish intact while no body closes at or below CE; a body close at or below it = stop adding (judged only once that 1h candle has closed). Judas cap (072): (high + max(open, close)) / 2, bearish intact while rallies fail to close above it. Wick entries only at CE or a quarter. Bot: `wick_quarters` (tier tag), `wick_bias_line` (no adds), `judas_wick_cap` (tag).
- **A24 Not codeable as stated:** (the implied FVG is defined in A5 now, low confidence); the Reaper is
  codeable now (see the caption-gap fix below); "inducement" (not an ICT term in the notes; the bot's sweep step is the closest
  codeable form).
  - Caption-gap fix (A24-reaper-definition; 076 ~21:44 / ~22:10, 081 ~11:49): the Reaper IS codeable - two definitions. Option A (076, bullish): breaker L1 < H, then L2 < L1, then a break above H; the Reaper = a bullish FVG in the discount half of the L1 -> H leg that was traded through on the way to L2 (bodies respect its CE; enter on the confirming candle or a limit inside; target the draw); the "retail pattern broken down before the touch" gate is not coded. Option B (081, bearish): a high-low-higher-high breaker whose zone (biggest-body, lowest-close down candle) coincides with a bearish OB; short the return. Mirror both. Bot: `reaper` + `reaper_def` "fvg" (A) / "ob_overlap" (B: a limit at the breaker top when the breaker zone overlaps `_ob_at_low`, tag `reaper_ob`).
- **A25 Converged PD arrays** (confluence-stacked-arrays; 100 ~6:05, 103 ~4:38/~25:04, 011 ~7:19) [2023]: a PD-array level is "converged" when an OB also contains an FVG and / or a VI (100), or a wick's CE lies inside an FVG, especially near its CE [our interpretation: within 2 ticks] (103, 011). Rank converged levels above single arrays for entries, partials and targets; a counter-trend retrace may spike to a converged level but should stop there (103). Bot: `converge_rank` (off) picks the entry gap with the most converging arrays and tags `converged_N` (entries only).

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
  - Caption-gap fix (X3-b5-15m-pools-5m-gaps; cc05_003 ~1:27:21 [CC]): the daily chart is where institutional orders are read; liquidity pools are mapped on the 15m; use the 5m only for small FVGs not visible on the 15m or 1h; never map pools from the 1m. Bot: `pool_tf` (minutes; 1 = the base bars; 15 = the 15m pivots, mapped to their base-bar extreme).
  - Caption-gap fix (B5-htf-arrays-anchor-transpose; 043 ~3:13, 072 ~1:45, 074 ~7:00, 080 ~11:28, cc04_012 ~0:37/~5:25): detect FVGs, VIs, IFVGs, OBs, breakers, rejection blocks and wicks on each HTF (W, D, 4h, 1h, 15m) from that TF's own bars; store edges, CE and quarters and project them unchanged onto the LTF chart as fixed zones - no LTF 3-candle gap needed; on the LTF look only for the trigger and refinement (LTF body gaps inside it, or an LTF rebalance); weekly -> daily likewise. The HTF level governs stop / invalidation when arrays overlap [our interpretation]. Conflict: A10 (void) vs cc04_012. Bot: `htf_entry_arrays` (minutes, e.g. (15, 60); FVGs and OBs).
  - Caption-gap fix (B5-mature-trend-continuation; cc02_007 ~1:56: "price will print a false bull flag"): a flag (sharp leg, then a small consolidation) can be false - a reversal - when the trend is mature or price is at an HTF premium / distribution array (bull flag), or an HTF discount / accumulation array (bear flag). Do not take a continuation entry there. Bot: `mature_flag_block` (off; proxy [our interpretation]: the order goes with the prior 5-day trend AND the prior daily close is beyond `mature_pd` = 0.62 of the 20-day range, or inside an opposing daily array).
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
  - Caption-gap fix (X3-b10-topdown-transposition; cc06_003 ~20:01): swing top-down: check the 9-18 month monthly / weekly profile for trend or range (an aggressive exit from a range = displacement); list the active monthly arrays and transpose them to the weekly, the weekly ones to the daily, then to the 4h; buy 4h discount arrays (turtle soup below old lows or rejection-block bodies) and scale out at the transposed daily, weekly and monthly premium arrays; bearish mirror. Bot: `topdown_targets` (off) puts the 4h / D / W / M opposing arrays (conf rows, each with its `tf`) into the target ladder.
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
  - Caption-gap fix (BH-B12-midnight-open-tolerance; 006 ~25:38, 010 ~38:48 / ~47:02: "as it goes back close to that opening price you can be a buyer there too if there's logic behind it", 048 ~1:00:57): beyond the open = best. Within ~2-3 points on the wrong side is ALLOWED when the open was already traded through in the Judas direction, the entry is at an OB / FVG and an MSS has formed since that move ("preferably"). Tag best vs allowed; strict mode keeps best only. The same for the 13:30 open in the PM. Bot: `open_tol_pts` (0 = strict, as built; test 2.0 / 3.0; `Trade.open_grade`).
  - Caption-gap fix (BH-B12-po3-sequence; 006 ~6:33: "you would ideally want to see a move above it and then go back below it"): the preferred bearish order - (1) after 00:00 price trades above the midnight open, (2) trades back below it, (3) an MSS + FVG / OB sell setup forms at or above the open or at a PD array just below it; bullish mirror; the 13:30 open works the same way for the PM. Bot: `po3_seq` "tag" / "filter" (off; `Trade.po3_seq`), `po3_seq_below_pts` = 3 ("just below it" [our interpretation]).
  - Caption-gap fix (B12-judas-depth-adr; cc08_003 ~12:59, FX translated by the ADR ratio): on a bullish day the ideal Judas drop below the open is ~0.2-0.3 x ADR, at most ~0.33; beyond ~0.4 x ADR is lower probability ("doesn't mean it can't"). A tag to test on index data, not a filter. Bot: `judas_depth_tag` (off; `Trade.judas_depth` at every fill with an open - the depth of the session's lowest low after the open bar up to the MSS, or the sweep extreme when lower) and `judas_max_adr` (0 = off; test 0.4; the gate).
  - Caption-gap fix (BH-B12-gap-up-short-below-0930; 044 ~34:06: "do we get below that I'm not interested in chasing this higher"): gap up into an HTF premium array (e.g. an old NWOG CE), ideally with index SMT divergence: arm shorts only after price trades below the 09:30 open; no longs; targets follow L7's ORG ladder. Mirror for gap-downs into discount. Bot: `gap_premium_arm` (off; the HTF array comes from the Confluence object, the SMT state of the sweep is tagged `gap_premium_smt` / `gap_premium_nosmt`).
- **B13 Weekly open.** Sunday 18:00 open and/or Monday 00:00 open. Bullish week: best longs below it
  early in the week, then buy each day while above it; bearish mirror; valid until an opposing
  daily PD array is hit (048 ~1:00:10; cc08_001 ~22:58-29:03; cc12_003 ~19:03) [both]. {needs:
  Sunday 18:00 = futures data; Monday 00:00 is in the CFD data}
  Bot (bias_htf): `weekly_open` sun18 / mon00 / either (the week's direction side: longs below the open Mon-Tue, above it from Wednesday; expired at an opposing daily array).
  - Caption-gap fix (BH-B12-midnight-open-tolerance; 048 ~1:00:57: "are better entered if you're bullish below the opening price on Sunday"): the Sunday-open rule is a PREFERENCE for position trades (> 2 weeks): longs below the week's Sunday 18:00 open, shorts above it - a tag, not a hard filter. Bot: `wk_open_side` (off; `Trade.wk_open_side` = sign(entry - the Sunday open)).
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
  - Caption-gap fix (B18-smt-only-with-bias; 099 ~56:49, cc04_001 ~13:14, cc10_011 ~11:35, cc10_002 ~7:14): remove "bias" from the uses. Order of operations: bias first (daily IOF, then the 4h / 1h PD array in the bias direction), then look for SMT only on the matching side (compare lows when bullish, highs when bearish) in 05:00-09:30; a divergence against the bias is not a signal - tag the non-confirming index a LAGGARD expected to catch up; for commodities / FX read the DXY's own HTF expectation first; with no clear daily IOF do not trade the SMT (B17). Bot: `smt_with_bias` (off; against the bias the SMT does not qualify, tag `smt_laggard`; with no bias an SMT-qualified order is rejected).
  - Caption-gap fix (B18-am-smt-window-points; cc10_011 ~12:50 "don't think like they're goal posts", 086 ~5:42): AM window - compare ANY relative highs / lows inside 05:00-09:30; the points need not sit on the boundaries; the 08:30 / 09:30 opens can be one point. One example (086) used a 02:00 low vs an ~11:00 low at a bullish breaker: test an extended 02:00-11:00 window as an option, not the default. Bot: `smt_win_a` / `smt_win_b` (300 / 570; test 120 / 660), `smt_open_points` (off; pools `open_0830` / `open_0930`), `smt_ref_window` (off; the COMPARED extremes - the swept level's own low / high and the partner's twin - must have printed inside [`smt_win_a`, `smt_win_b`], inclusive, so a 02:00 low vs an 11:00 low counts only with 120 / 660; acts without `smt_windows`).
  - Caption-gap fix (B18-pm-smt-reference-points; cc10_014 ~2:18: "the low that forms immediately after one o'clock"): PM reference points (bullish) - each index's lunch-hour low (12:00-13:00) vs the low formed right after 13:00; a failure to make the lower low in any index qualifies the PM long in ES. Bearish = highs (our inference). Bot: `smt_pm_points` (off; the first pivot low, n = 1, after 13:00).
  - Caption-gap fix (B18-smt-accum-distrib; cc03_005 ~10:20: "otherwise it would have been permitted to go lower"): before treating a break of an old high (low) as strength check the correlated asset over the same window; if it fails to confirm, label the breakout false (an M12 turtle-soup candidate): the breaking asset = distribution, the refusing asset = accumulation. Index trio: apply directly. Bot: `ts_need_smt` (off; a turtle-soup setup needs the SMT of the sweep).
  - Caption-gap fix (B18-smt-three-point-swing; cc11_004 ~27:39: "you can sometimes have to trade through a short-term low"): alternate SMT on 3-point swings: X prints low - lower low - higher low while the others print low - lower low - lower low = bullish SMT; the window may need to extend past a short-term low that all traded through. Mirror; the index application is an adaptation. Bot: `smt_mode` "pair" (as built) / "three_point" (`sm2.three_point_smt`; the first point may be an earlier swing than the one next to the lower low [our interpretation]).
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
  - Caption-gap fix (X3-b21-ipda-anchor; cc05_001 ~53:44/~23:23/~26:56, cc05_003 ~19:10): decision `ipda_anchor`: "rolling" (from yesterday, default; cc09_008, cc05_003 ~1:20:41), "month" (the first trading day of the most recent closed calendar month, cc05_001), "swing" (the last daily MSS within 60 days) - also a quarterly shift; LB20/40/60 count trading days LEFT of the anchor and record their extremes, gaps and arrays; 20/40/60 days to the right time the next shift.
  - Caption-gap fix (B21-ipda-windows-arrays; cc05_001 ~22:58, cc07_005 ~14:17, cc09_008 ~8:47): windows count trading days, skipping Sunday sessions; yesterday = day 1; they roll forward daily; 60 days is the primary look-back; collect PD arrays (OBs, FVGs, voids, breakers, rejection blocks, old highs / lows) inside Range60 tagged by window; day trading works in Range20 and goes to 40 (then 60) only when every 20-day array has been traded through. Bot: `ipda_arrays_first20` (off).
  - Caption-gap fix (B21-data-range-fv-eq; cc05_003 ~1:18:00): for each window (20 / 40 / 60 trading days): liquidity = the window high / low; fair value = the gaps (FVGs / voids) formed inside the window; equilibrium = 50% of each CONSOLIDATION inside the window, not of the whole window. Range ("Z") day: price hangs around one of these consolidation EQs with no driver (for an index: no CPI / NFP / FOMC [our interpretation]) - expect sideways until high-impact news, no expansion trades. Bot: `ipda_fv` (the open daily gaps' near edge and CE are array targets), `ipda_consol_eq` (the EQs are targets and `ipda_eq_day` tests against them); consolidations are daily runs of >= 5 bars (bodies <= 1.5x the mean range, EQ touched from both sides) [our interpretation].
  - Caption-gap fix (B21-reference-points-in-windows; cc05_001 ~24:28): for each LB20 / 40 / 60 note the range high / low as stop pools; if the extreme candles have long wicks (wick > body [our interpretation]) use the rejection block at the body edge (A17) instead of the wick extreme (the wick extreme stays a runner rung); also list the daily OBs, FVGs and voids inside the windows as reference points / targets; frame off the window low when the market has been trading higher and off the window high when lower. Bot: `ipda_rb`, `ipda_arrays` (off). Review fix: `ipda_arrays` limits EVERY merge of the arrays (main scan, Silver Bullet, entries.py, targets.htf_levels) through `Confluence.windowed` and the daily arrays / swings of `htf.table(ipda_window=<anchor>)` to those formed inside the 60-session window ending at the anchor; `ipda_window_arrays` (off) adds the daily OBs and liquidity voids of the window beside `ipda_fv`'s FVGs; `ipda_frame` (off) frames the window range off its LOW when yesterday closed in the upper half (trading higher) and off the HIGH otherwise (tags frame_low / frame_high, ipda_disc / ipda_prem).
  - Caption-gap fix (B21-progression-20-40-60-beyond; cc05_004 ~26:38, cc06_008 ~12:50, cc07_004 ~7:43, cc05_003 ~28:40): the near-term draw is the 20-day extreme in the IOF direction; roll out to the 40-day window when the 20-day extreme is taken OR every PD array of the 20-day window has been traded to; next target = the next unused lower low (higher high) or the opposing discount (premium) array; if the 40-day window adds nothing beyond the 20-day one go straight to the 60-day; prefer levels where range extremes and PD arrays converge (0.25 x ADR5 [our interpretation]); if the 60-day extremes are already run and an obvious older swing sits just beyond 60 days, target it and tag "expansion expected". Bot: `ipda_next` + `ipda_roll_arrays`, `ipda_beyond_days` (off, 0). Review fix: the 20-day window is exhausted by its daily OBs as well as its FVGs; `ipda_converge` (off) prefers the window extreme that coincides (0.25 x ADR5) with an open premium daily array as the draw (tag ipda_converge).
  - Caption-gap fix (B21-open-float-forward-windows; cc05_004 ~25:15, cc05_003 ~2:02:01: "you look back 60 and you look forward 60"): anchor D - back pools = the 20 / 40 / 60-day highs / lows before D; forward: the running high / low of D..D+19, D+20..D+39, D+40..D+59, each COMPLETED interval's high / low becomes a pool; the large-fund pool = the high / low of D-60..D+59 (the realised part only: a bot adaptation, no look-ahead); at each forward marker recompute the look-backs ending there (not built); levels hit by two or more windows rank higher; the forward D+60 marker anticipates an intermediate-term turn. Bot: `ipda_forward` (off), anchored by `ipda_anchor`. Review fix: with `ipda_forward` the back windows end the session BEFORE the anchor D (the forward intervals start AT D), whatever the anchor; `ipda_recompute` (off) adds the 20/40/60 look-backs recomputed ending at each forward marker D+20 / D+40 / D+60 reached (pools ipda_m<j>w<n>, ranked with the other multi-window levels); the forward pools are lock candidates too. With the "current_month" anchor a forward interval completes only as the month ends - the "month" anchor (the last closed month) shows them sooner.
  - Caption-gap fix (B21-anchor-month-vs-daily; cc05_004 ~16:04: "we keep moving that basis forward each new month"): `ipda_anchor` has both readings - "current_month" (the windows end on the first trading day of the CURRENT month, fixed until the next month; cc05_001 ~24:28, cc05_003 ~28:40, cc05_004 ~16:04) and "rolling" / "daily" (count yesterday as day 1 and roll every day; cc09_008 ~6:03; default). The earlier "month" value (the last CLOSED month's first day, cc05_001 ~53:44) is kept as it was. Contradiction: cc05_004 monthly anchor vs cc09_008 daily roll.
  - Caption-gap fix (L3-3-6-12-month-pools; cc05_002 ~2:41): the 3-month (~63 sessions), 6-month (~126) and 12-month (~252) highs / lows are open-float pools; the high a bearish shift came from, the prior week high and the prior month high are the shorter ones; the 3-month extreme has priority around the quarterly shift. Bot: `ipda_windows` accepts (20, 40, 60, 63, 126, 252).
- **B22 Quarterly shift**: a major turn or consolidation every 3-4 months; bias and sizing context,
  not timing (cc05_001 ~5:05; 084 ~22:12; 098 ~58:30) [both].
  Bot (bias_htf): `qshift_tag` / `qshift_size` (60-session turn or consolidation, due 3-4 months later, 252-session trend).
- **B23 Seasonals** (road map, never a trigger; use only when long- and short-sample lines agree and
  HTF trend agrees; a missing seasonal signals strength the other way) (cc05_010; cc05_011; 074
  ~49:22) [both]. Index map (Dow 20-yr, cc10_015 ~5:04): Jan bearish, Feb bullish, Mar
  consolidation, Apr bullish, May bearish, Jun consolidation ending bearish, Jul bullish, Aug
  consolidation, Sep split, Oct-Dec bullish; Mar/Jun/Aug low probability. Sources disagree on
  January and late May (cc10_016; 050 ~2:20; 074 ~16:54). Bot: tag only.
- **B24 Buy-side engineering tell** [CC] (BH-compressed-higher-highs; 028 ~1:26:02 / ~1:12:40 / ~1:24:53: "it's just constantly reaching for liquidity"): after a drop, a series of marginal higher highs that stays compressed (small extensions, overlapping back-and-forth) back into equilibrium / premium is buy-side engineering, not bullish structure: do not count it as a bullish shift and lean bearish once it fails; mirror. One source, judgment; the nearest existing match is the M-model "three drives into failing liquidity". Bot: `compressed_hh` (off): a run of `compressed_n` = 3 consecutive pivot highs each higher by < `compressed_k` = 0.1 x ADR5 above the dealing-range EQ [our interpretation] (`levels.compressed_highs`); a long whose MSS reference is one of them is rejected, a short after the MSS below the run is tagged `compressed_hh` and the leg low is its first target.
- **B25 Three pools run = exhaustion** (BH-three-pool-runs-exhaustion; 048 ~1:13:41, DXY: "it's already taken three pools of liquidity"): once a leg has taken three successive pools in the order's direction (a short: sell-side pools), do not take new continuation orders at premium arrays (FVG / OB) in that leg - expect consolidation or a run to the nearest opposite pool; the mirror for buy-side runs. The source example is DXY; applying it to the indices is [our interpretation]. Bot: `pool_runs_max` (0 = off; test 3, `sm2.pool_runs`, reject `x_pool_runs_exhausted`).

### 2.3 Day selection and news

- **N1 NFP Friday: no live trading.** Nobody trades the first hour after 08:30; experienced traders
  wait out the volatility (Ep 04; 006 ~8:35; 061 ~2:49:35; 105 ~11:50; cc08_001 ~6:37; cc08_006
  ~4:45) [both]. He traded several NFP Fridays live, each labelled an exception (071; 088/089;
  105). Don't pyramid on NFP (105 ~9:13). Bot: `nfp_day` trades the day (owner #4: the 30-minute floor); `nfp_first_hour` (on) drops the
  pre-09:30 windows and Ma Deuce on jobs days, `nfp_no_adds` (on), `nfp_day_from` test, the `nfp` day tag. D8.
  - Caption-gap fix (N1-nfp-release-4h-fvg; 105 ~5:54: "the market drops back down into that area overshoots it a little bit but that's fine"): a demonstration for EXPERIENCED traders only (the default stays blocked; D8 option B, apart from `nfp_day_from`): NFP Friday with a bullish 4h bias; before 08:30 mark the nearest 4h bullish FVG in the discount of the current swing range; if the release drives price into it, buy inside it at or just after the release (a small overshoot into an adjacent balanced range is fine); stop wide, below the HTF bodies; a first partial (~half) at the first liquidity, optionally one small add at the CE limit (no real pyramiding), then breakeven + commissions. Bearish mirror. Bot: `nfp_release_fvg` (off; a limit at the FVG's upper edge armed on the bar closing at 08:30, valid `nfp_release_fvg_min` = 5 minutes, bypassing `nfp_floor_min` / `news_wait` for itself only; 50% at the first pool, the rest to the table's draw; `nfp_release_fvg_add`). Contradicts N1 ("nobody trades the first hour") and Ep 04 ("ignore the immediate reaction").
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
  - Caption-gap fix (N5-entry-at-release; 040 ~1:28 (a drawdown drill), 049 ~2:27: "News at 10 o'clock high impact and I use this order block here ... I went short at 10 o'clock"): two EXPERIENCED switches, both off (D8 / D9 option B; `news_wait` and N6 stay the default). (a) `post_news_continuation`: after an 08:30 release, once the run-out has printed in the direction of the daily bias (>= `post_news_run_pts` = 5 [our interpretation]), enter on the first 1m OB retrace in that direction (a limit at the order block's body top, stop under it), targets by SD projection of the run-out leg (L12). (b) `release_ob_entry`: on a 10:00 high-impact day with a known daily draw, if price at 10:00 is inside a 5m OB in the bias direction, enter at the 10:00 open, stop beyond the OB's far edge, first target the nearest short-term swing (a scalp); "continue only if an SMT or sick-sister read supports it" is built: with SMT (the index took a pool, the partner did not) or the sick sister (`setups.sick_sister`) the trade continues to the table's draw after the nearest swing (tag `release_ob_continue`), otherwise it stays the scalp. The release setups respect the session / day done flags and the day stop. Conflicts with N5 (wait for the dealing range, or 30 minutes per 065B) and N6 (the first side is false).
- **N6 News delivery profile**: the side taken first after the release is usually false; the
  opposite pool is the real move (up-down-up / down-up-down) (064 ~52:12; 073 ~10:42; 078
  ~1:25:47) [2023]. After both pools are taken, price retraces to the CE between them (064
  ~1:10:43). On NFP/CPI/FOMC days breakers reject poorly (073 ~4:36).
  - Caption-gap fix (N6-nfp-first-move-fake-if-liquidity; 105 ~7:58 (also ~2:00-2:30): "I don't see this initial rally as the fake move"): the first post-release move is false ONLY if it ran a defined pool (an old high / low or relative equal highs / lows). If it takes no pool on its side, the counter move that follows is the Judas - e.g. a drop into an HTF PD array such as a 4h FVG in discount, aligned with the bias: enter in the bias direction at that array and target the pools the first move left untaken. Pool-penetration tolerance = `sweep_ticks` [our interpretation]. Bot: `news_profile="pool_test"` (off; a pool taken = as "require"; otherwise orders in the counter-move's direction are blocked until price is at a 1h / 4h array of their side, and only the bias-direction entry at the array is the trade, `x_news_pool_bias`; the pools move 1 left untaken on its own side are that entry's targets).
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
  - Caption-gap fix (N8-consolidation-builds-orders; cc01_002 ~17:28): the consolidation range edges are the pools for the coming expansion. While consolidating: no entries in skip mode; mark the range high / low as buy-side / sell-side pools (L1); the next leg is an impulsive expansion out of the range, never a retracement or reversal straight out of it; afterwards expect a retracement to the OB it left (then continuation) or a reversal; take the direction from the HTF premise (a false run of the opposite extreme is the manipulation); trade only after the expansion has printed. Bot: `consol_pools` (off): the released chop range's high / low are the pools `consol_h` / `consol_l`.
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
  - Caption-gap fix (T3-london-close-multiday-reversal; cc09_005 ~32:44: "the London close can time a market reversal"): a reversal at the London close (10:00-12:00 NY) from an HTF PD array can mark a MULTI-DAY turn (several one-sided days), judged with the weekly templates and structure: tag it as a possible multi-day flip. After an expected NY-session reversal the London close may run that reversal's stops one more time at the HTF array - a re-entry chance in the reversal direction. Bot: `lc_tag` (off; `Trade.lc_reversal`: an entry armed in 10:00-12:00 against the 09:30-10:00 leg whose sweep extreme sat INSIDE an HTF Confluence array), `lc_reentry` (off; after a stopped-out lc_reversal ONE more try in the same direction when the new sweep runs beyond the first extreme at an HTF array; bypasses the one-trade-per-session flag for this case only; the gate binds that slot (session + done key) only, the retry must sit in the SAME HTF array as the first trade, and it ends when the retry's trade closes).
- **T4 Opening range (OR).** OR = 09:30-10:00 "always"; don't trade it: erratic, the first move is
  often a Judas; bias is read from how it delivers; take an earlier setup only if obvious (029
  ~11:44; 031 ~4:52; 036 ~27:30; 042 ~4:29; 044 ~4:54; 065B ~4:53:40; 092 ~1:45:24 "amateur hour")
  [2023]. Exceptions: entries at 09:37-09:46 with price already deep in discount (034; 041; 053
  ~10:03). CC: OR = 09:30-10:30, tends to hold the HOD or LOD; wide OR -> its opposite end gets run
  (cc10_010 ~3:07-7:05) [CC]. Bot: AM entries from 09:30; `or_no_entry` (orders fill from `or_end`; `or_deep` = the 09:37-09:46
  exception with the entry in the lower quarter of the prior day's range [our interpretation]); `or_bias` (the OR's delivery:
  the first extreme was the Judas / the close vs the midpoint); `or_wide` (trade toward the far end of a wide OR). D1.
  - Caption-gap fix (T4-or-length; 073 ~25:03, cc10_010 ~11:09): OR20 (09:30-09:50) is usable after 20 minutes ("it can form in 20 minutes"; liquidity taken outside it informs the 09:50-10:10 macro's next draw); the 2023 "don't trade the OR" uses OR30; the CC index rules use OR60. Decision `or_minutes` in {20, 30, 60} (30 default); `ctx.or20` is always built.
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
  - Caption-gap fix (T13-judas-news-driver; cc01_002 ~15:16: "that's always going to come by way of some news event some news driver"): the manipulation (Judas) leg is usually triggered by a news driver released at the time of the move or just before it. Tag the Judas window to the nearest release (window = +-`judas_news_min` = 30 minutes [our interpretation]). Conflict: cc08_006 says no-news sessions are wildcards that can still be clean; N5: no 08:30 news = soft bias. Bot: `require_judas_news` (off; with `require_judas` only news-backed Judas sweeps count), `judas_news_tag` (off).
  - Caption-gap fix (DS2-two-session-close-templates; cc10_013 ~1:33 / ~3:26 / ~5:10: "that down close is high probability until we get to a four hour or a daily or weekly discount array"): two-session UP close - daily / 4h IOF bullish, mid-swing, no 4h / daily / weekly premium array reached yet: the AM returns to a discount array then rallies; lunch consolidates with shallow retracements (on strong-catalyst days it may trend straight through); the PM runs the lunch-hour low (sell stops) or drops into a fair-value discount array, then rallies into the close; rough measured move PM leg ~= AM leg. Bot (our mapping): AM longs off the discount array, PM longs after a lunch-low sweep or a discount-FVG tap, no shorts. DOWN close = the mirror. Valid only until price trades into an opposing 4h / daily / weekly PD array; then the AM-move / PM-reversal or consolidation profiles apply. Bot: `profile_two_session` (off; tags `two_session_up` / `two_session_down`; valid while no opposing 4h / D / W array was traded into anywhere between the AM swing origin and its extreme; the measured move PM leg ~= AM leg is an extra target from the entry), `two_session_catalyst` (off; on a scheduled-release day the lunch-sweep / discount trigger is dropped, tag `two_session_catalyst`), `two_session_am` (off; the AM: with the bias up and nothing opposing reached, AM orders are bias-direction only and at a same-side 1h+ array; tags `two_session_am_up` / `_down`).
  - Caption-gap fix (DS2-am-move-pm-reversal-templates; cc10_013 ~6:36-11:03): AM rally, PM reversal - daily / 4h IOF bullish but a 4h / daily premium array lies just above: the AM returns to discount then rallies into the HTF premium array; lunch consolidates; the PM runs the lunch-hour high (a lower high vs the AM high is a failure swing) OR the AM high, then reverses down into the close. Exception: if the AM rallied off a 4h / daily / weekly discount array the PM may instead retrace to it and resume higher; expect the reversal to carry through only when that AM array was lower-timeframe (60m / 15m). AM decline / PM reversal is the mirror. The trigger after the sweep is an MSS [our mapping]. Conflict with M6 (015 requires the intraday high to be taken). Bot: `pm_reversal_pool` "am_high" (as built) / "lunch_or_am", `pm_reversal_ltf_only` (off).
  - Caption-gap fix (DS2-consolidation-profiles; cc10_013 ~11:35 / ~12:00 / ~14:43: "especially if there's no real high impact or medium impact news expected during the 10 o'clock hour or later"): CONSOLIDATION profiles - preconditions: daily / 4h premium-discount location unclear (neutral IOF) AND no high- or medium-impact release in the 10:00 hour or later; not with a strong directional bias. AM rally / PM decline: the AM returns to a discount array then rallies (or expands up from the opening range's equilibrium to run London buy stops / the intraday highs); lunch consolidates; if the AM high reached a 1h / 4h+ premium array the PM runs only the lunch high, then reaches for the day's sell stops, otherwise the PM runs the intraday high, then the intraday / London sell stops; the PM may also just consolidate into the close. AM decline / PM rally is the mirror. Bot: `profile_consol_pm` (off; neutral bias [our interpretation] and no release from 10:00; the counter side only, sweep pool `lunch` or `am_session`, targets the day's / London's opposite extreme; tags `consol_am_rally` / `consol_am_decline`), `profile_consol_am` (off; the AM variants: neutral bias, no release from 10:00 - orders at an array of their side or, once the opening range has formed, from its EQ's expansion side; the day's / London's far extreme as targets; tags `consol_am_up` / `consol_am_down`). NOT built: 'the PM may also just consolidate into the close' (a possibility with no trigger).
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
  - Caption-gap fix (L1-rth-session-pools; 067 ~15:00, ~32:00-33:00, ~55:50): previous PM (13:30-16:00), AM (09:30-12:00) and lunch (12:00-13:30) ranges = the max high / min low of RTH bars in the window; London (02:00-05:00) = ETH bars. Overnight (16:00-09:30) prints never redefine an RTH session pool and an overnight trade beyond it does not retire it; the RTH pool stays the reference for the next RTH session (London stays spent by any print). Bot: `rth_pool_spent` (off): a previous PM / AM / lunch pool is spent only by prints from 09:30 today.
  - Caption-gap fix (L1-prior-day-london-pm-pools; 072 ~27:52: "we rip lower to take out the London session"): the previous day's London 02:00-05:00 high / low are pools next to today's London and the previous PM range; each stays a pool until traded through by a tick. Bot: `prev_london_pool` (off).
  - Caption-gap fix (LLT3-london-extreme-preny-range; cc08_007 ~2:37): at the NY open LR = [the London session extreme E (high when bearish, low when bullish), the opposite extreme printed between E and the NY open (09:30 for indices [our interpretation])]; bearish: the next trading day's retracement up into LR sells its premium half with an entry PD array; bullish mirror; also mark the prior NY session high / low - a retracement inside it often frames the next day's higher low (lower high). Bot: `london_lr_zone` (off; "tag" / "require"). Review fix: `ny_hl_frame` (off) marks the prior NY session (09:30-16:00) high / low - a retracement inside it frames the next higher low / lower high (tag in_ny_range); the premium-half test is up to E itself (a short above E is outside LR) [our interpretation].
  - Caption-gap fix (LLT3-0800-0900-pool-stock-open; cc10_006 ~4:06) [bonds-only; index carryover is our test]: the 08:00-09:00 high / low are liquidity pools that tend to be raided around the 09:30 stock open; for ES they are AM sweep pools (expect a raid of one edge at / after 09:30, then an M0 reversal). Bot: `or0809_pool` (off) = (480, 60) in `session_ors`.
- **L2 Liquidity matrix**: highs and lows of today, yesterday and the day before, plus the 3-day
  extreme (Ep 08; 010 ~65:54; cc09_005 ~14:22) [both]. PDH/PDL are the first daily targets and
  raid levels (006 ~37:12; cc04_011 ~12:57). An old daily high/low alone is not an entry: it needs a
  PD array there plus time of day (Ep 08; 010 ~63:38). Reversal at PDH/PDL needs an HTF array at
  the level and HTF order flow (cc09_005 ~03:12) [CC]. Bot: pdh1-3/pdl1-3 from RTH bars.
  - Caption-gap fix (L2-sr-needs-fvg; 058 ~13:34, 076 ~21:21: "classic support resistance is only confirmed if it has one of my fair value gaps"): an old swing low price has broken becomes resistance on a retrace only if an FVG from the breaking leg overlaps it and the HTF bias agrees (expect the rejection at the FVG CE / near edge); the high mirror needs an overlapping bullish FVG. Without an FVG the old level carries no S/R weight. Conflict: L2 above (Ep 08; 010) says any PD array plus time of day suffices - kept as `daily_level_needs_array` True / "any"; the FVG-only reading is "fvg" (a same-side FVG within a tick of the swept level; the entry stays the engine's own PD-array entry). Review fix (levels_detectors #3/3): the setup itself - `flip_retest_entry` (off) with `daily_level_needs_array="fvg"`: an old swing level a body close has broken, with an FVG of the breaking leg within a tick of it and the bias for the side, is armed once as a resting limit at that FVG's CE (stop under the gap).
- **L3 Higher pools**: previous week high/low, previous month high/low (054 ~4:02; cc04_003;
  cc08_007 ~18:27); 20/40/60-day highs/lows (B21); overnight (Globex) high as near buy-side (023
  ~17:00); OR30/OR60 high/low (T4). Lunch REL/REH are the PM's targets (015 ~29:22; 067 ~46:00;
  cc10_013).
  - Caption-gap fix (L3-midnight-session-opening-ranges; 050 ~18:13, a journaling remark): optional reference levels - the midnight OR30 = H/L 00:00-00:30 ET and OR60 = H/L 00:00-01:00 ET each day; the same idea can be applied to the first 30 / 60 minutes of the Asian (20:00), London (02:00), NY (09:30) and PM (13:30) sessions. ICT gives no rule for using them (pool, target or filter): low-priority candidate liquidity pools to test, not a core rule; he warns against bringing every concept into the trading plan. Bot: `session_ors` (empty; ((start_minute, minutes), ...); each range is a pool once complete, tag sor_<start>_<minutes>).
  - Caption-gap fix (L3-monthly-ohlc-3m; cc03_004 ~1:46): each month store O, H, L and C of the last 3 completed monthly candles (12 levels) and draw them on weekly, daily and intraday charts as reference levels (confluence / context, not standalone signals); also frame the monthly range from the most recent down-close monthly candle and the up-close candle above its high (cc03_004 ~2:30). The "support in bullish / resistance in bearish" clause is dropped. Bot: `monthly_ohlc` (off): `ctx.m_ohlc`, lv_tag `m_ohlc` on an entry / target within 1 pt; the confluence-scoring input (item 94 `confl_rank`) is not built. Review fix: a first month the history starts on the first trading session of is complete (not dropped); `monthly_frame` (off) frames the monthly range from the most recent down-close month's low to the high of the up-close month above its high (ctx.m_frame; tags m_frame_disc / m_frame_prem for an entry in that range's discount / premium half); with `converge_rank` the 12 monthly levels count as converging levels of an entry gap (the scoring input).
  - Caption-gap fix (L3-htf-pd-arrays-intraday; cc05_015 ~19:55: "you should have these monthly weekly levels on regardless even if you're a day trader"): build weekly and monthly PD-array levels (OB open / MT, FVG / gap edges and CE, voids, old highs / lows) and keep the untested ones while day trading as S/R, targets and partial levels; if a daily array fails, expect the next weekly array, then monthly (B9). Bot: `htf_targets` accepts "W" and "M" (the confluence object already builds them). Review fix: `htf_monthly_arrays` (off) builds the monthly FVG / OB arrays (htf.months) in `htf.table` next to the daily and weekly ones (react weight 3, [our interpretation]).
  - Caption-gap fix (new-lookback-per-tf-topdown; cc01_003 ~13:38, ~18:23: "your daily chart needs to show 12 months no less than nine months view"): build the level set top-down - daily 9-12 months (not multi-year), 4h 3 months, 1h >= 3 weeks, 15m >= 3-4 days; each lower timeframe inherits the higher-timeframe levels and adds its own recent untested highs / lows, clean equal highs / lows and levels price moved quickly away from; tag each level with its source TF (higher ranks higher; ranking is ours). Bot: `tf_lookback` {"D": 252, "4h": 63, "1h": 15, "15m": 4} (trading days, off): the HTF array lives, the htf.table daily lookback and the daily pivot history; the intraday pivot windows are not widened. Review fix: the DayCtx higher-timeframe FVG zones (15m / 30m / 1h / 4h) honour their own `tf_lookback` window; `tf_pools` (off) adds the untaken swing highs / lows of those bars inside their window and older than the prior session as pools (tag tf_<label>; pool_rank ranks them by the timeframe).
  - Caption-gap fix (L3-or-refs-expire-1100; 090 ~49:21: "the opening range and whatever liquidity is established at that point we use that going forward into 11 o'clock"): at 10:00 record the OR30 high / low and the FVGs formed inside it; they are sweep / target pools and entry arrays for 10:00-11:00 (the SB included); stop treating them as OR references after 11:00 (single source). Bot: `or_expire` = 660, `or_fvg_entries` (off). Review fix: with `or_fvg_entries` the Silver Bullet's array list (sb_model, still off by default) gets the OR FVGs too.
- **L4 Pool quality**: prefer the larger pool (REL over a single low); a 4h REL outranks a nearer 1h
  REL; target the pool below the leg's equilibrium (042 ~1:09:17; 049 ~3:40; 103 ~29:42) [2023].
  Low-resistance runs (few overlapping swings between price and target) over high-resistance runs
  (cc01_007 ~5:38-14:38; 025 ~15:00; 102 ~2:16) [both]. Fund stops can sit up to ~10 handles beyond
  old highs (027 ~44:20).

  - Caption-gap fix (new-reactionary-high-liquidity; 046 ~56:01, 099 ~51:16): in a down leg shorts' trailed stops sit above the most recent REACTIONARY high (the swing high that launched an energetic leg lower; update it as newer ones form) - the buy-side liquidity a retracement reaches for; after a deep-discount move with no FVG / VI between price and the recent 15m swing highs the retracement target is the buy stops above those single highs or the REH; with the low intact expect the run next session, then an MSS + FVG short back to the lows; mirror for up legs. Reactionary = a pivot high whose following leg contains a displacement bar (A20) [our interpretation]. Bot: `reactionary_pools` (off). Review fix: `reactionary_precond` (off) requires a deep-discount move (>= 0.5 x ADR5 below the high) with no 15m FVG between the close and it [our interpretation].
  - Caption-gap fix (new-parent-pool-bodies-short; 050 ~56:39: "the parent price swing and liquidity pool is this one"): given an earlier swing low L0 and n >= 2 later lows in the same area (within 0.25 x ADR5 above L0 [our interpretation]) whose candle bodies all stay above L0's low, L0 is the parent swing and the real sell-side pool - target it, not the intermediate lows (partial levels at most); mirror for highs. Single source, hindsight. Bot: `parent_pools`, `parent_n` (off, 2). Review fix: the parent low must be untaken through the bar being tested, not only up to its confirmation.
  - Caption-gap fix (new-trendline-trap-target; cc03_007 ~11:26: "that's where a lot of the buy stops are going to be residing"): trendline trap (HTF bullish, a retail down-trendline with touches H1 > H2 > H3 within 0.1 x ADR5 of the line [our interpretation]): buy at a bullish OB at, or a turtle-soup run of, the low between H2 and H3; T1 = just above H2 (buy stops); further targets from the HTF draw. Bearish mirror. Bot: `trendline_pools` (off). The entry side is M12 below.
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
  - Caption-gap fix (L5-nwog-high-low-labelling; 051 ~5:38): nwog_high = max(Friday close, Sunday open), nwog_low = min; gap_dir = "down" if the Friday close is above the Sunday open, else "up"; the Friday close is the last print before the Friday session ends (16:59; on 5m bars the 16:55 bar close). Bot: `htf.opening_gaps` carries `dir` (always on, a tag); `gaps_for_day(with_dir=True)` passes it on.
  - Caption-gap fix (L5-partial-redelivery; 019 ~16:36, a single example): if after the Sunday open price (a) trades to the NWOG far edge (Friday close), (b) trades back through the gap to the open side, (c) returns only to the CE and fails, and (d) leaves the gap with a lone FVG at its edge, the gap is treated as rebalanced and the Friday close is no longer required; on a later return target the exit FVG / the NWOG near-edge area (exit just before it), not the Friday close. Conflict: L9 "unvisited remainder is the next draw". Bot: `nwog_rebalanced` (off; `htf.nwog_rebalanced` runs the causal state machine within the first trading week after the Sunday open on gaps taller than 2 pts, the exit FVG must be the lone FVG of the leg and close outside the gap; the ladder keeps the near edge and the exit FVG's near edge until a later full redelivery to the Friday close).
  - Caption-gap fix (L5-cfd-nwog-mapping; 036 ~1:32:40: "it's not going to be perfect"): an SPX / NDX CFD's NWOG = the CFD close of the bar at the futures' Friday close time and the CFD open of the first bar at or after Sunday 18:00 (futures data preferred). If those bars are missing flag the NWOG unavailable, or fall back to the Friday close -> Monday 09:30 variant (039) as a tested option. Bot: `nwog_cfd_src` "auto" (= sunday_bars, the built behaviour) / "sunday_bars" (a weekend without Sunday bars is flagged in `opening_gaps(...).attrs["nwog_unavailable"]`) / "monday_0930" (every weekend: Friday close -> the Monday 09:30 open) / "sunday_else_monday" (per weekend: Sunday bars when present, else the Monday variant) / "none".
  - Caption-gap fix (L5-rth-and-eth-gap-views; 019 ~4:31: "you use regular trading hours and electronic trading hours"): scan both the ETH bars (NWOG Fri 16:59 close -> Sun 18:00 open; NDOG 17:00-18:00) and the RTH bars (the prior 16:00 / 16:15 close -> the 09:30 open: ORG, and the Friday-close -> Monday-09:30 NWOG variant) for opening gaps - an ETH-only view hides the RTH gaps; keep both sets without de-duplicating (ICT notes they are not always relevant). Bot: `gap_views` = "both" (kind `nwog_rth`; "auto" = ETH only).
  - Caption-gap fix (L5-holiday-nwog; 046 ~16:23-21:11: "if I don't have it then I don't use it"): if a holiday shortens Friday trading ignore that week's NWOG and use the closest normal NWOG to current price formed within the last 60 days - none if there is none; if a holiday disrupts the Sunday / Monday session use Tuesday's opening price as the week's opening reference (09:30 for indices, midnight for FX). Bot: `nwog_skip_holiday` + `nwog_holiday_pick` = "closest", `tue_open_ref` (the weekly_open filter reads the Tuesday 09:30 open; off). Review fix: the closest-NWOG pick draws on the 60 trading days (not nwog_keep) and keeps the ETH and RTH rows of that ONE weekend; `tue_open_time` ("0930" / "midnight") selects the Tuesday reference for indices / FX; the RTH weekend gap (nwog_rth) follows the NWOG rules wherever they are applied (CE only, quarters, inversions, halfway).
  - Caption-gap fix (L5-nwog-sr-levels; 039 ~10:52-12:06, 024 ~18:37: "they many times are treated as support and resistance"): the stored NWOG high / CE / low are PD-array levels (support / target from above, resistance / target from below); the CE weighs like the edges and price moves from one NWOG level to the next. In a consolidating week (B14) expect reactions at the exact levels (use them for partials / targets and scalp turns); in a trending week price leaves the gap and these reactions are not expected. Bot: `nwog_sr_entries` (off; in a consolidation week - the htf.table `nwog_regime` "cons" - a limit at the nearest level in the bias direction, stop `nwog_sr_stop_pts` = 1 beyond, first target the next level; tag `nwog_sr`).
  - Caption-gap fix (L5-quarter-level-no-imbalance; 030 ~1:23:49: "was there any imbalance in here no so what level are we looking at"): for an NWOG price has broken through (a break below shown; mirror above): if the retrace leg has no FVG / VI, the retrace level is the near quarter, (CE + gap low) / 2; if price reaches it and is repelled expect continuation toward the sell-side pools and the nearest wick CE below; the bearish read holds until price trades above the next higher reference (the gap's far edge), not merely until a body closes above the quarter. Bot: `gap_quarter_retrace` (off; tag `gap_quarter`; stop beyond the CE + 1 tick).
- **L6 NDOG** = 17:00 close to 18:00 reopen, Mon-Thu; high, low, midpoint; ignore gaps <= ~1 ES
  pt; lifetime through Friday (052 ~0:46-5:46) or 5 trading days (068 ~9:49); confluence only,
  never a standalone signal (052 ~6:16) [2023]. {needs: futures data with the 17:00-18:00 break}
  - Caption-gap fix (L6-ndog-nwog-primary-entry; 050 ~54:42, ~51:00: "we went up to the bottom end of that same new day opening gap"): CONTRADICTION - 050 trades the first return to the near edge of an active NWOG / NDOG as an entry on its own with the daily bias (short at the gap's lower edge, stop above the gap high, target the next sell-side pool), against 052 ~6:16 (NDOG confluence only) and 051 ~13:55 (NWOGs never standalone). Bot: `gap_edge_entry` (off; tag `gap_edge`; once per gap and session; windows = the bot's AM / PM [our interpretation]).
- **L7 Opening range gap (ORG)** = prior RTH close to today's 09:30 open (033 ~11:36; 042 ~11:20;
  069 ~10:06; 092 ~1:55:54) [2023]. ES: the last-trade close of the last RTH 1m bar (stamped 16:14), not the 16:15
  settlement (069); for SPX/SPY data 15:59 (the 16:00 close). Levels: high, 75%, CE, 25%, low; bodies respect them (044 ~7:12; 060
  ~31:00).
  - Behaviour: 09:30 volatility seeks the prior close; expect a trade back into the ORG unless it
    acts as a breakaway gap (033 ~14:57; 055 ~20:50). A quarter fill that holds = strength; half
    filled -> a later move into the unfilled half (036 ~53:00; 058 ~53:24). Direction tell: B15.
  - Target ladder: near edge, CE, far edge (= prior close) (069; 041; 068; 043) [chart].
  - Lifetime: 3 days (060), 5 trading days (068), ~60 days (092). Default 5. Bot: none (P2 `org`).
  - Caption-gap fix (L7-org-close-and-direction; 069 ~10:03/~11:05): ORG = the close of the prior day's LAST RTH 1m bar (ES: stamped 16:14; SPX / SPY: 15:59) to the 09:30 1m open - the last-trade close, not the exchange settlement (replaces "16:15 settlement"). Direction label: discount if the open < the prior close (ORG high = the prior close, low = the open), premium if above; CE = the midpoint. Bot: `org_close` auto = the last RTH bar before the session close (verified, test); `Trade.org_dir` = "discount" / "premium" from the 09:30 bar.
  - Caption-gap fix (L7-org-lifetime-sr; 068 ~9:51, 072 ~23:03, 092 ~1:59:32: "they'll eventually be offered buy side and sell side"): keep a list of daily ORGs (prior RTH close -> 09:30 open) marked on RTH bars and project low, 25%, CE, 75% and high onto ETH charts; an ORG above price is resistance, one below is support; track per ORG whether price traded through it upward and downward - it stays active after a one-way fill; if delivery in one direction stopped part-way the pending draw = [the partial-delivery extreme, the far edge]. Lifetime: 5 trading days (068, ICT's personal filter) vs ~60 days (092); 072 gives no number; 3 days (060). A revisit of an ORG high / 75% / CE in the bias direction counts only with another PD array nearby at a valid time (10-11, 14-15, 15-16) (092). NWOGs are exempt. Bot: `org_both_ways` (off) with `org_days` up to 60. Review fix: `org_revisit_gate` (off) makes today's revisit of an ORG high / 75% / CE count only inside 10:00-11:00, 14:00-15:00 or 15:00-16:00 with another PD array within 1 pt (NWOGs exempt).
  - Caption-gap fix (L7-gap-up-premium-template; 042 ~11:31, ~1:00:16): on a significant gap up after an overnight rally into premium (down into discount, mirror): (1) expect an initial rally that draws in buyers; (2) a dip to the ORG high (the 09:30 open) where early shorts enter with stops above the first high; (3) a second rally that takes those stops; (4) only then look for failure (a bearish FVG / structure break) and short into the ORG; target about a 5-handle run, the prior close optional; no shorts during steps 1-2. Bot: `org_two_rally` (off; significant = the gap >= `org_sig_adr` = 0.25 x ADR5 and the open beyond the 20-day EQ [our interpretation]; T1 = open - 5 pts, then the prior close).
- **L8 Vacuum block** = the gap between the last close before an event/session open and the first
  open after; gaps at 08:30/early NY usually fill the same day, gaps from 10:00 on tend to stay
  partly open (cc04_009 ~3:58-10:05) [CC].
  - Caption-gap fix (X3-l8-vb-exhaustion-gap; cc04_009 ~2:48): a bullish vacuum block is valid when the bias is bullish and the gap opens up away from a discount (its lower edge below the 20-day range EQ), after a retracement in an uptrend; a gap up after a multi-day / week rally (5 straight up days, or a close above the high of the 20 days before it) may be an exhaustion gap: tag it and do not treat it as a bullish VB; bearish mirror. Bot: `vb_context` (off) filters the vacuum-block rungs and tags `vb_exhaustion`.

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
  - Caption-gap fix (L10-older-daily-weekly-wick-ce; 010 ~1:45, 015 ~31:48, 011 ~5:22, 093 ~6:48): for each daily candle in the lookback (~5-20 trading days; 015 "20 days") the premium (upper) wick CE = (high + max(o, c)) / 2 and the discount (lower) wick CE = (low + min(o, c)) / 2, on daily candles only; keep each while it has not been traded through since it formed (after a touch it stays a reference); targets, partial levels, S/R and the default draw when bias is neutral. LOD / HOD: with bullish bias the nearest unrevisited lower-wick CE below price that coincides with an intraday discount array (within 1 pt of a 5m / 15m array [our interpretation]) is the expected low of day (allow ~2 ticks through); mirror for upper wicks. Weekly: wick CEs "several weeks" old (011). Bot: `wick_untraded`, `wick_weeks`, `wick_lod_tag` (off, 1, "off"). Review fix: a CE today's own bars have traded through is no longer untraded (targets; for the LOD tag the bars before the sweep extreme count); `wick_lod_tag="require"` rejects only trades on days biased the trade's way.
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
- **L18 Initial FVG references** (N-initial-fvg-reference; 048 ~5:40, 082 ~5:13) [2023]: reference arrays, tagged respected / disrespected later; confluence and a narrative tag only, never a stand-alone entry. `initial_fvg_day` = the first 5m FVG whose third candle closes 09:30-10:00, extended to 16:00; `initial_fvg_week` = the first FVG of Monday's session (048: a 5m FVG at Monday 14:50) [our interpretation: the week's first trading session], extended to Friday's close; `monday_10am_1h_fvg` = if Monday's 10:00 1h candle is c2 of a 1h FVG, its high / low / CE as a weekly array (082: a BISI used as resistance later in the week). Bot: `initial_fvg` (empty; "day" / "week" / "mon10"); `Trade.init_fvg_respected`.
- **L19 Graduated pricing / second touch** (X3-graduated-pricing-second-touch; cc04_010 ~11:24: "it can't be done on the first pass"): institutional repricing is graduated - after price runs away from a level the return often tests it more than once (the second pass may poke a few ticks beyond); a second test followed by bearish candles that leave a gap / void = a sell limit inside that gap (mirror for buys). A confluence TAG from one CC example, not a mandatory touch count. Bot: `touch_tag` (off; `Trade.touch_n` = the separate approaches to the swept level within 4 x `eq_tol_pts` of it since it formed, the sweep included).

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
  - Caption-gap fix (NEW-low-of-day-zone-tag-first; 093 ~8:46: "it has to drop down to that level first"): when a pre-market low-of-day level is defined (093: the CE of an hourly candle's tail, with the 5m discount FVG, a breaker and the daily inversion-FVG levels beneath), take no longs until price trades down to it; then require SMT + MSS + FVG on the lower timeframe. Mirror for a high of day. Bot: `lod_zone_first` (off; [our interpretation] the zone = the nearest completed 60m candle tail (a lower wick of at least 0.1 x ADR5) CE below the 08:30 price with a 5m bull FVG - or a daily array - within `eq_tol_pts`; no long until a bar's low <= zone + 2 ticks, then the sweep needs the SMT tag).
  - Caption-gap fix (new-delivery-states-machine / new-state-to-array-map; cc01_001 ~2:33 / ~7:51, cc01_002 ~12:42 / ~18:35): label the current leg CONSOLIDATION (a clear range) / EXPANSION (a quick move away from the range EQ) / RETRACEMENT (back inside the recent range) / REVERSAL (a run just beyond an old high / low, then rejection); transitions C -> E only; E -> Ret or Rev, eventually C (cc01_001 also allows E -> C and Rev -> Ret; cc01_002 forbids C -> E -> C). Bot: no entry in CONSOLIDATION. Tool map: EXPANSION <-> order blocks (wait for the return to the OB near EQ), RETRACEMENT <-> FVG / void / VI inside the recent range, REVERSAL <-> a liquidity pool / stop run beyond an old extreme, CONSOLIDATION <-> EQ (wait for the impulse away); specialising in one pair is acceptable. Bot: `levels.delivery_state` (thresholds [our interpretation]), `state_machine` (off; helper of the DWC package built here), `consol_bars` (20), `consol_adr` (0.3), `state_tool_map` (off; entry kinds outside the map pass).
  - Caption-gap fix (new-divergence-types; cc04_013 ~2:41 / ~12:15 / ~13:52): type 1 (classic) = price higher high, momentum lower high - the retail reversal signal, often trapped (expect a stop run into an OB, then continuation the other way); type 2 (hidden) = price higher low, momentum lower low = continuation above the recent high. No overbought / oversold reading needed; confirmation only, never a trigger. Mirrors. Bot: `div_tag` (off; `Trade.div_type` "type1" / "type2" from the last two swing lows and the 14-bar stochastic %K, `levels.stoch_divergence`).
  - Caption-gap fix (new-consolidation-exit-direction; cc09_004 ~5:07: "that's going to be the direction of the move outside the consolidation"): a lower-timeframe consolidation most often exits in the direction of daily / 4h order flow; a move out of the range against that flow is a stop run to fade - expect a return through the EQ to the opposite extreme and just beyond; use the HTF-side pool as the draw. Bot: `consol_fade` (off; a wick out of a CONSOLIDATION range against the bias that closes back inside: a limit at the range edge, stop beyond the break extreme, target the opposite extreme).
  - Caption-gap fix (new-price-engine-models; cc09_006 ~0:54, cc09_007 ~1:27 / ~2:23): for a bullish HTF IOF: OA = a sweep of a key intraday old low, then a long to a short-term premium array; RA = (often after a sell-stop raid) a retrace into a discount fair-value array (typically OTE), long there. Bearish: OD (buy-stop run, then a short to a discount array) and RD (retrace up into a premium array, short). All are scalps in the London / NY kill zones. Bot: `Trade.setup_model` in {OA, RA, OD, RD} (always tagged: a sweep-driven order = OA / OD, a non-sweep array retrace = RA / RD).
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
  - Caption-gap fix (M1-original-consolidation; 104 ~27:53): the original consolidation (bullish example): upper bound = a smooth-edge level that bodies / highs touch repeatedly ("a repetitive overlapping or reoccurrence of a level"); lower bound = the range's lowest low; bearish mirror. [our interpretation] >= 3 body tops / highs within 0.5 ES pt inside the bars around the parent swing. Bot: `orig_consol` (off) with `orig_consol_touches` (3) and `orig_consol_tol_pts` (0.5): `mmxm_ctx` draws to that level instead of the parent swing high.
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
  - Caption-gap fix (M4-failure-swing-no-new-extreme): see A15 (the failure swing needs no "fails to reach K"; `fs_def`).
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
  - Caption-gap fix (DS2-am-move-pm-reversal-templates; cc10_013 ~7:46-8:58): CONFLICT - 015 requires the intraday (AM) high to be taken; cc10_013 also accepts a sweep of the LUNCH high (a failure swing vs the AM high). Bot: `pm_reversal_pool="lunch_or_am"`; `pm_reversal_ltf_only` (the reversal carries through only when the AM move started off a 60m / 15m array).
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
  - Caption-gap fix (new-trendline-trap; cc03_007 ~8:18, ~10:46: "I'm looking for a bullish order block at that low in between the two points"): up-trendline with the HTF not bullish (price at a daily bearish array, a draw below): pivot lows L1 < L2, touch 3 = L3, H23 = the high between L2 and L3; when price rallies back toward H23 either sell the bearish OB just below H23, sell an LTF bearish breaker, or sell the failure after a small poke above H23 (turtle soup, a poke <= 1-2 ES pts [our interpretation]); stop above the run high; target below L2, then the daily draw. Down-trendline mirror with the HTF bullish: buy at L23 via the OB or a turtle soup below L23; target the buy stops above H2. Touch tolerance a few ticks. Bot: `trendline_trap`, `tl_tol_ticks` (off, 4): the low between H2 and H3 is a priority sweep pool (poke within `ts_max_pts`) when the bias is with the trade; the OB / breaker variants without a sweep are not built. Review fix: `tl_trap_entries` ("ob" / "breaker", off) adds the entries that need no sweep - a resting limit at the bullish order block formed at L23 (price dips into the old low and does not go through it; "just above" = within ts_max_pts) or at an LTF bullish breaker reaching the L23 area - with the ladder H2 + 1 tick (the buy stops, T1) then the daily draw; the bearish case is the mirror (up-trendline of lows, H23). `tl_tol_adr` (0 = tl_tol_ticks) unifies the touch tolerance with the 0.1 x ADR5 of trendline_pools (OWNER QUESTION 15).
  - Caption-gap fix (new-hs-fade; cc03_008 ~6:30, ~7:11: "i see that as a turtle soup long that took out two previous lows"): HTF bullish (price in the body of a daily bullish OB); on the hourly (index: 15m-1h [our interpretation]) find S1 < head H > S2 with relatively equal lows between them (the neckline); when price trades below the neckline lows buy the sell stops there with a resting limit at or just below the lows; partial at the right shoulder S2, main objective the buy stops above H; the stop is beyond the sweep extreme, wide enough to survive repeated runs of the lows (ICT's example ran them 4 more times). Inverse H&S in a bearish HTF: sell above the neckline highs (wick high or highest body), partial at S2, objective the sell stops below the head; re-sell if price runs the level again (not built). Bot: `hs_fade`, `hs_tf`, `hs_stop_pts` (off, 60, 0). Review fix: `hs_rearm` (off) re-arms the fade once per run of the neckline lows ("re-sell if price runs the level again"); the same-side HTF array gate no longer depends on a confluence object - without one the higher-timeframe FVG zones of the frame decide, and with neither the pattern is not traded.
  - Caption-gap fix (new-intra-week-extreme-raid; cc09_005 ~4:07, ~6:08: "coupled with the running out of a previous intra week low"): short - the market is trending up and an HTF premium array above has not yet been reached; on Tue / Wed / Thu price trades above the intra-week high (the highest of the week so far, relative equal highs preferred) AND into that array -> sell intraday at London or NY with a PD-array entry, expecting the high of the week. Long mirror: price trades below the intra-week low (Mon-Thu; it may blend with the prior Friday / previous-week lows on a Mon / Tue raid) into an unmet HTF discount array -> the low of the week or at minimum a tradable bounce. Exceeding the level alone is no signal; Tue-Thu is a preference for highs. Equal highs alone can be a target for a longer move, so the HTF array is required. Bot: `week_pools`, `week_raid_days` (off, (1, 2, 3)). Review fix: the running week extreme includes the evening before (the Sunday evening for a Monday) and today's own earlier bars, so the Monday low raid exists; a Monday / Tuesday raid of the LOW also has the prior Friday's low and the previous week's low as pools (week_lo_pf / week_lo_pw).
  - Caption-gap fix (M12-classic-patterns-fade; cc03_008 ~2:29: "our higher time frame premise indicates the opposite direction"): classic head and shoulders / inverse H&S are genuine only at intermediate or long-term extremes. With bullish HTF order flow a H&S neckline break is a turtle-soup long at the sell stops under the neckline lows, first target the buy stops above the head; with bearish HTF an inverse H&S neckline break is a run on buy stops to short, target the sell stops below the head. Already built (levels_detectors#3/3: `hs_fade`, `levels.head_shoulders`, `hs_rearm`).
  - Caption-gap fix (M12-second-takeout-turtle-soup; 046 ~1:01:58: "I don't think it's something to build a framework on"): a sell-side low that was already swept and followed by a rally (without taking the opposing high) is not a turtle-soup long on a LATER break - continuation should break it decisively with displacement; a shallow break and recovery means a likely deeper retracement: protect shorts (a partial), not a long trigger. Mirror. FX-only note (cc08_007, London KZ): with no upside protraction a second take-out can be bought - out of scope, consistent with 046. Bot: `ts_skip_reswept` (True; only acts with `turtle_soup` on), `second_break_partial` (off; an open trade takes `partial` of the rest at a shallow (<= `ts_max_pts`) failed break of a target pool already traded before the fill).
  - Caption-gap fix (new-stop-run-overshoot-next-array; 025 ~1:05:16, 038 ~46:12 / L4 / L5): mirror of the sell-side rule - when a stop run above an old high is expected its likely extreme is the next opening gap (NWOG / NDOG / ORG) or PD array (e.g. a VI) above the high; a level hugging the high (a wick CE immediately overhead) is not a reasonable stopping point - look to the next array beyond it; that level is the turtle-soup entry and the stop goes beyond it. Bot: `ts_next_array` (off; `turtle_soup` "2023" and "cc_limit"; the first array / gap level more than `ts_min_beyond_pts` = 1 beyond the pool, stop one tick beyond its far edge [our interpretation]).
  - Caption-gap fix (new-intermediate-term-hl-fade; cc09_005 ~23:14: "it's beyond just yesterday"): an intermediate-term high / low = an old extreme older than yesterday (earlier in the week up to ~2 months back). Fade a raid of it only with context: a range-bound market, OR the move beyond reaches an HTF array, OR it comes after a long trend (profit taking), confirmed with the matrix; otherwise expect it to be traded through. Bot: `ts_itl_context` (off; pools pdl2 / pdl3 / week / month / IPDA; range bound = the last 10 sessions within 3 x ADR5, long trend = a >= 3 ADR move into the pool [our interpretation]).
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

- Caption-gap options (setups_models#1/7): the experienced release models are separate exceptions to A - `nfp_release_fvg` (105 ~5:54: the 4h-FVG release model), `post_news_continuation` (040 ~1:28, a drill) and `release_ob_entry` (049 ~2:27); all off.

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

- Caption-gap options (setups_models#1/7): strict vs tolerance - A is strict (`open_tol_pts` = 0); a wrong-side entry within ~2-3 points is allowed after the open was traded through in the Judas direction, at an OB / FVG with an MSS since (006 ~25:38; 010 ~38:48): test `open_tol_pts` = 2.0 / 3.0, tags `open_grade`, `po3_seq`.

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
- A: the stronger one for longs / weaker for shorts (003; 065B; 079; 085; 089; the CC leader tests cc10_002 ~5:20,
  cc11_003 ~48:46, cc11_002 ~7:54: "markets lead in strength by failing to make lower lows"). ~9.
  (086 moved to the option "depth" below; 090 moved to B; cc10_011 dropped from A - it calls the stronger and the swept index equal.)
- B: the laggard "sick sister" that will catch up (045; 048; 053; 056; 061; 063 ~20:57; 070; 090 ~2:07:49; 099 ~26:53). ~8.
  ICT: sick sister only in consolidation (053 ~8:20) - CONFLICT with 056 ~9:10 / 070 ~18:41 / 099 ~26:53, which route
  with-bias setups to the laggard once the leader met its HTF objective, also on trend days.
  Trend-context rule (BH-D15-sick-sister-laggard): once the leader has met its HTF objective and the laggard has not,
  route with-bias setups to the laggard (after its own MSS + PD array) toward its own unmet analogous target; each
  instrument's objective is the draw of its own htf.table row. Bot: `smt_pick="laggard_objective"` (engine-level
  `Trade.obj_met_t` / `attrs["objective_met"]`), `laggard_consol_only` for the 053 reading.
- His trades: A won in 003, 085, 086, 089; B won in 045, 053, 070.
- Recommended: A (the index that did not make the new extreme at the sweep). Test
  `smt_pick = "laggard"` on consolidation days. Bot today: `combine()` takes the first fill.
- Options added by the caption-gap pass (setups_models#1/7), each a `smt_pick` value: "laggard_objective" (above); "middle" (048 ~2:16:00, needs a
  third index); "clean_swing" (072 ~34:33: prefer the index with a clear 15m swing point between entry and T1, else the first);
  "depth" (086 ~9:49; 100 ~25:56, observational: the fill whose sweep ran deeper into its own HTF array, penetration = (high - array low)
  / array range, ties by the share of bodies respecting the array, then the earlier); "swept" (cc10_011: the index that made the sweep
  / new extreme = the SMT-tagged fill, equal to the stronger one) and "fixed_es" (cc10_012 / cc10_014: the crack in any index signals the
  trade in ES - ES fills only, SMT-qualified when either index diverged). The picks compare the fills of one slot (date + session)
  after the fact: a study-level comparison of conventions, not a live decision (a live bot has the first fill).

- Caption-gap options (setups_models#1/7): (C) the MIDDLE index - when the leader has largely completed its run trade the index that lagged the leader but is not the weakest (048 ~2:16:00: "I don't want to buy the weakest one"; needs YM): `smt_pick="middle"`. (Depth) shorts: the index that went DEEPER into its own HTF premium array (penetration = (high - array low) / array range) with organized structure, whichever printed the SMT extreme (086 ~9:49; 100 ~25:56 - moved out of A): `smt_pick="depth"`. (Laggard by objective) once the leader met its HTF objective and the laggard has not, route with-bias setups to the laggard toward its own analogous target - not limited to consolidation (056 ~9:10; 070 ~18:41; 099 ~26:53; 063 ~20:57; 090 ~2:07:49 moved from A to B; 053 ~8:20 'consolidation only' is the conflicting source): `smt_pick="laggard_objective"` (+ `laggard_consol_only`). (Clean swing) between correlated indices prefer the one with a clear swing point to break or target (072 ~34:33): `smt_pick="clean_swing"`. (Swept / fixed ES) cc10_011 calls the stronger and the swept index equal and says the swept one often moves fastest; cc10_012 / cc10_014: the crack in any index signals the trade in ES - cc10_011 is dropped from A's citations: `smt_pick="swept"` (= the SMT-tagged fill) and `"fixed_es"`. Test all the `smt_pick` values.

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

**24. Specialise in one market or scan all of them? (M3)**
- A: one market, do not switch (054 ~18:18; 046; an SB forms daily in every market).
- B: the model may form in only one index, so watch all three SPX / NDX / DJI (067 ~1:33:29).
- Recommended: test both through the same `combine`: `Params.markets` = ("ES",) vs ("ES", "NQ"); report the setups per day and the share of days with a setup in only one market (`report_decisions.m3_scan`; decision `BH-M3-scan-all-indices`).

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
