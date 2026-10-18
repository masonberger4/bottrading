# Rulebook gaps: other (instruments, data, journal, backtest acceptance, checklists, parked FX / stocks)

Topic `other`. Every item below is a verified gap between ICT's captions and `mentorship_rules.md`. When the checker gave a corrected rule, that corrected rule is the one written here; when it gave none, the claim's full rule is used. "[our interpretation]" marks thresholds or readings that ICT does not state.

Conventions (the same as the other `rulebook_gaps` files):
- Times are New York. Params times are minutes from midnight (570 = 09:30, 600 = 10:00).
- New Params switches default off, so with every switch off the engine's trades are unchanged (rule_coverage.md section 3). Each work package adds its fields in its own commented block at the end of `Params` (`strategy.py:65`).
- Work packages are the names in `rule_coverage.md` section 3. Code anchors are current line numbers on branch `mentorship`: `run_day` `strategy.py:2490`, the per-bar `blocked()` / sloppy check `~2862`, the bias `want` block `~2579`, `_scan_core` `~3308` with the `use_bias` gate `~3984`, `Trade` `~893`, `backtest.stats` `:352`, `backtest.report` `:365`, `backtest.combine` `:414`, `htf.table` `:95`.
- Items scoped `fx_only` or `needs_unavailable_data`, and items that belong to the parked swing mode (M17), get the rulebook fix only, with no build spec. Data on disk: SPX/NDX CFD (HistData / Dukascopy), SPY/QQQ (Schwab / Alpaca), and Databento ES/NQ/YM 1m/5m futures with per-bar `adj` / `instrument_id` / `roll` meta (`data/mentorship/*_db*.parquet`). Not on disk: per-contract back-month prints, CME open interest, IBD ratings, fundamentals, options chains, sector / industry-group membership.
- Tests go in `tests/test_other_gaps.py` unless a package's own test file fits better (`tests/test_setups_models.py`, `tests/test_levels_detectors.py`).

Summary: 25 items, 15 new build specs. Items without a build spec:
- 3 fx_only: OT-fx-crosses-strong-vs-weak, OT-fx-no-exotics, OT-fx-sunday-candle
- 2 that need data we do not have: OT-cfd-level-precision (as scoped by the checker; see the note there) and OT-stocks-canslim-fundamentals
- 2 parked swing mode (M17): OT-htf-market-selection-rotation and OT-M17-osok-holding
- 3 already listed in rule_coverage with the same content:
  - OT-execution-contract-highest-OI: the #13 / DATA1 Databento volume roll (section 4); open interest = B20.2 `oi_tag`.
  - OT-no-indicator-triggers: B20.3 `wpr_tag` is already specified as a tag only, and the engine uses no oscillator as a signal (the same text-only result as X3-indicators-contrarian-only in `bias_htf_intermarket.md`).
  - OT-T13-eight-vs-six-profiles: the six profiles are built as `profile_tags` (T13, section 4 setups_models). The new part is a rulebook note only.

---

## A. Instruments and data

### 1. OT-cfd-level-precision
- **rule_id / kind:** new / missing_rule. Scope: needs_unavailable_data. judgment = true.
- **Rule (corrected):** ICT: CFDs move with the futures but respect PD-array levels (FVGs, VIs) less precisely, so derive levels from ES/NQ futures data when it is available. When using CFD/cash data, add a level-tolerance parameter (value chosen by test, not from ICT) to tick-precise rules, don't treat a VI as a tick-precise stop, and label level-dependent backtest results as approximate.
- **Sources:** 007_bGtQOXrrK9c ~00:26:03, ~00:26:45-00:27:57; 029_dwJcsi3ddFg ~00:27:23.
- **Quotes:**
  - "it's a cfd so it's going to be a little spotty ... the levels of precision in the entry points are going to be slightly off"
  - "I've noticed that they don't really respect them so much or as precisely as in the Futures market"
- **Conflicts:** none.
- **[our interpretation]:** the tolerance value (the claim's 0.5-1.0 ES pt is a test range, not ICT's).
- **Rulebook fix:** In the header data section (lines ~15-17), after the SPX/NDX CFD sentence, add: "ICT: CFD prices respect FVGs / VIs less precisely than futures (007 ~26:03; 029 ~27:23). Levels come from ES/NQ futures where available (`source="databento"`). On CFD data, tick-precise rules carry a test tolerance, a VI is never a tick-precise stop, and level-dependent CFD results are labelled approximate."
- **Build spec:** none (scope). Note for the owner: the futures data is on disk, so the main fix is to run the level-dependent studies on `source="databento"`. The tolerance pieces already exist or are specified: A2 `sweep_ticks` (built) and A4 `mohawk_ticks` (rule_coverage, entries_stops_sizing). If a CFD tolerance is wanted later, it is one multiplier on `_tick()` (`strategy.py:1467`) applied when the source is a CFD.

### 2. OT-D15-default-instrument
- **rule_id / kind:** D15 / missing_rule. Scope: index. judgment = true.
- **Rule (corrected):** ICT's preference: avoid executing on the Dow (YM), use it only as an SMT reference. ES is the smoothest; NQ tends to over-deliver past levels, so give NQ/NDX a wider overshoot tolerance. Index choice otherwise follows D15. This is a preference, not a hard default.
- **Sources:** 028_wWvFUW-jY4w ~00:23:58 (to ~24:50).
- **Quote:** "NASDAQ can overreact and over deliver versus the ES ... much more smoother"
- **Conflicts:** none in the rulebook. ICT frames it as personal ("don't let me influence something that's already working for you") and trades NQ often in 2023.
- **[our interpretation]:** the size of the NQ overshoot tolerance; the ES tie-break.
- **Rulebook fix:** Under D15 add: "Preference (028 ~24:00): never execute on YM, use it as an SMT reference only. ES is the smoothest; NQ over-delivers past levels, so NQ gets a wider overshoot tolerance. Otherwise D15 decides. Not a hard default."
- **BUILD SPEC (setups_models; owns `backtest.combine`):**
  - `backtest.combine(..., pick, exec_exclude=("YM",), prefer="none")`: drop rows whose `symbol` is in `exec_exclude` before picking. YM runs are then reference-only (they already enter as `partner2` / `smt2`). With `prefer="es"`, on same-bar ties (same `entry_time`) keep the ES/SPX/SPY row over NQ/NDX/QQQ, ahead of the `_weak` / `_rel` tie-break.
  - NQ overshoot: in `_tick()` (`strategy.py:1467`) multiply by `p.nq_overshoot_mult` when the run's symbol is NQ/NDX/QQQ (`ctx.symbol`). It then applies wherever `sweep_ticks` already applies (sweep, intact, SMT, seen filter, SB tag) and to the `mohawk_ticks` stop tolerance once built.
  - Params: `combine_prefer: str = "none"` ("none" / "es"), `combine_exec_exclude: tuple = ("YM",)` (always on: the bot never executed YM, so trades are unchanged), `nq_overshoot_mult: float = 1.0` (test 1.5 / 2.0).
  - Test `test_combine_excludes_ym_and_prefers_es`: three one-row runs (ES, NQ, YM) with the same `entry_time` -> YM never kept; `prefer="es"` keeps ES; `prefer="none"` keeps the current pick. `test_nq_overshoot_tick`: `_tick` on an NQ ctx with mult 2.0 is twice the ES value.

### 3. OT-max-two-correlated-markets
- **rule_id / kind:** Ep05 / unlisted_contradiction. Scope: general. judgment = false.
- **Rule (corrected):** Monitor at most two closely correlated instruments (ES and NQ; bot: SPX/NDX or ES/NQ data, SPY/QQQ execution). Never add instruments to find extra setups (055 ~27:38; 054 ~16:01; 095 ~23:00). Use the second instrument for SMT and decoupling reads (B18). Execute in one per session (D15) and don't switch mid-session (M3). Ep 05's 'one market only' was said after he lost track switching between ES and the US500 CFD of the same index, so it does not forbid a correlated companion. List this as a decision.
- **Sources:** 055_qiv8pkcNvGk ~00:27:38; 095_LPmMtq9jLm8 ~00:23:43; 054_tRq1hyGGtl4 ~00:16:01; Ep05 (Appendix A, line ~1362).
- **Quotes:**
  - "I teach you to have one market or two if it's closely correlated but nothing more than that"
  - "you need to look at something that's closely correlated because you'll see a crack"
- **Conflicts:** Ep 05 (one market only) vs 055 (one, or two if correlated, nothing more) vs 054 (one, 1-2 at most, 3 "if you want to be a deviant") vs 095 (one alone is "foolish"). cc09_003 / cc11_001 scan many markets; those are HTF selection or parked models (see item 4).
- **Rulebook fix:** Add a section 3 decision "Number of markets": "Watch two closely correlated indices (ES + NQ) for SMT, execute one per session (D15), never switch mid-session (M3), never add markets to find setups. Ep 05's 'one market' note is about not hopping between ES and its own CFD." Amend the Appendix Ep 05 line to point at the decision.
- **BUILD SPEC (setups_models; `backtest.combine`):**
  - The engine already executes one instrument per (date, session) (`combine` groups by `["date", "session"]`). New: a guard that the execution set is at most two correlated indices. In `combine`, after `exec_exclude` (item 2), raise `ValueError` when more than `max_exec` distinct execution symbols remain, or when the two are not one S&P and one Nasdaq instrument (symbol map: ES/SPX/SPY -> "spx", NQ/NDX/QQQ -> "ndx").
  - `one_market` (D15 spec in rule_coverage) stays as specified; this item only adds the cap.
  - Params: `max_exec_markets: int = 2` (the current studies use two, so trades are unchanged).
  - Test `test_combine_caps_two_markets`: ES + NQ runs pass; adding a third execution symbol (e.g. a synthetic "RTY") raises; ES + SPY (same index twice) raises.

### 4. OT-htf-market-selection-rotation
- **rule_id / kind:** B22 / missing_rule. Scope: general (swing mode). judgment = true.
- **Rule (corrected):** Swing/position mode only (parked with the swing idea; M17). Each quarter, and whenever a large move is expected (time of year), review the monthly/weekly profile of every market in the asset class. Drop lackluster markets (little movement over the last ~3 months) and markets confined to an obvious range. Build the watch list from markets whose monthly/weekly profile is trending or has just left consolidation (cc06_001 ~1:54; cc05_001 ~8:01). Don't keep last quarter's mover by default, and don't specialise in one favourite market (cc11_001 ~2:29). With no clear signal, do nothing (cc11_001 ~3:52). Intraday execution still follows the one-or-two-correlated-markets rule. For the index-only bot: re-check the SPX/NDX monthly/weekly profile each quarter and stand aside from swing trades while it is range-bound.
- **Sources:** cc06_001_0juYnbKays0 ~00:01:54; cc05_001_n7SPAK_tpN8 ~00:08:01; cc11_001_u5S6Zt1ZIpA ~00:02:29, ~00:03:52.
- **Quotes:**
  - "there is no standard swing trading market or pair every three months there is a new opportunity formed"
  - "when following the commodity markets in my opinion it's best to avoid being a specialist or one market Trader"
- **Conflicts:** cc11_001 (avoid being a one-market trader) vs Ep 05 (watch one market only). Resolved by scope: HTF selection vs intraday execution (item 3).
- **Rulebook fix:** Under M17 (swing, parked) add the quarterly watch-list rule above, and under B22 add: "Selection consequence (swing only): re-screen each quarter, drop lackluster / range-bound markets, no favourite market."
- **Build spec:** none. The engine has no swing mode (M17), and the B22 `qshift_tag` (rule_coverage, bias_htf) already covers the quarterly-shift read for the indices.

### 5. OT-htf-array-data-series
- **rule_id / kind:** new / unlisted_contradiction. Scope: index (the checker corrected needs_unavailable_data: Databento ES/NQ/YM is on disk). judgment = true.
- **Rule (corrected):** On the Databento futures data (ES/NQ/YM): draw daily/weekly FVGs and VIs on the front-month price frame (#13). Note that this frame approximates 056's method, which uses the delivery month's own back-month prints, and the bot doesn't have those prints (they would need per-contract raw data). Draw monthly arrays (and weekly ones where per-contract history is missing) on the continuous front-month series (078 ~35:43), mapped to the traded contract with the per-bar adj. Add a switch `htf_series = contract | continuous`, record the 056-vs-078 conflict as a decision, and flag HTF array levels on the SPX/NDX CFD data as approximate.
- **Sources:** 056_NeZlyG8FZLQ ~00:01:13; 078_FQqwmDJOtxk ~00:35:43.
- **Quote:** "the continuous contract is not going to show you the inefficiencies that the actual individual delivery contract months will"
- **Conflicts:** 056 (individual delivery month, continuous hides inefficiencies) vs 078 (monthly/weekly on NQ1! continuous, execution on the most active contract).
- **[our interpretation]:** the back-adjusted engine frame as the stand-in for 056's per-contract history; the raw-continuous mapping.
- **Rulebook fix:** Add a section 3 decision "HTF array series": "056 draws daily/weekly arrays on the delivery month's own history; 078 draws monthly/weekly on the continuous chart. Bot default: daily/weekly on the #13 front-month frame (approximates 056); monthly on the raw continuous series (078). On SPX/NDX CFD data HTF array levels are approximate."
- **BUILD SPEC (bias_htf; `htf.table`, with `htf._arrays` owned by levels_detectors unchanged):**
  - Today `htf.table` builds "D" and "W" arrays on the engine frame (back-adjusted continuous when `source="databento"`). That is `htf_series="adjusted"` and stays the default.
  - `htf_series="raw"`: `backtest.prepare` passes the raw front-month frame (`{sym}_1min_dbraw`) and the meta `adj` to `htf.table(..., raw=df_raw, adj=meta.adj)`. Arrays are built on the raw series (roll gaps left in, as on an unadjusted NQ1! chart). When an array is used on day k, its prices are mapped into the engine frame by adding the `adj` of the last closed bar before the session (no look-ahead), the same mapping `_round_levels` uses (`strategy.py:1288-1315`).
  - `htf_monthly=True` adds "M" arrays (calendar-month bars from `sessions(df)`, usable the day after the month's last session) built on the series chosen by `htf_monthly_series` ("raw" default, per 078).
  - `htf_series="contract"` (056 exact) raises `NotImplementedError("needs per-contract raw data")` until that data exists (DATA1 roll_kind="calendar" note in rule_coverage section 4).
  - Non-databento sources: every value except "adjusted" warns and falls back (CFD / ETF have no roll meta).
  - Params: `htf_series: str = "adjusted"` ("adjusted" / "raw" / "contract"), `htf_monthly: bool = False`, `htf_monthly_series: str = "raw"`. Add `htf_series` to the `__post_init__` choices list (`strategy.py:~718`).
  - Test `test_htf_series_raw_maps_by_adj`: a synthetic 2-contract series with a +10 roll; a daily FVG formed before the roll sits 10 pts lower in "raw" than in "adjusted" after mapping, and identical when it formed after the roll. `test_htf_monthly_known_next_day`: an "M" array's `known` is the first session of the next month.

### 6. OT-execution-contract-highest-OI
- **rule_id / kind:** new / missing_rule. Scope: index (checker: volume is available, OI is not). judgment = false.
- **Rule (corrected):** Analyse and trade the most actively traded delivery month: highest open interest and volume, normally the nearby (cc10_003 ~5:19; 078 ~35:43). Bot: on the Databento futures data, use the highest-volume contract per day (already the #13 volume roll). Use open interest as a confirmation where available {needs: CME OI}. Don't assume the calendar-nearest month. Not applicable to SPY/QQQ execution. State this in the rulebook next to #13.
- **Sources:** cc10_003_R2NjnYozhdw ~00:05:19; 078_FQqwmDJOtxk ~00:35:43.
- **Quote:** "look at open interest and volume whatever has the highest one"
- **Rulebook fix:** Next to owner directive #13 (header, line ~17): "Contract = the delivery month with the highest volume / open interest, normally the nearby; some markets skip months (gold). Bot: Databento volume roll; OI as confirmation {needs: CME OI}."
- **Build spec:** none. Already in rule_coverage with the same content: DATA1 front month = Databento volume roll (section 4, built), and the OI read is B20.2 `oi_tag` (bias_htf).

---

## B. Journal, staging and backtest acceptance

### 7. OT-X16-time-to-move-journal
- **rule_id / kind:** X16 / missing_rule. Scope: general. judgment = false (MFE/MAE are ours).
- **Rule (corrected):** For each trade, log at close (immediately): minutes from fill to the first favourable move, and minutes from fill to stop-out or target; day-context tags such as pre_fomc or news_day (042 ~51:03, ~53:29, ~55:46). MFE/MAE are optional additions [our interpretation].
- **Sources:** 042_hQ379EuyNKQ ~00:51:03.
- **Quote:** "how much time does it take for you to see it move in your favor or if it stops you out how fast"
- **[our interpretation]:** the size of "a favourable move" (`fav_pts`); MFE / MAE.
- **Rulebook fix:** Under X16 add: "Per trade, at close: minutes fill -> first favourable move, minutes fill -> stop or target, and the day context (e.g. trading ahead of FOMC) (042 ~51:03-55:46)."
- **BUILD SPEC (day_week_context, which owns X16; the tracking reads the run_day management loop and merges after management_exits):**
  - In the `run_day` position loop (`strategy.py:~2600-2760`), per open bar update `pos["mfe"]` / `pos["mae"]` (in engine points, signed by side) and set `pos["fav_t"]` the first bar whose favourable excursion from the fill is `>= p.fav_pts * p.es_pt`. Read-only: no exit or stop logic changes.
  - New `Trade` fields (all defaulted so `sb_model` / `pre_open` calls still work): `min_to_fav: float | None`, `min_to_exit: float | None` (fill -> final exit), `first_exit_kind: str` ("stop" / "target" / other, from `exits[0][3]`), `mfe_pts: float | None`, `mae_pts: float | None`. Fill them in `_close` / `_after_close` (`strategy.py:1851-1886`). The SB path (`sb_model.run_sb`) uses the same `pos` dict, so it gets them for free when it goes through `_close`.
  - Day tags: add `pre_fomc` (the next trading day, `calendar.next_trading_day`, is an FOMC day) and `news_day` (`events(day)` holds jobs / cpi / ppi / fomc) to `day_context` (`strategy.py:1902`); they flow into `Trade.day_tags`.
  - `backtest.report` adds `by_pre_fomc` and the medians of `min_to_fav` / `min_to_exit` split by winner / loser.
  - Params: `journal_timing: bool = False` (fields stay None when off), `fav_pts: float = 2.0` [our interpretation].
  - Test `test_journal_time_to_move`: a synthetic long filled at 09:40 that is +2 pts at 09:46 and stopped at 10:05 gives `min_to_fav=6`, `min_to_exit=25`, `first_exit_kind="stop"`; the day before a calendar FOMC date is tagged `pre_fomc`.

### 8. OT-target-progression
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule (corrected):** Staging parameter (judgment): start with a ~10 ES pt fixed target at base size. Step the target up by ~5 pts (10 -> 15 -> 20) only after a consistent non-negative run at the current level (N is ours). Do not raise contracts and target together. ICT's stages are: P&L breakeven first, then small base hits, then stretch targets step by step (099 ~40:55).
- **Sources:** 099_v_iJlBKYmUc ~00:40:55.
- **Quote:** "if you're doing 10 handles okay go for 15. you can do 15 okay stretch for 20"
- **[our interpretation]:** the N-weeks gate and the fixed-size condition. "Breakeven" means net P&L, not moving the stop.
- **Rulebook fix:** New rule next to X14: "Progression (099 ~40:55): breakeven P&L first, then base hits, then stretch the target 10 -> 15 -> 20 handles only after consistency; never jump to oversized positions for big targets."
- **BUILD SPEC (targets_partials; the weekly state lives in `backtest.run`, which day_week_context owns, so merge after it):**
  - The fixed target already exists: owner #2 `t1_fixed_pts` (`strategy.py:237`). New: a staging schedule that changes it week by week.
  - In `backtest.run` (`:269`), when `p.target_stage`, keep `stage` (index into `p.stage_targets`) and a count of consecutive completed weeks with net P&L >= 0. Before each week's first day, run that week with `dataclasses.replace(p, t1_fixed_pts=p.stage_targets[stage])`. After `p.stage_weeks` consecutive non-negative weeks, `stage += 1` (capped at the last); a negative week resets the count (and with `stage_drop`, steps back one). Risk / size is never changed by the stage (E8 / E11 stay as set).
  - Every trade carries `stage_pts` (new `Trade` field, default 0.0).
  - Params: `target_stage: bool = False`, `stage_targets: tuple = (10.0, 15.0, 20.0)`, `stage_weeks: int = 4` [our interpretation], `stage_drop: bool = False`.
  - Test `test_target_stage_steps`: a stub run returning +1 each week moves 10 -> 15 after 4 weeks and 15 -> 20 after 8; a losing week at week 3 resets the count; `shares` sizing is identical across stages for the same stop.

### 9. OT-backtest-acceptance
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule (corrected):** Report hit rate p, average realized R, expectancy E = p*RR - (1-p), R/month at ~10 trades/month, annual return and annual max drawdown. Accept only if E > 0. Reference: p=0.30 must still be net positive at 3:1 (cc02_004 ~8:30); the goal is 5:1 at ~50% (cc02_004 ~15:17); a win rate above 50% is never required. Annual max drawdown target ~15%, 20s tolerable, above ~25% unacceptable; annual return target 18-25% (cc05_013 ~2:17, ~9:28; position-trading context). Prefer the smoother equity curve with lower drawdown when ranking variants. Drop the '16% acceptable' figure; it has no source.
- **Sources:** cc02_004_pFdW8wdR9sQ ~00:19:52; cc05_013_crPpMwgwa7k ~00:02:17.
- **Quotes:**
  - "you'll never demand or need for it to be higher than 50 50"
  - "control your draw down to around 15 as a maximum"
- **[our interpretation]:** using cc05_013's position-trading numbers as intraday reference points; the lower-drawdown ranking.
- **Rulebook fix:** New section "Backtest acceptance" (after the owner directives / reporting notes): the corrected rule above, with the grid p=0.30/RR=3 -> +0.2R, p=0.50/RR=5 -> +2.0R.
- **BUILD SPEC (day_week_context, which owns `BT.run` reporting and the study scripts; no package owns `backtest.stats`, so this is the nearest):**
  - `backtest.stats` (`:352`) adds: `avg_win_R` (mean R of trades with net > 0), `avg_loss_R`, `expectancy_R` (= mean R; also `p * avg_win_R + (1 - p) * avg_loss_R`, which is the same number, kept for the report), `R_per_month` (sum R / distinct months), `ann_ret_pct` (mean over calendar years of net / account), `ann_dd_pct_max` (largest within-year max drawdown in % of account, the drawdown reset each 1 Jan), and `accept` = `"reject"` if expectancy_R <= 0 or ann_dd_pct_max > 25, `"tolerable"` if ann_dd_pct_max > 15, else `"ok"`. Thresholds come from `ACCEPT = dict(dd_ok=15, dd_max=25, ret_lo=18, ret_hi=25)` at the top of `backtest.py`.
  - `report_decisions.py` (`cols`, line 23) adds `expectancy_R`, `ann_dd_pct_max`, `ann_ret_pct`, `accept`; when it ranks variants, sort by `accept`, then `ann_dd_pct_max` ascending, then `sum_R` (lower drawdown first).
  - No Params switch: reporting only, the trades are unchanged.
  - Test `test_stats_acceptance`: 10 trades, 3 at +3R and 7 at -1R -> expectancy_R = +0.2, accept != "reject" when the drawdown is small; the same trades scaled so a year's drawdown is 30% of account -> "reject"; all losers -> "reject".

---

## C. Session order and checklists

### 10. OT-filters-before-bias
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = false.
- **Rule (corrected):** Session decision order: (1) evaluate every applicable avoidance/no-trade filter (N1-N10 and the CC day filters); if any fires, no trade that session; (2) only then evaluate daily bias / draw on liquidity; (3) then the setup. A strong or ideal bias never overrides a filter veto (cc08_006 ~19:14, stated for the London session).
- **Sources:** cc08_006_stK2gNqhLaM ~00:19:14.
- **Quote:** "regardless of what we have as a daily bias ... all those things fall second to this criteria"
- **Rulebook fix:** Add to section 3 (decision order) and to the N-rules intro: "Filters first: any no-trade filter vetoes the session before bias is read; bias never overrides it (cc08_006 ~19:14)."
- **BUILD SPEC (day_week_context; `blocked()` and the run_day session gate):**
  - The engine already never lets bias override a block, but the order is implicit and spread out: whole-day stand-asides at `run_day` ~2542-2553, the per-bar `blocked()` / `skip_news` / sloppy check at ~2862-2868, and separate `blocked()` calls in `sb_model.run_sb` and `pre_open`. The bias `want` is computed at ~2579, before the per-bar veto, which is harmless but invites a future bias-based override.
  - Make the order explicit: a helper `session_veto(day, session, t, p, ctx) -> str | None` that returns the first firing reason among `blocked()`, `skip_news`, sloppy stand-aside and `block_side`, called once at the top of the per-bar loop and by `run_sb` / `pre_open` instead of their own `blocked()` calls. Bias (`want`, `use_bias`) is read only after it returns None. Every veto is appended to `skips` with its reason.
  - No Params switch: a refactor that must leave trades identical (the test below checks that).
  - Tests: `test_veto_precedes_bias` (a day blocked by `blocked()` with a maximal bias table yields no trades in AM, PM, SB and pre-open); `test_session_veto_refactor_identical` (the synthetic `backtest.synthetic` run gives the same trades before and after).

### 11. OT-pre-session-checklist-order
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = false.
- **Rule (corrected):** Pre-session pipeline in ICT's order (cc12_004): 1) HTF monthly/weekly/daily bias, viewed on the 4H; 2) day of week and expected weekly/daily template (Mon-Wed preferred; fall back to Thu/Fri templates if Mon-Wed fails); 3) IPDA true-day hours (bulk 03:00-10:00 NY); 4) kill zone; 5-7) CBDR, Asian range and flout SDs [fx-only]; 8) intraday profile (London/NY continuation vs reversal); 9) key PD-array levels, internal vs external range, rounded to the nearest 10/5 level; 10) ADR5 high/low with 127/162 extensions overlapping 15m/60m arrays. Look for a setup only when every step is green. Avoidance filters veto first.
- **Sources:** cc12_004_Oec_0NM_OeY ~00:22:21 (list ~0:30-22:30).
- **Quote:** "I'm telling you in the order of the very specific detail of the order of how I do each thing"
- **Conflicts:** none; ICT notes the order is how he works, "not an invitation" never to experiment. The list is FX/London-heavy.
- **Rulebook fix:** Under M0 add "Pre-session checklist (cc12_004 ~22:21)" with the ten steps above, steps 5-7 marked [fx-only], and "setup scan only when all steps are green; filters veto first (item 10)".
- **BUILD SPEC (day_week_context; reads `htf.table`, `day_context`, `adr5`):**
  - A `checklist(ctx, hist, day, session, p) -> dict[str, bool]` evaluated once per session after `session_veto` (item 10), stored on `ctx.cl` and joined into a new `Trade.cl_fail` field (the failing step names, "" when all green):
    - `htf`: the `htf.table` bias for `p.htf_bias` (or `combo` when it is "off") is non-zero.
    - `dow`: weekday in `p.cl_days` (default Mon-Wed), or Thu/Fri when the week's Mon-Wed produced no session-target hit (the fallback template).
    - `ipda`: the session window starts inside 03:00-10:00 for AM / SB (PM always fails this step unless `cl_pm_ok`) [our interpretation of the IPDA true day for the PM].
    - `kz`: the arming time lies in a kill zone (`p.am`, the SB windows, or the London window when built).
    - `profile`: `profile_tags` gives an expected profile that agrees with the bias (requires `profile_tags=True`; otherwise counted green).
    - `levels`: at least one HTF array or pool lies in the trade direction (the #9 locked draw exists).
    - `adr`: the ADR5 projection from the session's extreme so far, using `strategy.adr5`, is not yet reached in the bias direction.
  - `p.checklist="tag"` only fills `cl_fail`; `"gate"` skips the session's new entries when any step fails (logged in `skips` as "checklist").
  - Params: `checklist: str = "off"` ("off" / "tag" / "gate"), `cl_days: tuple = (0, 1, 2)`, `cl_pm_ok: bool = True`. Add `checklist` to the choices list.
  - Test `test_checklist_steps`: a synthetic Tuesday with bias +1, draw above and ADR5 room -> all green; a Thursday after a Mon-Wed with a target hit -> `cl_fail="dow"`; `"gate"` blocks that session and `"tag"` does not.

### 12. OT-M17-cc09_001-checklist
- **rule_id / kind:** M17 / wrong. Scope: general. judgment = false.
- **Rule (corrected):** Remove cc09_001 from M17's fx-only list; keep only the Asian-range and pip-threshold parts fx_only. Long day trade (shorts mirror): (1) daily or 4h IOF bullish; (2) price recently traded into a daily/min-4h discount PD array and reacted; (3) sufficient room from entry to the opposing daily/4h premium array (convert ICT's 50-60 pip ideal and <40 pip scalp to index points; L15 minimum applies); (4) intraday price trades below the midnight NY opening price (and/or the overnight/Asian low); (5) the decline ideally ends in a 15m discount PD array; (6) price leaves that array sharply, and lingering lowers the odds; (7) optional confluence: short-term sentiment most bearish at entry (10-period Williams %R on 15m), used as a tag only. If (1)-(6) fail, no day trade.
- **Sources:** cc09_001__TNhWRPa6GA ~00:01:26 (conditions ~1:00-7:00).
- **Quote:** "daily and or 4-hour direction based on institutional order flow and combining the PD array matrix for the next level objectives"
- **Conflicts:** none. Partial overlaps: B5 (4h minimum alignment), B12 (buy at/below midnight open), L15 (room), M0.
- **[our interpretation]:** the pip-to-point conversion; "sharp departure" as a bar count; condition (5) "ideally" as a tag.
- **Rulebook fix:** In M17 change "cc09_001-007 fx-only" to "cc09_001 general except the Asian range and pip thresholds; cc09_003 setup 2 index (item 13); the rest fx-only", and add the cc09_001 checklist under M0 / B5.
- **BUILD SPEC (setups_models; the `_scan_core` bias gates are shared with bias_htf, merge after setups_models):**
  - Where: `_scan_core` after the `use_bias` gate (~3984), on the candidate entry, when `p.cc09_gate != "off"`:
    - (1) `iof`: the B6 `iof` column of `htf.table` (rule_coverage bias_htf) on D or 4h is in the trade direction; until B6 is built, fall back to `flip` on D or the 4h structure in `td_agree`.
    - (2) `react`: `Trade.b_react` (`htf.table` react, last `react_days`) is in the trade direction.
    - (3) `room`: distance from entry to the nearest opposing D/4h array (the owner #7 cap, `resist_lo` / `resist_hi`) >= `p.cc09_room_pts * p.es_pt`; below `p.cc09_scalp_pts` tag `cc09_scalp`.
    - (4) `open`: the session's extreme since 00:00 traded beyond the midnight open in the Judas direction (the existing `_judas` / `ref_open` data).
    - (5) `m15`: the sweep extreme sits in a 15m discount array (`_htf_tag` with the 15m zones from `sd.zones_tf`); tag only.
    - (6) `depart`: the leg from the sweep extreme reaches the MSS within `p.cc09_depart_bars` bars (the same speed measure as the setups_models displacement speed check).
    - (7) `wpr15`: 10-period Williams %R on 15m bars at the fill <= -80 (long) / >= -20 (short); tag only (B20 sentiment, never a gate).
  - `"tag"` writes the failing names into `Trade.cc09` (new str field); `"gate"` rejects the candidate when any of (1)-(4) or (6) fails.
  - Params: `cc09_gate: str = "off"` ("off" / "tag" / "gate"), `cc09_room_pts: float = 10.0`, `cc09_scalp_pts: float = 7.0` [our interpretation: ~50 / ~40 EURUSD pips as a % of price, then ES points], `cc09_depart_bars: int = 3` [our interpretation].
  - Test `test_cc09_day_trade_gate` in `tests/test_setups_models.py`: a synthetic long with all conditions -> passes and `cc09=""`; the same with entry 5 pts under a D bear FVG -> "room" fails and the gate rejects; a slow leg (6 bars to the MSS) -> "depart" fails; `wpr15` never blocks.

### 13. OT-M17-cc09_003-ny-expansion
- **rule_id / kind:** M17 / wrong. Scope: index. judgment = false.
- **Rule (corrected):** Exclude only cc09_003 setup 1 (Asian-session 20:00-midnight short-term-low/high fade) as fx-only. Add setup 2 as an index model: on a day when London has set the daily low (high) and the ADR5 low/high projection is still unfilled, between the NY open and 10:00 NY, buy (sell) when price runs below (above) a 5m short-term low (high) formed in the NY open session, as a turtle soup. Target expansion toward the ADR5 projection, with a fixed target and stop converted from 20 FX pips to index points (our scaling). Multiple setups per day are possible on 5m.
- **Sources:** cc09_003_km0haQkTalc ~00:17:37 (setup 2 ~11:10-12:30).
- **Quote:** "it's actually a really good pattern for S&P trading too so if you're an es Trader uh you can do this same pattern"
- **Conflicts:** none (the rulebook cites cc09_003 only in N8).
- **[our interpretation]:** the pip-to-point scaling; "NY open" = 08:30 for futures and 09:30 for cash (switch); the stop size (the verdict gives no number).
- **Rulebook fix:** In M17 drop cc09_003 setup 2 from the fx-only list; add a model "NY expansion turtle soup (cc09_003 ~11:10, ~17:37)" with the corrected rule.
- **BUILD SPEC (setups_models; new setup branch, reusing the turtle-soup core `levels.turtle_soup`):**
  - Day precondition, computed at `p.nyx_start` from closed bars only: the low (high) of 00:00 -> `nyx_start` was made in the London window 02:00-05:00, and ADR5 (`strategy.adr5(hist)`) projected from the day's high (low) so far, `high - adr5`, has not been traded.
  - Window `p.nyx_start` -> 600. Short-term lows / highs = `levels.pivots(h, l, 1)` on 5m bars formed after `nyx_start` (the 5m frame from `htf_bars(df, 5)` when the run is 1m).
  - Entry: when a 5m bar trades `sweep_ticks` below such a low and closes back above it (the `levels.turtle_soup` test with `max_depth = p.nyx_stop_pct * price`), buy at that close. Stop = entry - `nyx_stop_pct * price`; target = min(entry + `nyx_target_pct * price`, the ADR5 projection). Shorts mirror. `entry_kind="nyx_ts"`, `setup="NYX"`.
  - Several per day allowed up to `p.nyx_max` (one open position at a time, as in `run_day`); counts toward the session's `done` only when `p.nyx_counts_session`.
  - Passes through `session_veto` (item 10) and `use_bias` like every setup.
  - Params: `nyx_model: bool = False`, `nyx_start: int = 570` (510 = 08:30 futures test), `nyx_target_pct: float = 0.0018` (20 EURUSD pips at ~1.10 as a fraction of price; ~7 ES pts at 4000) [our interpretation], `nyx_stop_pct: float = 0.0018` [our interpretation], `nyx_max: int = 2`, `nyx_counts_session: bool = False`.
  - Test `test_nyx_turtle_soup` in `tests/test_setups_models.py`: synthetic day with the low at 03:15, ADR5 = 40 and today's range 25, a 5m low at 09:40 run at 09:50 and reclaimed -> one long, stop / target sized by the pcts and capped at the ADR5 projection; the same day with the low made at 09:35 (NY, not London) -> no trade; a trade after 10:00 -> none.

---

## D. Day templates, specialisation, indicators

### 14. OT-T13-eight-vs-six-profiles
- **rule_id / kind:** T13 / unlisted_contradiction. Scope: index. judgment = true.
- **Rule (corrected):** In T13, record the conflict: in cc10_013 ICT says 'eight' projected ranges (~3:06, ~16:37) but presents six named profiles. Why the counts differ is unexplained in the source. Implement the six named profiles, each with its stated PM alternatives (run the lunch extreme, run the intraday extreme, or consolidate into the close). Do not invent two extra profiles.
- **Sources:** cc10_013_P5pyzmgZA1s ~00:16:37 (also ~00:03:06).
- **Quote:** "there's only eight projected ranges that I use for the s p"
- **Conflicts:** spoken "eight" vs the six named slides / T13 "CC six index profiles".
- **Rulebook fix:** T13 (~line 487): append "ICT says 'eight' projected ranges (cc10_013 ~3:06, ~16:37) but names six; the difference is unexplained. We use the six, each with its PM alternatives (lunch extreme / intraday extreme / consolidate into the close)."
- **Build spec:** none. Already in rule_coverage with the same content: `profile_tags` (T13, section 4 setups_models, "profiles = expected profile from D / 4h") builds the six; this item adds the rulebook note only.

### 15. OT-one-state-tool-pairing
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true. (The checker gave no corrected rule; the claim's full rule is used.)
- **Rule:** Parameter `pairing` = expansion_ob | retracement_void | reversal_pool | consolidation_eq; the bot runs one at a time. Backtest each pairing alone, and combine pairings only after each proves out alone.
- **Sources:** cc01_001_0LhteuLVuDU ~00:19:34 (conditions and tools ~10:00-20:00).
- **Quote:** "you need know what context or framework you're going to trade in couple that with an ICT tool and then wait for those conditions"
- **[our interpretation]:** the four pairing names (only expansion + order block is stated explicitly near the quote) and the state classifier below.
- **Rulebook fix:** Under M0 add: "CC (cc01_001 ~18:30-19:40): pick one market condition (consolidation / expansion / retracement / reversal) coupled with one tool, trade only that, and add others over time."
- **BUILD SPEC (setups_models; `_scan` setup branches):**
  - State of the session, from data known at the session start: `consolidation` = the B17 daily-range regime (the `drange == 0` column specified in `bias_htf_intermarket.md` item 1, or the existing `Chop` when that column is absent); `expansion` = the prior day's range > ADR5 and its close in its top / bottom quarter in the bias direction; `retracement` = bias direction set but price inside the prior day's range and below (long) its 50%; `reversal` = otherwise (sweep of a session pool against the prior move, the current default engine).
  - Allowed entry kinds per pairing: `expansion_ob` -> `ob_pre` and the OB entries (`entry_kind` startswith "ob"); `retracement_void` -> "fvg" / "ifvg" entries whose gap lies in the leg's discount; `reversal_pool` -> the sweep + MSS entries (all current `entry_kind`s after a pool sweep, `swept != ""`); `consolidation_eq` -> entries within `eq_tol_pts` of the session range EQ, fading toward the opposite pool.
  - At the end of `_scan` (before the order is returned), when `p.pairing != "all"`, reject a candidate whose session state or `entry_kind` does not match. Every trade carries `state` (new `Trade` field) so `backtest.report` can split by it.
  - `study.py`: a block running each pairing alone ("pairing_expansion_ob", ...) and "all".
  - Params: `pairing: str = "all"` (current behaviour) / "expansion_ob" / "retracement_void" / "reversal_pool" / "consolidation_eq"; add to the choices list.
  - Test `test_pairing_filters` in `tests/test_setups_models.py`: on a synthetic sweep + MSS day classified `reversal`, `pairing="reversal_pool"` keeps the trade and `"expansion_ob"` drops it; `"all"` gives the same trades as before.

### 16. OT-no-indicator-triggers
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = false.
- **Rule (corrected):** Never use oscillator/indicator signals (RSI, stochastics, overbought/oversold crossings) as a bias or entry trigger (cc01_003 ~3:42). An indicator such as Williams %R (weekly per B20, 10-period on 15m per cc09_001 ~5:40) may be used only as a sentiment confluence tag: crowd most bearish at a long entry, most bullish at a short entry. Never use it as a gate. This is consistent with B20, not in conflict with it.
- **Sources:** cc01_003_B7_cjybYQ0g ~00:03:42; cc09_001 ~00:05:40.
- **Quote:** "get that off your charts because it is not how you're going to be able to see smart money"
- **Conflicts:** the claimed conflict with B20 is not real (both use %R as a sentiment read).
- **Rulebook fix:** Next to T1: "No oscillator / indicator as a bias or entry trigger (cc01_003 ~3:42). Williams %R only as a sentiment tag (B20 weekly; cc09_001 15m, 10-period)."
- **Build spec:** none. Already in rule_coverage with the same content: B20.3 `wpr_tag` (tag only), and the engine has no oscillator signal. The 15m %R tag is part of item 12.

---

## E. Parked swing / FX / stocks (M17)

### 17. OT-M17-osok-holding
- **rule_id / kind:** M17 / missing_rule. Scope: general (parked swing mode). judgment = false. (No corrected rule; the claim's full rule is used.)
- **Rule:** OSOK (parked swing mode): minimum hold 1 day, maximum 5 trading days; no requirement to enter Monday or exit Friday. Conflicts with the T11/N10 no-overnight rules, so it must be a separate swing mode.
- **Sources:** cc07_005_y0lVKWLsZeM ~00:22:40.
- **Quote:** "it can be as little as one day and as long as a week"
- **Conflicts:** overnight holds vs T11 / N10 (flat daily, no weekend holds).
- **Rulebook fix:** In M17 next to OSOK: "Holding period 1 day to 1 week (5 trading days); not Monday-in / Friday-out (cc07_005 ~22:40). Needs its own swing mode because T11 / N10 keep the intraday bot flat."
- **Build spec:** none (parked swing mode; no swing engine exists).

### 18. OT-fx-crosses-strong-vs-weak
- **rule_id / kind:** new / missing_rule. Scope: fx_only. judgment = true.
- **Rule (corrected):** [fx-only] Base FX selection on the seven majors (EURUSD, GBPUSD, AUDUSD, NZDUSD, USDCHF, USDCAD, USDJPY) and their currency futures, confirmed by DXY (cc11_002 ~5:39). Choose a cross only from relative strength between its two legs, not because it has a bigger range. When DXY is consolidating, the dollar pairs range; trade the non-dollar cross of the two majors in the direction of their divergence (EURUSD flat, GBPUSD falling -> EURGBP higher) (048 ~1:17:02).
- **Sources:** cc11_002_CxwFON8MLB0 ~00:05:39; 048_gGxVE8zUIRQ ~01:17:02.
- **Quotes:**
  - "to find it in the cross you have to understand these Majors"
  - "find big trending days or big trending model days in crosses that are not dollar based"
- **Note:** the example direction is as given by the checker. With GBPUSD falling and EURUSD flat, EUR is the stronger leg, so EURGBP rises.
- **Rulebook fix:** Add to the FX-only list (line ~1242).
- **Build spec:** none (fx_only).

### 19. OT-fx-no-exotics
- **rule_id / kind:** new / missing_rule. Scope: fx_only. judgment = false.
- **Rule (corrected):** [fx-only] Don't trade exotic pairs (ICT's example: EUR/CHF). Look at them only for interest-rate-differential study in hindsight (cc05_008 ~17:38).
- **Sources:** cc05_008_w6VlX-rsTUs ~00:17:38.
- **Quote:** "i don't tell people or even advise people to trade exotic pairs"
- **Rulebook fix:** Add to the FX-only list.
- **Build spec:** none (fx_only).

### 20. OT-fx-sunday-candle
- **rule_id / kind:** new / missing_rule. Scope: fx_only. judgment = false.
- **Rule (corrected):** [fx_only, low priority] On FX daily charts, treat the short Sunday session candle as part of Monday (blend the Sunday and Monday bodies into one candle) when measuring a daily order block or its mean threshold. This comes from one example in cc08_004 ~7:10. It does not apply to the SPX/NDX CFD daily bars unless they show a separate Sunday bar.
- **Sources:** cc08_004_JKzEhfwV1dY ~00:07:10.
- **Quote:** "blending that small little Sunday candle and Monday candle into one candle"
- **Rulebook fix:** Add to the FX-only list. Note: the engine's daily bars (`htf.sessions`) already fold the Sunday 18:00 reopen into Monday's session (N10.1), so nothing changes for the indices.
- **Build spec:** none (fx_only).

### 21. OT-stocks-smt-weekly-screen
- **rule_id / kind:** M17 / missing_rule. Scope: stocks. judgment = true.
- **Rule (corrected):** Stock buy-watchlist (parked, M17). Precondition: the stock market is technically poised to rally, in a seasonal buy window (Feb-May or Oct-Jan, studied about a month before). Universe: Dow 30 (optionally SPX500/NDX100, or an IBD list). Overlay the Dow on each stock. When the index (or two of the three averages) makes a lower low and the stock's matching low is higher, keep the stock. When one index then fails to make a lower low, the stock must make a higher high at the same juncture, or it is discarded. Prefer stocks already trending up on the weekly, with down-close weekly candles holding as support (cc10_016 ~1:49-4:24, ~10:03-11:00, ~14:14; cc11_003 ~23:35).
- **Sources:** cc10_016_rcO8-nb3S0Q ~00:02:01, ~00:13:07; cc11_003_kny8Kpisvoc ~00:36:08 (the checker notes ~36:08 is about the IBD rating; the SMT timing is ~23:35).
- **Quote:** "during bullish months we want to be selecting higher low stocks"
- **[our interpretation]:** the pivot size and the matching-low window; "weekly uptrend" as two rising weekly pivots.
- **Rulebook fix:** Under M17 stocks add the corrected rule as the stock watch-list screen.
- **BUILD SPEC (bias_htf, which owns new data loaders; a new parked module `mentorship/stocks.py`, not wired into `run_day`):**
  - Data: daily bars via `alpaca_data` (already used for SPY/QQQ) for a symbol list `DOW30` in `stocks.py`; the index = DIA (or YM daily from `htf.sessions` on the Databento frame).
  - `smt_screen(stock_d, index_d, asof, lookback=60) -> str`: using `levels.pivots(h, l, p.stock_piv_n)` on both daily series up to `asof` (closed bars only), find the index's last two pivot lows; if the second is lower and the stock's lowest low in the same window (+/- `match_days`) is higher than its own previous pivot low -> "keep". Then, if the index's next pivot low is not lower (failure) and the stock has not made a new pivot high above its last one within `match_days` -> "discard"; else "keep".
  - `weekly_up(stock_d, asof) -> bool`: on `htf.weeks(...)` bars, the last two weekly pivot highs and lows rise, and the low of the last down-close week has not been closed below.
  - `watchlist(asof)`: runs only when `asof` is in or within ~21 trading days before a buy window (Feb-May, Oct-Jan; the seasonal windows already in `bias_htf_intermarket.md`); returns the kept symbols ranked by `weekly_up` first.
  - Switch: `Params.stocks_mode: bool = False`; `stocks.py` raises if called with it off (parked per M17).
  - Test `test_stock_smt_screen` (`tests/test_other_gaps.py`): synthetic index with lower lows and a stock with higher lows -> "keep"; a stock that also makes lower lows -> not kept; the index's failure swing with no stock higher high -> "discard"; an `asof` in July -> empty watch list.

### 22. OT-stocks-exclusions-selection
- **rule_id / kind:** M17 / missing_rule. Scope: stocks. judgment = true.
- **Rule (corrected):** Before screening, drop VZ, KO and GE (ICT in 2017 also dropped MSFT and INTC as 'not exciting'; this is his opinion and may change). From the screened survivors, select 2-4: affordable call options; positioned at or just below old weekly highs, poised for a low-resistance breakout; not already too extended from weekly/daily structure; with quarterly sales and profit increases as a supporting factor (cc10_016 ~3:01, ~11:08-13:14).
- **Sources:** cc10_016_rcO8-nb3S0Q ~00:03:01, ~00:11:55.
- **Quotes:**
  - "we want to avoid safe stocks like Verizon GE or general electric or Coca-Cola"
  - "selecting call options that were affordable as well as where each were trading in historical terms"
- **[our interpretation]:** "at or just below old weekly highs" and "too extended" as distances.
- **Rulebook fix:** Under M17 stocks add the exclusion list and the 2-4 selection step.
- **BUILD SPEC (bias_htf; `mentorship/stocks.py`, parked):**
  - `EXCLUDE = ("VZ", "KO", "GE")`, `EXCLUDE_2017 = ("MSFT", "INTC")` (applied when `p.stock_excl_2017`). `watchlist` (item 21) drops them before screening.
  - `select(kept, asof, n_max=4)`: for each kept stock, `near_high` = close within `p.stock_near_high_pct` below the highest weekly high of the last 52 weeks (or at / above it); `extended` = close more than `p.stock_ext_atr` x 20-day ATR above the last weekly pivot low. Keep `near_high and not extended`, rank by distance to the old high (closest first), return up to `n_max` (at least 2 when available, else none).
  - Option affordability and quarterly sales / profits need data we do not have: hooks `opt_cost(sym)` and `fund_ok(sym)` return None and are ignored when None.
  - Params (with `stocks_mode`): `stock_excl_2017: bool = False`, `stock_near_high_pct: float = 0.05`, `stock_ext_atr: float = 3.0` [our interpretation].
  - Test `test_stock_select`: VZ in the input is never returned; a stock 2% under its 52-week weekly high is kept, one 20% under is not, one 5 ATR above its weekly pivot low is dropped as extended; more than 4 survivors -> 4 returned.

### 23. OT-stocks-canslim-fundamentals
- **rule_id / kind:** M17 / missing_rule. Scope: needs_unavailable_data. judgment = true.
- **Rule (corrected):** Candidate universe = IBD 50 or IBD Sector Leaders with SmartSelect Composite Rating >= 98 (a proxy without IBD, RS rank >= 90 plus top EPS growth, is [our interpretation]). Filters: C = latest-quarter EPS growth >= 25%, accelerating over the last 3 quarters, with quarterly sales above the same quarter last year; A = annual EPS growth >= 25% in each of the last 3 years, rising annual sales, ROE >= 17%, consistently profitable (not one first profitable quarter); N = something new (product, management, new price high, IPO within ~8 years); S = price > $20 (preferred >= $25; the cc11_003 demo scanned $25-$80), with a reasonable float and the smaller float preferred among equals; L = leader by relative strength (item 24); I = >= 10 mutual funds holding, institutional ownership rising 2-3 quarters; M = Dow Theory confirmed uptrend plus seasonal buy windows (Feb-May; mid-Sep/Oct-Dec), ideally after the Sep-Nov index SMT divergence into a discount (cc10_018 ~22:38-23:28, ~34:58-35:11). Passing the filters is not a buy until the higher-low SMT test (item 21) passes.
- **Sources:** cc10_018_cv-fwKKXrwQ ~00:08:48, ~00:19:26; cc11_003_kny8Kpisvoc ~00:35:32, ~00:36:08, ~00:22:01; cc10_016_rcO8-nb3S0Q ~00:13:07.
- **Quotes:**
  - "I like to see stocks about twenty dollars preferably 25 a share"
  - "the smart select composite rating okay and I want 98 or higher"
- **Conflicts:** ICT rejects O'Neil's 8% per-stock stop as unnecessary (cc10_018 ~29:40) and gives no stock sizing of his own.
- **Rulebook fix:** Under M17 stocks, replace the bare "CAN SLIM" with the thresholds above, ICT's M (Dow Theory + IOF + PD arrays + quarterly shifts + seasonals instead of O'Neil's timing), and the note that the 8% stop is rejected.
- **Build spec:** none (needs IBD ratings, fundamentals and fund-holding data). The price-only parts (S price floor, M windows, SMT test) are covered by items 21-22.

### 24. OT-stocks-rs-leadership
- **rule_id / kind:** M17 / missing_rule. Scope: stocks. judgment = true. (The checker kept the claim's rule.)
- **Rule:** Only when the major-market-direction precondition is bullish: rank sectors by relative performance and keep the top one(s); inside them rank industry groups and keep the leaders; inside those keep the stocks with the strongest relative strength that are moving up away from a discount toward buy-side liquidity. ICT gets the sector, industry-group and stock rankings from IBD (cc11_003 ~14:03, ~22:24), so for the bot this needs data we do not have.
- **Sources:** cc11_003_kny8Kpisvoc ~00:14:23 (~13:05-15:15); cc10_018 ~16:02-16:56.
- **Quote:** "in a bullish Market you're looking for bullish sectors in the marketplace and inside those sectors you want to find the strongest industry groups"
- **Rulebook fix:** Under M17 stocks add the top-down leadership filter (L of CAN SLIM) with the IBD data note.
- **BUILD SPEC (bias_htf; `mentorship/stocks.py`, parked) - price-only stock leg; the sector and group legs wait for data:**
  - `rs_rank(stocks: dict[str, DataFrame], index_d, asof, n=63) -> dict[str, float]`: each stock's n-day % change minus the index's, ranked to a 0-100 percentile across the universe (closed bars to `asof`).
  - `leaders(...)`: runs only when the market precondition is bullish (the index's `htf.table` `flip` > 0, or `weekly_up(index_d)` from item 21); keeps stocks with `rs_rank >= p.stock_rs_min` whose close is above the 50% of their last 60-day range (leaving a discount). Hooks `sector_of(sym)` / `group_of(sym)` return None; when they return values, rank sectors and groups by the mean member `rs_rank` and keep the top `p.stock_top_sectors` before ranking stocks.
  - Order in `watchlist`: exclusions (item 22) -> `leaders` -> `smt_screen` (item 21) -> `select` (item 22).
  - Params (with `stocks_mode`): `stock_rs_min: float = 80.0`, `stock_top_sectors: int = 2` [our interpretation].
  - Test `test_stock_rs_leaders`: three synthetic stocks returning +20%, +5% and -5% against an index at +3% rank in that order; with a bearish index `flip` the list is empty; with the sector hooks None the sector step is skipped.

### 25. OT-stocks-swing-only
- **rule_id / kind:** M17 / missing_condition. Scope: stocks. judgment = false.
- **Rule (corrected):** Individual stocks (cc10_018): swing only, entered in the seasonal buy windows (Feb-May; last half of Sep/Oct to year end). Take profit on runs to new highs and reinvest; no buy-and-hold; no intraday stock setups. Index futures and index ETF proxies are unaffected.
- **Sources:** cc10_018_cv-fwKKXrwQ ~00:33:36 (also ~29:19-29:28, ~31:34-32:50).
- **Quote:** "there's no getting in your day trading stocks that's nonsense it's foolishness"
- **Rulebook fix:** Under M17 stocks: "Individual stocks are swing-only (cc10_018 ~33:36): no intraday stock setups, no buy-and-hold; exit on runs to new highs and reinvest. Index futures and SPY/QQQ are unaffected."
- **BUILD SPEC (day_week_context, which owns `BT.run`; guard in `backtest.run` and `run_day`):**
  - `INDEX_SYMBOLS = {"SPY", "QQQ", "DIA", "SPX", "NDX", "ES", "NQ", "YM"}` in `strategy.py`. At the top of `run_day` (`strategy.py:2490`), if `symbol.upper()` is not in it and `not p.stock_intraday`, return `[]` and append `(day, symbol, "stock", "swing_only")` to `skips`. `backtest.run` (`:269`) warns once for such a symbol.
  - The swing exit rule (runs to new highs, reinvest) belongs to the parked swing mode; nothing is built for it.
  - Params: `stock_intraday: bool = False`. Trades are unchanged: every current run uses an index symbol.
  - Test `test_stock_intraday_guard`: `run_day` on a synthetic frame labelled "AAPL" returns no trades and logs the skip; labelled "SPY" it gives the same trades as before; `stock_intraday=True` lets "AAPL" trade.
