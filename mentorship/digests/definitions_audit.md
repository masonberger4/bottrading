# Definitions audit: ICT wording vs what the code does

Scope: every PD array / structure / level definition the bot uses or should use. Sources:
`mentorship_rules.md` 2.1 (A*), 2.5 (L*), section 3 (D3, D4, D6, D11, D17, D21);
`digests/pd_arrays.md`, `digests/levels.md`; spot checks in `notes/*.md`. Code read in full:
`levels.py`, `strategy.py`, `htf.py`, `confluence.py`, `backtest.py` (state as of commit aa72f33).
Read-only audit; no code changed.

Verdicts: MATCH / PARTIAL / MISMATCH / MISSING / USED-DIFFERENTLY (same object defined
differently in different files). "S" = strategy.py, "Lv" = levels.py, "H" = htf.py,
"C" = confluence.py, "B" = backtest.py. Strategy works in "bull space" (shorts mirror prices,
S:236-245), so only the bullish condition is quoted.

---

## 0. Mismatches ranked by likely impact on trades

| # | Item | Verdict | Why it moves trades |
|---|------|---------|---------------------|
| 1 | Swing points `pivot_n=2` (5-candle) in S; `n=1` in H | MISMATCH + USED-DIFFERENTLY | Sets every MSS reference, every REL/REH pool and the breaker window (D17). |
| 2 | Spent liquidity still counted (PDL2/3, PDH1-3, OR/AM/pre-market and gap targets) | MISMATCH | Sweeps of levels already taken yesterday = false setups; dead targets set T1/T2, min_rr and the 10-pt room filter. |
| 3 | MSS on a body close (`mss_mode="close"`) | PARTIAL (D3 pending) | 5 later sources (012, 026, 030, 035, 075) say a wick / 1 tick is enough; changes entry timing and the number of setups. |
| 4 | MSS reference swing = the most recent pivot before the extreme (plus a non-swing fallback) | PARTIAL | ICT wants the parent swing that delivered the sweep (010, 058). With n=1 this becomes even more minor. |
| 5 | Stop OB: one candle, search window runs past the MSS into pullback candles, no series blending | MISMATCH | Sets the stop, so it sets risk, the min/max risk filter, size and R. |
| 6 | Entry FVG: no check that it is still open when armed; the last gap is picked, not the first one | PARTIAL | Can arm on a gap that is already rebalanced or closed through (042 validity rule). |
| 7 | No minimum FVG size; SPY 1-cent gaps (0.1 ES pt, less than an ES tick) count | MISSING | Sub-tick "displacement" on SPY passes the MSS step; no effect on ES/MES. |
| 8 | Single old highs/lows are not pools (only clusters, PDx, sessions) | PARTIAL | T1 is often farther than ICT's nearest BSL, so min_rr and room filters cut differently. |
| 9 | Overnight pool = 00:00-09:30, not Globex 18:00; no London / prior PM / lunch pools | PARTIAL | Missing sweep pools that ICT ranks first at 09:30 (067). |
| 10 | Breaker candle searched only `pivot_n` bars before H, not between L1 and L2 | PARTIAL | Affects only the unicorn tag and which FVG gets picked. |
| 11 | PDH/PDL: RTH in S, futures session in H | USED-DIFFERENTLY | Strategy pools and HTF bias draws disagree on the same level. |
| 12 | ORG: no 25/75% quarters although the Params comment says so; `org_close=975` wrong for SPY | MISMATCH (doc) / PARTIAL | Missing target levels; SPY ORG anchored to a post-market print. |
| 13 | HTF/confluence OB: no MSS/CISD validation; zone is the full range, not high-to-open | PARTIAL | Bias and confluence tags only. |
| 14 | Array lifetimes differ: H 60 days, C D=365D, S HTF tag 5 sessions | USED-DIFFERENTLY | Tags and bias only. |
| 15 | Missing arrays: IFVG, FVG quadrants and VI extension, liquidity void, mitigation, propulsion, CISD, displacement size | MISSING | Not in the current model; matters only once added (P2). |
| 16 | Small items: FVG c2 colour not checked; NWOG holiday weeks; NDOG weekday; stale docstrings | PARTIAL | Low. |

---

## 1. Gaps

### 1.1 Fair value gap (BISI / SIBI)
- **ICT.** BISI = "buy side imbalance sell side inefficiency": c2 delivers only buy side; zone =
  [high c1, low c3] when low[c3] > high[c1]. SIBI mirrors this: [high c3, low c1] when
  high[c3] < low[c1]. Measured on wicks (001 ~13:02, ~21:00; 024 ~20:15; 056 ~6:08 "named for the
  up-close middle candle"; cc04_012 ~1:52). Known at the close of c3. Valid only after "a candle
  close, a new candle open, and then trade back into it without first taking the low" (042 ~34:53).
  Must sit on the path to the draw (048 ~28:06; 091 ~14:27). The old CC body-based version
  (cc01_006 ~3:51) is superseded (conflict C6).
- **Code.** `Lv:43` `if l[i] > h[i - 2]: Zone("bull", l[i], h[i - 2], i, i - 1)` and `Lv:45`
  `elif h[i] < l[i - 2]` for SIBI. Known index = i (c3). Used by S:243 (entries, trail, adds),
  S:316 (15m/60m HTF tag), H:68 (daily/weekly), C:40 (1m to monthly).
- **Verdict.** MATCH on candles and wicks; PARTIAL on extras:
  - c2 colour/displacement is not required (ICT: c2 is the up-close displacement candle for a BISI).
  - There is no state check at arm time (see 1.4).
- **Fix.** Optional `fvg_c2_dir=True`: require `c[i-1] > o[i-1]` for a BISI and `c[i-1] < o[i-1]`
  for a SIBI. Low impact.

### 1.2 Consequent encroachment (CE) and quadrants
- **ICT.** CE = 50% of the gap. Quadrants at 25% and 75% only on large gaps (020 ~8:21; 029
  ~30:44; 055 ~4:50; 101 ~51:58, where small = "under ~10 pips FX"). CE of a higher-TF FVG is the
  default session objective (029 ~44:48). When bullish, price should hold the upper quarter (030
  ~15:46).
- **Code.** `Lv:22-25` `Zone.mid = (top + bottom) / 2`. Entry `S:651`
  `entry = g.top if p.entry == "edge" else g.mid`. No quadrants anywhere. FVGs are never targets.
- **Verdict.** CE: MATCH. Quadrants: MISSING. FVG CE as a target: MISSING (L9).
- **Fix.** Add `Zone.q(f) = bottom + f*(top-bottom)`. In `_targets` (S:340), add open HTF FVGs
  beyond price: near edge, then CE, as "array" targets (P2 item 2 in levels.md).

### 1.3 Minimum FVG size
- **ICT.** No number for FVGs. NDOG: ignore gaps of 1-2 ticks and prefer more than 1 handle (052
  ~4:03). Quadrants are skipped on small gaps (101). "Choose the pair with one clean, obvious gap"
  (061 ~1:49).
- **Code.** None. On SPY (`es_pt=0.10`), a 1-cent gap equals 0.1 ES pt, which is smaller than one
  ES tick (0.25 pt) and could not exist on ES.
- **Verdict.** MISSING. This matters for SPY: noise gaps satisfy the "displacement leaves an FVG"
  step at S:635.
- **Fix.** Add `Params.min_fvg_pts=0.25` (one ES tick) and filter
  `top - bottom >= p.min_fvg_pts * p.es_pt` in `Side.__init__` (S:243) and in `htf_bars` FVGs
  (S:316). Test 0.25 vs 1.0.

### 1.4 FVG validity and state (repriced / rebalanced / filled), first vs last gap
- **ICT.** A touch = "repriced"; "rebalanced" after price trades through and leaves; "filled"
  needs bodies through, not wicks (021 ~12:28; 050 ~30:29; cc10_011 ~4:29; cc04_012 ~13:08). The
  retrace must not first take the low (042 ~34:53). Breakaway gap = the first FVG after the MSS
  and must stay partly open (062 ~37:02). With two FVGs in the leg, the retrace may go to the
  higher one (042 ~47:20; 082 ~5:31).
- **Code.**
  - S:635 `gaps = [g for g in sd.gaps if g.i <= i and g.i - 2 >= sw["ext_i"]]`.
  - S:650 `g = (uni or gaps)[-1]` picks the most recent gap.
  - Nothing checks whether price has already traded into or through `g` between `g.i` and the arm
    bar `i`.
  - A pending order is not cancelled when price makes a new low below `sw["ext"]` before the fill.
  - Invalidation used elsewhere is a body close beyond the far edge: S:333 `closes.min() < bot`,
    H:135 `cl.min() < lvl`, C:62 `seg < inv`. Those three agree with each other and with ICT's
    "filled = bodies through".
- **Verdict.** PARTIAL.
- **Fix.**
  - At arm, skip a gap if `c[g.i+1:i+1].min() < g.bottom` (closed through), and prefer gaps with
    `l[g.i+1:i+1].min() > g.top` (untouched).
  - In the pending block (S:518), cancel if `sd.l[i] < pending["ext"]` (the low was taken first).
  - Test `fvg_pick = "last" | "first"` (breakaway).

### 1.5 Inversion FVG (IFVG)
- **ICT.** An FVG that a candle closes beyond, then acts in the opposite role (015 ~21:00; 078
  ~53:07; 102 ~1:02:03). Valid only when a NEW candle opens, trades back in and it holds; a spike
  through does not count (048 ~21:32, ~36:40). Allowed depth depends on prior use (102 ~1:09:00).
- **Code.** None. When a gap closes through, S, H and C simply drop it (S:333, H:135, C:62).
- **Verdict.** MISSING.
- **Fix.** Where `dead` is computed (C:56-64 and H:132-140), emit a new opposite-kind array with
  the same top/bottom, `known = dead + 1 bar`. Its invalidation is a body close back through its
  CE (102: "near edge to CE"; 084 ~12:00).

### 1.6 Volume imbalance (VI)
- **ICT.** Consecutive bodies do not overlap while the wicks do. Bullish:
  `min(o,c)[i] > max(o,c)[i-1]` and `low[i] <= high[i-1]` (009 ~2:16; 022 ~54:26; 090 ~13:01).
  Dead once a later body on its own or a higher TF closes across it (035 ~5:50). Extend an FVG box
  over an adjacent VI (022 ~55:00; 098 ~60:00).
- **Code.** `Lv:56` `if cb_lo > pb_hi and l[i] <= h[i - 1]`. Used only in tests.
- **Verdict.** MATCH as a definition; unused (MISSING in the model).
- **Fix.** None needed for the definition. If FVG box extension is added, merge a VI whose edge
  touches the FVG's near edge. On SPY, apply the same minimum size as 1.3 (cent-level body gaps are
  everywhere).

### 1.7 Liquidity void
- **ICT.** A true price gap, `high[i-1] < low[i]`. Above all, session or week gaps with no prints
  (NWOG, NDOG, ORG) (028 ~36:17; 039 ~3:06; 074 ~20:51). CC's "one-sided range" is a misnomer per
  2023 (C4).
- **Code.** No detector. Session gaps exist (H:211, S:294).
- **Verdict.** MISSING for intraday true gaps; session gaps are covered (see 4.x).
- **Fix.** Low priority: add `Lv.voids(h, l)` returning bars with `l[i] > h[i-1]`, treated like a
  gap target.

### 1.8 Balanced price range (BPR)
- **ICT.** The overlap of a bullish and a bearish FVG, a single pass each way (046 ~50:02; 065B
  ~4:21). A body close through its midpoint = abort (065B ~4:28).
- **Code.** `Lv:171-172` overlap of opposite FVGs, `Zone(b.kind, min(tops), max(bottoms))`.
  Unused.
- **Verdict.** MATCH as a definition; unused.
- **Fix.** None. It is O(n²); restrict it to gaps within N bars if it is ever used.

---

## 2. Blocks

### 2.1 Order block (OB) and mean threshold (MT)
- **ICT.**
  - Bullish OB = the last down-close candle, or a run of consecutive down-close candles blended
    into one block, before the up move that breaks structure (002 ~4:14; 029 ~29:28 "a series of
    down-close candles that price rallies above the bodies of"; 032 ~23:06 "a series of same-color
    candles is one block"; cc04_003 ~0:35).
  - Anchor: the open of the first (highest) candle (032 ~52:45). Sensitive range = high down to
    open (012 ~5:13; 071 ~35:37). Long wick: use the low and the wick CE (055 ~1:44).
  - Several down candles run through: use the original/highest (012 ~14:06).
  - Validation: CISD, i.e. price trades above the open of the last down candle after the MSS, and
    then the low must hold (075 ~1:16:40). CC version: a later candle trades above the OB high
    (cc04_003).
  - MT = 50%: bodies must not close through it, wicks may. Body vs range is decision D4 (rules
    recommend body).
  - Quality: an FVG right after it; move away >= 2-3x the OB body (cc04_003 ~26:51).
- **Code.**
  - `Lv:79-80` `if (kind == "bull" and c[k] < o[k]): return Zone(kind, h[k], l[k], end, k)`. This
    is a single candle with a full-range zone, and `Zone.mid` = full-range midpoint.
  - S:652 `ob = L.order_block(sd.o, h, l, c, sw["ext_i"] - 3, g.src - 1, "bull")`, then S:654
    `mt = (o+c)/2 if p.mt_mode == "body" else ob.mid`, then the stop is `min(fvg bottom, mt)`
    (S:655-656). There is no displacement check and no MSS/CISD check. The window runs to the
    chosen FVG's c1, which can be after the MSS break, so a pullback candle inside the up leg can
    become "the OB" and give a tighter stop.
  - H:72-77 and C:43-48: `order_block(..., z.i-4, z.i-2, kind)` (c1 and the two bars before it),
    accepted only if the displacement candle closes beyond the OB, `c[z.i-1] > h[k]`. Zone = full
    range h..l; MT/invalidation = body midpoint `(o[k]+c[k])/2`; H:134 and C:62 invalidate on a
    close through the body MT. No MSS requirement.
- **Verdict.** USED-DIFFERENTLY-IN-DIFFERENT-FILES and MISMATCH:
  - S searches up to 3 bars before the sweep through c1 with no displacement test. H and C search
    c1-2..c1 and require the c2 close above the OB high.
  - Zone is the full range in all files (ICT: high..open, or the low on long wicks).
  - No blending of consecutive candles anywhere.
  - No CISD/MSS validation in H and C.
  - MT: S defaults to body (D4); `Zone.mid` (full range) is still the documented "mean threshold"
    in Lv:24.
- **Fix.** One function `Lv.order_block_v2(o,h,l,c,start,end,kind,blend=True)`:
  1. Find the last down-close candle k in `[start, end]`.
  2. While `k-1 >= start` and `c[k-1] < o[k-1]`, set `k -= 1` (blend the series; anchor = the open
     of the first candle).
  3. Zone `top = max(h[k..last])`, `bottom = min(l[k..last])`, `open_anchor = o[k]`, and
     `mt_body = (max open + min close)/2` over the series.
  4. In S, call it with `end = sw["broke"] - 1` (candles before the structure break), not
     `g.src - 1`.
  5. In H and C, use the same function so that all three agree.
  6. Optional `ob_disp_mult=2`: the leg high minus the OB top must be >= 2x the OB body.

### 2.2 Breaker block
- **ICT.**
  - Bullish breaker: swing low L1, swing high H, lower low L2 that runs L1's stops, then a break
    above H. The zone is the up-close candle at H (001 ~45:02; 007 ~22:46; cc04_005 ~0:37).
  - The candle is "the highest up-close candle between a low and the lower low that followed it"
    (029 ~24:13), chosen by body, not wick (048 ~1:06:07).
  - Bodies, not wicks, ~8 sources (029 ~22:34; D6 recommends body).
  - MT of the zone should not be closed through (018 ~1:22; 070 ~56:01).
- **Code.**
  - `Lv:84-115` `breakers()`: L = last swing low before H; requires `seg.min() < L.price`
    (lower low) and `c[i] > H.price` (body close); zone = `order_block(H.i - n, H.i, "bear")`, i.e.
    the last up-close candle with full range. Used only by tests.
  - S:643-648 inline breaker: `order_block(ref_i - pivot_n, ref_i, "bear")`; with
    `breaker_zone="body"` it takes `k = max(ups, key=lambda k: c[k])` (highest close) and uses the
    zone `[o[k], c[k]]`. H here is the MSS reference swing, not tied to L1/L2. The swept pool
    (PDL, etc.) need not be L1. The break is a close or a wick depending on `mss_mode`.
- **Verdict.** USED-DIFFERENTLY: Lv uses the last candle, full range and needs L1 swept; S uses
  the highest-close body and needs any pool swept. Against ICT: PARTIAL. The search window is
  `pivot_n` bars before H, but ICT searches the whole swing from L1 to L2. Body mode matches D6.
- **Fix.** In S:645, search `k in [L1.i, sw["ext_i"]]`, where `L1 = last pivot low with i < ref_i`
  (fallback `ref_i - pivot_n`), pick up-close candles by max `c[k]`, zone = body. Make
  `Lv.breakers` call the same helper or delete it. This affects only `unicorn` and the FVG choice
  at S:650.

### 2.3 Unicorn
- **ICT.** An FVG overlapping the breaker zone (007 ~22:39; 101 ~84:31). Ignore 104's other usage.
- **Code.** S:649 `uni = [g for g in gaps if bz is not None and g.overlaps(bz)]`, preferred at
  S:650.
- **Verdict.** MATCH, given the breaker caveats in 2.2.
- **Fix.** None beyond 2.2.

### 2.4 Mitigation block
- **ICT.** A failure swing: high A, swing low, LOWER high B (no stop run), break below the swing
  low; the zone is the last down-close candle in that swing low (cc04_004 ~2:42-14:35; bullish 033
  ~1:03:50). Weaker than a breaker; ICT uses it more as a target (075 ~21:40).
- **Code.** None.
- **Verdict.** MISSING.
- **Fix.** In `Lv.breakers`, emit `typ="mitigation"` when `swept` is False, i.e. a higher low
  followed by a close above H.

### 2.5 Rejection block
- **ICT.** A swing high made of long-upper-wick candles; zone = highest open/close of the swing up
  to the highest wick, any colour (cc04_006 ~5:04-10:43). In 2023 only the body edge is used as a
  level (015 ~2:15; 059 ~10:03).
- **Code.** `Lv:151-155`: pivot candle ±1; `body = max(o, c)`; the zone exists if `body < high`.
  Unused.
- **Verdict.** PARTIAL and unused. There is no "long wick" test, so nearly every pivot qualifies.
  The neighbour window is fixed at ±1 whatever `n` is.
- **Fix.** Require `(high - body) >= 0.5 * (high - low)` on the pivot candle. Only needed if it is
  used.

### 2.6 Propulsion block
- **ICT.** A down-close candle that trades into an earlier bullish OB and becomes the new support;
  losing its MT = idea wrong (cc04_008 ~0:30-5:40; 027 ~11:31; 079 ~10:27).
- **Code.** None.
- **Verdict.** MISSING. Low priority.

### 2.7 Reclaimed OB
- **ICT.** cc04_007; 104 ~46:56. Not codeable in real time (needs the curve low).
- **Code.** None.
- **Verdict.** MISSING by design.

---

## 3. Structure

### 3.1 Swing high / low
- **ICT.** A 3-candle pivot: "not the 5-candle Williams fractal" (cc01_005 ~11:49; 012 ~30:08; 050
  ~6:02). Hierarchy STL / ITL / LTL (014 ~0:12). Confirmed by a later lower candle (cc01_004
  ~9:44).
- **Code.**
  - `Lv:68` `h[k] > max(h[k - n:k]) and h[k] > max(h[k + 1:k + n + 1])`, known at `k + n`.
  - S:54 `pivot_n: int = 2` (a 5-candle fractal), used at S:242, S:423, S:625, S:643.
  - H:103 `L.pivots(h, l, 1)` (3-candle on daily bars).
- **Verdict.** MISMATCH in S (D17); USED-DIFFERENTLY between S (n=2) and H (n=1).
- **Fix.** Test `pivot_n=1` (D17). Add an ITL helper (a swing high whose neighbouring swing highs
  are lower) for the MSS reference (3.2).

### 3.2 Market structure shift (MSS)
- **ICT.**
  - After a sweep, price breaks the swing that led into the sweep extreme, with displacement
    leaving an FVG (002 ~2:37; 006 ~16:59; 022 ~38:38).
  - It must be the parent swing that delivered the sweep, not a minor one, because minor ones
    "can fail" (058 ~41:15; 010 ~41:31). With relative equal lows, wait for the lower one (044
    ~42:55).
  - Wick vs close: a wick or 1 tick is enough (012 ~30:30; 026 ~1:31:22; 030 ~20:06; 035 ~20:15;
    075 ~33:20) vs a body close (Ep 01/02; 035 ~42:44). D3 recommends keeping close as the default
    and testing wick.
- **Code.**
  - S:621-628 `refs = [q for q in sd.ph if q.i < sw["ext_i"] and q.known <= i]; ref = refs[-1]`.
    The fallback when there is no pivot is the highest high of the `3*pivot_n` bars before the
    extreme, which is not a swing.
  - S:630 `(h[i] if p.mss_mode == "wick" else c[i]) > ref`, default `close` (S:89).
  - S:618-619: a new lower extreme resets `broke`.
- **Verdict.** Close/wick: MATCH to D3 as a parameter, but ICT's majority wording is wick, so the
  verdict against ICT is PARTIAL. Swing choice: PARTIAL, because the most recent pivot is a minor
  swing (more so with n=1) and the fallback is not a swing at all.
- **Fix.**
  - Keep the `mss_mode` test.
  - Add `mss_ref = "last" | "itl"`. For `itl`, ref = the most recent swing high before
    `ext_i` that is higher than the swing highs on both sides of it, or the high where the final
    down-leg into the sweep began: `max(h[last swing high above the swept level : ext_i])`.
  - Drop the non-swing fallback (return None) or tag it.

### 3.3 Displacement
- **ICT.** Fast, large one-directional candles leaving FVGs (006 ~9:55; cc01_004 ~6:13). The only
  number: the move away >= 2-3x the OB body (cc04_003 ~26:51). "Speed and distance" (009 ~15:51).
- **Code.** S:635-640: some bullish FVG with `c1 >= ext_i` exists within `fvg_wait=2` bars of the
  break. H and C require `c[z.i-1] > h[k]` for OBs. No size test.
- **Verdict.** PARTIAL. Combined with 1.3 (no minimum gap), any sub-tick gap counts as
  displacement on SPY.
- **Fix.** The minimum FVG size (1.3), plus optional `disp_mult`: the leg height from `ext` to the
  break bar's high must be >= k x the OB body.

### 3.4 CISD (change in state of delivery)
- **ICT.** The first trade through the open of the last opposite candle before the MSS (075
  ~1:16:40; 032 ~23:06).
- **Code.** None.
- **Verdict.** MISSING. It could serve as OB validation or as a `mss_mode="cisd"` variant.

### 3.5 Premium / discount / equilibrium
- **ICT.** EQ = 50% of the dealing range. Intraday after an MSS: the displacement leg (sweep
  extreme to the high that broke structure) (010 ~58:09; 022 ~38:38). No adds past 25%. Daily: 20
  days or the nearest swings. Wicks for intraday legs, bodies for multi-day (C16).
- **Code.**
  - S:666-669 / S:515-517: `entry > ext + leg_pd*(leg_hi - ext)` rejects or waits; `leg_hi` = the
    max high since the extreme (arm or fill time).
  - S:661-665: entry below the midnight (AM) or 13:30 (PM) open.
  - H:193-197: midpoint of the nearest untaken daily swing high and low.
- **Verdict.** MATCH (D12 implemented). The leg high keeps rising after the break, which is
  ICT's "re-anchor if the leg extends" (cc01_004 ~13:55); fine.
- **Fix.** None. The no-adds-past-25% rule is still missing (only matters with `adds`).

---

## 4. Liquidity and levels

### 4.1 Buy-side / sell-side liquidity pools and "intact"
- **ICT.** BSL = buy stops above old highs and REH; SSL mirrors this (001 ~13:02; cc01_007 ~1:09).
  A level is booked when price trades 1 tick through (042 ~59:04). Use only targets not yet traded
  through since they formed, and skip exhausted ones (028 ~54:55; cc07_004 ~4:00; L14).
- **Code.**
  - Sweep pools, S:571-582: `pdl1..3`, `premarket`, `opening_range`, `am_session`, plus REL
    (S:600-601).
  - Sweep test S:609 `l[i] < v and intact(k, v)`, where `intact` (S:606-608) checks only
    `l[a:i].min() >= v` from `ctx.start` (today 00:00 / 04:00).
  - PDL2/PDL3 already taken by a later day (e.g. `pdl1 < pdl2`) still count as "intact".
  - Targets, S:340-369: PDH1-3, pmh, REH, gaps, OR high, AM high, ORG. They are filtered only by
    `> above = max(leg_hi, entry)`; nothing checks that the level was not already traded today
    before the leg or on an earlier day.
  - Single (non-equal) intraday swing highs/lows are not pools or targets.
- **Verdict.** MISMATCH on "intact": spent PDL2/3 produce false sweeps, and spent PDH2/3 or
  levels traded through pre-sweep become T1/T2 and set the room filter. PARTIAL on pool coverage.
- **Fix.**
  - In DayCtx (S:275), drop `pdl_k` if any later hist day's low or today's pre-sweep low went below
    it: keep `pdl_k` only if `min(low of hist[-k+1:]) > pdl_k`. Same for `pdh_k`.
  - In `_targets`, drop a level `v` if `h[ctx.start:sw_ext_i].max() >= v` (in side space). This
    applies to pools only; gap levels are never retired (039).
  - Optional `single_swings=True`: add untaken pivot highs from the frame as "pool" targets and
    untaken pivot lows as sweep pools.

### 4.2 Relative equal highs / lows
- **ICT.** Two or more highs (lows) close together; no tolerance is ever given. Nearly level
  bodies count (cc05_003 ~1:07:26). Draw the REL at the lower low (038 ~43:43). Smooth ones get
  run even under an older higher high (025 ~36:20).
- **Code.** S:372-383 untaken pivots, then `Lv:118-130` clusters within `tol = eq_tol_pts*es_pt`
  (0.5 ES pt) of the cluster's first price. It returns the cluster extreme (lowest low / highest
  high). Pivots use `pivot_n=2`.
- **Verdict.** MATCH on the extreme; tolerance is a free parameter (no ICT number). PARTIAL:
  wick-only (no body test), inherits n=2.
- **Fix.** None required. Test `eq_tol_pts` 0.25 / 0.5 / 1.0 together with `pivot_n=1`.

### 4.3 Session and prior-period pools (PDH/PDL, overnight, London, PM, lunch, PWH/PWL)
- **ICT.**
  - Liquidity matrix: today / yesterday / the day before (010 ~65:54).
  - Prior PM 13:30-16:00, London 02:00-05:00, lunch 12:00-13:30, AM 09:30-12:00; at 09:30 the prior
    PM range comes first, then London (067 ~12:40-52:30).
  - Overnight (Globex) high as near buy-side (023 ~17:00).
  - PWH/PWL (054 ~4:02). PDH/PDL session: RTH vs ETH is open (levels C17).
- **Code.**
  - S:275-276 PDH/PDL from `hist` = `rth(x)` (B:116), so RTH only.
  - S:281-283 `pre = df[tt < 570]` = 00:00 (futures) / 04:00 (SPY) to 09:30, not Globex 18:00.
  - S:284-285 AM high/low 09:30-13:30 as PM pools.
  - H:175-185 PDH/PDL and PWH/PWL from futures sessions (18:00-17:00) for bias draws only.
- **Verdict.** USED-DIFFERENTLY (PDH/PDL: RTH in S, ETH in H). PARTIAL / MISSING: London, prior
  PM range, lunch range, PWH/PWL as strategy pools. The overnight pool misses 18:00-24:00.
- **Fix.**
  - Add `pm_prev = (13:30-16:00 high/low of hist[-1])` and `london = 02:00-05:00` from df to
    `_sell_side` (AM) and `_targets`.
  - Add `lunch = 12:00-13:30` for the PM.
  - With futures data, extend `pre` to the prior 18:00 (pass the prior evening bars).
  - Choose one PDH/PDL convention (param `pd_session = "rth" | "eth"`) and use it in both S and H.

### 4.4 Opening range (09:30-10:00)
- **ICT.** The 09:30-10:00 range: watch which liquidity it leaves (031 ~4:52; 042 ~4:29). CC uses
  OR60 (cc10_010).
- **Code.** S:302-305 `orb = df[(tt >= 570) & (tt < 570 + or_minutes)]`. It is a sweep pool
  (S:578-579) and a target (S:353-354) once `t[i] >= or_end`; "intact" is measured from the OR's
  completion (S:607).
- **Verdict.** MATCH.

### 4.5 Opening range gap (ORG)
- **ICT.** Prior RTH close to today's 09:30 open. ES close = 16:15 settlement (most videos); SPY
  = 16:00 (033 ~11:36; 069 ~10:06; 092 ~1:55:54). Levels high, 75%, CE, 25%, low (044 ~7:12; 060
  ~31:00). Lifetime 3 / 5 / ~60 days (default 5).
- **Code.**
  - B:94-96 `closes` = the last bar before `org_close` (default 975 = 16:15) on the full df.
  - S:294-300 pairs (prior close, 09:30 open) over the last 6 days.
  - S:357-359 `for q in (0.0, 0.5, 1.0)` gives edges and CE only, while Params S:117-118 says
    "high / 75% / CE / 25% / low".
- **Verdict.** MISMATCH (the quarters are missing, contradicting the comment). PARTIAL on data:
  for SPY with extended-hours bars, 975 picks a 16:14 post-market print, not the 16:00 close.
- **Fix.** S:359 `for q in (0.0, 0.25, 0.5, 0.75, 1.0)`. Set `org_close=960` whenever
  `symbol` is an equity/ETF (or derive it from `es_pt != 1`).

### 4.6 NWOG
- **ICT.** Friday 16:59 close to the Sunday 18:00 first print, on 1m/5m (039 ~0:57-6:40; 051
  ~5:38). Levels: high, low, CE (+ optional quarters). Never discarded; keep >= 4-5, up to 60 days.
  Holiday-shortened week: use the nearest normal one (046 ~16:01). Variant: Friday close to
  Monday 09:30 (039 ~14:41).
- **Code.**
  - H:220-233 reopen = a bar gap > 45 min with the reopen at 17:00-19:00; weekend if the gap is
    > 30 h; `high/low/ce`, no minimum size. H:245 keeps the last 5. C:117-121 kills it when 5 newer
    exist. Never retired by a fill (H:132, C:110). S:347-349 uses high/CE/low as targets
    (`gap_mode="ict"`).
  - Fallback S:286-292: RTH Friday close to Monday 09:30 open, edges only, last 4.
- **Verdict.** MATCH (`ict` mode). PARTIAL: no holiday-week rule; no quarters; the fallback is
  really the 039 Monday variant (labelled NWOG).
- **Fix.** Skip a NWOG whose Friday session closed early or whose week has a holiday. Rename the
  fallback `monday_org`.

### 4.7 NDOG
- **ICT.** 17:00 close to 18:00 reopen, Mon-Thu; ignore gaps <= ~1 handle; lives through Friday
  (052 ~0:46-5:46) or 5 days (068); confluence only.
- **Code.** H:229 `if not weekend and abs(b - a) <= ndog_min_pts * es_pt: continue`; the week
  filter (H:246, C:115) keeps it through that week. S uses it as a target (array).
- **Verdict.** MATCH. Minor: there is no Mon-Thu check, so a holiday early close (13:00 to 18:00)
  becomes an "NDOG".
- **Fix.** Require `t[k-1]` to be within 16:00-17:00.

### 4.8 Midnight open and other opens
- **ICT.** The open of the 00:00 NY 15m candle (006 ~5:51; 069). 08:30, 09:30, 13:30 are
  secondary opens.
- **Code.** `Lv:133-142` first bar >= 00:00 / 08:30 / 09:30 / 13:30 of the day frame; on SPY that
  is the 04:00 proxy (D22).
- **Verdict.** MATCH on futures data; PARTIAL on SPY (known, D22).

### 4.9 Wick CE
- **ICT.** 50% from the body edge to the wick tip; prior daily and weekly wick CEs are targets
  and invalidation levels (012 ~4:14; 028 ~16:43; 101 ~78:20).
- **Code.** `Lv:176-178` on the prior RTH day only (S:279), off by default. `weekly_bias`
  (S:176, S:178) uses `o + (h - o)/2`, i.e. the wick CE from the open, which is correct for the
  candle colour it is applied to.
- **Verdict.** MATCH as a formula; PARTIAL in scope (prior day only, RTH candle, no weekly).

### 4.10 SD projections
- Not a definition item. See D23. `_targets` S:362-364 `hi + k*(hi - lo)` from sweep extreme to
  leg high. MATCH to the recommended anchor; the "first level beyond the pool" rule is MISSING.

---

## 5. Daily / weekly / monthly versions of arrays

| Array | S (intraday) | H (bias) | C (confluence) | ICT |
|---|---|---|---|---|
| FVG | 1m/5m entry; 15m/60m tag over 5 sessions (S:308-317) | D, W; 60-day lookback (H:121) | 1m..M; life 1D..3700D (C:31-32) | Same rule on every TF; 60-day lookback (015; 051; 065B) |
| FVG invalidation | close beyond far edge (S:333) | close beyond far edge (H:135) | close beyond far edge (C:62) | Bodies through = filled; then IFVG (missing) |
| OB | single candle, window ext-3..c1, MT body/range (S:652-654) | c1-2..c1 + c2 close beyond, zone h..l, MT body (H:72-77) | same as H (C:43-48) | Blended series, high..open, MSS/CISD validated |
| Gaps | NWOG/NDOG/ORG targets | NWOG last 5, NDOG week | NWOG until 5 newer, NDOG week | Same |
| Swings | n=2 | n=1 | n/a | n=1 |
| PDH/PDL | RTH | futures session | n/a | open question (RTH vs ETH) |

- **Verdict.** USED-DIFFERENTLY on OB, swings, PDH/PDL and lifetimes (C's daily FVG life of 365D
  vs H's 60 days).
- **Fix.** Set C `LIFE["D"]="90D"` (≈ 60 trading days) to match H, or make H's lookback a shared
  constant.
- **Docstring drift.** C:10-11 says gaps are "valid until a close below the gap's bottom" and
  that the daily gap is "16:14 close"; the code (C:108-129) never retires gaps by a fill and uses
  `htf.opening_gaps`. H:7-11 data note is HistData-specific.

---

## 6. Proposed changes, in order (all as Params switches so they can be A/B tested)

1. `pivot_n=1` test (D17), with `mss_ref="itl"` so the MSS reference does not become a minor swing.
2. Pool and target hygiene: drop PDx levels taken on a later day; drop pool targets traded through
   before the sweep (4.1).
3. `mss_mode="wick"` test (D3; ICT majority).
4. `order_block_v2`: blended series, window ends before the MSS break bar, high..open zone, body
   MT; shared by S, H and C (2.1).
5. Entry-FVG state check at arm and cancel on a new low before the fill; `fvg_pick` test (1.4).
6. `min_fvg_pts=0.25` (1 ES tick) for SPY (1.3).
7. Single swing highs/lows as pools/targets; prior-PM, London, lunch and Globex overnight ranges
   (4.1, 4.3).
8. Breaker candle search between L1 and L2 (2.2).
9. One PDH/PDL convention across S and H (4.3).
10. ORG quarters (fixes the comment mismatch) and `org_close=960` for SPY (4.5).
11. Later (P2): IFVG, FVG targets near edge / CE, mitigation block, CISD, propulsion, voids.
