# Swing version of the ICT model: spec (draft 1, 2026-10-18)

Source: the 2016-17 Core Content notes in /mnt/project-files/mentorship/laptop/mentorship/notes/
(cc05 = Month 5 long-term/position, cc06 = Month 6 swing, cc07 = Month 7 short-term / One Shot One
Kill), plus the 2023 rules already in mentorship_rules.md where they overlap. Timestamps refer to
those notes. ICT taught all three months on forex and metals; everything marked
**[our interpretation]** is the closest exact rule for ES/NQ futures, since he gives no index
version. Standing rules apply: exact ICT rules in full detail, experienced version default,
2023 beats older videos, closed candles only, bodies decide and wicks sweep, every alternative a
switch tested against the default.

## 0. Which ICT model is "the swing version"

ICT has three multi-day horizons. Mase's idea (1h/4h/daily bars, multi-day holds, previous week's
high/low as targets) is closest to Month 7, so that is the default model. The other two are
switches in the same code.

| `model` | ICT source | Hold | Find setups on | Execute on | Target |
|---|---|---|---|---|---|
| `osok` (default) | Month 7, One Shot One Kill | 1 day to 1 week (cc07_001 ~01:14, cc07_005 ~22:29) | monthly, weekly, daily, 4h | 1h (never below; cc07_006 ~18:30) | opposing PD array one timeframe lower; the week's projected range |
| `swing` | Month 6 swing model | 2 weeks to ~1 month (cc06_001 ~0:31, cc06_004 ~30:07) | monthly, weekly, daily | 4h (cc06_001 ~4:49, cc06_006 ~4:57) | next opposing monthly/weekly PD array |
| `position` | Month 5 position trade | 2-4 months (cc05_018 ~3:32) | monthly, weekly, daily | daily (cc05_016/017) | weekly/monthly PD array objective |

`position` gives 2-3 trades a year (cc05_013 ~24:12), about 20 in 2019-26, so it is built but
reported only as a curiosity.

## 1. Data and bars

- ES front-month 1-minute bars (Databento, Jan 2019 - Oct 2026; from the "Cloud backtesting
  setup" thread). Levels and round numbers use native front-month prices (owner directive #13);
  P&L uses back-adjusted continuity across rolls.
- Bars are built from the 1m data [our interpretation, CME session]:
  - **1h**: clock hours.
  - **4h**: blocks anchored at the 18:00 ET Globex open: 18-22, 22-02, 02-06, 06-10, 10-14,
    14-17 (the last is 3h because of the 17:00-18:00 halt).
  - **Daily**: 18:00 ET to 17:00 ET, dated by the session's end day.
  - **Weekly**: Sunday 18:00 ET to Friday 17:00 ET. **Monthly**: calendar month of daily sessions.
- Trading days for 20/40/60 counts are exchange sessions (mentorship/calendar.py), not calendar
  days (cc05_001 ~22:42, cc05_003 ~1:23:20).
- A bar is usable only after it closes (closed candles only). Every array keeps the bar it became
  known on (mentorship/levels.py `Zone.i`).

## 2. IPDA data ranges (time)

- **Default (later lessons, cc06_008 ~12:40, cc07_004 ~00:00:09):** look back 20, 40 and 60
  trading days from today, rolled forward every day. Near-term = 20, short-term = 40,
  intermediate-term = 60 (cc05_004 ~26:48).
- In each window: the highest high (buy stops above) and lowest low (sell stops below)
  (cc05_003 ~27:50); the unfilled FVGs and liquidity voids (fair-value targets); the 50% of each
  window (equilibrium) (cc05_003 ~17:12).
- If every PD array in the 20-day range has been traded to, move out to 40, then 60
  (cc06_008 ~12:40). If the 20-day low (high) is violated, the next target is the next lower low
  (higher high) in the 40-day, else the 60-day window (cc07_004 ~00:07:00).
- **Expansion:** if every 20/40/60-day high and low has already been run, expect a fast move to
  the nearest older high/low just beyond 60 days (cc05_003 ~28:38).
- **Range day:** price near the 50% of the 20/40/60-day ranges with both sides already run =
  expect a range until high-impact news (cc05_003 ~1:18:26). Tag; with `range_skip=True` no new
  entries.
- The 60-day high and low are the overbought/oversold levels; no indicator (cc05_003 ~1:55:26).
- Switch `ipda_anchor="month"` (cc05_001 ~21:48, cc05_003 ~19:15): anchor on the first trading
  day of the month of the most obvious daily structure shift of the last ~3 months, look back and
  cast forward 20/40/60 days from it. Cast-forward days are a tag only (a turn is expected within
  each window, +/- 2 days; cc05_003 ~29:30).

## 3. PD array matrix (price)

- Arrays, on monthly, weekly, daily, 4h and 1h bars, from the existing detectors in
  mentorship/levels.py (not edited): order blocks (`order_block_blend`), FVGs (`fvgs`), liquidity
  voids (`voids`), breakers (`breakers`), mitigation blocks (`mitigation_blocks`), rejection
  blocks (`rejection_blocks`), old highs/lows (`pivots`, `swing_tiers`).
- **Order, from market price outward** (cc05_014 ~18:20, cc07_004 ~00:01:01): mitigation block,
  breaker, liquidity void, FVG, order block, rejection block, old high/low. The slides put FVG
  before void; the spoken order (void first) is the default [conflict inside ICT; switch
  `matrix_order="slide"`].
- **Breaker precedence:** a breaker between price and a void/FVG/OB stops price before them
  (cc05_014 ~21:04). With no breaker, the void and gap fill on the way to the OB (~28:47).
- Order block levels: the open and the high (bullish; low and open bearish) of the last down-close
  (up-close) candle(s); a series of same-colour candles blends into one block; the OB high is the
  "fair" level, the open the conservative one (cc06_004 ~13:07, ~18:12; cc05_015 ~16:46). A small
  candle whose body sits inside a bigger one is not its own OB (cc06_005 ~19:02).
- Mean threshold of multi-candle OBs: bodies only in Months 5-7 (cc06_005 ~5:45, cc07_004
  ~00:10:02), full range in the 2023 Ep 02. 2023 wins, so default `mt="range"`, switch
  `mt="body"`.
- **Exhausted arrays:** an array price already traded into and reacted from is used up; use the
  next one (cc07_004 ~00:04:00). Prefer arrays not yet traded to (cc07_005 ~23:13).
- **Dealing range and premium/discount:** fib from the dealing-range low to high with levels 0,
  0.2, 0.3, 0.5, 0.8, 0.9, 1 (cc06_004 ~31:39). Below 0.5 = discount, above = premium; 0.3 deep
  discount, 0.2 deepest; 0.8 deep premium, 0.9 very expensive. Dealing range = the most recent
  swing from an old high to an old low on that timeframe (cc05_014 ~17:34) [our interpretation:
  the last intermediate-term swing high and low from `swing_tiers`].
- For `osok` the range is the 60-day **body** range graded into halves, quadrants and eighths
  (cc07_005 ~3:10-14:14). Best longs in the lower half and lowest quadrant; best shorts in the top
  quadrant; the middle chops (~18:21, ~22:50). Grade levels are magnets: a level traded straight
  through targets the next grade (cc07_006 ~13:53).

## 4. Higher-timeframe bias: the MWD sequential

- A timeframe is **bullish** once a discount array there "induced buying": price displaced higher
  off it (cc06_004 ~1:02). Bearish mirrors it (cc06_005 ~0:46). [our interpretation: the last
  structure break on that timeframe was a body close above a swing high, leaving an FVG
  (displacement), and no bearish breaker has formed since.]
- A correcting timeframe keeps its bullishness; only a bearish breaker cancels it (cc06_004
  ~14:47). [our interpretation of "correcting": the latest closed bar is below the last up-move's
  OB, or a lower swing low has printed since the break.]
- Cases (cc06_004 ~2:31-7:36; cc06_005 ~1:34-3:40), bullish shown, bearish mirrored:
  - **A** monthly, weekly, daily bullish: buy every daily and 4h discount array.
  - **B** monthly + weekly bullish, daily correcting: buy daily arrays only at or nested inside a
    weekly discount array; 4h arrays only at daily and/or weekly arrays. Skip if the daily made a
    higher high, was rejected and broke structure (bearish breaker forming).
  - **C** monthly bullish, weekly + daily correcting: buy daily arrays only at or nested in a
    monthly discount array; 4h at weekly and/or monthly. Skip if the weekly formed a bearish
    breaker.
- Direction is the monthly/weekly direction only; no top or bottom picking (cc06_001 ~6:51).
- Market filter (cc06_001 ~2:36, ~5:29): skip when the monthly and weekly are in an obvious
  trading range, or price barely moved over the last 3 months. [our interpretation: the last 3
  monthly bars sit inside one 60-day range of < 1x the 60-day average weekly range, tag
  `lethargic`; switch `skip_lethargic`.]
- Two stop-outs in a row on with-trend signals = the trend is tiring, an intermediate-term shift
  is near (cc06_001 ~8:51). Tag; switch `pause_after_2_losses`.
- Daily bias inputs from the intraday bot (B6-B21, project memory) carry over unchanged as tags.

## 5. Model `osok` (default): One Shot One Kill

Procedure (cc07_008 ~6:20-10:10), with the parts that need data we do not have marked:
1. Current or next **quarterly shift** (a daily structure shift every 3-4 months; cc05_003 ~15:57).
2. HTF PD arrays inside the 20/40/60-day IPDA ranges (section 2-3).
3. Rate differentials / bond market: forex only, skipped.
4. Seasonals: only when long- and short-sample lines agree (cc05_011 ~4:01). No ES seasonal is
   given by ICT; tag `seasonal` from our own 15y vs 20y+ ES composite, off as a filter.
5. Swing analysis HTF down to 1h: classify impulse / retracement / expansion.
6. Weekly profile (section 5b). 7. The weekly Judas swing that goes with it.
8. Premium and discount ranges (section 3). 9. Volatility: enter when the market is quiet so a
   large range can follow (inside bar or smallest range of the last 3 or 7 days, judged on bodies;
   cc06_007 ~21:24). Tag.
10. COT and open interest: no data, skipped (tag later if Mase wants CFTC data).
11. Low-resistance liquidity run: sell at a premium array paired with a discount array target, no
   opposing arrays between (cc07_008 ~9:26).
12. Fib levels must converge with the opposing PD array (section 5c).
13. Intermarket: ES/NQ/YM SMT as a qualifier only (project memory), not a gate.

**5a. Direction and target pairing.** Direction from the active monthly (or weekly) PD array;
target = the opposing PD array one timeframe lower: monthly premium -> weekly discount; weekly
premium -> daily discount; daily -> 4h (cc07_001 ~09:29, cc07_003 ~00:02:40). If price already
left the monthly array, trade from weekly, daily or 4h arrays in the same direction, still aiming
at the weekly opposing array (cc07_001 ~17:28). No OB/breaker/void/FVG in the target direction ->
use a rejection block or old high/low (cc07_001 ~11:25).
- **Previous week's high/low (Mase, 2026-10-16):** the prior week's high (buy stops) and low (sell
  stops) are liquidity pools (rulebook L3) and count as old high/low targets in the matrix. Switch
  `target="prev_week"` makes the opposite prior-week extreme the only target, to test Mase's
  version against ICT's array pairing.

**5b. Weekly profiles** (cc07_002, cc07_003). Bias first, then only same-direction profiles.
Bullish shown, bearish mirrored:
- Classic Tuesday low of week: Monday hovers above an HTF discount array without reaching it,
  Tuesday drops into it in London (02:00-05:00 ET) or NY (08:30-11:00 ET) and forms the week's
  low; high Thursday, small Friday pullback.
- Wednesday low of week: Mon-Tue hover above the array (may both be down days), Wednesday drives
  into it; rally into Friday.
- Consolidation Thursday reversal: Mon-Wed range, Thursday runs the intra-week low on a 14:00 ET
  rate release (FOMC) or 08:30 employment data, then runs the week's buy stops. ICT: very small
  size, limit below the Mon/Tue low after the knee-jerk (cc07_003 ~00:24:00). Default
  `thursday_reversal="small"` (0.25x risk) [our interpretation of "very small"].
- Consolidation midweek rally: Mon rally, Tue-Wed retrace into a discount FVG/void/OB, Wednesday
  news, expand through the intra-week high into Friday; only when price recently rallied off a
  discount array and has not reached the HTF premium array.
- Wednesday weekly reversal: Mon-Tue consolidate, Wednesday news drives below an old low into an
  HTF discount array at a long/intermediate-term low, then a strong reversal.
- Intraweek reversal (cc07_007): Mon/Tue range far above the 5-day ADR into an HTF array ->
  expect a Wed/Thu reversal back to the price-balanced range. [our interpretation: Mon+Tue range
  > 2x ADR5.] The higher-timeframe model wins when models disagree.
- **Seek & Destroy Friday**: Mon-Thu consolidation with shallow raids both ways; in weeks with a
  rate announcement or NFP, and in July-August. Avoid (cc07_003 ~00:33:00). Default
  `skip_seek_destroy=True` [our interpretation of the real-time test: in a FOMC or NFP week, or a
  July/August week, if Monday + Tuesday together ranged less than 1x ADR5, take no Wednesday
  entries].
- Weekly lows (bullish) form Mon-Wed about 70% of the time (cc07_008 ~1:35); 30-50% of the
  week's range is done by Wednesday's London close (cc07_006 ~23:35). Entries are Monday 00:00
  ET to Wednesday 17:00 ET by default; `entry_days="mon_wed"|"any"`.
- If Mon-Wed was missed, do not chase a big Thursday/Friday move (cc07_006 ~24:29).
- **Mon-Wed break:** in a bullish week, trading through the Mon-Wed high on Thu/Fri confirms
  aggressive expansion to the target; it may carry into next week, so the bias holds into next
  week (cc07_001 ~42:44). "Traded through" = wick. Mon-Wed range starts at the Sunday 18:00 ET
  open (ICT allows Sunday or Monday; switch `week_start="monday"`).

**5c. Entry.** On the 1h chart at weekly/daily/4h PD arrays inside a kill zone (London 02:00-05:00
ET or NY 08:30-11:00 ET; ICT prefers NY for indices), Mon-Wed (cc07_001 ~27:49).
- Order type by array (cc06_008 ~14:20): breaker, mitigation block, void, FVG -> stop order (buy
  stop as price trades back up through it); order block, rejection block, beyond an old low ->
  limit order. 2023 rule E1 says limits only, so default `order="by_array"` (CC, specific to
  multi-day trades) with switch `order="limit"` [2023 vs CC conflict on scope: the 2023 rule is
  for intraday; this spec keeps CC for multi-day holds].
- Limit price: OB high (fair) default, `ob_entry="open"` switch. Stop order: 1 tick through the
  array's far edge [our interpretation].
- Scale in (cc07_008 ~29:33): a small first piece Monday, add if Tue/Wed fail to make a higher
  high (short) / lower low (long). Default 1/2 first, 1/2 add at the close of the first later
  Mon-Wed session that fails to extend past the entry session's extreme, same stop
  [our interpretation; ICT gives no sizes].
- **Fib convergence:** the target array must overlap a 1.27 or 1.68 extension (or a 100%
  symmetrical swing) of the early-week swing: from the intra-week extreme (fulcrum) to the
  Tue/Wed retracement extreme, projected beyond the fulcrum (cc07_003 ~00:27:01). Tolerance
  [our interpretation]: 0.25x ADR5.

**5d. Stop.** ICT gives none for OSOK. Default [our interpretation]: beyond the swing that swept
the liquidity into the entry array (cc06_004 ~21:17 "beyond the sell-side liquidity, not right
under the level"), plus 1 tick: the nearest known 1h swing low below the array (stop entries: the
low made inside the array before the trigger). Never closer than 0.25x ADR5 to the fill
(`min_stop_adr`) [our interpretation]. Switch `stop="array"`: 1 tick beyond the entry-TF OB candle's
extreme (cc06_006 ~23:18).

**5e. Exits.** Partials at each opposing PD array on the way, a runner held to the full weekly
objective (cc07_001 ~08:54). Hold to Thursday NY / Friday (cc07_003 ~00:13:02). Default exits:
1/2 at the first 4h/1h opposing array, 1/4 at the next, 1/4 at the weekly objective. Anything
open at Friday 16:00 ET closes, unless the Mon-Wed break fired (then the bias holds into next
week and the trade may carry; switch `carry_weekend`). Management in section 7.

## 6. Model `swing`: Month 6 swing model and the Million Dollar Swing Setup

- **Setup sequence** (cc06_003 ~12:43): HTF bias -> impulse swing with displacement from a point
  of origin -> wait for the retracement -> enter during the retracement -> profit on the
  expansion. Don't chase the impulse.
- **12 steps** (cc06_003 ~18:41-22:54): 9-18 month monthly/weekly profile (prefer a market leaving
  a consolidation with displacement); monthly arrays, weekly, daily, then 4h, each transposed down;
  buy every 4h discount array inside the impulse range (point of origin to the intermediate-term
  high); scale out at daily, weekly and monthly premium arrays.
- **Frame at monthly/weekly levels only:** entry level and objective both from monthly/weekly PD
  arrays (cc06_006 ~0:58). Target = the first opposite-side PD array on the monthly chart in
  matrix order (cc06_006 ~2:54).
- **Minimum 3:1** to the closest opposing array on any timeframe (cc06_003 ~22:25; cc06_002
  ~12:34); ICT prefers 5:1.
- **Entry** on 4h with the January entries (cc06_006 ~5:59): stop at the open of the last
  opposite-colour closed candle (cc05_016), limit at its close (cc05_017), or by array type
  (cc06_008). Default `by_array`.
- **4h confirmation:** after the bounce, a new 4h higher high; if it fails, wait for the next
  lower (daily) level (cc06_004 ~21:34).
- **Stop:** beyond the sell-side liquidity (prior swing low) (cc06_004 ~21:17); 1 tick beyond the
  4h OB candle in the worked example (cc06_006 ~23:18) as switch.
- **Failure protocol** (cc06_003 ~23:24): if the 4h buy fails, buy the next lower 4h discount
  array; with none left, daily, then weekly, then monthly; re-entry size = 50% of the failed
  trade, halving after each failure. Don't try to win it all back.
- **Million Dollar Swing gates** (cc06_008): 1 seasonal (tag only for ES), 2 major markets
  trending (rates or dollar AND stocks or commodities; needs ZN/DXY data, tag later), 3-6 COT,
  DXY, commodities, open interest (no data; skipped). The portable gates are the MWD sequential,
  the PD arrays and the IPDA ranges. Frequency: one or two swings every 4-6 weeks (cc06_006 ~14:25).

## 7. Management (all models)

- **Million Dollar management** (cc06_008 ~16:20), used by `swing` and as the default for `osok`
  runners:
  - Leave the stop until price covers 1/3 of the distance to the objective.
  - At 1/4 of the objective, take 20-30% off (default 25%).
  - Breakeven only after the first partial, never before. [ICT conflict: "leave the stop until
    1/3" vs "partial at 1/4 then breakeven". Our interpretation: breakeven once both have
    happened, i.e. after the 1/4 partial AND price at 1/3.]
  - At 50%, add the partial size back after a short-term dip.
  - Close at the objective, or at 75-80% of it, and trail under the latest 4h short-term low.
  - Expect a stop run at or just above the 50% of the range; hold through it, don't trail tight.
  - If stopped out with the reasons intact, re-enter at the next MWD discount array.
- **Range quadrants** (cc06_008 ~26:02): after price crosses the swing's equilibrium, expect one
  retracement against the position; on the second leg one more after it takes the midpoint high;
  then a quick run to the objective. Projection: 1.27 and 1.62 extensions of the post-equilibrium
  retracement swing, lined up with weekly/monthly arrays (~28:08).
- **Position model stop** (cc05_018 ~5:52): initial and trailing stop beyond the 40-trading-day
  extreme (lowest low for longs), recomputed daily, moving only in the trade's favour; tighten to
  the 20-day extreme late in the move; no early breakeven. [ICT conflict, ask Mase: tighten at
  50% of the expected range (his long example) or at 75% (slides). Default 75%, switch 50%.]
- **Position partials** (cc05_013 ~18:56, cc05_016 ~4:37): take 1/4-3/4 off at logical targets,
  re-add the same size when price returns to the same open.
- Stops: closed candles decide structure, wicks stop out (standing rule).

## 8. Risk and sizing

- Reports use $1k risk per trade (standing rule), so ICT's sizing differences don't change the $
  results. For paper/live later: cc05_013 says 1% of a 30% allocation, cc05_018 1% of the account,
  cc06_006 ~1.5%, owner directive 1.2% at entry / 1.3% with adds (intraday). Default 1.2% to keep
  one house rule [our interpretation].
- Total open-risk cap (cc06_002 ~10:36): one swing/osok position at a time per model by default.
- Velocity rule: when capped, prefer the setup expected to pay faster (tag only).

## 9. Conviction score (label, not a filter)

Same idea as the intraday bot: count PD arrays from 1h to monthly that line up at the entry level,
weighted up by timeframe (1h 1, 4h 2, daily 3, weekly 4, monthly 5) [our interpretation of the
weights]. More levels converging = more sensitive level, monthly and weekly weigh most
(cc06_005 ~28:42). Reported per score bucket.

## 10. Tags (measurement only)

Weekly profile; entry weekday; MWD case A/B/C; IPDA window used (20/40/60); range-day; seasonal
agreement; volatility contraction; lethargic market; Mon-Wed break; quarterly-shift age; ADR5
ratio; Seek & Destroy; news week (FOMC, NFP, CPI); conviction score; hold time in days.

## 11. Testing and reporting

- Signals from ES; P&L in $ at $1k risk with ES costs (same cost model as the intraday bot);
  NQ/YM later as separate runs.
- Pick on 2019-22, check on 2023-26. Report by year, by half, by weekly profile and weekday,
  by MWD case, by conviction bucket. Hold time and max adverse excursion per trade.
- Look-ahead tests: every array/bias value at time t must be identical when computed on data
  truncated at t.
- Order: (1) `osok` defaults, (2) `target="prev_week"`, (3) each switch one at a time,
  (4) `swing`, (5) `position`.

## 12. Open conflicts for Mase

1. Position-trade stop: tighten from the 40-day to the 20-day extreme at 50% of the move (his long
   example, cc05_018 ~24:22) or 75% (his slides). Default 75%.
2. Premium/discount cutoff for new trades: no longs above 0.5 (the chart colouring) or only none
   above 0.8-0.9 (his words, cc06_004 ~34:27). Default 0.5.

Everything else above is either a single ICT rule, a 2023-beats-CC call, or labelled
"our interpretation" with a switch.
