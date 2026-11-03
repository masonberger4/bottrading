# Trade Executions + Charter Content: DRAFT rules for Mase's review

**Status: DRAFT. Nothing here is wired into the engine and nothing has been backtested.**
Every rule below is tagged DRAFT until Mase accepts it. Built 2026-11-03 from the per-video notes
in `mentorship/notes_te_charter/` (one file per video, with timestamps). Captions only: the
frames are on the laptop, so "this level / that candle" in ICT's speech is resolved from context.

## How to read this

- Source tiers: **2023 Mentorship wins on every conflict.** Charter Content (2018-2022, FX-first)
  and Trade Executions (TE, 2023-2026, mostly NQ/ES) sit below it. Older beats nothing here.
- Experienced-trader version is the default. Beginner-only advice is listed but marked [beginner].
- Tags (checked by grepping `mentorship_rules.md` and `mentorship/digests/*.md` on 2026-11-03):
  - **[new]**: term or rule not found in the rulebook.
  - **[in rulebook]**: already there in some form; the draft adds detail only.
  - **[conflict: X]**: differs from rulebook item X. Not resolved; the 2023 rule stays in force
    until Mase decides.
- Pips to index points: ICT's own index numbers are used where he gave them (Model 8: 25 handles
  a week or 5 handles a day; Model 12: 20 ticks = 5 handles, or 10 handles). **Every other
  pip-to-point conversion is our interpretation**, marked "(ours)".
- Times are New York local.

## Coverage

| Set | Videos | Status |
|---|---|---|
| Charter Content | 34 of 34 | notes ch01-ch34 |
| Trade Executions with speech | 25 | notes te09, 10, 20, 23, 25, 28, 29, 40, 43, 46, 47, 51, 57-68, 70 |
| Trade Executions 01-05 | 5 | **pending**: being re-downloaded; not covered |
| Trade Executions with no commentary | 41 | 06-08, 11-19, 21, 22, 24, 26, 27, 30-39, 41, 42, 44, 45, 48-50, 52-56, 69, 71. All in `data/ict_no_commentary.txt` (full-audio check). **Chart examples only, not rule sources.** |

Caption-quality warning: **te64** captions are a machine back-translation (garbled English).
Its rules are paraphrased from meaning and need checking against the audio.

---

## Part A. Charter Content: Models 1-13 (DRAFT)

Charter is FX-first. Pip numbers are ICT's; index equivalents are ours unless he gave them.

### Shared trade-plan block (every Charter plan: ch03, 05, 07, 10, 13, 19, 23, 25, 27, 29, 31, 33)
- DRAFT: Five stages: preparation, opportunity discovery, trade planning, execution, management.
- DRAFT: IPDA data range of 20 / 40 / 60 trading days, **no Sundays**; longest look-back 60 days.
  Model 9 alone uses the last **20 weeks**. [in rulebook: B21 / A21]
- DRAFT: Entry = convergence of a PD array (OTE 62%, FVG, OB) with a standard-deviation
  projection (<= 3 SD) of the CBDR / Asian range / flout, within 5 pips; limit at the convergence
  +/- 5 pips. [in rulebook: CBDR/flout; SD convergence partly]
- DRAFT: Calendar volatility injection (news) and the European open filter gate the day.
- DRAFT: Money management: halve risk after a loss; also cut risk after 5 straight wins.
  [in rulebook: E10 after a loss] [new: cut after 5 wins]
- DRAFT: Stop-reduction schedules (e.g. Model 11: at +15 cut stop 5, at +20 break-even;
  Model 12: at +10 cut 10, at +15 break-even). [new]
- DRAFT: Close ~80% at the main target, runner for the next array.

### Model 1: intraday scalp of previous daily range raids (ch01-03)
- DRAFT: NY session 5m OTE keyed at 62%, anticipating a run to a previous day high/low inside the
  20-day IPDA range (40-day once outside it). 15-20 pips a trade; aim one 25-30 pip scalp a week.
- DRAFT: Best structure: premium + raided high + break of a short-term low (displacement) +
  return to the breaker (shorts); mirror for longs. Dealing range framed on the daily
  (fallback 4h, then 1h, never lower). OTE on candle bodies.
- [conflict: rulebook MSS needs a close] ch02 accepts a wick break as the structure break.
- [conflict check] Model 1 plan: flat by 10:00 and no Fridays.

### Model 2: weekly range expansion, short-term (ch04-05)
- DRAFT: Buy at/below Tuesday's "04:00 platform" opening price (= 00:00 NY standard time, never
  DST-shifted) on Tue or Wed; 50 pip stop (25 in the plan); targets 50 / 75, close at 100;
  flat by Thursday NY open.
- DRAFT: Reversal profile after the weekly target is hit at an HTF array, 06:00 European open filter;
  "lazy" Asian-range-break stop entry.
- [conflict: rulebook uses local midnight] fixed 04:00 / 06:00 platform opens.
- [conflict check] Model 2 vs Model 3 on Monday trading.

### Model 3: swing, daily liquidity pools (ch06-07)
- DRAFT: Stage = COT commercial hedging program (12-month range midpoint); draw = daily equal
  highs/lows; 4h OTE, fine-tune 1h; 15m entry at 62% within 5 pips of <= 3 SD; Tuesday European
  open filter; 25 pip stop; **re-entry allowed**; 50 / 75 / 100+ with a runner. Needs data: COT.
- [conflict: COT 6 vs 12 months] Model 4 uses a 6-month look-back.

### Model 4: position trading on quarterly shifts (ch08-10)
- DRAFT: Quarterly shift + seasonal tendency + SMT + COT. After an old high is run, sell stop at
  the OPEN of the last up-close daily candle; stop at the high; 4h breaker / FVG refine (~50 pip
  risk). Pyramid only while price is in the premium of the dealing range, sizes 5-3-1.
  NFP = monthly Judas swing. TP 100 / 250 / 500, 80% off at 500.
- [conflict check] "largest open interest contract" vs owner directive #13 (front month).

### Model 5: day trading intraday volatility expansions (ch11-14)
- DRAFT: Daily draw for bias; trade only London and/or NY kill-zone moves toward it.
- DRAFT: Range for SD projections: CBDR if >= 15 pips and ranging, else Asian range if 20-40 pips,
  else flout (projected from its midpoint). Measured on 15m.
- DRAFT: "Grail": today's SD levels converging with previous days' SD levels (3-5 pips) at
  kill-zone times mark turning points. Level calibration to the nearest 5/10.
- DRAFT: FVG recipe: stalk an FVG in the correct half of the previous day's range; first return
  during a kill zone, institutional order flow entry drill (near edge); 40-50 pips; Tue-Thu only;
  stop 15 pips beyond the array; close 80% at 50.
- DRAFT: OB nuance: a one-pip gap between consecutive OB candles is the level price returns to. [new]

### Model 6: universal buy-side model (ch15-20)
- DRAFT: Range of opportunity between identifying a draw and reaching it. Buy Point 1 (first
  retracement after the impulse) and Point 2 (secondary retracement). ICT: "the model I trade most".
- DRAFT: Stage-1 reaccumulation at 20-30% of the origin-to-terminus range; 4h+ usually gives two
  buys, below 4h often one; **no stage 2 if <= 30 pips left**.
- DRAFT: Pyramid only while "unrealized range" remains; if the first run passes 50% of the expected
  range and retraces, assume one stage and don't pyramid.
- DRAFT: On the buy side of the curve the sell side's up-close candles become support; runs below
  short-term lows inside the bullish narrative are turtle-soup buys, not structure breaks.
- DRAFT plan: buy only in discount; 15m/5m discount FVG (<= -3 SD) or a sell-stop raid in
  London/NY; TP 20 / 40, close 80% at 60; stop 20 pips; re-entries allowed.
  [in rulebook: market maker models M1]

### Model 7: universal sell-side model (ch21-23)
- DRAFT: Qualified MSS = break of the HIGHEST reaccumulation-of-longs swing low on the buy side,
  after buy-side liquidity / the premium array is taken; then sell the return into that swing low's
  down-close bodies. [conflict: rulebook MSS definition]
- DRAFT: 1m tape reading: carry left-side buy areas to the right of the smart money reversal;
  a break above prior accumulation = no sell model.
- DRAFT plan: mirror of Model 6; sell limit at convergence - 5 pips; stop high + 20; sell-side runs
  are faster; check stage-2 distribution for a possible crash and let a portion ride.

### Model 8: 25 pips a week (ch24-25)
- DRAFT: Anchor = Monday, Tuesday or Wednesday high (bearish) / low (bullish). Enter in the FVG/OTE
  above equilibrium of the anchor range. **ONE order**, limit at convergence +/- 5, TP 25, stop 15,
  then stop trading for the week. Goal is to LOCK IN 25 (stop to +25), not bank partials.
- Index (ICT's own): **25 handles a week, or 5 handles a day in one session**; Monday can be
  skipped and used as intel.

### Model 9: One Shot One Kill (ch26-27)
- DRAFT: Catch the weekly high/low Mon-Wed; cover in the lower (upper) third of the weekly range;
  50 pips, up to 75. IPDA = last 20 WEEKS. Market order at the convergence.
- DRAFT: Coder key: internal-range entries (OB, FVG, void) run to external liquidity; external
  entries (turtle soup) run to internal liquidity.
- DRAFT: Tuesday makes the weekly low/high ~70% of the time [in rulebook ~70% Mon-Wed extreme];
  ICT gives up Monday. Two 1% orders: A = Model 8 logic, B = OSOK runner.
- DRAFT: Move the OSOK stop only when a lower-TF model would have hit its objective; break-even until
  Friday, then trail. Pyramid only above equilibrium (shorts).

### Model 10: external range liquidity both ways (ch28-29)
- DRAFT: Sell only above an old high / short-term high (turtle soup) in a bearish market in a kill
  zone; cover only below an old low or new short-term low. Old lows to the left beat fresh ones.
- DRAFT: Three exits: partial, partial, full. Plan: order 1 TP 50, order 2 TP 75; limit at
  convergence -/+ 5. ES 1m example: long below a dealing-range low, exit above the opposing high.

### Model 11: 30 pips a day trade (ch30-31)
- DRAFT: Weekly room >= 50 (ideally ~100) pips; draw = old DAILY highs/lows; internal-range entry
  in a 60m premium/discount OTE executed on 15m/5m in London/NY kill zones; limit at 62% +/- 5;
  TP 30; stop 20; at +15 stop -5, at +20 break-even. Exit 10-15 pips before the hard level.
  After terminus, run it in reverse via a MM buy model. Models 11-12 are "bread and butter",
  not for beginners.

### Model 12: 20 pips scalp (ch32-33)
- DRAFT: OB (down-close candle at the start of an impulse; FVG not needed) -> retest of the OB
  (upper half to mean threshold) -> expansion swing -> the FVG INSIDE that swing is the entry.
  Long at the FVG high + spread; short at the FVG low. 80% off at 20 pips.
- DRAFT: The OB may form outside a kill zone but the RETURN must be inside London/NY or no trade.
  TP by fixed limit; stop 20; at +10 cut 10, at +15 break-even.
- Index (ICT's own): **20 ticks (5 handles) or 10 handles**.

### Model 13: 2022 YouTube model for index futures (ch34)
- DRAFT: Windows: index AM 08:30-11:00 plus PM; FX 07:00-10:00. After a buy-side raid, rapid MSS
  below a recent 5m-1m low with displacement + FVG (ideally at/above equilibrium of the leg).
  Use the first FVG found going down from 5m to 1m. Risk <= 2%, ideally 0.5-1%.
- DRAFT: Entry = limit at the near edge of the FVG; stop = far edge, exactly, no tick added.
  [conflict check: slide says far edge; audio says "the candle's high" - flagged in ch34]

---

## Part B. Trade Executions (2023-2026): DRAFT rules by topic

### B1. Time windows and macros
- DRAFT: Macro = last 10 minutes of an hour + first 10 of the next (xx:50-xx:10); gives timing,
  not direction (te64, te28). [in rulebook: macros]
- DRAFT: Named macros used: 07:50-08:10 (te60), 08:50-09:10 (te58), 09:50-10:10 (te61),
  10:50-11:10 (te28), lunch macro (te46), 14:50-15:10 "macro one" (te62), 15:15-15:45 run (te62),
  MOC 15:50-15:57 (te25, te62). [conflict check: lunch macro, 14:50 macro]
- DRAFT: Expect expansion right after consolidation inside a macro; if not by xx:10, look to the
  next hour's macro (te64).
- DRAFT: Premarket entries 07:00-09:00 (te43, te51, te57, te58). [conflict: rulebook N5 limits
  early pre-market entries; experienced-only exceptions]
- DRAFT: Premarket dealing range: 07:00-08:29 high/low on news days (te58); 07:00-07:30 on
  CPI/PPI weeks, 07:00-08:00 otherwise (te60); graded in quadrants/octants and carried forward. [new]
- DRAFT: RTH opening range = 09:30-10:00 ("not 5, not 15 minutes") (te60).
- DRAFT: 10:30 = first hour's dealing range complete; algorithms more active after (te65).
- DRAFT: Asia: slow unless event-driven; small "bread and butter" trades to nearby liquidity (te70).
  [conflict: rulebook skips Asia by default]

### B2. Day and week selection, news
- DRAFT: NFP week: Mon-Wed until ~11:00 is the clean window; Monday before NFP is a focus day;
  Thu/Fri highly manipulated (te57, te64, te66, te67). ICT himself trades NFP Thu and Fri
  (te09, te10, te58, te66, te67). [conflict: rulebook N1 NFP Friday no live trading /
  experienced-only exceptions]
- DRAFT: NFP is a two-stage delivery like FOMC (te58); on NFP Friday of a holiday week wait for the
  first hour (te67). Don't pyramid on NFP (te10) [in rulebook N1].
- DRAFT: CPI/PPI midweek: Mon/Tue RTH tends to be range-bound (high-resistance liquidity run);
  London/premarket trend instead; only one of AM/PM trends (te60). [new]
- DRAFT: 10:00 news day: wait 30 minutes after 09:30 and trade what's left after the release
  (te64); exit or fund the trade before a scheduled 10:00 Fed speech (te63). [conflict check]
- DRAFT: Jackson Hole: day 1 most likely "seek and destroy" (both sides swept, megaphone);
  expect "second runs" all week (te61-63). [new]
- DRAFT: After a holiday: trade light (1 contract) or paper (te68). [conflict check: rulebook holiday rules]
- DRAFT: Experienced traders can trade every day; Fridays optional after a profitable week (te63).
- DRAFT: Year-end last day "breaks rules": stop above the day's initial high (te20).

### B3. PD arrays and definitions
- DRAFT: **Suspension block** = a gap with volume imbalances at BOTH its high and low; CE entries
  (te57, te62, te64, te68). [new]
- DRAFT: Inversion FVG (iFVG): a gap closed through on a BODY basis takes the opposite role; a wick
  through does not make it one (te65). Strongest when "qualified" by closes twice (te59).
  [in rulebook A8; qualification count new]
- DRAFT: FVG/iFVG split into quadrants and octants (0, .125, .25, .375, CE ...); levels that line
  up with graded higher-range levels are the valid ones (te47, te58, te60, te62). [octants new]
- DRAFT: **First presented FVG (FPFVG)** = first FVG after 09:30; prior days' FPFVGs stay as PD
  arrays (no bodies in the lower half of a bullish one) (te62, te65-68). [new]
- DRAFT: Rejection block = highest up-close price in a swing high (te57). [in rulebook; check wording]
- DRAFT: Volume imbalance = most flexible (weakest) PD array (te40); volume imbalances "ladder" a
  strong run and each should hold (te70).
- DRAFT: **Instant rebalance** (displacement filled at once by the next candle, no FVG) = one of
  ICT's strongest PD arrays (te64). [new]
- DRAFT: **Event horizon** = midpoint between two levels/pools; partial there (te62, te64, te70).
  [in rulebook, 1 mention]
- DRAFT: Change in state of delivery candle open = re-entry level (te51) [in rulebook].
- DRAFT: Midnight NY opening price on every chart; strong magnet (te59, te60) [in rulebook].
- DRAFT: RTH opening range gap (ORG) = previous 16:00 close to 09:30 open. **CE reached by 10:00
  ~70% of the time** (te64); a premium/discount gap open draws to half-gap (te68).
  [conflict check vs rulebook opening-gap rules]
- DRAFT: Best target = where an ORG fib level coincides with a daily PD-array level (te65). [new]
- DRAFT: Friday's final RTH hour (15:00-16:00) high/low = Monday liquidity (te60). [new]
- DRAFT: Liquidity menu: session H/L, daily H/L, London lunch range H/L, previous week H/L,
  highest high / lowest low of the last 3 days (te60).
- DRAFT: Weekly range retracement levels 20 / 25 / 30% as targets (te67). [new]
- DRAFT: "Corking" = a tight block under a target high that won't go lower = pre-breakout (te61, te62). [new]

### B4. Entries
- DRAFT: Wick CE ("high frequency algorithm" entry): buy the retrace to a swing-low wick's CE,
  stop below the CE (te25, te09, te43).
- DRAFT: Enter at the LAST inefficiency of the run (walk left from the extreme candle) (te57).
- DRAFT: Seek & destroy entry: after the intraday low is run inside a macro, take the candle that
  forms the iFVG (te61); minimum criterion to buy sell-side = price below the low (te62).
- DRAFT: Short after a gap fill: entry at the high of the up-close candle, stop one tick above its
  mean threshold (te64).
- DRAFT: Large ORG: at least try to trade into the gap; favor that direction; a stop-out on the
  attempt often precedes an easier setup (te65).
- DRAFT: Micro-scouting (5s/15s charts, no bias) (te28, te29, te40). [new; needs sub-minute data]

### B5. Stops and management
- DRAFT: Bodies vs wick CE: no bodies closing beyond the reference wick's CE; if one does, the next
  candle must reverse immediately (te59, te61, te62).
- DRAFT: Upper half of a wick (longs) / lower half (shorts) is the "order-flow" zone: bodies stay
  in it, wicks don't reach CE (te62, te64).
- DRAFT: Three PD arrays frame the stop (e.g. wick CE, iFVG low / ORG low, lower part of a BISI);
  used DEFENSIVELY, not for adds (te57, te61, te70).
- DRAFT: Once a candle closes beyond the reference level, roll stop to cover costs (te59).
- DRAFT: After the iFVG is validated by a close, stop to the mean threshold of the last opposite
  candle (te66).
- DRAFT: Stop placement lesson: after the last up-close candles form an OB, stop at that candle's
  open (te62).
- DRAFT: Range-redelivery trail: if price retraces and redelivers the same range again, move the
  stop under that retrace low (te65). [new]
- DRAFT: **Never move a stop back once profit is locked** (te57, te61).
- DRAFT: Re-enter immediately with the same size if stopped and the idea holds (te62).
  [conflict: rulebook E10 / X13 half size and no re-entry after an AM loss]
- DRAFT: Futures for tight stops: everyone gets the same high/low (te62).

### B6. Partials and targets
- DRAFT: **Running down equity**: whenever price makes a new short-term low (shorts) and no partial
  has been taken, take one (te09, te29, te68). [in rulebook, 4 mentions]
- DRAFT: Partial on a STOP order during a retracement (te59). [new]
- DRAFT: **Double tap**: "center mass" (first, easiest target, ~half off) + "head shot"
  (best-case target) (te70). [new]
- DRAFT: Lowest-hanging-fruit first; don't need the full terminus (te66).
- DRAFT: Don't give back more than ~half of unrealized profit near the target (te67).
- DRAFT: Gaps near the target rarely fill before it ("in a hurry") (te62); a gap left partly
  open = continuation; full fill makes continuation harder (te59, te61, te65).

### B7. Pyramiding
- DRAFT: **Add longs only at or below equilibrium of the range from the entry low to the target;
  shorts at or above; once price passes equilibrium, no more adds.** Re-measure when the terminus
  is extended (te62). [conflict check vs Charter Model 4 premium-only adds / Model 6 unrealized
  range / Model 9 above equilibrium; rulebook pyramid rules]

### B8. Market maker model as ICT's main model
- DRAFT: ICT's predominant model is the market maker sell/buy model, trading the second-stage
  redistribution / reaccumulation: original consolidation -> smart money reversal -> low-risk
  sell -> first stage distribution -> second stage redistribution (longest leg); stop anchored to
  first stage distribution (te66, te67; also Charter Model 6). [in rulebook M1 AM MMXM;
  conflict check on model priority]

### B9. [beginner] process (not engine rules)
- Weekly prep on the weekend with the USD-filtered calendar; mark previous month H/L/close and
  weekly/daily levels on all timeframes (te64).
- Record the 1m chart, replay 09:30-10:30 predicting each candle, journal every "price should do X"
  moment; backtest for months, then demo at least 3 months (2 if very good) (te63, te64).
- Jackson Hole week and NFP Thu/Fri: tape reading only (te63, te66).

---

## Part C. Conflicts to decide (2023 rule stays in force meanwhile)

1. Wick break counts as MSS (ch02) vs rulebook close requirement.
2. Fixed 04:00 / 06:00 platform opens (ch04-05) vs local midnight.
3. Largest-open-interest contract (Charter) vs owner directive #13 (front month).
4. Model 1: flat by 10:00 and no Fridays.
5. Model 2 vs Model 3 on Mondays.
6. COT look-back 6 months (Model 4) vs 12 months (Model 3).
7. Model 7's MSS definition (highest reaccumulation low).
8. Breaker definition differences (Charter).
9. Model 13 entry/stop edge (slide vs audio).
10. NFP Thursday/Friday trading (TE trades them) vs N1.
11. Lunch macro and 14:50-15:10 macro vs rulebook macro list.
12. Premarket entries 07:00-09:00 vs N5.
13. Asia session trades vs default skip.
14. Same-size re-entry after a stop (te62) vs E10 / X13.
15. Pyramid-at-equilibrium rule (te62) vs Charter pyramid rules.
16. Opening-gap CE by 10:00 70% (te64) vs rulebook opening-gap handling.

## Part D. Backtestable switches (all default OFF; DRAFT names)

| Switch | Values | Source |
|---|---|---|
| `mss_wick_ok` | on/off | ch02 |
| `platform_open_fixed_0400` | on/off | ch04-05 |
| `charter_cut_after_5_wins` | on/off | ch03 |
| `stop_reduction_schedule` | none / M11 / M12 | ch31, ch33 |
| `m8_one_order_lock_25` | on/off (25 handles/wk, 5/day) | ch24-25 |
| `osok_20_week_range` | on/off | ch27 |
| `no_stage2_if_room_lt` | 30 pips (index value ours) | ch16 |
| `pyramid_eq_rule` | off / entry-to-terminus EQ | te62 |
| `ifvg_min_qualifications` | 0 / 1 / 2 | te59 |
| `entry_suspension_block_ce` | on/off | te57 |
| `entry_last_inefficiency` | on/off | te57 |
| `fpfvg_arrays` | today / prior days / off | te62, te65 |
| `premarket_range_len` | 07:00-07:30 / 07:00-08:00 / 07:00-08:29 | te58, te60 |
| `org_ce_target` | on/off | te64, te68 |
| `org_gap_bias` | on/off | te65 |
| `confluence_target_org_daily` | on/off | te65 |
| `friday_final_hour_liquidity` | on/off | te60 |
| `weekly_retrace_targets` | 20 / 25 / 30% | te67 |
| `skip_seek_destroy_days` | off / JH day 1 / JH week | te61-63 |
| `flat_before_fed_speech` | on/off | te63 |
| `wait_30m_after_10am_news` | on/off | te64 |
| `nfp_friday_wait_until` | off / 10:30 | te67 |
| `post_holiday_size` | full / 1 contract / skip | te68 |
| `skip_friday_if_week_profitable` | on/off | te63 |
| `allow_asia_session` | on/off | te70 |
| `three_pd_array_stop` | on/off | te57, te61, te70 |
| `stop_mt_last_opposite_candle` | on/off | te66 |
| `range_redelivery_trail` | on/off | te65 |
| `partial_on_new_swing` (running down equity) | on/off | te09, te68 |
| `partial_on_stop_order` | on/off | te59 |
| `double_tap_exit` | off / 50% at first target | te70 |
| `max_giveback_unrealized` | off / 50% | te67 |
| `reentry_same_size` | on/off | te62 |
| `gap_partly_open_filter` | on/off | te59, te61 |

Per-video switch ideas and every [conflict check] are in each note's "Open questions" section.

## Part E. Questions for Mase

1. TE rules come from ICT trading live in 2023-2026. Should they rank below the 2023 Mentorship
   (current default) or count as "experienced version" overrides where they differ?
2. Charter is FX-first. Port pip targets to NQ/ES with our conversion, or test only the models
   where ICT gave index numbers (8, 12, 13)?
3. Sub-minute micro-scouting (te28, 29, 40, 46) needs 5s/15s data. Skip, or buy data later?
