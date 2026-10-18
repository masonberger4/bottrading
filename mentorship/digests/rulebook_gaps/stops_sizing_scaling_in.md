# Rulebook gaps: stops, sizing and scaling in

Topic `stops_sizing_scaling_in`. Every item below is a verified gap between ICT's captions and `mentorship_rules.md`. When the checker gave a corrected rule, that corrected rule is the one written here; when it gave none, the claim's full rule is used. "[our interpretation]" marks thresholds or readings that ICT does not state.

Conventions:
- Times are New York. Prices in ES points unless stated; the engine converts with `p.es_pt` (SPY ~ ES/10) and one ES tick = 0.25 pt.
- New Params switches default off (rule_coverage.md section 3). Each work package adds its fields in its own commented block at the end of `Params` (strategy.py ~65-705) and validates string switches in `__post_init__` (~759).
- Code anchors (current `mentorship` branch):
  - Sizing: `_risk_budget` / `_total_cap` / `_first_units` (strategy.py ~815-826); `Params.adds = (0.5, 0.33, 0.17)` (fractions of the first unit, ~116), `risk_pct` 1.2% / `max_total_risk_pct` 1.3% (~319-321), `max_notional` (~110), `lot` (~228).
  - Adds: the run_day add block (~2717-2736: new FVG -> `_arm_add`, `_ob_add`, `setups.more_adds`), `_arm_add` (~2970), `_ob_add` (~2986), `setups.add_ok` (~1053), `setups.more_adds` (~1074).
  - Stops: the `_scan_core` stop block (~3540-3600: `stop_mode` ob_mt / fvg / ob_near / fvg_candle / ce2, `vi_stop`, `ifvg_stop`, `ote_adjust`); `_turtle` (~3776, `ts_stop`); `SB._arm` (sb_model.py ~213-250).
  - Management: the run_day position loop (~2590-2716), `_after_close` (~1858, `state["day_pts"]`).
- Work packages are the names in `rule_coverage.md` section 3. Most items here belong to **entries_stops_sizing** (the `_scan_core` entry/stop block, the pending-fill and add-arming blocks, `SB._arm`). Exit-side items go to **management_exits**, final-target R:R to **targets_partials**, the SB entry split to **silver_bullet**, turtle-soup / re-entry branches to **setups_models**, seasonal size multipliers to **day_week_context**, HTF/swing studies to **bias_htf**.
- Tests go in a new `tests/test_entries_stops.py` unless a spec names another file (`tests/test_setups_models.py`, `tests/test_levels_detectors.py`). Each spec names its test function.
- Items scoped `fx_only` or `needs_unavailable_data` get the rulebook fix only, with no build spec. Sub-minute bars, retail sentiment, war/geopolitical flags, commodity baskets and stock option chains count as unavailable.
- Swing, position, weekly and daily-chart models are parked under M17. Their `general`-scope build specs are research studies on daily / 4h bars (`study.py`, `htf.py`), not live `_scan_core` branches.

Summary: 72 items, 57 new build specs. Items without a build spec:
- 6 fx_only: E6-mt-stops-futures-only, M12-ts-sweep-depth-fx, E6-tf-proportional-stops, E6-london-stop-table, L16-adr5-stop, M17-split-entry-open
- 5 that need data we do not have: E12-subminute-adds, E9-retail-sentiment-max, E9-war-regime, new-basket-allocation, new-stock-calls (stock scope, but needs an option chain with Greeks)
- 4 already listed in rule_coverage.md with the same content, or already built:
  - E10-cascading-halving: E10 "`loss_halving` with halving_floor and winback_frac carried across days" is the same rule (halve per loss down to a floor, win back ~50%). Rulebook text fix only; the spec note below pins the reference risk.
  - E6-two-gap-ce: already built as `stop_mode="ce2"` (strategy.py ~3587, M2 069 ~13:46). Only the E6 wording is wrong.
  - E6-at-the-high: E6c `stop_mode="sweep"` + E6f `stop_pad_ticks` (section 3, entries_stops_sizing High/Medium) already give "at the high" as `stop_pad_ticks=0`.
  - E11-020-fomc-size: a contradiction to record only. The bot keeps risk-% sizing, and the FOMC-eve size-down is already E9 `size_rules` (section 3).

Shared pieces this topic adds (build first, entries_stops_sizing):
- `add_size_fracs(p) -> tuple`: resolves `add_ladder` / `add_sizes` into the fraction tuple `_arm_add` reads instead of `p.adds` directly. Items 1-4, 11, 12 use it.
- `wick_ce(o, h, l, c, k, side)`: (high + max(o, c)) / 2 for an upper wick, (low + min(o, c)) / 2 for a lower wick. Put it in `levels.py` (levels_detectors owns the file; one-line helper, no detector state). Items 13, 14, 17, 44 use it.
- `size_mult(ctx, p, d, tags) -> float`: the E9 `size_rules` multiplier hook already listed in section 3; items 36-38 add rows to it.

---

## A. Adds and pyramids (E12)

### 1. E12-equal-size-adds
- **rule_id / kind:** E12 / unlisted_contradiction. Scope: index. judgment = true.
- **Rule:** Param `add_sizes` = 'decreasing' (default) | 'equal_or_less' (each add <= the first unit; 013 variant: 10, 10, then 5s; 006: the final FVG-low-end add repeats the last unit). Observed add locations: in 001, the entry 1m FVG's low (exact-tick wick tags while 1m bodies fail to close beyond the 60m FVG), the breakaway gap and the breaker. In 096, the breaker body/MT and a retouch of a prior wick. In 002, the top of a 30m FVG (orange) above price on a retrace. All units share the original or trailed stop within the total risk cap. Test equal vs decreasing.
- **Sources:** 001_XN8tuO4QIRw ~00:39:05; 002_GHaD0mebgMU ~00:08:24; 013_V1thfpo-R9U ~00:27:18; 096_tjnir-o4rsQ ~00:09:30.
- **Quotes:** "I added more and then added one more time just to show you that I was not fearful of the stop being hit" (001); "I went in with 10 contracts ... with a down closed candle I went in with 10 more" (013).
- **Conflicts:** E12 (006 6/3/2/1, 083/085 5/4/3/2/1, "never a larger add") vs 001/002/096 equal 1-lot adds and 013 10/10/5/5.
- **[our interpretation]:** the claim's "max 2 wick-tag adds" and "within 1 tick" are not in the source and are dropped.
- **Rulebook fix:** E12 Sizes: "Usually decreasing, but equal-size adds also occur (001, 002, 096 1-lot adds; 013 10/10/5/5; 006 final FVG-low-end add = last unit). Never larger than the first unit except 070 / 103 (see below)."
- **BUILD SPEC (entries_stops_sizing):**
  - Where: new `add_size_fracs(p)`; `_arm_add` (~2970) uses `fracs[k]` instead of `p.adds[k]`, and the `len(tr.adds) < len(p.adds)` checks in the add block (~2721-2735) use `len(fracs)`.
  - 'equal_or_less': `fracs = (1.0,) * add_max_n`; 'equal_013': `(1.0, 0.5, 0.5)`. The 1.3% cap shrink in `_arm_add` still applies.
  - New add locations (each a switch, all off): `add_far_edge` (a 1m wick tags the entry FVG's far edge while no 1m body closes beyond it; limit there), `add_wick_retouch` (limit at the prior retrace's wick extreme), `add_htf_fvg_edge` (limit at the near edge of the nearest 30m FVG on the retrace side, via `ctx.conf` 30m rows). Each goes through `setups.add_ok`.
  - Params: `add_sizes: str = "decreasing"` ("decreasing" / "equal_or_less" / "equal_013"), `add_max_n: int = 3`, `add_far_edge: bool = False`, `add_wick_retouch: bool = False`, `add_htf_fvg_edge: bool = False`.
  - Test: `test_add_sizes_equal`. A long with first unit 6 and two FVG adds: "decreasing" gives 3, 2; "equal_or_less" gives 6, 6 shrunk by the 1.3% cap (assert the shrink, never above 6).

### 2. E12-ladder-631
- **rule_id / kind:** E12 / unlisted_contradiction. Scope: index. judgment = false.
- **Rule:** Standard 10-lot ladder = 6/3/1 (each add about half the previous; 021, 026, 060, 070). Aggressive = 6/4/2/1 (021). The 006 variant is 6/3/2/1, plus a repeat 1 at the FVG low. Adds are resting orders at the next PD array (VI, FVG/CE, OB MT, wick CE) on a retrace against the open position, within the E12 cutoffs. Param ladder in {631, 6421, 6321}.
- **Sources:** 021_DVxC7UAHzwk ~00:20:04; 060_ZtLMTXv-Dr0 ~01:03:12; 026_GFdWahZUNOw ~01:48:03 (also 070 ~36:23).
- **Quotes:** "six contracts and then I'll go down to three on the second one and I'll just do one" (021); "it's one contract that's my standard 10 lot model" (060).
- **Conflicts:** 006 (6/3/2/1) vs 021/026/060/070 (6/3/1 standard).
- **Rulebook fix:** E12: "Standard 10-lot = 6/3/1 (021, 026, 060, 070); aggressive 6/4/2/1 (021); 006 shows 6/3/2/1. Adds are resting limits at the next PD array on a retrace against the position, not on new highs."
- **BUILD SPEC (entries_stops_sizing):**
  - Where: `add_size_fracs(p)`: `add_ladder` "631" -> (0.5, 0.17); "6421" -> (0.67, 0.33, 0.17); "6321" -> (0.5, 0.33, 0.17) (= today's `adds`). Empty = use `p.adds`.
  - Params: `add_ladder: str = ""`. Study grid runs all three; 631 is the candidate default once tested (owner decision; keep "" now).
  - Test: `test_add_ladder_presets`. First unit 6: "631" arms 3 then 1 and no third add; "6421" arms 4, 2, 1.

### 3. E12-067-citation-wrong
- **rule_id / kind:** E12 / wrong. Scope: index. judgment = true.
- **Rule:** E12 exception list = 070 only (1, 3, 6 when entering early in a breaker A-B leg). 067 is a separate pattern: first unit largest (8), then adds of 5, 5, 2, 5, 5 at each new discount PD array on the 15s chart (the reclaimed bullish OB, the IFVG). The adds sit above the first entry, all before the first partial. With full size on, the stop sits under the reclaimed OB/IFVG (4413.25) and is not chased higher. Most adds (5) are smaller than the first unit, but 5 follows 2, so this is not a strictly decreasing ladder.
- **Sources:** 067_vuBRMFhFZAY ~01:18:09 (frames 1:19:00, 1:20:40).
- **Quote:** "I'm adding pyramiding and I've already annotated that fair value Gap ... it's an inversion fair value Gap" (067).
- **Conflicts:** none.
- **[our interpretation]:** the claimed stop progression 4409.75 -> 4410.50 -> 4413.25 could not be checked; only 4413.25 at full size is confirmed.
- **Rulebook fix:** E12 exceptions: remove 067 from the 1/3/6 exception. Add: "067: 8 then 5/5/2/5/5 (30 lots) at reclaimed OB / IFVG retests on 15s, all above the first entry and before any partial; stop under the reclaimed OB/IFVG, not chased higher."
- **BUILD SPEC (entries_stops_sizing):**
  - Where: `add_size_fracs` preset `add_ladder="067"` -> (0.625, 0.625, 0.25, 0.625, 0.625) with `add_max_n=5`; adds come from `reclaimed_ob` (A18, built) and IFVG retests via `setups.more_adds` (new branch `add_on_ifvg`: an IFVG formed after the fill, limit at its near edge). 1m approximation of the 15s chart.
  - Stop: when `add_stop_under_array` is on, each add raises `pos["stop"]` to the add array's bottom - pad only if that is higher and keeps the add's risk >= `min_risk_pts` (never lowers; E7).
  - Params: `add_on_ifvg: bool = False`, `add_stop_under_array: bool = False`.
  - Test: `test_add_ladder_067`. Synthetic long with a reclaimed OB and an IFVG after the fill: five adds armed in the 067 fractions, total open risk <= 1.3%, stop ends at the IFVG bottom - pad.

### 4. E12-in-zone-larger-second
- **rule_id / kind:** E12 / unlisted_contradiction. Scope: index. judgment = true.
- **Rule:** Record as an E12 exception (103, NQ): two resting sells inside the same entry array (breaker zone); the better-priced, deeper fill was larger (5 then 10). Later adds outside the zone were 5 and 5, below the larger unit, at lower prices in the trade direction. Test an 'in-zone ladder' (1x, 2x, then 1x adds) vs the default decreasing ladder.
- **Sources:** 103_IU673ZUGuxI ~00:34:22 (frame 34:20).
- **Quote:** "that candle has my two entries here right in here so it went up hit it came back off and I got filled there" (103).
- **Conflicts:** E12 "never a larger add" vs 103 5/10/5/5.
- **Rulebook fix:** E12 exceptions: "103 (NQ): two resting entries in the same breaker zone, deeper one larger (5 then 10); later adds 5, 5."
- **BUILD SPEC (entries_stops_sizing):**
  - Where: `_finish_order` (~3949) builds the pending order. When `in_zone_ladder` is on and the entry array is a breaker (`pos["bz_side"]` / `breaker_entry`), place two limits: 1/3 of the first-unit size at the near edge and 2/3 at the breaker MT (deeper). Store both in `pending["legs"]`; the fill block (~2740-2780) fills each leg separately; `tr.shares` = the sum of filled legs. Later adds use `add_size_fracs` relative to the first leg (1x).
  - Params: `in_zone_ladder: bool = False`.
  - Test: `test_in_zone_ladder`. Short breaker zone: price fills the near-edge leg only -> 1/3 size; fills both -> full; the next add = the first leg's size.

### 5. E12-start-small-build
- **rule_id / kind:** E12 / unlisted_contradiction. Scope: general. judgment = true.
- **Rule:** Daily stop-entry model (cc05_016): start with about 50% of normal size; add when price returns to the opening price of prior trigger candles (now OBs); the position may build larger than the initial unit. Weekly OSOK (cc07_008, bearish week; bullish mirror): Monday, in the anticipated weekly premium array, sell only a small portion (fraction is our choice); add the rest if Tue/Wed makes a higher high into premium; if Tuesday fails to make a higher high, the small piece is already at the high. Beginners don't try to pick the weekly high with full size; experienced traders may.
- **Sources:** cc05_016_vb_Yc-gCBfU ~00:13:37; cc07_008_LBlK6JB0QS0 ~00:29:33, ~00:29:50.
- **Quotes:** "if you go with a half position or half of your traditional size you can go and add more back in" (cc05_016); "you can sell us a very small portion on Monday" (cc07_008).
- **Conflicts:** E12 largest-unit-first vs cc05_016 / cc07_008 small-first.
- **[our interpretation]:** the Monday fraction (0.25).
- **Rulebook fix:** E12 + M17: "Swing/weekly models build small-first: cc05_016 starts at ~50% and adds at prior trigger-candle opens; cc07_008 OSOK sells a small Monday piece and adds on a Tue/Wed higher high into premium."
- **BUILD SPEC (bias_htf, research study; parked under M17):**
  - Where: `study.py` new `osok_scale_in(daily, weekly, p)` on daily bars of ES/SPY. Weekly bias from `htf.table` (`weekly_bias`). Monday: if price trades into the weekly premium array (htf `_arrays` W/D rows), sell `osok_first_frac` of planned size; add the rest at the Tue/Wed higher high into the same/next array, or at the next intraday premium retrace (daily approximation: next day's open above Monday's close) if Tuesday makes no higher high. Compare vs full size on Monday.
  - Second variant `daily_stop_half`: daily stop-entry at 50%, add at returns to prior trigger-candle opens (shares item 22's engine).
  - Params (study config): `osok_first_frac: float = 0.25`, `daily_first_frac: float = 0.5`.
  - Test: `test_osok_scale_in_study` (tests/test_setups_models.py style, synthetic weekly path): Monday piece filled at 0.25, Wednesday higher high adds 0.75, average price above Monday's.

### 6. E12-adds-after-partials-intraday
- **rule_id / kind:** E12 / unlisted_contradiction. Scope: index. judgment = true.
- **Rule:** Default: no adds after the first partial (E12, 006). Switch add_after_partial (default off): after partials, one small add is allowed if price retraces into the low edge of a bullish FVG it just broke down through (071, short; long mirror), or into a still-valid PD array in high-volatility conditions (092, add back up to the size taken as partials). The trailed stop must hold; the add is no larger than the earlier units; combined risk <= max_total_risk.
- **Sources:** 071_3FGFEuaDSOc ~00:15:58; 092_9MLRE-n6St8 ~01:30:08; 003_ojy5ApHhEu4 ~01:06:27 (weak).
- **Quotes:** "just to prove the theory I'm going to add one contract" (071); "I'm going to be more likely to take partials and maybe maybe add them back later on" (092).
- **Conflicts:** 006 ~53:53 (no adds after partials) vs 003, 071, 092.
- **[our interpretation]:** "high volatility" = ADR5 above its 20-day median.
- **Rulebook fix:** E12d: "Exceptions: 071 one 1-lot add after partials at the broken FVG's edge; 092 in high volatility partials may be added back."
- **BUILD SPEC (entries_stops_sizing; shares the add block with management_exits):**
  - Where: add block `can_add` (~2721): allow `pos["t1_done"]` when `add_after_partial` != "" and `pos.get("post_partial_adds", 0) < 1`. "inv_fvg": a same-side FVG (bull for a long mirror: bear FVG for a short) that price closed through after the fill; limit at its near edge on the retrace. "high_vol": any new same-side FVG while `adr5(hist) > add_hv_mult x median(20-day ranges)`; size up to the units taken as partials.
  - Size: min(smallest earlier unit, partial units) for "inv_fvg"; partial units for "high_vol"; then the `_arm_add` cap shrink.
  - Params: `add_after_partial: str = ""` ("inv_fvg" / "high_vol"), `add_hv_mult: float = 1.2`.
  - Test: `test_add_after_partial`. Short, T1 taken, price retraces to the broken bull FVG low: one add armed at 1 lot; a second retrace arms nothing.

### 7. E12-readd-after-partials-swing
- **rule_id / kind:** E12 / unlisted_contradiction. Scope: general. judgment = true.
- **Rule:** Swing/position mode only: after a partial of fraction f at a logical opposing level, re-add f (up to slightly more, e.g. a third for a quarter; cc05_013) when price retraces into a newly formed PD array in the trade direction (a new FVG confirmed on its 3rd candle close, 098; a new OB, cc04_003). In cc06_008 the add-back comes after price reaches 50% of the objective, on a short-term decline. The stop stays at the original level (098), or at breakeven after the first profit (cc06_008). Day trades keep E12.
- **Sources:** 098_PejS-nZTQlE ~00:25:13; cc04_003_PIYh0CxoY9c ~00:30:31; cc05_013_crPpMwgwa7k ~00:19:55; cc06_008_VL4YLTRerHY ~00:17:00.
- **Quotes:** "whatever you took off as a partial down here you can add it back when it trades up into here" (098); "add back the one quarter taken off after a short-term decline" (cc06_008).
- **Conflicts:** 006 (no adds after partials), E12 no adds past EQ vs 098, cc04_003, cc05_013, cc06_008.
- **Rulebook fix:** E12 + M17: "Swing/position trades may re-add the partial size (to slightly more) on a retrace into a new PD array; stop at the original level (098) or breakeven (cc06_008). Day trades: no adds after partials."
- **BUILD SPEC (bias_htf, research study on daily / 4h bars):**
  - Where: `study.py` new `swing_readd(df4h, daily, p)`: entries from the existing HTF swing study path; partial f at the first opposing HTF array; re-add f x `readd_mult` at the first new same-side 4h FVG (confirmed on candle 3's close) or new OB after the partial; variant "half_obj" waits until price reached entry + 0.5 x (target - entry). Stop: "orig" or "be".
  - Params (study config): `readd_mult: float = 1.0` (test 1.33), `readd_gate: str = "any"` ("half_obj"), `readd_stop: str = "orig"` ("be").
  - Test: `test_swing_readd`. 4h synthetic leg: partial 0.25 at the first array, new FVG after it -> re-add 0.25 with the stop unchanged.

### 8. E12-add-cutoff-definition
- **rule_id / kind:** M2/E12 / shortened. Scope: general. judgment = false.
- **Rule:** Short (long mirror): implied range H (premium high) to T (undelivered target pool), EQ = (H+T)/2. Entry at EQ or premium is allowed (025). Adds only at PD arrays that formed at or above EQ (092); arrays formed below EQ are only a calibration check, never a new entry or add. Separately, stop all adds once price trades past the midpoint of the discount half, T + 0.25*(H-T) (025). Keep the existing displacement-leg 25% cutoff as an alternative parameter.
- **Sources:** 025_7RiUUCqQ3SY ~00:48:05; 092_9MLRE-n6St8 ~01:16:43.
- **Quotes:** "you can't go in and start pyramiding once ... we start Crossing into the halfway point of the discount level" (025); "we can't add to a pyramid of position ... this is just an observation level" (092).
- **Conflicts:** 025 cutoff by price at 75% of the range vs 092 cutoff by where the array formed.
- **Rulebook fix:** E12e / M2: "Two tests: (a) the add array must have FORMED at or above EQ of the implied range H..T (092); (b) no adds once price trades past T + 0.25(H-T) (025). The leg-based cutoff stays as an alternative."
- **Already in coverage:** E12e `add_cut` (EQ of range or leg 75%) and the built `add_leg_cut` cover test (b). Test (a) is new.
- **BUILD SPEC (entries_stops_sizing):**
  - Where: `setups.add_ok` (~1053). With `add_form_eq`: H = the session's sweep extreme / leg extreme stored in `pos["leg"]`, T = `pos["t_final"]` (the last ladder rung, i.e. the locked draw). Reject an add whose array's formation price (FVG: its far edge from T, i.e. the edge nearer H; OB: its body top for a short / body bottom for a long) lies on the T side of EQ. Also store the rejected array as tag `cal_check` on the trade (calibration only).
  - Test (b) when `add_cut_ref="range"`: same as E12e `add_cut` but measured on H..T, not the leg.
  - Params: `add_form_eq: bool = False`, `add_cut_ref: str = "leg"` ("range").
  - Test: `test_add_form_eq`. Short H=4100, T=4060 (EQ 4080): a bear FVG formed at 4085-4088 is an add; one formed at 4072-4075 is rejected and tagged; after a print at 4069 no add at all.

### 9. E12-trend-day-adds
- **rule_id / kind:** E12 / unlisted_contradiction. Scope: index. judgment = true.
- **Rule:** Param add_mode = 'eq_cutoff' (default) | 'trend_day'. On a day without a Fed/news smoke screen that is trending (classifier is our assumption), keep adding on retraces into new PD arrays until price reaches the far extreme of the daily range (the opposing daily draw). Sizes still follow E12 and total risk stays within the cap. Evidence is a single passing remark (038), so it is low priority.
- **Sources:** 038_4H74nXabvL0 ~01:15:27.
- **Quote:** "we can see trending days and keep on adding to the position until it rolls to the far extreme of the daily range" (038).
- **Conflicts:** E12 add cutoff (022/025/092) vs 038.
- **[our interpretation]:** trend-day classifier: no high-impact news that day (`calendar.events`) and price >= 0.5 x ADR5 away from the 09:30 open by the add bar, without trading back through the open.
- **Rulebook fix:** E12: "038 (single remark): on clean trending days (no Fed/news) adds may continue until the far extreme of the daily range."
- **BUILD SPEC (entries_stops_sizing):**
  - Where: `setups.add_ok`: when `add_mode == "trend_day"` and the day qualifies, skip the `add_leg_cut` / `add_cut` tests; reject adds once price is within `0.1 x ADR5` of the opposing daily draw (`ctx` daily pools / PDH-PDL). `add_max_n` still caps the count; sizes from `add_size_fracs`.
  - Params: `add_mode: str = "eq_cutoff"` ("trend_day"), `trend_day_adr: float = 0.5`.
  - Test: `test_trend_day_adds`. A trending synthetic day: a third add past the leg 75% is armed under "trend_day" and rejected under "eq_cutoff"; on an FOMC day it is rejected in both.

### 10. E12-low-end-add-conditions
- **rule_id / kind:** E12 / missing_condition. Scope: index. judgment = false.
- **Rule:** If an IOFED add was followed by a body close inside the FVG, place one final add at the FVG's low end. Size = the smallest earlier add, never larger. Only if the earlier units still show open profit ('equity behind' them), risk room remains (max_total_risk), and no partial has been taken. The 'body close beyond the far edge = no add (X6)' clause is our addition, not stated here.
- **Sources:** 006_VKkn8uckkW0 ~00:52:14 (context ~51:40-52:50).
- **Quote:** "I won't do two or anything higher than I'll just do the same thing I did on the lowest new pyramid entry" (006).
- **Conflicts:** none.
- **Rulebook fix:** E12c: "Size = the smallest earlier add; only with the earlier units in open profit, risk room left and no partial taken (006 ~51:40-52:50)."
- **Already in coverage:** E12c `add_low_end` (Low priority, not built). This item adds the size and conditions to that spec; build it as part of E12c.
- **BUILD SPEC (entries_stops_sizing, extends E12c `add_low_end`):**
  - Where: add block after the new-FVG branch (~2730). Trigger: the last add was an IOFED/top add on FVG g, bar i closes with its body inside g (close between g.bottom and g.top), no body close below g.bottom since. Arm once at g.bottom + 1 tick.
  - Gates: `not pos["t1_done"]`; open P&L of the earlier units at bar i's close > 0 (`c > pos["basis"] / pos["n"]` for a long); `_arm_add` cap shrink. Size = min of the earlier add quantities (`min(q for *_, q in tr.adds)`), not `fracs[k]`.
  - Params: `add_low_end: bool = False` (E12c name), `add_low_end_size: str = "smallest"`.
  - Test: `test_add_low_end_size`. Adds 3 then 1; a body close inside the FVG arms a 1-lot at its bottom; with open P&L <= 0 nothing arms; after T1 nothing arms.

### 11. E12-repeat-dig-smaller-add
- **rule_id / kind:** E12 / missing_rule. Scope: index. judgment = true.
- **Rule:** (Judgment, single source) When adding at a new FVG that price has already dug into twice, ICT sized the add at 2 instead of his usual ~3 (about 2/3), with the add placed at the FVG top while support forms there. The caption leaves open whether the second dig causes the smaller size.
- **Sources:** 003_ojy5ApHhEu4 ~00:44:27.
- **Quote:** "we dug down into it two times ... so I'm putting two in there whereas I normally would have done like three" (003).
- **Conflicts:** none.
- **[our interpretation]:** a "dig" = a bar whose low trades below the FVG top after a bar that closed above it.
- **Rulebook fix:** E12 Sizes: "003 (single case): an add at an FVG price has already dug into twice was cut to ~2/3 of plan (3 -> 2)."
- **BUILD SPEC (entries_stops_sizing):**
  - Where: `_arm_add` gets an optional `mult`; the new-FVG add branch (~2728) counts digs into g between its formation and bar i; if >= 2 and `add_dig_mult < 1`, pass `mult=add_dig_mult`.
  - Params: `add_dig_mult: float = 1.0` (test 0.67).
  - Test: `test_add_dig_mult`. FVG entered twice before the add arms: q = 2 instead of 3 with 0.67; unchanged at 1.0.

### 12. E12-single-add-variants
- **rule_id / kind:** E12 / missing_condition. Scope: index. judgment = true.
- **Rule:** Param max_adds (variant = 1). 020: after entering at the OB, one add of ~25% of the initial unit as price runs away from the OB, possibly at market, and no adds on later retests of the OB. 031 (stated as a hypothetical, valid only with bullish daily bias and DXY delivering lower): long as price runs through the identified sell-side pool, add once on the retrace into the FVG of the up move, no more adds, hold to the buy-side target.
- **Sources:** 020_MqOVbd1oqZk ~00:01:40; 031_8YSVu51hUWQ ~00:52:40.
- **Quotes:** "okay so it's running over here add five more contracts" (020); "I would be adding if it went back down into this Fair value gap and then I would not add any more" (031).
- **Conflicts:** E12 adds only on retests vs 020 market add on momentum.
- **[our interpretation]:** "runs away" = the first bar that closes above the entry OB's body top + 0.5 x initial risk.
- **Rulebook fix:** E12: "One-add variants: 020 one ~25% add at market as price runs from the OB, none on later OB retests; 031 (hypothetical) one add at the first FVG retrace after a bias + DXY sweep entry."
- **BUILD SPEC (entries_stops_sizing):**
  - Where: `add_size_fracs` respects `add_max_n` (item 1). New `add_momentum`: with `pos.get("ob_pre")` and no adds yet, on the first close >= entry + `add_mom_r` x initial risk (before T1) arm a market add (`pos["add"] = dict(px=c, q=..., i=i, market=True)`, filled at bar i+1's open by the add-fill code) of `add_mom_frac` x first unit; then set `pos["no_adds"] = True` (blocks `_ob_add` retests).
  - 031 variant: setups_models already has the turtle-soup external entry; with `max_adds=1` the first FVG add is the only one. DXY is unavailable intraday, so the DXY gate is not built (bias gate only).
  - Params: `add_momentum: bool = False`, `add_mom_r: float = 0.5`, `add_mom_frac: float = 0.25` (the `add_max_n` field from item 1 = 1 for both variants).
  - Test: `test_add_momentum_single`. OB long of 20: the run bar arms a market add of 5; a later OB retest arms nothing.

### 13. E12-wick-ce-add-5m
- **rule_id / kind:** E12 / missing_condition. Scope: index. judgment = false.
- **Rule:** Short pyramid: when price retraces to the CE of an upper wick in the trade leg and fails there, add a smaller unit. The wick may be visible only on a higher TF such as 5m while you execute on 1m. CE = (high + max(open,close))/2. Long mirror. Choosing 'the most recent' wick is our choice; ICT just points to the wick in the leg.
- **Sources:** 010_cWekmMLqiNM ~00:58:28, ~01:01:47.
- **Quote:** "the wick where's it trading up to midpoint right there there's another sell so you can sell here pyramid" (010).
- **Conflicts:** none.
- **[our interpretation]:** the most recent 5m wick in the leg since the fill; "fails" = the limit fills and the bar closes back on the trade side of the CE.
- **Rulebook fix:** E12 Where: "the CE of a wick in the trade leg, possibly a 5m wick seen while executing on 1m (010 ~58:28, ~1:01:47)."
- **BUILD SPEC (entries_stops_sizing):**
  - Where: `setups.more_adds` new branch `add_wick_ce`: resample the session bars since the fill to `add_wick_tf` minutes (5); take the latest bar with an opposing wick (lower wick for a long) of at least 2 ticks; limit at `wick_ce(...)` via `_arm_add` (through `add_ok`). The `wick_ce` helper is shared (see top).
  - Add the flag to the `more_adds` call guard (~2734).
  - Params: `add_wick_ce: bool = False`, `add_wick_tf: int = 5`.
  - Test: `test_add_wick_ce_5m`. Long; a 5m bar with lower wick 4010-4014 (body low 4014): add armed at 4012.

### 14. E12-631-vi-wickce-invalidation
- **rule_id / kind:** E12 / missing_condition. Scope: index. judgment = true.
- **Rule:** Short: unit1 = 6 at the first bearish VI; unit2 = 3 (half) at the next VI; unit3 = 1 at the CE of the upper wick left below old lows. Adds sit below the initial VI, keeping the position net short from it. If price trades to the MT of the up-close candle (bearish OB) before the displacement, the idea is invalid. If the candle after the wick flirts with the wick CE and starts rallying, put on at most 1 contract. Long mirror. The FVG fallback is not from this source.
- **Sources:** 026_GFdWahZUNOw ~01:48:03 (context ~1:44:00-1:44:40).
- **Quote:** "six contracts short here it trades down comes back up volume advance three contracts one contract consequent encroachment" (026).
- **Conflicts:** none.
- **Rulebook fix:** E12 Where: "026 6/3/1: first VI, next VI, wick CE; adds only beyond the initial VI; invalid if price trades to the MT of the OB before the displacement; a weak wick-CE reaction caps the last add at 1."
- **BUILD SPEC (entries_stops_sizing):**
  - Where: `setups.more_adds` with `vi_ladder` on: rung 1 = the next VI after the fill (existing `add_on_vi` path), rung 2 = the latest opposing wick CE (`wick_ce`); sizes from `add_ladder="631"`. `add_ok` rejects any add on the wrong side of the entry VI (long: add px must be above the entry VI's top).
  - Invalidation (management_exits): `pos["ob_mt"]` (already stored for ob stops) - when `vi_ladder_exit` and a bar trades through it, exit all at that level (close, not wait for the stop).
  - Params: `vi_ladder: bool = False`, `vi_ladder_exit: bool = False`.
  - Test: `test_vi_ladder_631`. Long 6 at a VI: next VI arms 3, wick CE arms 1, an add below the entry VI is rejected; a trade to the OB MT exits all.

### 15. E12-liquidity-void-add
- **rule_id / kind:** E12 / missing_condition. Scope: index. judgment = false.
- **Rule:** After a long entry, if a 1m liquidity void (high[i-1] < low[i]) sits at the 5m FVG CE and in the upper part of the bullish OB (last down-close candle before the displacement), expect it to fill and place a smaller pyramid add in it. The OB MT should hold. Below the MT = invalid.
- **Sources:** 018_eTMS36H7HA0 ~00:04:01 (context ~04:00-06:40).
- **Quote:** "that is a real liquidity void ... and I will buy more if it trades into it" (018).
- **Conflicts:** none.
- **[our interpretation]:** "at the 5m FVG CE" = the void overlaps the band CE +/- 25% of the 5m FVG height; "upper part of the OB" = above the OB MT.
- **Rulebook fix:** E12 Where: "a 1m liquidity void (A10) stacked with the 5m FVG CE and the upper OB is an add location (018); OB MT must hold."
- **BUILD SPEC (entries_stops_sizing; detector from levels_detectors L14b `irl_entries` void):**
  - Where: `setups.more_adds` branch `add_void`: a void formed after the fill (bar k with h[k-1] < l[k], same side), overlapping the 5m FVG CE band (`ctx.conf` 5m rows) and above the entry OB MT; limit at the void's bottom + 1 tick via `_arm_add`. A close below the OB MT cancels the add (and is the existing ob_mt stop).
  - Params: `add_void: bool = False`.
  - Test: `test_add_void`. Long with a 5m FVG CE at 4012 and a 1m void 4011-4013 above the OB MT 4008: add armed at 4011.25.

### 16. E12-070-rung-order
- **rule_id / kind:** E12 / missing_rule. Scope: index. judgment = true.
- **Rule:** Long ladder inside a breaker's A-B leg (1m execution, 11:50-12:10 macro): rung1 at the 5m FVG CE, rung2 at the IFVG CE, rung3 at the low end of that gap/range. Sizes may follow the 070 increasing 1/3/6 breaker exception (from ~36:23). Stop placement is not given in this passage.
- **Sources:** 070_1HtRfFYiwO0 ~00:58:44 (context ~58:40-1:00:50; sizes ~36:23).
- **Quote:** "I'm buying consequent encroachment of that five minute favorite ... then I'm buying what consequent approachment of the inversion parability gap" (070).
- **Conflicts:** none.
- **[our interpretation]:** stop = the `adv_breaker` stop (beyond L2).
- **Rulebook fix:** M4.3 / E12 exception: "070 rung order inside the A-B leg: 5m FVG CE, then IFVG CE, then the low end of that range; sizes may be 1/3/6."
- **BUILD SPEC (setups_models, extends the built `adv_breaker`):**
  - Where: `_breaker_order` / `adv_breaker` path in `_scan_core`: when `adv_rungs` on, replace the single MT limit with up to three resting legs (same `pending["legs"]` mechanism as item 4): 5m FVG CE inside the A-B leg, the 1m IFVG CE, the low end (bottom) of that IFVG. Size fractions `adv_rung_fracs`.
  - Params: `adv_rungs: bool = False`, `adv_rung_fracs: tuple = (0.1, 0.3, 0.6)`.
  - Test: `test_adv_breaker_rungs` (tests/test_setups_models.py). A-B leg with a 5m FVG and an IFVG: three legs at the expected prices; a fill of rung 1 only gives 10% size.

### 17. X8-downclose-wickce-add
- **rule_id / kind:** X8 / missing_condition. Scope: index. judgment = false.
- **Rule:** Short toward a BISI/SSL with a down-close candle in the way: if price smashes through the candle (bodies through its open, digging into it) and runs to the CE of its wick, add more shorts there, target unchanged. If bodies respect its open and trade back above, close (X8). Long mirror. 'Smaller unit' is from E12, not stated here.
- **Sources:** 085_6-KNSUN-UaU ~00:10:04 (context ~09:40-10:30).
- **Quote:** "if it would have done a run to this midpoint of this Wick here I would have added more shorts" (085).
- **Conflicts:** none.
- **Rulebook fix:** X8 offside: "Positive case (085 ~10:04): bodies through the down-close candle's open and a run to its wick CE = add, target unchanged."
- **BUILD SPEC (entries_stops_sizing; the close case is X8e in management_exits):**
  - Where: at the fill, store `pos["gate_c"]` = the nearest opposing-close candle between entry and T1 (short: a down-close candle above T1). `setups.more_adds` branch `add_gate_wick`: once a body closes beyond its open, arm a limit at its wick CE (`wick_ce`, the wick on the target side), size from `add_size_fracs`.
  - Params: `add_gate_wick: bool = False`.
  - Test: `test_add_gate_wick`. Short with a down-close candle open 4020, low 4014, close 4017: a close at 4019 arms a sell at 4015.5.

### 18. E12-mohawk-add-ifvg
- **rule_id / kind:** E12 / missing_condition. Scope: general. judgment = false.
- **Rule:** One-pass IFVG short: first entry above the CE; place a smaller resting add 1-2 ticks above the IFVG's far (upper) edge, which fills only on a mohawk. ICT calls this fill the superior entry. Stop per M10 (beyond CE + 3-4 ES pts). Bullish mirror.
- **Sources:** 102_uzPM1CuSSx8 ~01:14:30.
- **Quote:** "if I can get a mohawk right here on the high of it ... I'll add a partial and pyramid in that very thing" (102).
- **Conflicts:** none.
- **Rulebook fix:** M10 / E12 Where: "One-pass IFVG: a smaller resting add 1-2 ticks beyond the far edge, filled only by a mohawk (102 ~1:14:30)."
- **BUILD SPEC (entries_stops_sizing; IFVG entry path is setups_models `ifvg_stop`):**
  - Where: `_finish_order` for IFVG entries (`is_ifvg`) with `ifvg_mohawk_add` on and the IFVG untouched before (one-pass): attach `pending["legs"]` second leg at far edge + `mohawk_add_ticks` x 0.25 pt (the A4 `mohawk_ticks` field when built), size = `add_size_fracs[0]` x first unit. The stop from `ifvg_stop` must sit beyond this leg (else skip the leg).
  - Params: `ifvg_mohawk_add: bool = False`, `mohawk_add_ticks: int = 2`.
  - Test: `test_ifvg_mohawk_add`. IFVG 4030-4034 short: main leg above CE, second leg at 4034.5; a bar to 4034.25 fills only the main leg.

### 19. E12-mm-sell-model-adds
- **rule_id / kind:** E12 / missing_rule. Scope: general. judgment = false.
- **Rule:** MM sell model: after the first short (low-risk short / smart money reversal), add once at the 2nd-stage redistribution. That is a retest from below of a down-close candle that was a bullish OB on the buy side of the curve, with bodies respecting its low/body (buy side of the curve used in reverse). The add is smaller than or equal to the first unit. Take ~80% off at the original consolidation, then see if price goes deeper. Buy model is the mirror. A18 is the long-side counterpart.
- **Sources:** 104_iKsIbUblSWM ~00:53:29.
- **Quote:** "for me that would be a pyramiding entry so I would have even more going short" (104).
- **Conflicts:** none.
- **Rulebook fix:** M1 / E12: "MM sell model: one add at the 2nd-stage redistribution, a retest from below of a buy-side-of-curve bullish OB (104 ~53:29); ~80% off at the original consolidation. A18 is the long mirror."
- **BUILD SPEC (entries_stops_sizing; uses the built A18 `reclaimed_ob` detector and `mmxm_ctx`):**
  - Where: `setups.more_adds` branch `add_reclaimed_ob`: both sides (A18 is long-only as an entry array). Short: a bullish OB from before the fill (the buy side of the curve) that price has closed below; a retest from below where bodies stay under its body bottom -> limit at its body bottom, size `min(first unit, add_size_fracs[0] x first unit)`, once (`pos["mm_add_done"]`).
  - With `mmxm_ctx` on, the 80% partial at the original consolidation is a targets_partials ladder option (`mm_t1_frac=0.8`), listed here for reference only.
  - Params: `add_reclaimed_ob: bool = False`.
  - Test: `test_add_reclaimed_ob_short`. Short after a bullish OB at 4040-4044 broke; retest to 4039.75 with closes under 4040: one add at 4040; a second retest arms nothing.

### 20. E12-sb-as-add
- **rule_id / kind:** E12 / missing_rule. Scope: general. judgment = false.
- **Rule:** If an M2 position is open and a same-direction SB fires in its window, treat the SB fill as a pyramid add (size <= previous unit), not a separate trade. It is subject to the existing E12 add rules: add price below EQ of the range from the swing low to the projected target for longs (mirror for shorts), and no partial taken yet. Otherwise ignore the SB signal and manage the existing position.
- **Sources:** 058_hcSGlyfgKgA ~00:43:10.
- **Quote:** "you don't have to have the 2022 entry but guess what this becomes that's a pyramid" (058).
- **Conflicts:** none.
- **Rulebook fix:** E12 / M3: "A same-direction SB fill during an open 2022-model trade is a pyramid add, not a new trade (058 ~43:10), subject to the EQ and no-partial rules."
- **BUILD SPEC (silver_bullet + entries_stops_sizing):**
  - Where: the engine-level combine of `run_day` and `SB.run` (backtest.combine / the SB hook in run_day). With `sb_as_add`, when an SB order fills while a same-side `_scan_core` position is open on the same instrument, convert it into `_arm_add(pos, tr, sb_entry, i, p, eq)` (no new Trade, no SB stop); `add_ok` with `add_cut_ref="range"` (item 8) and `not t1_done` gate it; otherwise drop the SB order. Opposite-side SB orders are dropped while a position is open (current behaviour unchanged).
  - Params: `sb_as_add: bool = False`.
  - Test: `test_sb_fill_becomes_add`. Open M2 long; a 10:05 SB long fill below EQ appears as `tr.adds[0]`, no second Trade; after T1 the SB fill is dropped.

### 21. E12-subminute-adds
- **rule_id / kind:** E12 / missing_rule. Scope: needs_unavailable_data. judgment = true.
- **Rule:** Once on side, adds (and partials) can be timed from new FVGs/OBs on 30s/15s charts, up to the size cap (10-16 contracts) and within the risk model. Several adds in the same price area as the first fill are taken only if each has its own sub-1m OB or FVG; otherwise take a single entry. Bot has 1m data only: approximate on 1m or disable same-area adds.
- **Sources:** 010_cWekmMLqiNM ~01:02:08; 060_ZtLMTXv-Dr0 ~01:03:29.
- **Quote:** "if I don't see the lower timeframes doing this I'm not going to do those real close proximity entries" (060).
- **Conflicts:** none.
- **Rulebook fix:** E12: "Adds/partials may be timed on 30s/15s charts (010, 060); same-area adds need their own sub-1m array. Bot: 1m only."
- **No build spec:** needs sub-minute bars.

### 22. E12-daily-downclose-add-stops
- **rule_id / kind:** E12 / missing_rule. Scope: general. judgment = false.
- **Rule:** Daily model (CC): with a monthly/weekly PD array as the draw, place a buy stop at the open of the latest closed down-close daily candle. If it is not filled, move the stop to the next down-close candle's open. After a fill and a partial, if price retraces to that same opening price, put the partial quantity back on there. New down-close candles can give further buy-stop entries while price is at or below HTF equilibrium and has not reached the monthly/weekly premium array. Short is the mirror (sell stop at an up-close candle's open).
- **Sources:** cc05_016_vb_Yc-gCBfU ~00:03:14 (context ~2:30-7:00).
- **Quote:** "every time you get a new successive down candle you keep adding that new entry at the opening price" (cc05_016).
- **Conflicts:** none.
- **Rulebook fix:** M17 (daily model): "cc05_016 daily buy-stop at the latest down-close candle's open, rolled forward until filled; re-add the partial quantity at the same open on a retrace; further entries only at/below HTF EQ and before the premium array."
- **BUILD SPEC (bias_htf, research study on daily bars):**
  - Where: `study.py` new `daily_stop_model(daily, p)`: draw = the next monthly/weekly array (`htf._arrays` M/W rows); buy stop at the open of the last down-close daily candle, rolled daily; partial `dsm_partial` at the first opposing daily array; re-add on a retrace to the same open; extra entries while close <= HTF EQ (range from the HTF swing low to the draw). Stop per item 66 (below the most recent daily swing low).
  - Params (study config): `dsm_partial: float = 0.5`, `dsm_eq_gate: bool = True`.
  - Test: `test_daily_stop_model`. Daily synthetic: two down-close candles, the second's open triggers; partial, retrace to that open re-adds the same quantity.

## B. Size caps and risk per trade (E8, E9, E10, E11)

### 23. E11-funded-account-caps
- **rule_id / kind:** E11 / missing_condition. Scope: index. judgment = false.
- **Rule:** Optional funded-account mode: max_contracts = firm limit (15 for the 150k option); ICT's own build stays at 6/3/1 = 10. Initial + adds never exceed max_contracts; size an add down or skip it. Daily loss limit = firm's max-loss day ($3,000 on 150k, about 2%): stop for the day when realized + open loss would reach it. The profit target ($9,000, about 6%) is the evaluation goal only.
- **Sources:** 040_JlbQ-Z88NsI ~00:01:56; 050_F509lJRrYIM ~00:48:18.
- **Quote:** "I built up positions up to 10 contracts here and never would have been stopped down never would have reached their 3 000 Max loss day" (050).
- **Conflicts:** 040 trades up to 15 vs 050 caps at 10 of 15 (firm limit vs his usual build; not a real conflict).
- **Rulebook fix:** E11: "Funded mode: contract cap = firm limit (15 on 150k; ICT builds 10), daily loss limit = firm max-loss day (~2%)."
- **Already in coverage:** the contract cap is E11 `max_contracts_initial`/`total` (section 3). The daily loss limit is new.
- **BUILD SPEC (entries_stops_sizing + management_exits):**
  - Where: `state` in run_day (~2574) gains `day_loss` (realized, from `_after_close`). Before arming any order or add: `day_loss + open risk of the new order + open loss of the current position >= daily_loss_pct x start-of-day equity` -> skip (filter tag `x_daily_loss`). If an open position's realized + open loss reaches the limit, flatten at the bar's close.
  - Params: `daily_loss_pct: float = 0.0` (off; test 0.02 with `max_contracts_total=15` in MES-equivalent units).
  - Test: `test_daily_loss_limit`. Start equity 150k, first trade loses 2,500: a second order risking 600 is skipped; risking 400 is taken.

### 24. E11-020-fomc-size
- **rule_id / kind:** E11 / unlisted_contradiction. Scope: index. judgment = false.
- **Rule:** List as a contradiction: 020 (day before FOMC, PM last hour 15:35-15:45) built about 25 contracts (inferred about 20 at the OB + 5 add; instrument not stated, very tight stop). This is against E11's 6 initial / 10-16 max contract counts and possibly N3/E9 'trade light day before FOMC'. Bot keeps risk-% sizing and the E9 size-down before FOMC.
- **Sources:** 020_MqOVbd1oqZk ~00:04:49 (also ~1:40, ~9:44).
- **Quote:** "I'm going to take 80 of the position off which will be 20 contracts" (020).
- **Conflicts:** E11 / N3 / E9 vs 020.
- **Rulebook fix:** Contradictions list: "020: ~25 contracts (20 + 5 add) the afternoon before FOMC, very tight stop, instrument unstated, vs E11 counts and N3/E9 'trade light'. Bot keeps risk-% sizing and the FOMC-eve size-down."
- **No build spec:** a contradiction record; the FOMC-eve multiplier is already E9 `size_rules` in rule_coverage section 3.

### 25. E11-portfolio-exposure-cap
- **rule_id / kind:** E11 / missing_rule. Scope: general. judgment = true.
- **Rule:** Total open risk across all concurrent positions (size x distance to current stop) plus the new trade's risk must stay <= max_exposure (CC example: 2% for two trades at 1% each). If the new trade would exceed it, skip it, or close an existing position only if the new setup has higher probability or a larger/faster expected payout. Never exceed the cap to take a setup.
- **Sources:** cc05_013_crPpMwgwa7k ~00:26:39; cc06_002_Xs1i0aIeTME ~00:12:27.
- **Quote:** "you cannot take the setup if your risk and or Equity management doesn't permit it" (cc06_002).
- **Conflicts:** none.
- **[our interpretation]:** "higher probability" = a higher model score is not available, so the bot only skips.
- **Rulebook fix:** E11: "Cross-position cap: open risk of all positions + the new trade <= max_exposure (cc05_013 2%); otherwise pass, or swap only for a clearly better trade (cc06_002)."
- **BUILD SPEC (entries_stops_sizing; `backtest.combine` is shared with setups_models):**
  - Where: `backtest.combine` (where per-instrument / per-model trade lists merge). With `max_exposure_pct > 0`, walk trades in fill-time order, keep a running open-risk total (first-unit risk + adds, released at each exit), and drop a trade whose entry risk would push it over the cap (tag dropped trades `x_exposure` in the report). SB and `_scan_core` trades on the same day count together.
  - Params: `max_exposure_pct: float = 0.0` (test 0.02 and 0.026).
  - Test: `test_exposure_cap_combine`. Two overlapping trades at 1.2% each with a 2% cap: the later one is dropped; non-overlapping ones both stay.

### 26. E8-alloc-30pct
- **rule_id / kind:** E8 / unlisted_contradiction. Scope: general. judgment = false.
- **Rule:** allocation_base = alloc_frac x equity (default 1.0 = E8; CC = 0.30). risk_dollars = risk_pct x allocation_base, with risk_pct 1% default and up to 2% for skilled traders ($10k -> $3,000 base -> $30). Size = risk_dollars / stop distance. This is about 0.3-0.6% of the full account vs 2023's 1-2.1%; report results under both bases.
- **Sources:** cc05_013_crPpMwgwa7k ~00:04:16, ~00:06:31.
- **Quote:** "i'm gonna be using two percent of thirty thousand not two of one hundred thousand" (cc05_013).
- **Conflicts:** CC cc05_013 (1% of 30%) vs 2023 E8 / Ep 03 (1-2.1% of the whole account).
- **Rulebook fix:** E8: "CC (cc05_013): risk % applies to a 30% allocation of equity (1% of 30% = 0.3% of the account); 2023 applies it to the whole account. Conflict recorded."
- **BUILD SPEC (entries_stops_sizing):**
  - Where: `_risk_budget` and `_total_cap` (~815-820) multiply `eq` by `alloc_frac`.
  - Params: `alloc_frac: float = 1.0` (study 0.30 with `risk_pct` 0.01 / 0.02).
  - Test: `test_alloc_frac`. eq 10,000, alloc 0.3, risk_pct 0.01 -> budget 30.

### 27. E8-2pct-new-trader
- **rule_id / kind:** E8 / unlisted_contradiction. Scope: general. judgment = false.
- **Rule:** Conflict: cc02_001 ~3:41 (2% ideal for a new trader, no more than 2% on average) vs 022 ~1:38:24 (2% too much for new traders). cc02_001 ~16:41 starter model: 1.5% risk, 1:1, aiming for 6%/month. Test risk_pct in {1.0, 1.2, 1.5, 2.0}; the default stays per E8. Drop 'hard cap 2% per idea including adds' because cc02_001 does not say it.
- **Sources:** cc02_001_mjVHmE1gVMg ~00:03:41, ~00:16:41.
- **Quote:** "two percent ideally if you're a new trader but no more than two percent on an average" (cc02_001).
- **Conflicts:** 022 ~1:38:24 vs cc02_001.
- **Rulebook fix:** E8 contradictions: "cc02_001 (2% ideal for a new trader; starter model 1.5%, 1:1, 6%/month) vs 022 (2% too much for new traders). Default stays at owner #12 (1.2% / 1.3%)."
- **BUILD SPEC (entries_stops_sizing, study preset only):**
  - Where: `study.py` preset `risk_grid` running `risk_pct` in (0.010, 0.012, 0.015, 0.020) with `max_total_risk_pct = risk_pct + 0.001`, and a `cc_starter` preset: `risk_pct=0.015`, single exit at 1R (`t1_fixed_r=1.0` from targets_partials, or `min_rr=1` with the ladder truncated to T1).
  - Params: none new (presets only).
  - Test: `test_risk_grid_preset`. The preset yields four Params with the expected risk_pct values and unchanged other fields.

### 28. E8-2pct-split-experienced
- **rule_id / kind:** E8 / missing_condition. Scope: general. judgment = false.
- **Rule:** Experienced mode (cc02_003, FX example with a 10-pip stop): risk_pct = 2% split into two 1% halves. Half 1 exits at 3R (+3% equity). Half 2 runs to the HTF objective (daily/weekly/monthly level). New-trader mode keeps the E8 default.
- **Sources:** cc02_003_pctqB3UD6dk ~00:12:32 (also ~4:35).
- **Quote:** "if every trade you take is two percent once you know what you're doing you scale off one percent at three to one" (cc02_003).
- **Conflicts:** none (2% vs owner #12's 1.3% cap is a study-only setting).
- **Rulebook fix:** E8 / X3: "Experienced (cc02_003): 2% risk in two halves; half off at 3R, half to the HTF objective."
- **BUILD SPEC (targets_partials):**
  - Where: `_targets` / the ladder in `_finish_order`: preset `ladder_kind="half_3r"` = rung 1 at entry + 3R for 50% of units, rung 2 = the locked HTF draw (htf daily/weekly pool from `htf.table`) for the rest. Run with `risk_pct=0.02`, `max_total_risk_pct=0.02`, adds off.
  - Params: `ladder_kind: str = ""` ("half_3r"); validate.
  - Test: `test_ladder_half_3r`. Risk 2 pts: rung 1 at entry + 6 for half the units, rung 2 at the HTF level.

### 29. E8-E9-5pct-near-htf
- **rule_id / kind:** E8/E9 / shortened. Scope: general. judgment = false.
- **Rule:** risk_pct = 5% per entry (initial and each pyramid add, up to ~20% total) when trading toward a stored monthly/weekly/daily/4h level and price is within 20-30 ES handles of it. Trades moving away from those levels: <= 1.5%. Context: his MT4 accounts, experienced only. Bot keeps its cap; 5% is a research switch. Conflict with the cc02_004 2% max.
- **Sources:** 102_uzPM1CuSSx8 ~01:24:11.
- **Quote:** "if we get within I don't know 20 to 30 handles I would likely be at my maximum risk which is 5%" (102).
- **Conflicts:** E8 2% hard max (cc02_004) vs 102 5% per entry.
- **Rulebook fix:** E9: "Near an HTF target (102 ~1:24:11): 5% per entry (each add too, ~20% total) when within 20-30 ES handles of a stored M/W/D/4h level and trading toward it; 1.5% max trading away. MT4 accounts, experienced only; research switch."
- **BUILD SPEC (entries_stops_sizing, via the E9 `size_mult` hook):**
  - Where: `size_mult`: when `htf_near_risk_pct > 0` and the trade's draw (lock) is an htf level (`level_kinds` in M/W/D/4h) within `htf_near_pts` ES pts of entry, set the per-unit budget to `htf_near_risk_pct` (first unit and each add) and the total cap to `htf_near_cap_pct`; trades whose draw is not an HTF level get `min(risk_pct, 0.015)`.
  - Params: `htf_near_risk_pct: float = 0.0` (test 0.05), `htf_near_pts: float = 30.0`, `htf_near_cap_pct: float = 0.20`.
  - Test: `test_htf_near_risk`. Draw = weekly high 25 pts away -> 5% first unit; draw = session pool -> 1.2% (default) capped at 1.5%.

### 30. E8-risk-by-trade-class
- **rule_id / kind:** E8 / missing_condition. Scope: general. judgment = false.
- **Rule:** trade_class scalp: risk 0.5% (new) up to 1.0% max, target ~1R, kill zones only (frequency ~1 per session across several markets; not a stated cap). swing: risk 1.5% (cc06_006). position: risk <= 1% (cc05_018; stop trailed at the 40-day extreme). day trade: E8 default. Source: CC FX lessons.
- **Sources:** cc09_006_OVfn-gDk2dE ~00:05:42; cc09_007_-oMtfDvc18Y ~00:24:20; cc06_006_JAjL7rUX2Iw ~00:17:13; cc05_018_okN5p701T7Y ~00:05:13.
- **Quote:** "ideal risk for trade is a half percent to one percent and one percent may be a little high" (cc09_006).
- **Conflicts:** cc09_006 scalp cap 1% vs Ep 07 1.2-1.3% default; cc06_006 swing 1.5% vs cc05_018 position <= 1%.
- **Rulebook fix:** E8: "By trade class (CC): scalp 0.5-1% at ~1R in kill zones; swing 1.5%; position <= 1% (40-day extreme trail); day trade per E8."
- **BUILD SPEC (entries_stops_sizing):**
  - Where: `size_mult` reads `p.class_risk` (a dict keyed by `Trade.kind` class: "scalp" = trades with a single exit at <= 1.5R, i.e. `t1_fixed_r` set; "day" = everything else in `_scan_core`). The study swing/position engines (items 5, 7, 22, 66) take their risk from the same dict ("swing" 0.015, "position" 0.01).
  - Params: `class_risk: dict = field(default_factory=dict)` (empty = off).
  - Test: `test_class_risk`. With `{"scalp": 0.005}`, a 1R-scalp trade sizes at 0.5%, a ladder trade at 1.2%.

### 31. E8-leverage-cap-3x
- **rule_id / kind:** E8 / missing_rule. Scope: general. judgment = false.
- **Rule:** Swing trades (CC FX): position notional <= 3 x equity (his example: $10k account = 3 FX mini lots). Size = min(risk-based size, 3x-notional size). Never size off broker max leverage. For ES, 3x notional is about 1 MES per ~$10k of equity.
- **Sources:** cc06_006_JAjL7rUX2Iw ~00:15:32.
- **Quote:** "you can actually trade with just three to one Leverage" (cc06_006).
- **Conflicts:** none.
- **Rulebook fix:** E8: "Notional cap ~3x equity for swing trades (cc06_006); size = min(risk size, 3x-notional size)."
- **BUILD SPEC (entries_stops_sizing):**
  - Where: `_first_units` (~822) and `_arm_add`: the notional term becomes `min(p.max_notional, p.max_lev x eq) / abs(entry)` when `max_lev > 0`; for adds, cap total units x price at the same bound. Price in instrument units x `contract multiplier` (SPY: 1 per share; MES: 5 per point via `lot`).
  - Params: `max_lev: float = 0.0` (test 3.0 on swing studies and on the intraday engine).
  - Test: `test_max_lev`. eq 10,000, SPY at 500, max_lev 3 -> at most 60 shares even if risk allows 200.

### 32. E8-new-trader-drill
- **rule_id / kind:** E8 / missing_rule. Scope: index. judgment = false.
- **Rule:** Drill mode (demo/paper): size = 1 ES contract. Limit at the FVG edge +1 tick, bracket stop 5 ES pts, target 5 ES pts. Exit all at +5 with no partials, then watch the rest of the move without a position. Expected frequency 'a few times a week' (001); 2-4/week is our reading.
- **Sources:** 001_XN8tuO4QIRw ~00:55:20; 042_hQ379EuyNKQ ~00:32:11, ~00:45:29, ~01:09:55.
- **Quote:** "the initial drill is five for five that means you're going to risk five handles to make five handles" (042).
- **Conflicts:** none.
- **Rulebook fix:** E8 (new-trader section): "Drill (042, 001): 1 ES contract, limit at the FVG edge + 1 tick, 5-pt stop, 5-pt target, all out at +5, no partials."
- **BUILD SPEC (entries_stops_sizing):**
  - Where: `_scan_core` stop block (~3580): `stop_mode="fixed"` -> stop = entry - `stop_fixed_pts` x es_pt. Entry: `entry_px="edge_1tick"` (D11, already listed) = FVG near edge + 1 tick inside. Ladder: one rung at entry + `t1_fixed_pts` (owner #2 switch, built), 100% off. Size: `fixed_units` overrides `_first_units` when > 0. Adds off.
  - Preset `drill_55`: `stop_mode="fixed"`, `stop_fixed_pts=5`, `t1_fixed_pts=5`, `fixed_units=1 x lot`, `adds=()`.
  - Params: `stop_fixed_pts: float = 0.0`, `fixed_units: int = 0`; add "fixed" to the `stop_mode` validator (~759).
  - Test: `test_drill_55`. FVG long: stop 5 below entry, single exit at +5, units = 1 contract regardless of equity.

### 33. E8-new-trader-graduation
- **rule_id / kind:** E8 / missing_condition. Scope: index. judgment = true.
- **Rule:** trader_mode 'new': 1 contract per trade regardless of %-risk or account/prop allowance, stepping to 2, 3, 4 only after a track record (N is ours). Deployment gate: paper/demo at 1 micro for >= 6 months, consistent ~70% of the time (how that is measured is our reading). Then live at 1 micro, scaling slowly.
- **Sources:** 042_hQ379EuyNKQ ~00:21:02; 048_gGxVE8zUIRQ ~02:26:37.
- **Quote:** "you want to start with one contract and you want to desensitize yourself" (042).
- **Conflicts:** none.
- **[our interpretation]:** step-up = +1 contract after each block of 20 trades with positive net P&L; "70% consistent" = >= 70% of weeks net non-negative.
- **Rulebook fix:** E8: "New traders: 1 contract regardless of allowance, step up slowly (042 ~21:02); paper/demo at 1 micro for >= 6 months and ~70% consistency before live (048 ~2:26:37)."
- **BUILD SPEC (entries_stops_sizing + paper/live tooling):**
  - Where: `BT.run` carries `state["trader_units"]` across days when `trader_mode="new"`: `fixed_units` (item 32) = `trader_units x lot`, starting at 1; after every `grad_block` closed trades with positive net, +1 up to `grad_max`. The deployment gate is a report, not a trading rule: `study.py` `deploy_gate(trades)` prints months of history at 1 micro and the share of non-negative weeks, PASS at >= 6 months and >= 70%.
  - Params: `trader_mode: str = ""` ("new"), `grad_block: int = 20`, `grad_max: int = 4`.
  - Test: `test_trader_mode_new_steps`. 20 winning trades -> the 21st uses 2 units; a losing block keeps 1.

### 34. E10-cascading-halving
- **rule_id / kind:** E10 / shortened. Scope: general. judgment = false.
- **Rule:** risk_next = 0.5 x the risk of the most recent losing trade, halved again on each consecutive loss (2% -> 1% -> 0.5%). Hold until wins since that loss recover >= 50% of it, then step up gradually ('a little bit higher'; one doubling capped at base is our reading).
- **Sources:** 061_wWvXWmC_gqU ~02:26:40; cc02_005_vWDElb65YHg ~00:05:20, ~00:14:02.
- **Quote:** "cut your business size in half each time you take a loss" (061).
- **Conflicts:** none.
- **Rulebook fix:** E10: "Halve relative to the LAST losing trade's risk, again on each consecutive loss (2 -> 1 -> 0.5%); step back up only after wins recover >= 50% of that loss, one step at a time."
- **Already listed:** rule_coverage section 3, entries_stops_sizing E10 "`loss_halving` with halving_floor and winback_frac carried across days". Same rule; no new spec. Build note for that spec: the reference is the last losing trade's risk (not base risk), each consecutive loss halves again down to `halving_floor`, and the step-up is one doubling per recovery, capped at base.

### 35. E9-retail-sentiment-max
- **rule_id / kind:** new / missing_rule. Scope: needs_unavailable_data. judgment = true.
- **Rule:** If retail consensus (streamers/social sentiment) strongly opposes the algorithmic read, max risk is allowed. Judgment call, needs unavailable sentiment data; record only.
- **Sources:** 010_cWekmMLqiNM ~00:34:53.
- **Quote:** "I love that tug of war because that I'm going to go in there with my maximum risk then" (010).
- **Conflicts:** none.
- **Rulebook fix:** E9 size-up: "Retail consensus strongly against the algorithmic read -> max risk allowed (010 ~34:53). Not codeable."
- **No build spec:** needs sentiment data.

### 36. E9-deep-discount-reduced
- **rule_id / kind:** E9 / missing_condition. Scope: general. judgment = true.
- **Rule:** After a steady multi-week (about 3-4 weeks) one-direction run that puts price in deep discount (or deep premium), trend continuation is still expected, but new with-trend trades are taken only when clearly set up, at reduced size (e.g. 0.5x, our interpretation), with no max leverage and no pyramiding, and without 'marrying' the idea. Expect wicked intraday reversals (short-term buy-side runs) and daily candles with wicks on both sides. This is a size-down condition for E9, distinct from B17's 'HTF draw delivered -> stop for the week'.
- **Sources:** 099_v_iJlBKYmUc ~00:28:59.
- **Quote:** "you don't want to take heavy shorts don't do maximum leverage" (099).
- **Conflicts:** B17 (stop for the week) vs 099 (smaller trades allowed); different triggers, both kept.
- **[our interpretation]:** "steady multi-week run" = 3+ consecutive weekly closes in one direction and the latest close in the bottom (top) 25% of the 13-week range; 0.5x size.
- **Rulebook fix:** E9 size-down: "After a 3-4 week one-way run into deep discount/premium (099 ~28:59): with-trend trades only when clearly set up, reduced size, no max leverage, no pyramids; expect two-sided wicks."
- **BUILD SPEC (entries_stops_sizing, via `size_mult`; weekly state from bias_htf):**
  - Where: `htf.table` adds a weekly column `deep_run` (+1 deep premium after up-run, -1 deep discount after down-run, 0 otherwise) computed from completed weeks only. `size_mult` returns `deep_run_mult` for with-trend trades when `deep_run` agrees with the trade direction (short in deep discount), and sets `pos["no_adds"] = True`.
  - Params: `deep_run_mult: float = 1.0` (test 0.5), `deep_run_weeks: int = 3`.
  - Test: `test_deep_run_size_down`. Four down weeks, close in the bottom quarter: a short sizes at 0.5x and arms no adds; a long is unaffected.

### 37. E9-frequency-small-size
- **rule_id / kind:** E9 / missing_rule. Scope: general. judgment = true.
- **Rule:** High-frequency trading (many trades a week) is discouraged for developing traders. If done, use low contract size / much less leverage, because commissions erode a low hit rate. Bot: include round-turn commission in P/L. Optional risk_pct scaling, e.g. base x min(1, 3/trades_per_week) [our interpretation; ICT gives no number].
- **Sources:** 101_VElIka5sk0E ~00:44:29.
- **Quote:** "if you're gonna do a lot of high frequency trading you want to do it in low contract sizes" (101).
- **Conflicts:** none.
- **Rulebook fix:** E9: "High frequency -> low contract size, because commissions eat a low hit rate (101 ~44:29). One or two ideas a week preferred for developing traders."
- **BUILD SPEC (entries_stops_sizing):**
  - Where: `BT.run` keeps a rolling count of trades over the last 5 sessions in `state`; `size_mult` multiplies by `min(1, freq_ref / trades_per_week)` when `freq_ref > 0`. Commissions: `cost_per_share` already applies each way; confirm the report shows net P&L (no code change if it does; add a `costs` column if missing).
  - Params: `freq_ref: float = 0.0` (test 3.0).
  - Test: `test_freq_size_scale`. 6 trades in the last 5 sessions with freq_ref 3 -> the next trade sizes at 0.5x.

### 38. E9-may-october
- **rule_id / kind:** E9 / missing_rule. Scope: general. judgment = true.
- **Rule:** Index seasonal regime (cc10_015): May-October = low-magnitude, range-bound period. Trade with much less leverage and less activity, but do not block trading, since short-term directional opportunities still exist. Prime active periods: Feb-May and Oct-Dec. Bot: risk multiplier < 1 for May-Oct (e.g. 0.5x) and optionally a lower weekly trade cap; ICT gives no numbers [our interpretation].
- **Sources:** cc10_015_rlTl8QKpqCU ~00:03:49.
- **Quote:** "if you're gonna be trading do a lot less leverage ... don't be so aggressive" (cc10_015).
- **Conflicts:** E9 / N7 August only vs cc10_015 May-October.
- **Rulebook fix:** E9 / N7: "Equity indices May-Oct = low-magnitude period (cc10_015 ~3:49): less leverage and activity, not a block. Prime: Feb-May, Oct-Dec. August remains the strongest size-down."
- **BUILD SPEC (day_week_context, consumed by the E9 `size_mult` hook):**
  - Where: `day_context` tags `low_mag_season` when the date's month is in `low_mag_months`; `size_mult` multiplies by `low_mag_mult`; optional weekly trade cap `low_mag_week_cap` checked in `BT.run` weekly state (blocked() returns "low_mag_cap" once reached). August keeps its own E9 row (the smaller multiplier wins).
  - Params: `low_mag_months: tuple = (5, 6, 7, 8, 9, 10)`, `low_mag_mult: float = 1.0` (test 0.5), `low_mag_week_cap: int = 0`.
  - Test: `test_low_mag_season`. A June trade sizes at 0.5x; a November trade at 1x; with cap 2 the third June trade of the week is blocked.

### 39. E9-war-regime
- **rule_id / kind:** E9 / shortened. Scope: needs_unavailable_data. judgment = true.
- **Rule:** Manual war_regime flag (geopolitical/war escalation, unlike scheduled macro risk that ICT will trade ahead of): smallest leverage (minimum risk), always a hard stop, no home-run targets (take the first pool), few trades ('don't do too much') [trade cap is our interpretation]. Directional read is conditional on escalation (escalation -> continuation lower; no escalation -> buy-side run possible), not a blanket 'fade rallies'.
- **Sources:** 103_IU673ZUGuxI ~00:33:10.
- **Quote:** "these types of events where you don't know how bad things can just pop off" (103).
- **Conflicts:** none.
- **Rulebook fix:** E9: "War shocks (103 ~33:10) differ from scheduled macro risk: price can move at odd times. Smallest size, hard stop, first-pool targets, few trades; direction conditional on escalation."
- **No build spec:** needs a dated war/escalation event feed we do not have (a manual date list in `calendar.py` could later reuse the E9 multiplier).

### 40. new-probe-position
- **rule_id / kind:** new / missing_rule. Scope: index. judgment = true.
- **Rule:** On an indecisive session (bias set, no clean setup), an experienced trader may place a probe of 1-2 contracts (about 1/6-1/3 of normal size, our interpretation) to get a feel for price. If it comes against you, close manually before the full stop; no pyramiding. Developing traders do this on demo only.
- **Sources:** 026_GFdWahZUNOw ~00:16:16.
- **Quote:** "I'll put on a very small trade usually one contract maybe two to get me wanting to feel closer" (026).
- **Conflicts:** none.
- **[our interpretation]:** "indecisive" = bias set but no qualifying setup by `probe_t`; probe = market entry in the bias direction at `probe_t`; "comes against you" = price reaches 50% of the stop distance; stop = the session's opposite extreme so far.
- **Rulebook fix:** New rule (E-section): "Probe (026 ~16:16): experienced traders may take 1-2 contracts to feel an indecisive session; close early if it goes against them; no adds. Developing traders: demo only."
- **BUILD SPEC (entries_stops_sizing + management_exits; low priority):**
  - Where: run_day: if `probe_mult > 0`, bias set, no trade or pending order by `probe_t`, and the session is not blocked: market entry at bar close in the bias direction, size `probe_mult` x `_first_units`, stop = session extreme against the bias - pad, single target = the locked draw, `pos["no_adds"] = True`, early exit when price trades `probe_cut` x stop distance against the entry. Tagged `probe`; counts as the session's trade (sets `done`).
  - Params: `probe_mult: float = 0.0` (test 0.25), `probe_t: int = 630`, `probe_cut: float = 0.5`.
  - Test: `test_probe_trade`. Bullish bias, no setup by 10:30: a 0.25x long; a drop of half the stop distance closes it early.

## C. Stop placement and invalidation (E6, E7, X8, X13, M12, A12)

### 41. E7-reduce-size
- **rule_id / kind:** E7 / missing_condition. Scope: general. judgment = true.
- **Rule:** When the trade trades outside its entry FVG/boundaries against you, either close it all (X6) or cut position size (e.g. close 50%) at a loss while leaving the original stop where it is. Never move or remove the stop instead. Extends E7, alongside the existing half-off cases in X7/X9.
- **Sources:** 046_VLis0LcbUaQ ~01:33:39.
- **Quote:** "you can take your stop loss and reduce it without moving it ... take partials in terms of the position size and reduce it" (046).
- **Conflicts:** none.
- **Rulebook fix:** E7: "Instead of moving a stop, reduce risk by cutting size (e.g. close 50% at a loss) and leave the stop where it is (046 ~1:33:39). X6 full close stays the default."
- **BUILD SPEC (management_exits):**
  - Where: the X6 abort in the run_day position loop (the `ce_hold` / FVG-outside branch ~2654): when `abort_mode="half"`, the first body close outside the entry FVG closes `abort_frac` of `pos["left"]` at the close (exit kind `abort_half`), sets `pos["no_adds"]`, and leaves the stop; a second close outside closes the rest.
  - Params: `abort_mode: str = "full"` ("half"), `abort_frac: float = 0.5`.
  - Test: `test_abort_half`. Long 10: a close below the FVG exits 5, stop unchanged; a second close below exits 5 more.

### 42. X8-offside-flip
- **rule_id / kind:** X8 / missing_rule. Scope: index. judgment = true.
- **Rule:** Short open with a down-close candle below that price should smash through. If price instead trades back above that candle's open (failing to go through it and the SIBI), you are offside. Close at market (not a stop-out). If the experienced flag is on (default off), reverse long with the same contract count. Stop below the reaction candles' bodies / the CE of the defending lower wick; target the nearest buy-side pool. Conflicts with X13 (no reversal after an AM loss) and D18's 'small' wording.
- **Sources:** 085_6-KNSUN-UaU ~00:14:05 (context ~13:30-14:30).
- **Quote:** "I did not get stopped out I stopped the short in a loss and went immediately long" (085).
- **Conflicts:** X13 / D18 (no reversal after an AM loss; flips "small") vs 085 immediate same-size flip.
- **Rulebook fix:** X8e / D18: "Offside (085 ~13:30-14:30): price trades back above the down-close candle's open -> close at market; experienced flag: reverse with the same size, stop below the reaction bodies / defending wick CE, target the nearest buy-side pool."
- **BUILD SPEC (management_exits; builds on the X8e offside test listed in rule_coverage):**
  - Where: X8e exit in the position loop uses `pos["gate_c"]` (item 17). On the offside close, when `offside_flip` is on, set `pending` to a market order on the opposite side at bar i+1 open: units = the closed units, stop = min(reaction bars' body lows, the defending lower wick's `wick_ce`) - pad, target = nearest buy-side pool from `ctx` pools. Overrides `lost_side` / X13a for this one reversal (tag `offside_flip`).
  - Params: `offside_flip: bool = False`.
  - Test: `test_offside_flip`. Short 5 with a down-close gate candle: a trade back above its open closes the short and opens a long 5 next bar with the expected stop.

### 43. X13-reentry-turtle-soup
- **rule_id / kind:** X13 / missing_condition. Scope: general. judgment = false.
- **Rule:** In a consolidating market with a defined range, after a stopped short, a new short is allowed when price is still above the range's equilibrium (premium) and runs another old 3-candle swing high (turtle soup). Short the failure; target below the next old low. Redefine the range as new swings form. Re-entries can repeat (ICT shows the stop taken twice); size per X13/D18 (half risk, our choice; ICT gives no size).
- **Sources:** cc01_005_YuefjnUKQdM ~00:12:36 (context ~12:30-13:30).
- **Quote:** "you're gonna be looking for old highs to be breached while we're above the fifty percent level" (cc01_005).
- **Conflicts:** none.
- **Rulebook fix:** X13b: "Consolidation re-entry (cc01_005): after a stop-out, re-short only while still above the range EQ and on a new run of an old swing high (turtle soup); may repeat."
- **BUILD SPEC (setups_models; uses the built `turtle_soup` and `reentry_half`):**
  - Where: `_after_close` / the re-entry gate (`reentry_half`, `state["reentered"]`): with `reentry_ts` on, a same-direction re-entry after a stop-out is allowed only via a `_turtle` signal (any `turtle_soup` variant) whose swept high is a 3-bar swing high formed inside the session range and with price above the range EQ (range = session high/low since 09:30, recomputed per bar). Allow `reentry_max` re-entries per session; size `reentry_mult` (0.5).
  - Params: `reentry_ts: bool = False`, `reentry_max: int = 2`, `reentry_mult: float = 0.5`.
  - Test: `test_reentry_turtle_soup` (tests/test_setups_models.py). Short stopped; a new swing-high run above EQ re-enters at half size; a run below EQ does not.

### 44. E6-wick-ce-stop
- **rule_id / kind:** E6 / missing_rule. Scope: index. judgment = false.
- **Rule:** stop_mode='wick_ce': place the stop just beyond the CE of the relevant defending wick (short: the longest upper wick of the swing high / the candle above a balanced VI; wick CE = (high + max(open,close))/2; long: (low + min(open,close))/2, ideally aligned with the IFVG low), plus 1 tick padding. Price trading about 1 tick through the CE is tolerated (085). Can be used as the initial stop (085, 089) or as a managed/tightened stop on an open position (022). Risk bounds still apply.
- **Sources:** 022_ALMsQytQ1fg ~01:14:11; 085_6-KNSUN-UaU ~00:27:39; 089_h0yOpwSilnE ~00:06:48.
- **Quote:** "A wick is a gap to a algorithm... Midpoint of that is consequent encroachment" (022).
- **Conflicts:** none.
- **Rulebook fix:** E6: "Wick-CE stop (022, 085, 089): just beyond the CE of the defending wick (+1 tick); ~1 tick through tolerated."
- **BUILD SPEC (entries_stops_sizing):**
  - Where: `_scan_core` stop block (~3580): `stop_mode="wick_ce"` -> long: the bar between `sw["ext_i"]` and i with the longest lower wick; stop = `wick_ce(...)` - `stop_pad` (1 tick) - (`wick_ce_tol_ticks` x 0.25 pt). Fall back to the current stop if the risk is outside min/max risk. Management variant `trail_wick_ce`: after the fill, each new defending wick on the trade side raises the stop to its CE - pad (never lowers).
  - Params: `wick_ce_tol_ticks: int = 1`, `trail_wick_ce: bool = False`; add "wick_ce" to the stop_mode validator.
  - Test: `test_stop_wick_ce`. Sweep bar o=4012 c=4013 l=4006: stop = 4009 - 0.25 - 0.25.

### 45. M2-stop-by-fvg-choice
- **rule_id / kind:** M2 / missing_condition. Scope: general. judgment = false.
- **Rule:** If the entry FVG coincides with a VI and a bearish OB: stop just above the OB MT (022: MT 4131.50 -> stop 4132, i.e. ~2 ticks / next round quarter, giving ~2 ES pts of risk). Plain first FVG above EQ with no confluence: stop above the displacement-leg high (wide), so be more selective, preferring the confluence FVG.
- **Sources:** 022_ALMsQytQ1fg ~00:53:59 (context ~53:59-59:30).
- **Quote:** "Where would your stop need to be? Here, it needs to be at the high. That's a lot" (022).
- **Conflicts:** none.
- **Rulebook fix:** M2 stops: "The stop depends on the FVG chosen: VI+OB+FVG -> above the OB MT (~2 ticks; 022 4131.50 -> 4132); plain FVG -> above the leg high."
- **BUILD SPEC (entries_stops_sizing; uses `fvg_pick="2022"` from setups_models):**
  - Where: stop block: `stop_mode="m2_auto"` -> if the picked FVG has VI+OB confluence (the `fvg_pick="2022"` first-choice tag), stop = OB MT + `mt_pad_ticks` ticks (2); else stop = leg extreme (`sw["ext"]`) + 1 tick. The existing max-risk filter then skips wide plain-FVG trades.
  - Params: `mt_pad_ticks: int = 2`; add "m2_auto" to the validator.
  - Test: `test_stop_m2_auto`. Short: confluence FVG with OB MT 4131.50 -> stop 4132.00; plain FVG with leg high 4140 -> stop 4140.25.

### 46. E6-breakaway-gap-stop
- **rule_id / kind:** E6 / missing_rule. Scope: general. judgment = false.
- **Rule:** Breakaway-gap re-entry (missed 2022-model entry): after two bearish MSSs, short the retrace into the breakaway gap. Stop = above the high of the candle at the gap (the retrace candle) + 1 tick, justified by the two MSSs. If the gap stays partly open and price leaves to a new low, the stop can be dropped to the gap level. If the gap fills completely it is not a breakaway gap: wait for price to reach the HTF array, break again and form a new FVG, then re-short.
- **Sources:** 062_sfRO5LrTgTA ~00:37:28 (context ~36:40-38:10).
- **Quote:** "your stop if you were shorting in here would be above this candle's High not fearing any return back into this because we have two shifts in Market structure" (062).
- **Conflicts:** none (the rulebook's M2 citation of 062 ~37:28 as a plain FVG-candle stop is corrected).
- **Rulebook fix:** M2 / E6: "062 ~37:28 is a breakaway-gap re-entry after two MSSs: stop above the retrace candle's high; once price leaves to a new low, the stop may drop to the gap. A full fill = not breakaway."
- **BUILD SPEC (setups_models entry + entries_stops_sizing stop; uses the built `breakaway` tag / next_fvg):**
  - Where: `_scan_core` after a missed/unfilled 2022 order: when `breakaway_reentry` and the session has two same-direction MSS events (count `mss` flips since the sweep), a retrace bar that enters the breakaway FVG (built tag) arms a limit at its near edge; stop = that retrace bar's high + 1 tick. Management: after a new low beyond the fill, if the gap is still partly open, `pos["stop"] = min(stop, gap top + 1 tick)`. A full fill of the gap cancels (no breakaway).
  - Params: `breakaway_reentry: bool = False`.
  - Test: `test_breakaway_reentry_stop` (tests/test_setups_models.py). Two MSSs, missed first order, retrace bar high 4105 into the gap -> stop 4105.25; new low -> stop drops to gap top + 1 tick.

### 47. M12-ts-stop-midpoint
- **rule_id / kind:** M12 / shortened. Scope: general. judgment = false.
- **Rule:** Turtle soup long (SSL taken at a predefined level + SMT, one discount PD array): stop below the VI low if the array is a VI, below the FVG CE if an FVG, below the OB MT if an OB (minus 1 tick). Short mirror.
- **Sources:** 022_ALMsQytQ1fg ~02:48:40 (context ~2:47:50-2:48:50).
- **Quote:** "have it show you a defined level where below midpoint of a fair value gap or a order block" (022).
- **Conflicts:** none.
- **Rulebook fix:** M12.1: "Stop below the VI low / FVG CE / OB MT of the entry array (022 ~2:48:40), not below the whole array."
- **BUILD SPEC (setups_models, extends the built `_turtle` `ts_stop`):**
  - Where: `_turtle` (~3776): `ts_stop="mid"` -> by array kind: VI -> its bottom; FVG -> its CE (`g.mid`); OB -> its MT; minus 1 tick.
  - Params: extend `ts_stop` values with "mid" (validator).
  - Test: `test_ts_stop_mid` (tests/test_setups_models.py). Turtle soup at an FVG 4010-4014: stop 4011.75; at an OB with MT 4009: stop 4008.75.

### 48. E6-old-low-rejection-body
- **rule_id / kind:** E6 / missing_condition. Scope: general. judgment = true.
- **Rule:** Long near an old low: if the OB-MT / FVG stop would sit above the old low, place the stop below the old low instead, using its rejection-block body (the lowest close/open of the old-low swing) rather than its wick, minus 1 tick (022 example: close 4112.50).
- **Sources:** 022_ALMsQytQ1fg ~02:50:25.
- **Quote:** "your stop would have to be below the old low. So, you use like the rejection block here" (022).
- **Conflicts:** none.
- **[our interpretation]:** "near" = the old low within the max-risk distance below entry; the old low = the nearest session/prior-session swing low below entry that has not been traded through.
- **Rulebook fix:** E6: "If an old low lies below the OB-MT/FVG stop, the stop goes below that old low's rejection body (lowest close/open), not its wick (022 ~2:50:25)."
- **BUILD SPEC (entries_stops_sizing):**
  - Where: stop block, after the stop_mode choice: with `stop_old_low_body`, find the nearest untaken swing low L below entry (`levels.swing_tiers` / sell-side pools from DayCtx); if L < stop and entry - L <= max risk, stop = min(o, c) of the swing-low bar (and its neighbours in the 3-bar swing) - 1 tick.
  - Params: `stop_old_low_body: bool = False`.
  - Test: `test_stop_old_low_body`. Entry 4120, OB MT stop 4116, old low wick 4110 with lowest body 4112.50 -> stop 4112.25.

### 49. E6-two-gap-ce
- **rule_id / kind:** E6 / shortened. Scope: index. judgment = false.
- **Rule:** Short in the lower of two bearish FVGs from one displacement leg: stop = just above the CE of the higher FVG (+1 tick); the leg swing high need not be covered. Long mirror. Applies only once price has already shown it is not going higher (MSS).
- **Sources:** 069_Sf_uYZBWTrA ~00:14:09.
- **Quote:** "I have to use the two rule when there's two gaps you have to factor in the higher Gap" (069).
- **Conflicts:** E6 ("beyond the higher of two FVGs") vs M2 / 069 ("above the CE of the higher FVG").
- **Rulebook fix:** E6: replace "beyond the higher of two FVGs" with "beyond the CE of the higher of two FVGs (069 ~13:46-14:09), matching M2".
- **Already built:** `stop_mode="ce2"` (strategy.py ~3587: for a long, below the CE of the lower of the last two FVGs; the short is the mirror). No new spec; only the rulebook wording.

### 50. E2-sb-split-limits
- **rule_id / kind:** E2 / shortened. Scope: index. judgment = true.
- **Rule:** SB short: build the full size (e.g. 10) with two resting limits in the FVG, no market entry: ~60% (6) at a limit just inside the near edge and ~40% (4) a few ticks below it (shallower, at/just beyond the near edge, so it fills first). Both share one stop. If the SB evolves, move both limits (and the stop) to the new FVG. Long mirror.
- **Sources:** 057_DkOuO0eNwUA ~00:01:46.
- **Quote:** "I want to see if I can build my typical 10 contracts into this morning limit entry not just marketing" (057).
- **Conflicts:** none.
- **[our interpretation]:** "a few ticks" = 2 ticks.
- **Rulebook fix:** E2 / M3: "SB full size can be split into two resting limits (057): ~60% just inside the near edge, ~40% 2 ticks shallower; one stop; both move with an evolved SB."
- **BUILD SPEC (silver_bullet):**
  - Where: `SB._arm` (sb_model.py ~213-250): with `sb_split`, the order carries two legs: `sb_split_frac` at entry (g.top for a long mirror: near edge - 1 tick inside), the rest at the near edge + `sb_split_ticks` ticks outside (fills first). The fill loop (~150-170) fills legs independently; `tr.shares` = filled units; one shared stop. When the SB re-arms on an evolved FVG (existing evolve path), both legs move.
  - Params: `sb_split: bool = False`, `sb_split_frac: float = 0.6`, `sb_split_ticks: int = 2`.
  - Test: `test_sb_split_limits`. SB short FVG near edge 4200: legs at 4199.75 (60%) and 4199.25 (40%); a touch of 4199.50 fills only the 40% leg.

### 51. E6-mt-stops-futures-only
- **rule_id / kind:** new / missing_rule. Scope: fx_only. judgment = false.
- **Rule:** Scope note on E6: the precise MT/volume-imbalance stops (009) are stated as valid only on exchange-traded futures. ICT says they cannot work with real size in retail FX because of broker stop-hunting. He does not give an alternative FX stop. For the index bot, no rule change is needed beyond recording that tight MT/VI stops are a futures-only method.
- **Sources:** 009_tnxvmHq8xEg ~00:14:15.
- **Quote:** "you can't trade this precise with Forex it can't happen it won't happen not with real money" (009).
- **Conflicts:** none.
- **Rulebook fix:** E6 note: "Tight MT/VI stops are futures-only (009 ~14:15); not usable with retail FX size."
- **No build spec:** fx_only.

### 52. E6-nwog-stop
- **rule_id / kind:** E6 / missing_condition. Scope: index. judgment = true.
- **Rule:** When shorting into an opening gap (NDOG/NWOG), the stop goes above the high of the opening gap that defines the trade (050: above the March 5 NWOG), plus 1 tick or a buffer. Whether another gap above should be ignored is not established by the source, so test both against E6's 'beyond every nearby inefficiency'.
- **Sources:** 050_F509lJRrYIM ~00:54:56 (context ~53:30-55:10).
- **Quote:** "stop was above the new day I'm sorry the new week opening gap on the 5th of March" (050).
- **Conflicts:** possibly E6 "beyond every nearby inefficiency" (not verifiable from the source).
- **Rulebook fix:** E6: "Opening-gap fade (050 ~54:56): stop above the defining NWOG/NDOG's far edge + 1 tick."
- **BUILD SPEC (entries_stops_sizing; gap levels from the built L5 `pool_gaps` / NWOG-NDOG levels):**
  - Where: stop block: when the entry array is (or sits inside) an NWOG/NDOG band from the L5 levels and `stop_gap_edge` is "own", stop = that gap's far edge + 1 tick; "all" = beyond every opening gap within max risk (the E6d `stop_all_ineff` reading).
  - Params: `stop_gap_edge: str = ""` ("own" / "all").
  - Test: `test_stop_gap_edge`. Short at an NWOG 4085-4089.25 with an NDOG up to 4096: "own" -> 4089.50; "all" -> 4096.25.

### 53. E6-three-pd-arrays
- **rule_id / kind:** X7/E6 / missing_condition. Scope: general. judgment = true.
- **Rule:** At entry, identify three PD arrays protecting the trade (098 short: mitigation-block candle MT, bearish OB MT, high of the FVG/inefficiency). The stop sits behind all three, i.e. beyond the outermost one, plus 1 tick. Wicks into the inner arrays are tolerated. If the stop would exceed max risk, skip or size down via E8 (bot choice). stop_mode='three_pd'.
- **Sources:** 098_PejS-nZTQlE ~00:47:02 (context ~46:50-47:35).
- **Quote:** "my stops are always be will be behind three PD arrays because if three PD arrays fail next thing's my ass" (098).
- **Conflicts:** 098 (behind the third array) vs cc12_004 (below the next array, item 54).
- **Rulebook fix:** E6: "Three-array stop (098 ~47:02): stop behind the third protecting PD array (+1 tick). X7 keeps the early-exit reading."
- **BUILD SPEC (entries_stops_sizing):**
  - Where: stop block: `stop_mode="three_pd"` -> collect candidate protecting levels beyond entry on the stop side: entry OB MT, the nearest opposing OB MT (`L.order_block_blend`), FVG far edges and VI far edges formed in the leg (`sd.gaps`, `sd.vis`), sorted by distance from entry; stop = the 3rd one + 1 tick (fewer than 3 -> the outermost found). Max-risk filter as usual (risk-based size makes "size down" automatic).
  - Params: `three_pd_n: int = 3`; add "three_pd" to the validator.
  - Test: `test_stop_three_pd`. Short with MT 4102, OB MT 4104, FVG top 4106 above entry 4100: stop 4106.25.

### 54. E6-next-pd-array
- **rule_id / kind:** E6 / missing_rule. Scope: general. judgment = false.
- **Rule:** Long: list discount arrays below the entry array (PD array matrix: swing highs, OBs, FVGs). Stop = below the first one fully below the entry array that the candle forming the entry array has not already spiked through, minus a buffer (cc12_004: next array swing high 1276 was pierced, so step down to the array with high 1275, stop 1274). Short mirror.
- **Sources:** cc12_004_Oec_0NM_OeY ~00:55:21 (context ~54:20-56:20, ~58:00).
- **Quote:** "we protect it with a stop below the next discount array" (cc12_004).
- **Conflicts:** cc12_004 (next array) vs 098 (third array).
- **Rulebook fix:** E6: "Next-array stop (cc12_004): below the next discount array beneath the entry array, skipping any the entry array's candle already spiked through."
- **BUILD SPEC (entries_stops_sizing; same candidate list as item 53):**
  - Where: stop block: `stop_mode="next_pd"` -> from the item 53 candidate list (plus swing highs below entry from `levels.swing_tiers`), take the first level fully below the entry array whose price the entry array's forming candles (g.i-2..g.i) did not trade below; stop = its bottom - `stop_pad` (1 tick).
  - Params: add "next_pd" to the validator.
  - Test: `test_stop_next_pd`. Entry FVG 1278-1280 whose first candle wicked to 1275.5; swing high 1276 skipped; array high 1275 -> stop 1274.75 (index pad 1 tick).

### 55. E6-bpr-75-stop
- **rule_id / kind:** E6 / missing_rule. Scope: general. judgment = true.
- **Rule:** Long after price trades through and clears a range it has traded both ways [L,H] (a balanced price range in the 075 sense, not only A11's FVG overlap): stop anywhere inside the range is acceptable. ICT's preference is below the 75% level (interpretation: H - 0.25*(H-L), alt L + 0.25*(H-L); test both). Short mirror.
- **Sources:** 075_vN2BkfyRWE4 ~01:07:19 (context ~1:06:45-1:07:35).
- **Quote:** "75 of that range if my stop is below that I'm comfortable with that" (075).
- **Conflicts:** none.
- **[our interpretation]:** which end the 75% is measured from; "a range traded both ways" = an up leg and a down leg within the last N bars whose ranges overlap, with price now closed above H.
- **Rulebook fix:** E6 / A11: "075 BPR stop: after price clears a two-way range, a stop inside it is acceptable, preferred below its 75% level."
- **BUILD SPEC (entries_stops_sizing; BPR detector from levels_detectors A11):**
  - Where: stop block: `stop_mode="bpr75"` -> the most recent range [L,H] the leg traded through both ways (A11 `bpr` objects plus a new `two_way_range` candidate in `levels.py`: the high/low span of the last up-close/down-close leg pair that price has since closed above), stop = `bpr75_ref` "upper" H - 0.25(H-L) or "lower" L + 0.25(H-L), minus 1 tick.
  - Params: `bpr75_ref: str = "upper"` ("lower"); add "bpr75" to the validator.
  - Test: `test_stop_bpr75`. Range 4100-4120, long above 4120: "upper" stop 4114.75, "lower" 4104.75.

### 56. E6-new-trader-wide-stops
- **rule_id / kind:** E6 / missing_condition. Scope: general. judgment = false.
- **Rule:** New-trader mode (bot default): prefer wider stops, with 15 ES pts as an example of acceptable size, and keep risk small via E8 sizing in micros. Stops tighten only as precision grows (also 098 ~48:45). An immediate same-direction re-entry after a stop-out from a tight stop is for experienced traders only. The <2-pt rule stays as already written in E6.
- **Sources:** 102_uzPM1CuSSx8 ~01:52:49 (also ~1:41:05).
- **Quote:** "you're not going to feel that way if you're trading with one micro" (102).
- **Conflicts:** none.
- **Rulebook fix:** E6: "New traders: wider stops (e.g. 15 ES pts) at micro size; tighten with precision (102 ~1:52:49, 098 ~48:45). Immediate re-entry after a tight-stop stop-out: experienced only."
- **BUILD SPEC (entries_stops_sizing):**
  - Where: `trader_mode="new"` (item 33) sets `max_risk_pts` to `new_max_risk_pts` (15) and disables same-direction re-entry when the stopped trade's risk was < `tight_stop_pts` (blocks `reentry_half` / `reentry_ts` for that loss). With `stop_widen_new`, structural stops tighter than `tight_stop_pts` are pushed out to the next structural level (the `next_pd` candidate list from item 54) instead of skipped.
  - Params: `new_max_risk_pts: float = 15.0`, `tight_stop_pts: float = 3.0` [our interpretation], `stop_widen_new: bool = False`.
  - Test: `test_new_mode_wide_stop`. Structural stop 1.5 pts with the next array 6 pts away -> stop at 6 pts; a stop-out at 1.5 pts allows no re-entry.

### 57. E6-refined-stop-htf
- **rule_id / kind:** E6 / missing_condition. Scope: general. judgment = true.
- **Rule:** When refining an entry to lower timeframes (15m to 5m) inside an HTF setup, keep the stop below the HTF level/sweep low (cc02_002: 7507 under the 7512 daily OB level). Do not tighten it to the LTF OB. Only the entry moves, so risk shrinks (17 to ~8 pips). The 1H version used a different stop (below the 1H OB MT).
- **Sources:** cc02_002_Zsg8IeBtfu0 ~00:06:34 (context ~4:55-8:10).
- **Quote:** "it should not go down to 757 if it's going to go higher it should go up higher from where it's at" (cc02_002).
- **Conflicts:** none.
- **Rulebook fix:** E6: "Refined LTF entries inside an HTF setup keep the stop beyond the HTF level / sweep low; only the entry moves (cc02_002)."
- **BUILD SPEC (entries_stops_sizing; HTF context from bias_htf `htf.table`):**
  - Where: stop block: with `stop_htf_anchor`, when the sweep traded into an HTF array (the existing `htf` tag on `sw`) the stop = min(sweep extreme, that HTF array's bottom) - pad, not the LTF OB MT; the LTF entry is unchanged. Max-risk filter as usual.
  - Params: `stop_htf_anchor: bool = False`.
  - Test: `test_stop_htf_anchor`. Sweep into a daily OB with level 4012, sweep low 4011, 1m OB MT 4016: stop 4010.75.

### 58. E6-attempt-based-stop
- **rule_id / kind:** E6 / shortened. Scope: general. judgment = false.
- **Rule:** First attempt: stop = entry OB MT minus a small buffer. If stopped out and the idea has not unraveled, re-enter on the new bullish OB that forms afterwards (a down candle price trades above), entry at its open/top, stop below that OB's low (full candle), risk = half the previous risk (2% -> 1%, 1% -> 0.5%). Short mirror.
- **Sources:** cc02_005_vWDElb65YHg ~00:01:47 (context ~1:13-5:45).
- **Quote:** "want to have a stop loss just a little bit below this means threshold and there's nothing wrong with that normally" (cc02_005).
- **Conflicts:** none.
- **Rulebook fix:** X13b / E6: "Re-entry after an OB-MT stop-out (cc02_005): new OB after the stop-out, entry at its open, stop below its full low, half the previous risk."
- **BUILD SPEC (entries_stops_sizing; uses the built `reentry_half`):**
  - Where: the `reentry_half` re-entry path: with `reentry_stop="ob_low"`, the re-entry order is the first new bullish OB (down-close candle whose high is then exceeded) after the stop-out, entry at its open (body top), stop = its low - 1 tick; risk_mult 0.5 (existing).
  - Params: `reentry_stop: str = ""` ("ob_low").
  - Test: `test_reentry_ob_low_stop`. Stopped at the OB MT; next down candle o=4015 l=4011 then exceeded: re-entry limit 4015, stop 4010.75, half risk.

### 59. E6-ob-body-stop
- **rule_id / kind:** E6 / missing_rule. Scope: general. judgment = true.
- **Rule:** Bullish OB entry (at the OB open): default stop = below the OB candle's close (body low) minus a buffer. Option ob_stop='wick' = below the OB wick low minus a buffer. Bearish mirror (above the close, or above the wick high).
- **Sources:** cc04_003_PIYh0CxoY9c ~00:10:44.
- **Quote:** "primarily... the low formed by the close of the body" (cc04_003).
- **Conflicts:** none.
- **Rulebook fix:** E6: "OB entry stop (cc04_003): below the OB's body low (close) by default, or below its wick low."
- **BUILD SPEC (entries_stops_sizing; the default `ob_entry="pre_break"` path):**
  - Where: the OB-entry stop in `_ob_pre` (~3691) / `_finish_order`: `ob_stop` "body" = min(o, c) over the OB candles - pad; "wick" = min(l) - pad; "" = today's MT stop.
  - Params: `ob_stop: str = ""` ("body" / "wick").
  - Test: `test_ob_stop_body_wick`. OB candle o=4020 c=4016 l=4013: body -> 4015.75, wick -> 4012.75.

### 60. A12-ob-anchor
- **rule_id / kind:** A12 / shortened. Scope: general. judgment = false.
- **Rule:** Param ob_anchor = 'highest_open' (default, first candle) | 'last_open' (tight variant, tighter stop).
- **Sources:** cc05_015_Y1oxwc354oo ~00:16:48.
- **Quote:** "you can use that one but if you want to be ultra Ultra tight on your stops" (cc05_015).
- **Conflicts:** none.
- **Rulebook fix:** A12: "Multi-candle OB: anchor at the highest (first) open; the last candle's open is an ultra-tight alternative (cc05_015 ~16:48)."
- **BUILD SPEC (entries_stops_sizing; OB geometry from levels_detectors):**
  - Where: `_ob_pre` (~3691) and `_ob_add` (~2986, which today uses `sd.o[j:k+1].max()`): `ob_anchor="last_open"` uses the last down-close candle's open (`sd.o[k]`) as the entry/zone top and MT reference; "highest_open" = current behaviour.
  - Params: `ob_anchor: str = "highest_open"` ("last_open").
  - Test: `test_ob_anchor_last_open`. Three down candles opens 4030, 4026, 4022: highest_open -> 4030, last_open -> 4022.

### 61. E6-mitigation-block-stop
- **rule_id / kind:** E6 / missing_rule. Scope: general. judgment = false.
- **Rule:** Mitigation-block short (A15): enter on the retrace into the last down-close candle of the broken swing low (body or whole candle). Stop = that candle's high + pad (E6 padding, 1 tick). Some drawdown into the candle is normal (ICT: ~20 pips), but price should not get much above it. Bullish mirror: stop below the low of the last up-close candle.
- **Sources:** cc04_004_FOUzW0QmsfI ~00:14:00 (context ~13:53-14:21).
- **Quote:** "our stop has to be somewhere above the down candle in here" (cc04_004).
- **Conflicts:** none.
- **Rulebook fix:** A15 / E6: "Mitigation-block entry: stop beyond that candle's extreme + 1 tick (cc04_004 ~14:00)."
- **BUILD SPEC (entries_stops_sizing; detector `levels` A15 mitigation blocks, built for targets as `mit_targets`):**
  - Where: new entry-array kind "mit" in `entry_arrays` (setups_models built list): limit at the mitigation candle's body edge on the retrace; stop = its far extreme (high for a short) + 1 tick. Short entries only exist where the engine trades both sides (`_scan_core` Side mirror handles it).
  - Params: `mit_entries: bool = False`.
  - Test: `test_mit_block_entry_stop`. Broken swing low with last down-close candle o=4040 c=4036 h=4041: short limit at 4036 (body bottom; body variant at 4040 via `ob_entry_px`), stop 4041.25.

### 62. E6-propulsion-mt
- **rule_id / kind:** E6 / missing_rule. Scope: general. judgment = false.
- **Rule:** Optional ultra-tight stop for propulsion-block entries (A16): long stop just below the propulsion candle's MT (measure per D4) minus 1 tick; short mirror above the MT. This is the same level as the X8 invalidation, but as a resting stop.
- **Sources:** cc04_008_glu98jAH8vE ~00:05:21.
- **Quote:** "you can have a really ultra tight stop loss" (cc04_008).
- **Conflicts:** none.
- **Rulebook fix:** E6: "Propulsion-block entry: ultra-tight stop just beyond the propulsion candle's MT (cc04_008 ~5:21)."
- **BUILD SPEC (entries_stops_sizing; extends the A16 `prop_entry` spec in rule_coverage):**
  - Where: when the order comes from `prop_entry` (A16), `prop_stop="mt"` sets stop = propulsion candle MT (D4 measure) - 1 tick instead of the X8d close-exit only.
  - Params: `prop_stop: str = ""` ("mt").
  - Test: `test_prop_mt_stop`. Propulsion candle range 4010-4018 (MT 4014): stop 4013.75.

### 63. E6-at-the-high
- **rule_id / kind:** E6 / shortened. Scope: general. judgment = false.
- **Rule:** Short at the breaking-point retest after a buy-stop run (bearish breaker/failure swing): stop = the stop-run high + 1 tick (standard), or exactly at that high (tight variant; ICT says price is unlikely to return because those stops are already taken). Bullish mirror.
- **Sources:** cc05_005_xRjKtUEKkSE ~00:11:19.
- **Quote:** "our stop loss could actually be above this high or rate at that high" (cc05_005).
- **Conflicts:** none.
- **Rulebook fix:** E6c: "cc05_005 ~11:19: the stop may sit exactly at the stop-run high (its stops are taken), or 1 tick above."
- **Already listed:** rule_coverage section 3 E6c `stop_mode="sweep"` + E6f `stop_pad_ticks` (0 = at the high), used by the built `cc_swings` path. No new spec.

### 64. M12-ts-sweep-depth-fx
- **rule_id / kind:** M12 / missing_rule. Scope: fx_only. judgment = true.
- **Rule:** FX, 15m/30m, bullish bias, old low L: expect a 10-20 pip sweep. Preferred: buy limit under L (example: low 130.95, limit 130.90), rather than at or above L (allowed in the definition, but discouraged as fear of missing out). Stop 30-50 pips below entry. A sweep beyond ~25 pips below L suggests a real decline, not a stop run. Index analog [our interpretation]: scale by ATR/ADR.
- **Sources:** cc04_011_Gnw54f9v6SA ~00:10:38 (context ~10:29-11:40, ~14:09).
- **Quote:** "you can expect a 10 to 20 pip sweep below the old low. a 30 to 50 pip stop is ideal" (cc04_011).
- **Conflicts:** none.
- **Rulebook fix:** M12 (cc limit, fx): "15m/30m sweep 10-20 pips; buy limit under the low preferred; stop 30-50 pips; > ~25 pips under = real decline."
- **No build spec:** fx_only (the built `ts_cc_below_pts` / `ts_max_pts` already carry the index analog).

### 65. E6-tf-proportional-stops
- **rule_id / kind:** E6 / missing_rule. Scope: fx_only. judgment = true.
- **Rule:** Intraday max stop ~ADR/3 (FX: 30-35 pips on a ~100-pip ADR; index analog [our interpretation]: ADR5/3). Daily-execution (HTF) trades: stop sized to daily structure, e.g. 200 pips; reward:risk at least 3:1, higher preferred; do not move the stop to breakeven or reduce risk early on HTF position trades. Position size follows from E8.
- **Sources:** cc05_013_crPpMwgwa7k ~00:15:53; cc05_009_4i_hnoEk6lw ~00:17:31.
- **Quote:** "a third of that would be 33 so i rounded to 35 pips" (cc05_013).
- **Conflicts:** none.
- **Rulebook fix:** E6 (fx note): "Intraday max stop ~ADR/3 (cc05_013); daily-chart trades need much wider stops, >= 3:1, no early breakeven."
- **No build spec:** fx_only. (An index `max_risk_adr=1/3` test could reuse `adr5()`; not specced here because the scope is fx.)

### 66. E6-swing-stops
- **rule_id / kind:** E6 / missing_rule. Scope: general. judgment = true.
- **Rule:** Swing long (daily/4h execution, parked per M17): stop below the most recent daily swing low at entry, or below the short-term sell-side liquidity that sits behind the 4h/daily entry level, not tight under the entry OB. Short mirror. Swing-low definition (3-candle pivot) is our interpretation.
- **Sources:** cc05_016_vb_Yc-gCBfU ~00:10:14; cc06_004_osRUnIpGIJ0 ~00:21:17.
- **Quote:** "your stop- loss as you'll learn will be below the swing low that's most recently been created on the daily chart" (cc05_016).
- **Conflicts:** none.
- **Rulebook fix:** E6 / M17: "Swing stops: below the most recent daily swing low, or behind the short-term sell-side beneath the 4h/daily entry level (cc05_016, cc06_004)."
- **BUILD SPEC (bias_htf, research study helper):**
  - Where: `htf.py` helper `swing_stop(daily, i, side, mode)`: "daily_swing" = the latest 3-bar daily pivot low before bar i; "ssl_behind" = the nearest 4h swing low below the entry level. Used by the study engines of items 5, 7 and 22 (`swing_stop_mode` in their config).
  - Params (study config): `swing_stop_mode: str = "daily_swing"`.
  - Test: `test_swing_stop_helper`. Daily pivots at 4000 and 4030, entry 4050: daily_swing -> 4030 - pad.

### 67. E6-london-stop-table
- **rule_id / kind:** E6 / missing_rule. Scope: fx_only. judgment = false.
- **Rule:** London buy day trades (fx-only; sells mirror): CBDR+PD array: entry - 30 pips; run under the Asian range low: entry - 40; any sell-stop raid: raid low - 30; first retracement into a 15m/5m bullish OB: low of day - 10; second run below the initial low (turtle soup): that low - 30; any other setup: Asian range low - 0.5 x ADR5. Don't move the stop to breakeven before ~40-50% of the daily range. Index analog [our interpretation]: overnight range extreme +/- 0.5 ADR5.
- **Sources:** cc08_007_5Z_3NbclMSY ~00:14:29, ~00:16:01.
- **Quote:** "if you're trading in Central Bank dealers range overlap with a PD array the stop has to be 30 Pips under your entry" (cc08_007).
- **Conflicts:** none.
- **Rulebook fix:** M17 (London, fx): add the stop table and the "no breakeven before 40-50% of the daily range" rule.
- **No build spec:** fx_only.

### 68. L16-adr5-stop
- **rule_id / kind:** L16 / missing_rule. Scope: fx_only. judgment = false.
- **Rule:** 0 GMT open model (fx-only, HTF trades): buy at the 0 GMT opening price; stop = 0 GMT open - ADR5 (mean daily high-low of the last 5 days); hold toward an HTF premium PD array. Short mirror: sell at the open, stop = open + ADR5. The wide stop is accepted because the target is several hundred pips. ATR substitute = our interpretation.
- **Sources:** cc08_008_1MnfiqKx5Uo ~00:14:03.
- **Quote:** "subtract it from the opening price at zero GMT there's your stop loss" (cc08_008).
- **Conflicts:** none.
- **Rulebook fix:** L16 / M17: "0 GMT model: stop = open -/+ ADR5 (cc08_008 ~14:03)."
- **No build spec:** fx_only.

### 69. M17-split-entry-open
- **rule_id / kind:** M17 / missing_rule. Scope: fx_only. judgment = false.
- **Rule:** [fx-only, parked under M17] Unit 1 (50%) sells at market at the 0 GMT open. Unit 2 (50%) is a sell limit at open +10 to 20 pips (mirror for buys: below the open). The protective stop = limit entry + ADR5 (open +20 + ADR5 for shorts). If unit 2 never fills, keep unit 1. Exits at HTF objectives.
- **Sources:** cc08_008_1MnfiqKx5Uo ~00:18:31.
- **Quote:** "take half of that risk and just simply add it at the zero GMT" (cc08_008).
- **Conflicts:** none.
- **Rulebook fix:** M17 (0 GMT, fx): "Split entry: half at the 0 GMT open, half at a 10-20 pip limit; stop = limit + ADR5."
- **No build spec:** fx_only.

### 70. L15-min-rr-3
- **rule_id / kind:** L15 / missing_rule. Scope: general. judgment = false.
- **Rule:** Day-trade setups should ideally pay 3:1 to 5:1 to the final target (stated as the standard, not a strict filter). Test min_rr=3 measured to the final target, with 5 as the ideal; keep the existing T1 check separate.
- **Sources:** cc08_001_-cXnnHjy9s0 ~00:05:01.
- **Quote:** "we're looking for setups that pay out five to one or three to one ideally" (cc08_001).
- **Conflicts:** none.
- **Rulebook fix:** L15 / X1: "Day trades ideally pay 3:1 to 5:1 to the final target (cc08_001 ~5:01); the T1 min_rr check stays."
- **BUILD SPEC (targets_partials):**
  - Where: `_finish_order` target merge: after the ladder is built, if `min_rr_final > 0` and (final rung - entry) / (entry - stop) < `min_rr_final`, reject (filter tag `x_rr_final`). Also record `rr_final` on every Trade for the report.
  - Params: `min_rr_final: float = 0.0` (test 3.0 and 5.0).
  - Test: `test_min_rr_final`. Risk 2, final rung +5 -> rejected at 3.0; +7 -> accepted.

## D. Out of scope for the bot

### 71. new-basket-allocation
- **rule_id / kind:** new / missing_rule. Scope: needs_unavailable_data. judgment = true.
- **Rule:** Commodity basket (annual mega trade): one leader per commodity sector. Rank leaders by which breaks short-term highs/bearish OBs first and holds bullish OBs. Put ~50% of the idea's capital into the top ~3, and spread the rest across the remaining sector leaders. With options, buy more contracts in the strongest names. Scope: commodities, needs unavailable data.
- **Sources:** cc11_001_u5S6Zt1ZIpA ~00:30:49.
- **Quote:** "say 50 of your investment Capital goes into those three" (cc11_001).
- **Conflicts:** none.
- **Rulebook fix:** M17: "Commodity mega trade (cc11_001): ~50% of capital in the top ~3 sector leaders, the rest spread over the other leaders."
- **No build spec:** needs commodity futures data.

### 72. new-stock-calls
- **rule_id / kind:** new / missing_rule. Scope: stocks. judgment = true.
- **Rule:** Stock mega trade (bullish seasonal/earnings setup): instrument = an option on the screened leader stock, with strike and expiry chosen from the Greeks (calls implied, since the setup is long). No stop or target given here (deferred to the August options lessons). Out of scope for the index bot.
- **Sources:** cc11_003_kny8Kpisvoc ~00:22:41.
- **Quote:** "go into the options chain and look at the Greeks to determine which option and what strike place you would look to trade" (cc11_003).
- **Conflicts:** none.
- **Rulebook fix:** M17: "Stock mega trade (cc11_003): executed with options chosen from the Greeks; no stop/target given."
- **No build spec:** stock scope, but it needs an option chain with Greeks, which `alpaca_data.py` does not load; the stock research studies stay on shares.
