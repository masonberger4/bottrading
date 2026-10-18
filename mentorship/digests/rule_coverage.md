# Rule coverage map: every ICT rule vs the bot, with build specs

Read-only audit, 2026-10-17. Sources: `mentorship_rules.md` (section 2 rules, section 3 decisions,
Appendix A Ep 01-08), every digest in `mentorship/digests/`, and the code in `mentorship/`
(strategy.py, levels.py, htf.py, confluence.py, sb_model.py, pre_open.py, backtest.py,
calendar.py). The code was read as the **working copy** on branch `mentorship`, including
uncommitted edits made during the audit: `ladder_by_day`, `ladder_fracs_slow`, `slow_frac`,
`be_on`, and `ladder_trail="fvg"` as the default. Re-check those rows if those edits are reverted.

Owner decisions applied:
- The bot follows the **experienced** version wherever ICT splits the rule (`experienced_rules.md`).
- The Silver Bullet is off by default.
- Every new rule is a `Params` switch.
- Data: ES/NQ/YM 1m futures for all hours (Databento), SPX/NDX CFD, daily DXY, daily 10y yield.
- Trades are executed as SPY or futures.

**Default policy used in the specs.** A new switch defaults ON only when all four hold:
1. ICT states it as a rule, not only in one chart example.
2. At least two sources, or one source that states it explicitly as a rule.
3. It is not a beginner-only rule.
4. No other ICT statement contradicts it.

Everything else defaults OFF and gets a test variant. "[our interpretation]" marks a number or
condition that ICT never gives; each one carries the reasoning.

Units: thresholds are in ES points ("pts") and convert to price with `p.es_pt`. 1 tick = 0.25 ES
pt. "Side space" is the code's mirrored-bull frame: a long's logic applied to `-price` for a short.

---

## 0. Findings that need attention first (bugs or rule violations in today's defaults)

1. **Pyramiding is ON by default and allowed on NFP Friday.** `adds=(0.5, 0.33, 0.17)` and
   `nfp_day=True`. ICT: "no pyramiding on NFP" (105 ~9:13). Rule N1b / E12f. Fix: spec M-14f.
2. **The stop padding is below one tick on futures data.** `stop_buffer=0.01` is in price units, so
   on ES/SPX (`es_pt=1.0`) it is 0.01 pt; one tick is 0.25. ICT pads "one tick beyond the level"
   (Ep 08 ~16:01). It is the same on SPY (0.01 = 0.1 ES pt). Rule E6f. Fix: spec E-10.
3. **On 10:00-release days the AM starts at 10:00, but ICT waits 30 min after any release**
   (065B ~4:07). The `NEWS_1000` dates also exist only for 2026, so before 2026 the gate never
   fires. Rules N5a and N5b. Fix: specs W-1 and W-2.
4. **FOMC: `fomc_pm_from=885` only blocks arming.** An order armed before 14:00 can fill at
   14:00-14:45, and an open AM/PM position is held through the 14:00 release. Rule N3a/b. Fix:
   spec M-13 (`fomc_flat_t`).
5. **`fvg_abort` is not ICT's rule.** The code arms on a bar whose whole body is below the gap and
   then exits on any later bar that trades below that bar's low. ICT says a candle **closes**
   beyond the FVG and the **next** candle trades beyond it (045 ~1:19:58). Rule X6. Fix: spec M-9.
6. **`reentry_half` does not force the same direction or the "idea intact" condition, and does
   not exempt FOMC days** (021 ~43:56). Rule X13b / N3f. Fix: spec M-16.
7. **Silver Bullet `_arm` scans both sides every bar** and can switch direction inside a window.
   ICT chooses the draw first and trades one direction (054 ~9:31-9:52). Rule M3b. Fix: spec SB-1.
8. **`Params.org_close=975` (16:15) is right for ES futures** but wrong if the signal data is SPY
   (no 16:15 print). It is not a problem when the signals come from Databento futures. Mention only.

---

## 1. Summary counts

Counted from the tables in section 2 (one row = one rule or sub-rule).

| Group | Rows | FULL | SIMPLIFIED | MISSING | N/A |
|---|---|---|---|---|---|
COUNTS_PLACEHOLDER

---

## 2. Coverage tables

Column "code location" gives `file:function` and the param. "Spec" names the build spec in
section 3 that closes the gap (prefix = work package: B = bias, M = management, T = targets,
E = entry/stop/size, C = context, W = news, D = detectors, SB = Silver Bullet, S = setups).

### 2.1 Definitions (A)

| ID | Rule (short) | Status | Code location | What is missing / spec |
|---|---|---|---|---|
| A1 | 3-candle swing; STL / ITL / LTL hierarchy; confirmed by a later lower candle | SIMPLIFIED | levels.pivots; `pivot_n=1` | No ITL/LTL hierarchy (needed for the parent-swing MSS and SD clusters). D-1 |
| A2 | BSL above highs / SSL below lows; a level is booked only 1 tick through; an imbalance is not liquidity | SIMPLIFIED | strategy._scan sweep test `l[i] < v`; `exit_mode="split"` | A sweep should need >= 1 tick (0.25 ES pt) through. E-1 |
| A3 | REH/REL: 2+ highs close together; smoother = stronger; near-level bodies count; REL line at the lower low | SIMPLIFIED | strategy._eq_levels, levels.equal_levels; `eq_tol_pts=0.5` | No body-based equality; no touch-count weight. D-2, T-18 |
| A4 | Bodies tell the story, wicks do the damage; a 1-2 tick "mohawk" is still respect; CC: stops sit beyond the body cluster | SIMPLIFIED | sweep on wicks; `stop_buffer` | Stop padding ignores mohawks; no body-cluster sweep variant. E-2, E-10 |
| A5a | FVG = 3-candle wick gap, known at c3 | FULL | levels.fvgs; `min_fvg_pts=0.25` | Optional c2-colour check (D-3) |
| A5b | Levels high/low/CE; 25/75% quadrants on large gaps; HTF FVG CE = session objective | SIMPLIFIED | Zone.mid; confluence.targets (near edge + CE) | No FVG quadrants. D-3, T-10 |
| A5c | Extend the box over an adjacent VI; a body gap inside the FVG gives the exact limit | MISSING | - | D-3, E-7 |
| A5d | Valid after close + new candle + trade back without first taking the low; on the path to the draw | SIMPLIFIED | limit armed after c3 closes; `_scan` "still open" filter | No cancel when the bar opens below the sweep extreme (gap-through fill). E-9 |
| A5e | State: repriced (touch) / rebalanced (through and out) / filled (bodies through) | SIMPLIFIED | `_scan` open / fresh filters | No per-gap state tracker. D-4 |
| A5f | Retrace into a BISI stops at the top or CE; bullish = holds the upper quarter | SIMPLIFIED | `ce_hold` (off) | Upper-quarter tag. D-4 |
| A5g | Two FVGs in a leg: the higher (second) one is allowed; skip an FVG sitting right above a pool | SIMPLIFIED | `fvg_pick="last"` | Skip-above-pool rule. E-13, T-12 |
| A5h | FVG overlapping an OB: the FVG near edge comes first | SIMPLIFIED | confluence.targets returns both | OB levels inside an FVG are not suppressed. T-11 |
| A5i | Lifetime: extend forward, reuse after fills, up to 60 days | SIMPLIFIED | confluence LIFE (D = 90D); arrays die at a close-through | Filled FVGs are dropped instead of kept as levels / turned into IFVGs. D-5 |
| A6 | Breakaway (protected, at most half retraced), measuring (project -1 SD), common gaps | MISSING | `ce_hold` only approximates the breakaway hold | Classification, measuring-gap projection, protected-zone trail. D-6, T-7, M-8 |
| A7 | Immediate rebalance (intraday; daily open trades exactly to PDH/PDL) | MISSING | - | Detector and uses. D-7, S-6, SB-10 |
| A8 | IFVG: close beyond, NEW candle back in, holds; depth by prior use; bias switch | SIMPLIFIED | levels.inversion_fvgs; `ifvg_entries` | Hold check, depth rule, CE entry, CE +/- 3 pt stop. D-8, S-5 |
| A9 | VI: bodies apart, wicks overlap; stop at its low; dead when a body crosses it; clusters = porous | SIMPLIFIED | levels.volume_imbalances (definition only, unused) | Uses: entries, stops, adds, death, porous flag. D-9, E-14, M-14 |
| A10 | Void = true gap + session gaps; CC one-sided range: leg start = fill target | SIMPLIFIED | levels.voids (`fvg_targets`); NWOG/NDOG/ORG | Leg-start fill target. D-10 |
| A11 | BPR: trading TO it easy, THROUGH it rare; a body close through its midpoint = abort | MISSING | levels.balanced_ranges (unused) | Target, abort, size-up. D-11, M-15, E-11 |
| A12a | OB = last opposite candle(s), blended; anchor = open of the first; sensitive range high..open; stubby wick -> open, long wick -> low + wick CE | SIMPLIFIED | levels.order_block_blend (blend + body MT) | No high..open zone; no wick rule. D-12 |
| A12b | Validation: CISD (trade through the open, then the low holds); CC: trade above the OB high | SIMPLIFIED | `mss_cisd` (MSS reference only) | "Low must hold" cancel. D-12, E-6 |
| A12c | Quality: FVG right after, larger body, move away >= 2-3x the body, use the original/highest candle | MISSING | - | D-12 (tags), E-5 |
| A12d | Mean threshold 50%; bodies must not close through it | FULL | `mt_mode="body"` (D4); `_scan` stop | |
| A12e | Opposing OBs are targets; once price trades through an opposing OB's MT, its other half is not revisited | SIMPLIFIED | `htf_targets` (OB near edge + mid) | MT-crossed rule. T-11 |
| A13 | Breaker: L1, H, lower L2, break of H; highest up-close candle by body; MT not closed through; first touch valid; wrong time = time distortion | SIMPLIFIED | `_scan` inline breaker (unicorn tag only); levels.breakers (unused) | Breaker as entry, target, invalidation; time-distortion filter. D-13, S-1 |
| A14 | Unicorn = FVG inside the breaker; preferred | FULL | `_scan` `uni`; `Trade.unicorn` | |
| A15 | Mitigation block (failure-swing twin); used more as a target | SIMPLIFIED | levels.mitigation_blocks; `tag_blocks` | Target use. T-16 |
| A16 | Propulsion block: tag its high and leave; losing its MT = wrong | SIMPLIFIED | levels.propulsion_blocks; tag | MT-loss exit, high-tag entry. M-11d, D-16 |
| A17 | Rejection block (wick zone); 2023 = body-edge level | MISSING | levels.rejection_blocks (unused, no long-wick test) | D-17, T-5 |
| A18 | Reclaimed OB (MM model: buy retests of sell-side-curve down candles after the low) | MISSING | - | Codeable once the MSS confirms the low [our interpretation]. D-18, M-14b |
| A19a | MSS reference = the parent swing that delivered the sweep; with REL wait for the lower one | SIMPLIFIED | `_scan` `refs[-1]` + non-swing fallback | Parent swing; REL lower-one rule. E-3 |
| A19b | MSS on wick or close (D3) | FULL | `mss_mode="close"` | |
| A19c | Two MSSs, each leaving an open FVG = "on side" | MISSING | - | E-4 |
| A19d | Don't trust a shift until the liquidity run has happened | FULL | `_scan` requires a sweep | |
| A20 | Displacement: move >= 2-3x the OB body; the next candle follows | SIMPLIFIED | FVG within `fvg_wait`; `min_fvg_pts` | No size or follow test. E-5, E-12 |
| A21 | P/D: leg EQ intraday; 20-day range for the day; OTE 62-79%; wicks intraday, bodies multi-day | SIMPLIFIED | `leg_pd=0.5`, `leg_pd_at` | 20-day P/D, OTE, body ranges. B-13, S-8 |
| A22 | PD-array matrix order; a breaker in the path stops price first; skip exhausted arrays | MISSING | targets sorted by price only | T-1, T-2 |
| A23 | Wick CE = 50% body edge to tip; next-candle close beyond = continuation | SIMPLIFIED | levels.wick_midpoints (prior day); `wick_levels=True` | Intraday/weekly wick CEs; continuation read. D-19, T-4, M-2 |
| A24a | Implied FVG | N/A | - | Undefined (035 names it once) |
| A24b | Reaper (breaker + FVG in the discount half of its impulse leg, CE holds) | MISSING | - | [our interpretation] S-12 |
| A24c | "Inducement" = the sweep step | FULL | `_scan` sweep | |

### 2.2 Bias (B)

| ID | Rule (short) | Status | Code location | What is missing / spec |
|---|---|---|---|---|
| B1 | Price moves only to run liquidity or rebalance an inefficiency (<= 60 days) | FULL | `_targets` pools + arrays; no target -> no order | |
| B2 | Draw search order: inefficiency first, then liquidity by premium/discount; the nearest inefficiency beyond the pool sets the run | MISSING | htf.table `draw` = nearest of everything | B-6 |
| B3 | Bias = toward the next draw; ONE direction; expect the first delivery against it | SIMPLIFIED | `htf_bias` (off); `_judas` tag | One-direction lock (experienced default off: 095 ~11:46). B-7 |
| B4 | Bias needs displacement + FVG + retrace + time of day | FULL | engine | |
| B5 | Weekly first, daily main; >= 4h array alignment; 15m bellwether; news-day top-down | FULL | `topdown`, `topdown_min`, `conf_min_top` (all off) | |
| B6 | Daily institutional order flow score | MISSING | - | B-1 |
| B7 | Daily OB MT close rule; a close below 50% of the last down-close daily candle = high of week in | SIMPLIFIED | strategy.weekly_bias (Ep 05 one-week case) | B-2 |
| B8a | Flip: daily close through the last daily OB MT | MISSING | - | B-3 |
| B8b | Flip: bodies close through three daily arrays | MISSING | - | B-3 |
| B8c | Flip: weekly close below the last down-close weekly candle's low -> sells | MISSING | - | B-3 |
| B8d | Flip: daily close above Friday's high / a wick CE / a weekly wick's upper quadrant | MISSING | - | B-3 |
| B8e | Flip: Thursday trades back through the weekly open against the bias | MISSING | - | B-3 |
| B8f | Flip: stopped out above a breaker high cancels the SMT -> long rest of day | MISSING | - | B-3 |
| B9 | Not a flip: target reached (= neutral), two down days in an uptrend, a failed daily array, the Judas | MISSING | no bias state machine | B-4 |
| B10 | MWD sequential | MISSING | - | B-5 |
| B11 | Candle-pattern context: inside day/week, down-close outside day, 3 same-direction closes, NR3/NR7 | SIMPLIFIED | strategy.day_context (`inside_day`, `big_prev`, `three_*`); `three_day_rule` | Inside week, outside day, NR3/NR7, close>open variant. C-1 |
| B12 | PO3: buy at/below the midnight open, sell above; PM uses 13:30 | FULL | `use_bias` in `_scan`; levels.opens (true midnight on futures) | Variant: midnight also in the PM (B-16) |
| B13 | Weekly open (Sun 18:00 / Mon 00:00) filter | MISSING | - | B-8 |
| B14 | NWOG regime (returns = consolidation; leaves = trend); bias vs NWOG | MISSING | - | B-9 |
| B15 | ORG tell: no attempt back to the prior close within 30 min = very directional | MISSING | - | C-2 |
| B16 | No bias before the Sunday open; neither scenario -> trade from Tuesday | MISSING | - | B-10 |
| B17a | 50/50 (both sides frameable) = no trade | MISSING | - | C-3 |
| B17b | Stuck at a premium array / chop -> wait for 09:30 | FULL | AM from 09:30; pre-open windows off | |
| B17c | HTF/weekly draw delivered -> neutral, stop for the week | MISSING | - | C-3 |
| B17d | Multi-day daily range = scalping; inside a daily BISI = no trade; one-way run into HTF premium = sloppy | SIMPLIFIED | `neutral_skip` (> 2x ADR5 day only) | C-3 |
| B17e | Indices decoupled -> scalp/skip; SMT both ways with no bias -> no trade | MISSING | - | C-3 |
| B18a | SMT (ES vs NQ vs YM) as a qualifier: tag / filter | FULL | strategy._smt; `partner2`; `smt_min` | |
| B18b | SMT windows AM 05:00-09:30, PM 12:00-15:00 | MISSING | SMT checked at any sweep | B-17 |
| B18c | SMT uses: partials, instrument choice | MISSING | - | M-5, S-10 |
| B19a | DXY up = risk-off; no ES longs while DXY rallies above its range high (daily version) | SIMPLIFIED | backtest.INTERMARKET `dxy` tag | Gate. B-11 |
| B19b | ES lower low should come with a DXY higher high (intraday) | N/A | - | Needs DXY 1m (not in our data) |
| B19c | Bonds and stocks together; bonds in a range -> everything consolidates | SIMPLIFIED | `tnx` tag | Range regime. B-11 |
| B20a | COT hedging program | MISSING | - | Free CFTC download, not loaded. B-12 |
| B20b | Open interest 10-15% rule | N/A | - | No CME OI history in our data |
| B20c | Weekly Williams %R extremes | MISSING | - | B-12 |
| B21 | IPDA 20/40/60-day ranges, pools and EQ | MISSING | - | B-13, T-19 |
| B22 | Quarterly shift (context) | MISSING | - | B-14 |
| B23 | Seasonal map (road map only) | SIMPLIFIED | backtest.report `by_month` | Tag + filter. B-14 |

### 2.3 Day selection and news (N)

| ID | Rule (short) | Status | Code location | What is missing / spec |
|---|---|---|---|---|
| N1a | NFP Friday: experienced trade it after the first hour | FULL | `nfp_day=True` (AM from 09:30) | |
| N1b | No pyramiding on NFP | MISSING | `adds` on by default, no NFP exemption | M-14f |
| N2 | NFP week Wed PM / Thu / Fri: experienced trade them | FULL | `nfp_week_block=False`, `nfp_thu=True` | |
| N3a | FOMC: no trading the 14:00 release; 14:00-14:45 observe; normal after 14:45 | SIMPLIFIED | strategy.blocked `fomc_pm_from=885` (arming only) | Pending orders and open positions live through 14:00. M-13 |
| N3b | CC: FOMC AM tradeable; never hold into the release | SIMPLIFIED | AM open | Flat before 14:00. M-13 |
| N3c | FOMC-only day: AM consolidation, PM volatility | MISSING | - | Tag. W-6 |
| N3d | Day before FOMC, and FOMC week before Wed 14:00: trade light | MISSING | - | W-6 |
| N3e | Day after FOMC: sit still in the AM | MISSING | - | W-6 |
| N3f | Don't re-enter if stopped on FOMC | MISSING | `reentry_half` has no exemption | M-16 |
| N4a | CPI: no position into or at the release | FULL | AM from 09:30; `pre_flat_0830` for PRE7 | |
| N4b | Day before CPI: no trade or small bread-and-butter only | MISSING | - | W-7 |
| N5a | Any high/medium release: wait >= 30 min, then trade only with ~10 handles of room | SIMPLIFIED | AM starts 10:00 on 10:00-release days | 30-min wait; news room. W-2 |
| N5b | 09:45/10:00 releases: wait for the release, not just 09:30 | SIMPLIFIED | `NEWS_1000` tags (2026 dates only) | 2019-2025 dates. W-1 |
| N5c | No 08:30 news: wait for 09:30 | FULL | `am=(570, 660)` | |
| N5d | Two drivers in one session: stand aside / not ahead of the second | MISSING | - | W-3 |
| N5e | Fed chair testimony/speech at 10:00: no AM; trade 13:30-16:00 | MISSING | calendar not loaded (obtainable) | W-4 |
| N5f | Treasury auction day: avoid the AM | MISSING | calendar not loaded (obtainable) | W-5 |
| N6a | News: the first pool run after the release is usually false | SIMPLIFIED | `post_news` (sweep of the 08:30-09:00 range) | First-side-false logic. W-8 |
| N6b | After both pools are taken, price retraces to the CE between them | MISSING | - | W-8 |
| N6c | On NFP/CPI/FOMC days breakers reject poorly | MISSING | - | W-8 |
| N7a | Day before a long weekend / holiday: skip | MISSING | calendar.HOLIDAYS exists, unused | C-4 |
| N7b | Morning after a holiday: no trade; Tue after a Monday holiday acts like Monday | MISSING | - | C-4 |
| N7c | Holiday weeks deliver cleaner Thu/Fri | MISSING | - | Tag. C-4 |
| N7d | Last trading day of the year = inside day; first trading day: don't rush | MISSING | - | C-4 |
| N7e | Rollover week: more volatile and choppy | SIMPLIFIED | daytypes `roll_week` day_type tag | Size option. C-4 |
| N7f | August "meat grinder": trade small or stand aside, last two weeks especially | MISSING | - | C-4 |
| N8a | Consolidation = no trade, wait for expansion | MISSING | - | C-5 |
| N8b | Trending-day recipe (small prior ranges + daily array hit + 08:30 news) | MISSING | - | C-5 |
| N8c | Consolidation-day predictors and behaviour (AM scalp only if OR small, done by 11:00, PM only if no AM stop run) | MISSING | - | C-5 |
| N8d | Large ORG or very large prior range: sacrifice the AM, trade 13:30-16:00 | MISSING | - | C-5 |
| N8e | Prior range > 2x ADR5: skip; < ADR5: expansion due | SIMPLIFIED | `neutral_skip` (`big_prev`) | Expansion-due tag. C-5 |
| N8f | Seek & destroy: don't hold trades | MISSING | - | [our interpretation] C-5 |
| N9a | No draw / inefficiency / displacement -> no trade | FULL | engine requires all three | |
| N9b | Draw delivered before 09:30 -> choppy 09:30, trade the PM | MISSING | - | C-6 |
| N9c | Daily objective done before lunch -> skip the rest | MISSING | - | C-6 |
| N9d | Overnight range too narrow or pre-09:30 raid too shallow -> no AM | MISSING | - | C-6 |
| N9e | Macro window with no move toward the draw -> close the session | MISSING | - | C-6 |
| N9f | London already made ~80% of ADR5 -> skip NY | MISSING | - | C-6 |
| N10a | Don't trade the Sunday open | FULL | no evening session in the engine | |
| N10b | Mondays (experienced: trade them) | FULL | `skip_monday=False` | |
| N10c | Tue/Wed ideal; Thu reverses; weekly H/L Mon-Wed ~70%; Thu/Fri break of Mon-Wed = expansion | SIMPLIFIED | `Trade.weekday` tag | Stats and the Thu/Fri expansion tag. C-7, C-11 |
| N10d | Friday: small unless weekly objective unmet; most at the first pool; no trade after targets met; don't buy after a strong Thursday | MISSING | - | C-7 |
| N10e | No weekend holds or holds across 17:00-18:00 | FULL | `flatten=960` | |

### 2.4 Times and sessions (T)

| ID | Rule (short) | Status | Code location | What is missing / spec |
|---|---|---|---|---|
| T1 | New York clock incl. DST; time-based bars only | FULL | data in America/New_York; 1m/5m bars | |
| T2 | Opens: midnight, 08:30, 09:30, 13:30; after a release, retrace bodies stop at the 08:30 open | SIMPLIFIED | levels.opens | 08:30-open uses (stop / level). W-9 |
| T3 | Kill zones; for indices only the London 02:00-05:00 H/L matters (pool) | FULL | DayCtx.sess["london"]; `extra_pools=True` | Asia 20:00-00:00 is fx-only |
| T4a | Opening range 09:30-10:00: don't trade it; exception: price already deep in discount | SIMPLIFIED | `am=(570, 660)`; `or_minutes=30` (pool only) | `or_no_entry` switch. C-8 |
| T4b | CC OR60 holds the HOD or LOD; a wide OR's far end gets run | SIMPLIFIED | `or_minutes=60` variant (pools/targets) | Wide-OR rule. C-8 |
| T5 | NY AM session window | FULL | `Params.am` | |
| T6 | SB windows 10-11, 14-15, 03-04; also 15-16 and optional 07:00-08:30; entry inside the window | SIMPLIFIED | `sb_windows`, `sb_london` | 15-16 and 07:00-08:30 windows. SB-13 |
| T7a | Macros as timing windows (tags) | FULL | `MACROS`; `Trade.macro_win`, `macro` | |
| T7b | Macro behaviours: lunch macro runs the stops protecting the AM move; 14:50-15:10 swing start; MOC runs untaken liquidity, nothing if the HTF target is hit; a macro fails once the day's run is done | MISSING | - | S-15, S-2 |
| T8a | Lunch: experienced may trade it | MISSING | no lunch window (AM to 11:00, PM from 13:30) | C-9 |
| T8b | Lunch runs trailed AM stops; an AM draw not reached by lunch carries to the PM | SIMPLIFIED | `am_exit=720` closes AM leftovers | Carry the AM draw into the PM. C-9 |
| T9a | PM session 13:30 (or 14:00) to the close | FULL | `pm=(810, 950)` | |
| T9b | Divided day: bad AM -> back at 13:45; nothing by 14:30 -> skip the PM | MISSING | - | C-10 |
| T10a | No setup by 10 min before the close -> no trade | FULL | `pm` end 950 | |
| T10b | No clear setup: wait to 15:40-15:45 for a 5-8 (to 10) handle run | MISSING | - | S-2 |
| T10c | Pool taken before 15:50 -> flurry then pullback | MISSING | - | M-13 |
| T11a | Flat before 16:00; flat once the final level is hit | FULL | `flatten=960`; ladder last level exits all | |
| T11b | No adds or fades in the last ~15 min | MISSING | adds have no time cut-off | M-14 |
| T12 | When the day's extremes form (stats) | MISSING | - | Study script. C-11 |
| T13a | Daily PO3 / Judas | FULL | `use_bias`; `_judas` tag | |
| T13b | CC six index day profiles | MISSING | - | [our interpretation] C-12 |
| T14 | Weekly time (bulk Tue-Thu; Tue London low; 30-50% by Wed) stats | MISSING | - | Study script. C-11 |

### 2.5 Levels and draw (L)

| ID | Rule (short) | Status | Code location | What is missing / spec |
|---|---|---|---|---|
| L1a | Session pools: prev PM 13:30-16:00, London 02-05, lunch 12:00-13:30, AM 09:30-12:00, ORG | SIMPLIFIED | DayCtx.sess, `am_hl`, `extra_pools` | Previous day's AM range (09:30-12:00) pool. E-15 |
| L1b | Pool priority at 09:30: prev PM if near, else London, else prev AM | MISSING | `_scan` takes the lowest hit level | E-15 |
| L2 | Liquidity matrix (3 days + 3-day extreme); PDH/PDL first targets; needs a PD array + time; a reversal needs an HTF array + HTF order flow | SIMPLIFIED | DayCtx.pd (spent check); engine | HTF order-flow condition. B-1 |
| L3a | Previous week / month high-low as pools | SIMPLIFIED | `pool_prev_week`, `pool_prev_month` (both off) | Defaults off. T-20 |
| L3b | 20/40/60-day highs/lows as pools | MISSING | - | T-19 |
| L3c | Globex high; OR30/OR60 H/L; lunch REL/REH as PM targets | FULL | `globex_pool`, `or_minutes`, sess["lunch"], `_eq_levels` | |
| L4 | Pool quality: larger pool, 4h REL over 1h REL, pool below the leg EQ, low-resistance runs, fund stops up to 10 handles beyond | MISSING | - | T-18, M-4 |
| L5a | NWOG: Fri close -> Sun 18:00; high/low/CE; never discarded; 60 days | FULL | htf.opening_gaps, gaps_for_day(`nwog_days=60`), `gap_mode="ict"` | |
| L5b | Holiday-shortened week: ignore that NWOG | MISSING | - | D-20 |
| L5c | Quarters; halfway rule between NWOGs; a sell-side run stops at the nearest NWOG/NDOG/ORG | MISSING | - | T-13, S-7 |
| L6 | NDOG 17:00 -> 18:00, Mon-Thu, > 1 pt, through Friday, confluence only | FULL | htf.opening_gaps; gaps_for_day | |
| L7a | ORG: prior close -> 09:30; high/75/CE/25/low; 5 days; 16:15 close for ES | FULL | `org_days=5`, `org_close=975`, `_targets` | |
| L7b | ORG behaviour: 09:30 seeks the prior close; a quarter fill that holds = strength; half filled -> later the other half | MISSING | - | S-4, C-2 |
| L7c | ORGs kept ~60 days as dimmed confluence levels (092) | MISSING | - | T-14 |
| L8 | Vacuum block (event gap): 08:30 gaps fill the same day | MISSING | - | T-15 |
| L9 | FVG targets: near edge, then CE; weekly CE enough; a partly traded FVG's remainder + stops beyond = next draw | SIMPLIFIED | `htf_targets`, `fvg_targets`, `htf_far_edge` | Remainder rule; 30m timeframe. T-3, T-10 |
| L10 | Daily and weekly wick CEs as targets, partials, invalidation | SIMPLIFIED | `wick_levels` (prior day only) | T-4, M-2 |
| L11 | Cover at the old low's lowest body, not the wick | MISSING | - | T-5 |
| L12 | SD: -0.5, -1 ... beyond a broken swing; first level beyond the pool; clusters; -0.5 first partial, -1 most off; must align with pool/array/time | SIMPLIFIED | `sd_targets` (off), `sd_levels=(1..2.5)`, `sd_first_beyond` | -0.5..-4.5, clusters, alignment, anchors. T-6, M-3 |
| L13 | Breaker A-B +1x; measuring gap; ORG multiples; CC 1.27/1.62 at opposing arrays | MISSING | - | T-7 (CBDR/Asian/Flout are fx-only) |
| L14a | Decide the draw first, then trade only toward it | MISSING | - | B-6, B-7 |
| L14b | Enter at internal range liquidity, exit at external | FULL | engine | |
| L14c | Direction from the matrix: after a reaction at one side's arrays, the other side is the draw | SIMPLIFIED | `htf_bias="react"` | Part of B-6 |
| L14d | Only targets not traded through; skip exhausted arrays | SIMPLIFIED | `_targets` `seen`; DayCtx.pd spent check | Exhausted arrays. T-1 |
| L14e | Conditional draws: upper fails -> switch to lower; lower taken = spent | MISSING | - | B-15 |
| L14f | Sorted level list; mark each done | FULL | `mgmt="ladder"` | |
| L14g | Silver Bullet draw list | FULL | sb_model._arm via `_targets` | |
| L15 | Room: ~10 handles, experienced 5 | FULL | `min_draw_pts=5.0` | |
| L16 | ADR5: aim 65-70%; ADR before 10:00 -> take 80%, keep a runner | MISSING | - | T-8 |
| L17 | CC rounding toward price (2023 does not round) | MISSING | - | D-21 |

### 2.6 Models and setups (M)

| ID | Rule (short) | Status | Code location | What is missing / spec |
|---|---|---|---|---|
| M0 | One setup for life: bias, window pools, raid, MSS + FVG, any PD array, opposite pool | FULL | engine (`_scan`) | |
| M1a | MMBM/MMSM context + trigger | FULL | `_scan`; `require_htf` / `conf_min_n` | |
| M1b | Speed check: rip through the SIBI high; afterwards not below the lowest open/close of the swing low | SIMPLIFIED | `ep07_body_exit` (off) | Rip-through test E-12; default M-11f |
| M1c | First entry in the OB before the MSS (D10) | MISSING | - | E-16 |
| M1d | MM model phases | N/A | - | Context, not a trigger |
| M2a | 2022 model: sweep, MSS, FVG at >= 50% of the leg | FULL | `_scan`; `leg_pd=0.5` | |
| M2b | FVG choice: aligned with VI + OB; the higher of two allowed; else the first beyond EQ | SIMPLIFIED | `fvg_pick` | E-13 |
| M2c | 2022 stops: OB MT + 2 pts, FVG candle high, CE of the higher FVG | SIMPLIFIED | `stop_mode="ob_mt"` | E-10 |
| M2d | Pyramid only in premium; past the 25% line stop adding | MISSING | - | M-14e |
| M2e | Target sell-side below 50% of the range, larger pool | MISSING | - | T-18 |
| M2f | Three drives into failing liquidity, then MSS | MISSING | - | E-17 |
| M3a | SB windows; entry inside; FVG may be earlier; target after the window | FULL | sb_model.run_sb | |
| M3b | Displacement toward a draw chosen first; one direction | SIMPLIFIED | sb_model._arm (both sides each bar) | SB-1 |
| M3c | First FVG in the bias direction, beyond the broken level | FULL | `_arm` `g.top > ref`, newest untouched | |
| M3d | Evolving SB | FULL | `_arm` re-arm | |
| M3e | Cancel if the target trades first; a shallow 1-tick sweep is wanted | SIMPLIFIED | run_sb cancel | Shallow-sweep tag. SB-5 |
| M3f | Room 10 / experienced 5 | FULL | `sb_room_pts=5` | |
| M3g | Entry near edge; CE "worst case" for the room; 066 a little above the FVG candle high | SIMPLIFIED | entry = `g.top` | SB-4, SB-17 |
| M3h | Stops: 2 pts beyond / below c1 + OB MT / below the entry candle / above the higher FVG CE | SIMPLIFIED | stop = min(c1 low, OB MT) | SB-11 |
| M3i | London, else AM, else PM; one market | SIMPLIFIED | one per window; backtest.combine | SB-14 |
| M3j | Immediate rebalance in the window -> expect more than 5 handles | MISSING | - | SB-10 |
| M3k | Exits: layered limits; with the weekly profile aligned, keep a runner | SIMPLIFIED | `sb_mgmt`, `sb_runner` | SB-9, SB-19 |
| M3l | Skip spotty days and out-of-sync markets | MISSING | - | SB-7, SB-8 |
| M3m | Sweep optional (tag); MSS shown in nearly every example | SIMPLIFIED | `_arm` requires MSS; `swept` tag | SB-5 |
| M4a | Classic breaker entry (first return, bodies respect, stop beyond the sweep) | MISSING | - | S-1 |
| M4b | Unicorn: FVG/CE inside the breaker; add on each imbalance; accumulate before the breakout | SIMPLIFIED | unicorn preference in `_scan` | S-1 |
| M4c | Advanced breaker: A-B leg, early entry with bias, target B + (B-A) | MISSING | - | S-1 |
| M4d | Breaker pyramid: turtle-soup low, then add at the breaker retest | MISSING | - | S-1, S-7 |
| M4e | CC breaker swing vs failure swing | MISSING | - | S-1 |
| M5 | PM last hour (Ep 01 nested-FVG version; 2022 model 15:15-15:45) | SIMPLIFIED | `last_hour` tag; PM window | S-2 |
| M6 | PM reversal "2:00 macro" via IFVG | MISSING | - | S-3 |
| M7 | PM off lunch; PM 13:30 Judas | FULL | sess["lunch"] pools; `use_bias` 13:30 | |
| M8 | ORG repricing after the 09:30 Judas | MISSING | - | S-4 |
| M9 | News Judas: the first run is the losing side; FOMC real move 14:25-14:30 | SIMPLIFIED | `post_news` | W-8 |
| M10 | IFVG entry protocol (CE / near edge, depth, stop CE + 3-4 pts) | SIMPLIFIED | `ifvg_entries` | S-5 |
| M11a | Immediate-rebalance entry with a tight stop; out above range EQ | MISSING | - | S-6 |
| M11b | CISD OB entry at/below EQ of the post-CISD range | MISSING | (`mss_cisd` only changes the MSS reference) | S-6 |
| M11c | Wick-CE long after the next candle closes above the CE | MISSING | - | S-6 |
| M12a | 2023 turtle soup: external level, SMT, one PD array, no MSS | MISSING | - | S-7 |
| M12b | Turtle soup short at an old high, add on new FVGs/breakers (Ep 08) | MISSING | - | S-7 |
| M12c | CC turtle soup: limit at the old low; 1h sweep into a daily OB (1R/2R/5R); OR60 low | MISSING | - | S-7 |
| M12d | External turtle soup (pattern 2) | MISSING | - | S-7 |
| M13 | OTE 62-79% (70.5%) | MISSING | (`leg_pd=0.62` variant is only a filter) | S-8 |
| M14 | TGIF | SIMPLIFIED | strategy.day_context `tgif_*`; `tgif` (direction block) | C-13 |
| M15 | Ma Deuce | SIMPLIFIED | pre_open.run_ma_deuce; `ma_deuce` | S-9 |
| M16a | CC AM index SMT entry (buy stop above a down-close candle) | MISSING | - | S-10 |
| M16b | Sick sister | MISSING | - | S-10 |
| M16c | D15: trade the leader (or the laggard) | SIMPLIFIED | backtest.combine (first fill) | S-10 |
| M17 | London/CBDR/Asian models, OSOK, swing, stocks | N/A | - | fx-only / swing / stock models (out of scope) |

### 2.7 Entries, stops and sizing (E)

| ID | Rule (short) | Status | Code location | What is missing / spec |
|---|---|---|---|---|
| E1 | Resting limit in the array; adds/scalps at market; CC stop orders on breakers/FVGs | SIMPLIFIED | limit entries; adds as limits | Stop-order variant. E-18 |
| E2 | Entry: near edge / CE / IOFED (1 tick in, shallow touch) / ladder high-75%-CE | SIMPLIFIED | `entry="edge"` or `"ce"` | IOFED, ladder. E-7 |
| E3 | A limit fills only on 1 tick through | FULL | pending `l < entry` (futures tick); gap fills at the open | |
| E4 | Buy into down-close candles, sell into up-close | MISSING | - | E-8 |
| E5 | Don't chase; move to a newer FVG; cancel if target first; entry in window; don't enter early with a wide stop | SIMPLIFIED | pending cancel rules; `max_risk_pts` | Evolving FVG in the main engine. E-9 |
| E6a | Stop below the MT of the OB nearest the sweep low | FULL | `stop_mode="ob_mt"`; `ep07_stop` | |
| E6b | Stop beyond the FVG-forming candle / below its open and bodies | SIMPLIFIED | `stop_mode="fvg"` (= c1 high) | c2-open / bodies variant. E-10 |
| E6c | Stop beyond the sweep extreme | MISSING | - | E-10 |
| E6d | Stop beyond every nearby inefficiency and any overshoot wick | MISSING | - | E-10 |
| E6e | Not just past a level price may mohawk | MISSING | - | E-10 |
| E6f | Padding 1 tick; 3-4 pts on CE stops; NFP wider, behind HTF bodies | SIMPLIFIED | `stop_buffer=0.01` (price units: < 1 tick) | E-10 |
| E7 | Never widen a stop | FULL | stop only moves via `max()` | |
| E8 | Size = risk / stop distance | FULL | `_scan` `shares` | |
| E9 | Size down (mixed conditions) / up (BPR+FVG, near an HTF target) | MISSING | - | E-11 |
| E10 | After a loss: halve, win back ~50%, step up; never size up to recover | MISSING | (`reentry_half` 0.5x only) | E-11 |
| E11 | Caps: ~6 contracts initial, 10-16 with adds | SIMPLIFIED | `max_total_risk`, `max_notional` | Contract caps. E-11 |
| E12a | Adds decrease in size | FULL | `adds=(0.5, 0.33, 0.17)` | |
| E12b | Add on new FVG retests, down-close candles into OB/VI, breaker retests, IFVGs, next VI | SIMPLIFIED | adds at new FVG tops only | M-14b |
| E12c | Body closes into the FVG -> add once more at its low end | MISSING | - | M-14c |
| E12d | No adds after partials | FULL | `t1_done` check | |
| E12e | No adds past the 25% line of the leg or past EQ of the implied range | MISSING | - | M-14e |
| E12f | No pyramiding on NFP or low-probability / decoupled days | MISSING | - | M-14f |

### 2.8 Management and exits (X)

| ID | Rule (short) | Status | Code location | What is missing / spec |
|---|---|---|---|---|
| X1 | Target = next opposing liquidity or PD array | FULL | `_targets`; `htf_targets` | |
| X2 | Exit before arrays, just beyond pools | FULL | `exit_mode="split"`, `exit_before_pts`, `pool_beyond_pts` | |
| X3a | Scale out at each pool ("running down equity") | FULL | `mgmt="ladder"` (3 levels) | Unit-per-new-high variant M-1 |
| X3b | Bulk at the first target: 80/20 on slow / news-ahead days, 50/25/25 normal | FULL | strategy._split; `ladder_by_day`, `ladder_fracs(_slow)`, `slow_frac` | |
| X3c | A partial a little before the CE of any wick in the path; with two wicks the longer | MISSING | - | M-2 |
| X3d | -0.5 SD always a first partial; next partial halfway between the hit target and the next | MISSING | - | M-3 |
| X3e | Never the exact FVG edge; first partial at an FVG CE or a daily FVG top | FULL | `exit_mode` split; `htf_targets` CE | |
| X3f | Full pull in a low-resistance run, partials in a high-resistance run | MISSING | - | [our interpretation] M-4 |
| X3g | SMT warning (sister refuses to break) -> bank ~50% (most if YM diverges) | MISSING | - | M-5 |
| X3h | Aim to capture 80-85% of the best-case run | MISSING | - | M-6 |
| X4 | Breakeven only after the first partial and after expansion | FULL | `be_on="expansion"` (a later bar closes beyond T1) | BE + costs pad, Ep 03 variant: M-7 |
| X5a | Trail under the first breakaway FVG / the measuring gap after two rounds / each newer FVG after each partial | SIMPLIFIED | `ladder_trail="fvg"`, `"prior"`, `"hit"`; `ep07_trail` | Breakaway and measuring modes. M-8 |
| X5b | Don't trail early; never into the FVG right after the MSS | FULL | `ladder_trail="fvg"` uses only FVGs formed after the last partial | |
| X5c | A day trade keeps its initial stop; session trades trail | MISSING | - | M-8 |
| X6 | FVG abort: a body closes beyond the FVG and the next candle trades beyond it | SIMPLIFIED | `fvg_abort` (off): whole body below; any later bar | M-9 |
| X7a | Three PD arrays: body closes through all three -> exit before the stop | SIMPLIFIED | `pd3_exit` (off): own-side FVGs only | M-10 |
| X7b | Body close below the nearest VI + FVG + OB MT -> half off | MISSING | - | M-10 |
| X7c | Three arrays in a row fail -> stop for the session | MISSING | - | M-10 |
| X8a | Bodies close through a bullish FVG's CE -> close early | FULL | `ce_hold` (off: conflicts with the Ep 04 add) | |
| X8b | Retrace through the MT of the candle that started the leg | MISSING | - | M-11b |
| X8c | Immediate-rebalance trade back above range EQ -> out | MISSING | - | S-6 |
| X8d | Propulsion block MT lost -> wrong | MISSING | - | M-11d |
| X8e | Offside: bodies respect the opposing candle's open and trade back -> close | MISSING | - | M-11e |
| X8f | After the trigger, not below the lowest open/close of the swing low | FULL | `ep07_body_exit` (off) | Default: M-11f |
| X8g | Meandering inside the SIBI instead of rejecting -> close | MISSING | - | M-12c |
| X9a | Deliver within 2-3 1m candles of touching the array | SIMPLIFIED | `time_stop_min`, `time_stop_pts` (off) | M-12a |
| X9b | A 1m trade should move within ~10 min | FULL | `time_stop_min=10` variant | |
| X9c | After touching the far edge, 2 minutes to move back, else half or all off | MISSING | - | M-12c |
| X10a | Last AM unit off before noon | FULL | `am_exit=720` | |
| X10b | CC: bulk off 10:00-11:00; AM delivered the day's range -> flat before lunch, skip the PM | SIMPLIFIED | `am_exit=660` variant | Range-delivered rule. M-13 |
| X11a | Target hit by 15:00 -> done | FULL | `pm_done_by` (off; conflicts with cc10_014) | |
| X11b | Consolidation-profile PM trades exit ~14:00 | MISSING | - | M-13 |
| X12 | Session objective hit -> close everything, stop for the day | MISSING | - | M-13 |
| X13a | No reversal after a loss (experienced may reverse) | FULL | `reverse_after_loss=True` | |
| X13b | Same-direction re-entry at half risk while the idea is intact; not on FOMC | SIMPLIFIED | `reentry_half` (off; any direction) | M-16 |
| X14 | After a win (experienced keep trading) | FULL | `no_pm_after_am_win=False` | |
| X15a | Frequency caps | FULL | `max_trades_week`; one per session / window | |
| X15b | Weekly objective delivered -> done for the week | MISSING | - | C-3 |
| X16 | Journal items: range vs ADR5, last-3-day H/L taken, weekday/session of the weekly H/L, entry-array TF | SIMPLIFIED | `Trade.weekday` | C-15 |

### 2.9 Appendix A bullets (Ep 01-08)

Most bullets restate a section-2 rule; "maps to" names it. These rows are counted separately
(summary row "Appendix").

| ID | Bullet (short) | Status | Maps to / code | Spec |
|---|---|---|---|---|
| Ep01.1 | BSL/SSL definitions | SIMPLIFIED | A2 | E-1 |
| Ep01.2 | FVG, CE | FULL | A5a | |
| Ep01.3 | Liquidity void | SIMPLIFIED | A10 | D-10 |
| Ep01.4 | BPR: price should not re-enter | MISSING | A11 | D-11 |
| Ep01.5 | Breakaway gap expected to stay open | MISSING | A6 | D-6 |
| Ep01.6 | Breaker on bodies | SIMPLIFIED | A13 / `breaker_zone="body"` | S-1 |
| Ep01.7 | Narrative is separate from bias | N/A | not a trading rule | |
| Ep01.8 | Low-volatility day (last of year) = inside day; Monday refers to Friday's range | MISSING | N7d | C-4 |
| Ep01.9 | Year end reprices to buy-side | MISSING | tag | C-17 |
| Ep01.10 | AM 08:30-11:00; PM 14:00-16:00, focus 15:00-16:00 | FULL | `am`, `pm` | |
| Ep01.11 | PM setup window 15:15-15:45; none by 15:50 -> no trade | FULL | `last_hour` tag; `pm` end 950 | |
| Ep01.12 | AM loss -> no reversal (experienced may) | FULL | X13a | |
| Ep01.13 | A last-hour run to an old high/low/imbalance nearly every day | MISSING | T10b | S-2 |
| Ep01.14 | Mark the draw (old high/low, REH/REL, imbalance) | FULL | `_targets` | |
| Ep01.15 | Nested 4h/1h/15m/5m FVGs; bodies refuse to close beyond | SIMPLIFIED | `entry_tf="nested"`, `require_htf` | S-2 |
| Ep01.16 | Last hour should hold above the 4h FVG midpoint | MISSING | - | S-2 |
| Ep01.17 | Trigger: bodies refuse to close through the 60m FVG low end, then a breakaway FVG; move started by ~15:25 | MISSING | - | S-2 |
| Ep01.18 | Entry at the top of the 1m FVG; add on retests and on a breaker | SIMPLIFIED | edge entry; FVG adds | M-14b |
| Ep01.19 | Dip into the breakaway gap -> buy, stop below the bodies | MISSING | - | S-2 |
| Ep01.20 | Stop below the FVG candle open, later below bodies, trailed | SIMPLIFIED | E6b, X5 | E-10, M-8 |
| Ep01.21 | Target the pool; a nearer short-term high as intermediate; ~5 handles | FULL | ladder | |
| Ep01.22 | Clean delivery: few small down-close candles | MISSING | quality tag | S-2 |
| Ep02.1 | 09:45 release: wait for it | SIMPLIFIED | N5b | W-1 |
| Ep02.2 | AM short: BSL run, MSS, short FVG/OB/breaker; adds on later FVGs | SIMPLIFIED | engine (FVG only) | S-1, E-6 |
| Ep02.3 | OB MT measured high to low (wicks) | FULL | `mt_mode="range"` variant | |
| Ep02.4 | CE = 50% of the FVG, MT = 50% of the OB | FULL | Zone.mid, `ob.mt` | |
| Ep02.5 | Targets 15m/30m FVGs + sell-side; partials at each; runner while "heavy" below the 30m FVG | SIMPLIFIED | `htf_targets` (no 30m); ladder | T-10, M-8 |
| Ep02.6 | No daily breakout / no HTF narrative -> scalp only | MISSING | - | C-16 |
| Ep02.7 | First trading day of the year: don't rush | MISSING | N7d | C-4 |
| Ep02.8 | Top-down from the daily VI; daily VI as the draw | SIMPLIFIED | confluence has no VIs | T-10 |
| Ep02.9 | FVG left open on the way down = breakaway | MISSING | A6 | D-6 |
| Ep03.1 | NFP week Mon-Wed AM only (experienced: all days) | FULL | N2 | |
| Ep03.2 | FOMC: don't trade the release | SIMPLIFIED | N3a | M-13 |
| Ep03.3 | VI; daily-chart draw | SIMPLIFIED | A9 | D-9, T-10 |
| Ep03.4 | BISI / SIBI | FULL | levels.fvgs | |
| Ep03.5 | Measuring gap: project the target | MISSING | A6 | D-6, T-7 |
| Ep03.6 | IOFED: shallow dip short of CE | SIMPLIFIED | E2 | E-7 |
| Ep03.7 | Reclaimed OB (loose usage: OB retested as support) | N/A | descriptive | |
| Ep03.8 | OB anchored on the down-close candle's high or open | SIMPLIFIED | A12a | D-12 |
| Ep03.9 | First FVG after the shift = breakaway, protected; trail under it | SIMPLIFIED | X5a | M-8 |
| Ep03.10 | Trade the stronger index for longs | SIMPLIFIED | M16c | S-10 |
| Ep03.11 | MMBM: HTF draw above, price in a 5m OB / 1m BISI discount | FULL | M1a | |
| Ep03.12 | STL taken, STH broken (MSS) leaving an FVG | FULL | `_scan` | |
| Ep03.13 | BE after buy-side is run; pyramid on new FVGs | SIMPLIFIED | X4 variant | M-7 |
| Ep03.14 | Large candles turning small -> large candles in the bias direction next | N/A | descriptive | |
| Ep03.15 | Scale out one contract per new high near each pool | SIMPLIFIED | X3a | M-1 |
| Ep03.16 | Trail under the latest measuring gap after two rounds of partials | SIMPLIFIED | X5a | M-8 |
| Ep03.17 | Never widen a stop | FULL | E7 | |
| Ep03.18 | Final target an HTF PD array; accept the last units stopped | SIMPLIFIED | ladder caps at 3 levels | M-1 |
| Ep03.19 | Last contract off before noon | FULL | `am_exit=720` | |
| Ep03.20 | One good setup a week; 5-handle target | FULL | `max_trades_week` variant; L15 | |
| Ep03.21 | Time-based charts only | FULL | T1 | |
| Ep04.1 | NFP Friday (experienced: after the first volatility) | FULL | N1a | |
| Ep04.2 | Midnight open = true open; PO3 | FULL | B12 | |
| Ep04.3 | After news: the post-manipulation range is the framework; expansion to ERL | SIMPLIFIED | `post_news` | W-8 |
| Ep04.4 | MSS while the FVG stays open; enter near the midnight open | FULL | engine + `use_bias` | |
| Ep04.5 | Two MSSs with open FVGs = on side | MISSING | A19c | E-4 |
| Ep04.6 | IOFED ~1 tick into the FVG | SIMPLIFIED | E2 | E-7 |
| Ep04.7 | Pyramid 6/3/2/1; no adds after partials | FULL | E12a/d | |
| Ep04.8 | Closes into the FVG -> add at its low end | MISSING | E12c | M-14c |
| Ep04.9 | Smooth REH/REL are magnets | SIMPLIFIED | A3 | D-2 |
| Ep04.10 | Targets REH -> old daily highs -> daily VI; bulk (10 of 12) at the first | SIMPLIFIED | ladder; no daily VI | T-10 |
| Ep04.11 | Target hit by 15:00 -> be done | FULL | `pm_done_by` (off) | |
| Ep04.12 | SMT ES vs MES | N/A | same index | |
| Ep05.1 | Bearish breaker; MT and CE as reaction levels | SIMPLIFIED | A13 | S-1 |
| Ep05.2 | No 08:30 news -> wait for 09:30 | FULL | N5c | |
| Ep05.3 | NWOG as a target | FULL | L5a | |
| Ep05.4 | Unicorn: buy the FVG/CE in the breaker; add on each imbalance | SIMPLIFIED | M4b | S-1 |
| Ep05.5 | Accumulate inside the breaker before the breakout | MISSING | M4b | S-1 |
| Ep05.6 | MMSM: rally into REH, MSS, sell when price fails to reach the imbalance CE | FULL | engine, edge entry | |
| Ep05.7 | Weekly bias after a strong down day (that week) | FULL | `weekly_bias` | |
| Ep05.8 | Watch one market | FULL | backtest.combine | |
| Ep05.9 | Stop just below the FVG high when away from the screen | N/A | personal | |
| Ep06.1 | Kill zones (NY time) | FULL | T3 | |
| Ep06.2 | Trending-day template: LOD London, HOD London close, noon reversal | N/A | fx-leaning; the index version is T13b | |
| Ep06.3 | Retrace into a SIBI often stops at CE | SIMPLIFIED | A5f | D-4 |
| Ep06.4 | SD projection on the manipulation swing, after its high is taken | SIMPLIFIED | L12 | T-6 |
| Ep06.5 | DXY bearish = risk-on | SIMPLIFIED | B19a | B-11 |
| Ep06.6 | Midnight open as the reference | FULL | B12 | |
| Ep06.7 | REH/REL preferred pools | SIMPLIFIED | A3 | D-2 |
| Ep07.1 | An old daily close can be the draw | MISSING | - | T-9 |
| Ep07.2 | Wait for 09:30; sell-side purged; buy inside the FVG/VI near its midpoint | SIMPLIFIED | `entry="ce"` (VI entry missing) | E-14 |
| Ep07.3 | Stop below the body MT of the down-close candle nearest the sweep low | FULL | `ep07_stop`; `mt_mode="body"` | |
| Ep07.4 | Trail to the retracement low after bodies clear the prior swing high | FULL | `ep07_trail` | |
| Ep07.5 | VI should hold; stop at its low | SIMPLIFIED | A9 | E-14 |
| Ep07.6 | Pyramid on down-close candles into OB/VI; take profit on up-close candles | MISSING | E12b, E4 | M-14b, E-8 |
| Ep07.7 | Speed and distance through the trigger | SIMPLIFIED | A20 | E-12 |
| Ep07.8 | Not below the lowest open/close of the swing low | FULL | `ep07_body_exit` | |
| Ep07.9 | Macro 09:50-10:10 | FULL | T7a | |
| Ep07.10 | Bulk (9 of 14) at the target; risk 1-1.3% | FULL | X3b; E8 | |
| Ep07.11 | Think in 5-handle increments | N/A | expectation | |
| Ep08.1 | Daily wick 50% is a key level; daily FVG edges hit to the tick | SIMPLIFIED | L10 | T-4 |
| Ep08.2 | Neutral: wait for 09:30; chop = 2.5-5 handle scalps | SIMPLIFIED | B17b (scalp mode missing) | C-16 |
| Ep08.3 | Three opens; bearish sells above the open | FULL | B12 | |
| Ep08.4 | MSS validity = the parent swing; liquidity run first | SIMPLIFIED | A19a | E-3 |
| Ep08.5 | Bearish OB = up-close series; return to the open; next wick stops at its MT | SIMPLIFIED | A12a | D-12 |
| Ep08.6 | PM 13:30 Judas; last hour at old daily highs/lows | FULL | `use_bias` 13:30 (last-hour model: M5) | S-2 |
| Ep08.7 | FVG at or above 50% of the swing | FULL | `leg_pd` | |
| Ep08.8 | Exit 0.5-1 pt before an FVG; first partial at FVG CE / daily FVG top | FULL | X2, X3e | |
| Ep08.9 | Measured move | MISSING | L13 | T-7 |
| Ep08.10 | Liquidity matrix | FULL | L2 | |
| Ep08.11 | An old daily low alone is not an entry | FULL | engine | |
| Ep08.12 | 6 contracts building to 10-16; after a losing day no max size | SIMPLIFIED | E11, E10 | E-11 |
| Ep08.13 | IOFED needs only a touch of the gap's candle | SIMPLIFIED | E2 | E-7 |
| Ep08.14 | Turtle soup plan at an old high | MISSING | M12b | S-7 |
| Ep08.15 | Multi-TF shift: 1m breaks 5m equal lows, then the 5m FVG | SIMPLIFIED | `entry_tf="5m"` (no 5m equal lows) | E-15 |
| Ep08.16 | Stops one tick beyond; ~10 handles before engaging fully | SIMPLIFIED | E6f (room is FULL) | E-10 |

### 2.10 Section 3 decisions (D1-D23)

| ID | Decision | Status | Param today | Missing |
|---|---|---|---|---|
| D1 | AM start 09:30 vs 10:00 | FULL | `am` | `or_no_entry` variant C-8 |
| D2 | SB as its own setup; FVG in window; room 5/10; evolving | SIMPLIFIED | `sb_model`, `sb_room_pts`, `sb_only` | `sb_fvg_in_window` SB-2 |
| D3 | MSS close vs wick | FULL | `mss_mode` | |
| D4 | MT body vs range | FULL | `mt_mode` | |
| D5 | Exit split | FULL | `exit_mode` | |
| D6 | Breaker zone body / range / leg | SIMPLIFIED | `breaker_zone` | "leg" mode S-1 |
| D7 | PM window; pm_sb / last-hour tags | FULL | `pm`; setup tags | |
| D8 | News blocks (experienced) | FULL | `nfp_day`, `nfp_thu`, `fomc_pm_from` | `skip_post_fomc_am` W-6 |
| D9 | CPI | SIMPLIFIED | `skip_cpi` | `pre_cpi` W-7 |
| D10 | Early OB entry | MISSING | - | E-16 |
| D11 | Entry edge / CE / IOFED | SIMPLIFIED | `entry` | IOFED E-7 |
| D12 | Leg P/D + add cut-off | SIMPLIFIED | `leg_pd` | `add_cutoff` M-14e |
| D13 | First partial size | FULL | `ladder_fracs`, `ladder_by_day` | |
| D14 | BE / trail | FULL | `be_on`, `ladder_trail` | breakaway trail M-8 |
| D15 | Leader vs laggard | MISSING | - | S-10 |
| D16 | AM exit / PM done by 15:00 | FULL | `am_exit`, `pm_done_by` | |
| D17 | Pivot size | FULL | `pivot_n` | |
| D18 | Re-entry half | SIMPLIFIED | `reentry_half` | M-16 |
| D19 | Frequency | FULL | `no_pm_after_am_win`, `max_trades_week` | |
| D20 | Mondays | FULL | `skip_monday` | |
| D21 | NWOG / ORG definitions and lifetimes | SIMPLIFIED | `gap_mode`, `nwog_days`, `org_days`, `org_close` | 60-day ORG levels T-14; holiday NWOG D-20 |
| D22 | Real midnight open | FULL | futures data (levels.opens) | |
| D23 | SD anchor | SIMPLIFIED | `sd_targets` | `sd_anchor`, -0.5..-4.5 T-6 |
