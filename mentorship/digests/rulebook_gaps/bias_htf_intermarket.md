# Rulebook gaps: bias, HTF and intermarket

Topic `bias_htf_intermarket`. Every item below is a verified gap between ICT's captions and `mentorship_rules.md`. When the checker gave a corrected rule, that corrected rule is the one written here; when it gave none, the claim's full rule is used. "[our interpretation]" marks thresholds or readings that ICT does not state.

Conventions:
- Times are New York. Params times are minutes from midnight (480 = 08:00, 570 = 09:30, 600 = 10:00, 720 = 12:00, 780 = 13:00, 810 = 13:30, 900 = 15:00).
- New Params switches default off (rule_coverage.md section 3). Each work package adds its fields in its own commented block at the end of `Params`.
- Work packages are the names in `rule_coverage.md` section 3. The bias_htf package owns `htf.table` (new columns), the `want` / bias block of `run_day` (~2575-2585), `weekly_bias`, `backtest.INTERMARKET` (daily DXY / TNX from Yahoo, prior-day only) and new data loaders. The `_scan_core` bias gates (the `use_bias` open check ~3984) are shared with setups_models; merge after setups_models.
- `htf.table` already builds weekly arrays on weekly bars (`weeks(d)` -> `_arrays(..., "W")`), carries the stateful `flip` column (`_flip`, triggers in `htf.FLIP_TRIGGERS`) and the opening gaps (`opening_gaps`). New daily states below are new `htf.table` columns computed at the prior close and applied to the next session (no look-ahead), the same as `flip`.
- "Already in rule_coverage" means the item's switch is already specified there. Where only part of the item is new, the build spec covers only that part.
- Specs name test functions. New tests go in `tests/test_bias_htf.py` unless a package's own test file fits better (`tests/test_setups_models.py`, `tests/test_levels_detectors.py`).
- Items scoped `fx_only`, `bonds_only` or `needs_unavailable_data` get the rulebook fix only, with no build spec. Intraday DXY, bond futures (ZB/ZN/ZF), COT, open interest, commodities, YM/DJI intraday, sentiment text and news feeds count as unavailable. Daily DXY and the 10-year yield (`INTERMARKET`) are available.

Summary: 227 items, 168 new build specs. Items without a build spec:
- 16 fx_only
- 2 bonds_only
- 37 that need data we do not have
- 2 already listed in rule_coverage with the same content: X3-b10-4h-correction-cases (B10 `mwd` cases A/B/C) and D15-leader-and-relative-strength (the index part is D15 `smt_pick` leader; the cross-asset ranking is outside the bot's markets)
- 2 text-only: B5-style-timeframe-mapping (the bot already matches: entries <= 4h, bias daily+) and X3-indicators-contrarian-only (the bot uses no oscillator as a signal)

---

## A. Intraday bias, opens and PO3

### 1. BH-B17-daily-range-scalp-regime
- **rule_id / kind:** B17 / missing_condition. Scope: index. judgment = true.
- **Rule:** While the daily chart is in a multi-day consolidation (B17), target about 5 ES handles per trade and take T1 only. Once one side's pool has run, trade toward the opposite pool. Stop for the day after about 10 handles (two runs). The regime ends when price breaks out of the daily range; whether that means a close or a wick is undefined, so test both. After the breakout, allow runners in the breakout direction.
- **Sources:** 002_GHaD0mebgMU ~00:06:57; 043_NkwqJBzgQwo ~00:06:55, ~00:13:48.
- **Quote:** "we want to see a break out of that daily range before my interest has really peaked"
- **Conflicts:** none. Appendix A already has the regime end (line 1305) and the scalp size (line 1388, 2.5-5 handles).
- **[our interpretation]:** How the range is defined: the last N daily bars inside an envelope, N = 5 by default. Also the close-vs-wick test.
- **Rulebook fix:** Under B17 add: "Daily consolidation scalping: ~5 handles, T1 only. After one pool runs, trade toward the opposite pool. Stop after ~10 handles / two runs (043 ~6:55, ~13:48). Breakout of the daily range ends it (002 ~6:57)."
- **BUILD SPEC (bias_htf):**
  - Add `htf.table` column `drange` (+1 / -1 / 0). It is 0 while the last `drange_n` daily closes stay inside the high-low of the first of those days. It is +1 / -1 from the first daily close (or high/low, if `drange_break="wick"`) beyond that range, and stays set until a new range forms.
  - In `run_day`: when `p.drange_scalp` and `drange == 0`, set `scalp` on every order (single target, no adds; the same path as `sloppy_mode="scalp"`) and cap the T1 distance at `drange_t1_pts`.
  - After a session target hits, flip the next allowed side to the opposite pool.
  - Stop the day once `state["day_pts"] >= drange_day_pts` or two wins have been taken.
  - When `drange != 0`, the side gate is the breakout side and runners are allowed.
  - Params: `drange_scalp: bool = False`, `drange_n: int = 5`, `drange_break: str = "close"` ("close" / "wick"), `drange_t1_pts: float = 5.0`, `drange_day_pts: float = 10.0`.
  - Test: `test_drange_scalp_regime`. Synthetic daily history: 6 days inside 4000-4040 gives drange 0, scalp-tagged trades and a stop after 10 pts. A close at 4045 gives drange +1 the next day, with runners allowed.

### 2. BH-B12-midnight-open-tolerance
- **rule_id / kind:** B12 / B13, unlisted_contradiction. Scope: index. judgment = true.
- **Rule:** Long if entry <= midnight_open + tol; short if entry >= midnight_open - tol. tol is 2-3 ES pts; also test 0. A wrong-side entry inside tol needs three things: the open was already traded through in the manipulation direction, the entry is at an OB/FVG, and there has been an MSS since that move. Tag 'best' (beyond the open) vs 'allowed'; strict mode keeps 'best' only. Apply the same to the 13:30 open in the PM. Position trades (> 2 weeks) prefer longs below the week's Sunday 18:00 open and shorts above it, as a tag, not a hard filter.
- **Sources:** 006_VKkn8uckkW0 ~00:25:38; 010_cWekmMLqiNM ~00:38:48, ~00:47:02; 048_gGxVE8zUIRQ ~01:00:57. 008 was dropped as a DXY/FX example.
- **Quotes:**
  - "as it goes back close to that opening price you can be a buyer there too if there's logic behind it"
  - "are better entered if you're bullish below the opening price on Sunday"
- **Conflicts:** B12 / Decision 12 / `use_bias` treat the open as strict. B13 cites 048 for intraday weekly-open use.
- **[our interpretation]:** tol = 2-3 pts.
- **Rulebook fix:**
  - B12: "beyond the open = best. Within ~2-3 pts on the wrong side is allowed when the open was already traded through in the Judas direction, the entry is at an OB/FVG and an MSS has formed (006 ~25:38; 010 ~38:48 'preferably')."
  - Decision 12: list strict vs tolerance.
  - B13: the Sunday-open rule is a preference for >2-week trades (048 ~1:00:57).
- **BUILD SPEC (setups_models; bias gate shared with bias_htf):**
  - Already partly in code: Ep04.4 `po3_inclusive` + `eq_tol_pts` (0.5) let an entry sit within tol above the open. New is the separate tolerance, its preconditions and the tag.
  - Where: `_scan_core` `use_bias` block (~3984). When `p.open_tol_pts > 0` and the entry is on the wrong side by <= `open_tol_pts * es_pt`, accept only if all three hold:
    - (a) the session's extreme since 00:00 (13:30 in the PM) went beyond `ref_open` in the Judas direction;
    - (b) the entry gap is an FVG or OB (all current entries are);
    - (c) `sw["mss_i"]` is after that extreme.
  - Set `Trade.open_grade` = "best" / "allowed". With `open_tol_pts = 0`, behaviour is unchanged.
  - Params: `open_tol_pts: float = 0.0` (test 2.0 / 3.0).
  - Separately, in bias_htf, `Trade.wk_open_side` = sign(entry - Sunday 18:00 open) as a tag only. The source is `_open_known(ctx, "sunday", i)`; add "sunday" to `_open_known` from the NWOG open.
  - Test: `test_open_tolerance_grade`. Midnight open 4000 and a long entry at 4002 after a low at 3990 and an MSS give "allowed" with tol 3, and are rejected with tol 0. An entry at 3998 gives "best".

### 3. BH-B12-po3-sequence
- **rule_id / kind:** B12 / shortened. Scope: index. judgment = true.
- **Rule:** Bearish case. This is the preferred sequence: tag it 'po3_seq', and also test it as a filter.
  1. After 00:00, price trades above the midnight open.
  2. Price trades back below the open.
  3. An MSS + FVG/OB sell setup forms at or above the open, or at a PD array just below it.
  
  Bullish is the mirror. The 13:30 open works the same way for the PM.
- **Sources:** 006_VKkn8uckkW0 ~00:06:33.
- **Quote:** "you would ideally want to see a move above it and then go back back below it"
- **Conflicts:** none. Line 1392 states this order for 13:30 only.
- **[our interpretation]:** "just below it" = within `po3_seq_below_pts` (default 3 pts).
- **Rulebook fix:** B12: add the three-step preferred order ("ideally", 006 ~6:33) for both the midnight and the 13:30 open.
- **BUILD SPEC (setups_models):**
  - Where: `_scan_core` beside the `use_bias` block. Compute `po3_seq` for the order: the highest high since 00:00 (since 13:30 in the PM) > `ref_open`; a later bar closes back below `ref_open` before `sw["mss_i"]`; entry >= ref_open - `po3_seq_below_pts * es_pt`. Mirror for longs.
  - Tag `Trade.po3_seq`. When `p.po3_seq == "filter"`, reject orders without it (`_f("x_po3_seq")`).
  - Params: `po3_seq: str = "off"` ("off" / "tag" / "filter"), `po3_seq_below_pts: float = 3.0`.
  - Test: `test_po3_sequence`. A synthetic 1m day with the open at 4000, a high at 4006 at 02:00, a close at 3997 at 03:00 and a short MSS at 09:40 gives po3_seq True. A day that never traded above 4000 gives False and is rejected under "filter".

### 4. BH-B7-last-daily-OB-guard
- **rule_id / kind:** B7 / missing_condition. Scope: general. judgment = false.
- **Rule:**
  - MT = 50% of the last daily bullish OB (down-close candle).
  - Bullish IOF holds while no daily close is below MT. Wicks below MT are allowed.
  - If the level isn't reached during the week, carry it into the next week.
  - On a daily close below MT/OB, the draw = the next daily BISI / sell-side below.
  - In-week variant (101): a daily close below MT means the weekly high is likely in, for that week only. Block longs that need a new weekly high. This is not a short signal.
  - Optional variant flag: b7_mode in {mt_daily_close (default), mt_trade_through (058 wording ambiguous), ob_close (072)}.
  - Mirror for bearish.
- **Sources:** 058_hcSGlyfgKgA ~00:06:43; 072_AKg_r0DIa3k ~00:17:12; 101_VElIka5sk0E ~00:33:35.
- **Quotes:** "keep that level also into next week okay because that's my last line of defense"; "would it change anything if it did that no"
- **Conflicts:** 058 says "goes through", 072 says the OB low on a close, B7 says the MT on a close.
- **Rulebook fix:** B7: add the carry-forward (058), the wick allowance (101), the next draw after the break (072 ~17:40, lower BISI) and "a close below MT = weekly high likely in, not a short" (101 ~33:35). List `b7_mode` as a Decision.
- **BUILD SPEC (bias_htf):**
  - The `flip` trigger `ob_mt` already flips on a daily close through MT. New pieces:
    - `htf.table` column `ob_guard` with the MT level, carried across week boundaries (not reset on Monday).
    - Column `wk_high_in` (bool): set from the day after a daily close below the guard MT, cleared at the next weekly open. Mirror `wk_low_in`.
    - `b7_mode` selects the trigger level: MT close / any trade below MT / close below the OB low.
  - In `run_day`: when `p.wk_high_in_gate` and `wk_high_in`, drop long targets above the current week's high (`_targets` filter on levels > week high). Do not set `want` to -1.
  - After a break, `draw_dn` = the nearest daily BISI / pool below (existing draw column).
  - Params: `b7_mode: str = "mt_close"` ("mt_close" / "mt_trade" / "ob_close"), `wk_high_in_gate: bool = False`.
  - Test: `test_b7_guard_modes`. A daily OB 4000-4020 (MT 4010). Wick to 4005 with a close at 4012: no change. Close at 4008: `wk_high_in` True the next day and still False for `ob_close`. With no touch by Friday, the guard is still 4010 on Monday.

### 5. BH-A8-60m-BISI-loss-draw
- **rule_id / kind:** A8 / B2, missing_condition. Scope: index. judgment = true.
- **Rule:**
  - If a 60m close is below the nearest 60m BISI that sits under the swing's 50% (discount), lean the draw to the sell-side lows below.
  - A retrace that treats the lost BISI as resistance strengthens the read but is not required for the draw.
  - Entries still need A8: a close beyond, a new candle retests, and it holds.
  - Single source (007), so this is judgment with low weight. Mirror.
- **Sources:** 007_bGtQOXrrK9c ~00:06:46.
- **Quote:** "it doesn't need to do that but if it did"
- **Conflicts:** A8's retest applies to entries only.
- **Rulebook fix:** B2: add "a 60m close below the nearest discount 60m BISI leans the draw to the sell-side below; no retest needed for the draw (007 ~6:46, single source)".
- **BUILD SPEC (bias_htf):**
  - Where: `run_day` / `_lock_step` (draw lock). At each lock time, build 60m bars (`htf_bars(df, 60)`), take FVGs (`levels.fvgs`) of the current swing and find the nearest bull FVG below the swing EQ. If a 60m close below its low happened before the lock, set the lock candidate side to -1 (sell-side pools below) and tag `bisi60_lost`. Mirror.
  - Params: `bisi60_draw: bool = False`.
  - Test: `test_bisi60_lost_draw`. Swing 3950-4050, 60m BISI 3985-3990, and a 60m close at 3982 before 09:30 lock the AM side to -1.

### 6. BH-B17-neutral-lean
- **rule_id / kind:** B17 / missing_rule. Scope: index. judgment = true.
- **Rule:**
  - A neutral bias still carries a lean ('gun to head').
  - At a daily premium array after repeated failed upside attempts (and few sell-side runs), lean short toward the next daily discount array / sell-side. Still wait for 09:30.
  - Preferred trigger: a raid of the prior day's/Tuesday's high or a nearby key level, then short and add on new bearish FVGs/breakers.
  - If no raid comes, take only small trades inside the range.
  - Mirror. Judgment, single source (010).
- **Sources:** 010_cWekmMLqiNM ~00:36:36.
- **Quote:** "already tried going higher several times and we only had one real run on sell side"
- **Conflicts:** none. The claim's ~5 pts and "MSS at reduced size" were dropped.
- **[our interpretation]:** "Repeated failed attempts" = >= 2 daily highs within `lean_tol_pts` of the premium array without a close above it.
- **Rulebook fix:** B17: "Neutral still has a lean (010 ~36:36): at a daily premium array after repeated failed rallies, lean short after 09:30, preferably after a raid of the prior/Tuesday high. Without a raid, small trades inside the range only."
- **BUILD SPEC (bias_htf):**
  - Add `htf.table` column `lean` (+1 / -1 / 0), computed only when the main bias is 0.
  - -1 when price sits inside or within `lean_tol_pts` of a daily bear array (`_arrays` "D") and the last `lean_n` daily highs probed it without a daily close above it.
  - In `run_day`, when `p.neutral_lean` and `want == 0`, set `want = lean` but mark orders `scalp`, unless a raid of PDH (or the Tuesday high, on later days of the week) happened before the entry. With that raid, normal management applies.
  - Params: `neutral_lean: bool = False`, `lean_n: int = 2`, `lean_tol_pts: float = 5.0`.
  - Test: `test_neutral_lean`. Two days with highs at 4029 / 4031 under a bear daily FVG at 4030-4040, then a neutral main bias, give lean -1 and scalp-tagged shorts. A PDH raid before the entry clears the scalp tag.

### 7. BH-weekly-BISI-CE-and-full-close
- **rule_id / kind:** B8 / missing_rule. Scope: index. judgment = true.
- **Rule:**
  - Weekly BISI under price in a bullish HTF: expect support at its upper edge, or at worst its CE.
  - CE = the bulls' last line of defense. Losing it puts the bullish idea in doubt.
  - If price entirely closes the BISI in (body through its low), the bias is very bearish: look for lower targets / the next lower weekly array.
  - Mirror for a weekly SIBI. Index (ES) sources 011, 047.
- **Sources:** 011_w0CYBeFTzcM ~00:05:06; 047_441vklRYYR4 ~00:02:05.
- **Quote:** "does it entirely close that in if it does that means we're probably very bearish"
- **Conflicts:** none. The claim's "weekly body below CE = neutral" step is not sourced.
- **[our interpretation]:** What "in doubt" maps to: a weekly close below CE sets the state to neutral (test switch).
- **Rulebook fix:** B8: add the weekly BISI ladder: upper edge / CE support, CE last line, body through the low = very bearish, next lower weekly array (011 ~5:06; 047 ~2:05).
- **BUILD SPEC (bias_htf):**
  - Add a new `flip` trigger `wk_bisi`. On a weekly close below the low of the nearest weekly bull FVG under the prior state, the state goes to -1 and `draw_dn` = the next lower weekly array. With `wk_bisi_ce_neutral`, a weekly close below its CE (but above the low) sets the state to 0. Mirror for SIBI.
  - Add "wk_bisi" to `htf.FLIP_TRIGGERS`.
  - Params: `wk_bisi_ce_neutral: bool = False`. Enable by putting "wk_bisi" in `flip_triggers`.
  - Test: `test_flip_wk_bisi`. A weekly bull FVG 4000-4040 (CE 4020). Weekly close at 4015 with ce_neutral gives 0. Weekly close at 3990 gives -1.

### 8. BH-B8-draw-flip-via-inversion
- **rule_id / kind:** B8 / missing_rule. Scope: general. judgment = true.
- **Rule:**
  - State 1: the bias holds while level L (the swing low/high guarding it) is intact.
  - Price takes L and trades into the opposing inefficiency F: the bias is suspended (neutral).
  - A close through F, then a retrace into F that holds (treated as resistance/support): opposite bias. The draw = the next liquidity pool beyond.
  - Returning to State 1 after a close back beyond L is an extrapolation; the sources do not state it.
  - Sources 011, 063 (DXY).
- **Sources:** 011_w0CYBeFTzcM ~00:00:49; 063_qA9SCu4gGaU ~00:02:57.
- **Quote:** "if we trade down below it and come back up I would expect it to be treated as resistance"
- **Conflicts:** none.
- **[our interpretation]:** "Holds" = the next daily candle that trades into F closes back on the new side (A8 validity test on daily bars).
- **Rulebook fix:** B8: add the three-state order (bias -> neutral after L taken and F entered -> opposite after close through F + held retest) (063 ~2:57; 011 ~0:49).
- **BUILD SPEC (bias_htf):**
  - New `flip` trigger `inv3`, evaluated on daily bars in `htf._flip`:
    - state +1. A daily low below the guarding swing low (last daily pivot low, `piv_l`) that also trades into the nearest daily bear FVG below sets state 0, sub-state "F_entered".
    - A daily close below F's low, followed by a later day that trades back into F and closes below it, sets state -1. `draw_dn` = the next pool below.
    - Mirror.
  - Add "inv3" to `FLIP_TRIGGERS`.
  - Test: `test_flip_inv3`. A daily sequence through the three states gives +1 -> 0 -> -1 on the expected session dates, with no look-ahead (each state applies from the next session).

### 9. BH-B1-imbalance-ceiling-ladder
- **rule_id / kind:** B1 / missing_rule. Scope: general. judgment = true.
- **Rule:**
  - The nearest daily premium imbalance (VI/FVG) above price = the ceiling.
  - While price stays below it (no body close above), the discount arrays below (REL, FVG, OB, then sell-side) are expected to be reached in order (L14 ladder).
  - The bearish ladder is suspended if price trades above the ceiling/next FVG and then finds support on the retrace (two imbalances supporting).
  - Mirror. Source 011 (DXY), single source.
- **Sources:** 011_w0CYBeFTzcM ~00:00:24.
- **Quote:** "as long as we remain below that all the discount arrays ... would be reached"
- **Conflicts:** none.
- **Rulebook fix:** B1/L14: "An overhead daily VI/FVG is a ceiling: while no body closes above it, the lower arrays are drawn in order. Suspended by a trade above it that then holds as support (011 ~0:24)."
- **BUILD SPEC (bias_htf):**
  - Add `htf.table` column `ceiling` (level, from the nearest daily bear VI/FVG above the prior close; needs `vi=True`) and `ladder_dn` (bool). It is True while no daily body closes above `ceiling`. It goes False after a day trades above it and a later day's low holds at or above it (support).
  - In `run_day`, with `p.ceiling_ladder` and `ladder_dn`, set the lock side to -1 and order the session rungs by distance (L14 ladder already sorted). Mirror with `floor` / `ladder_up`.
  - Params: `ceiling_ladder: bool = False`.
  - Test: `test_ceiling_ladder`. A daily VI at 4050-4052 above with closes below it gives ladder_dn True. A day that trades to 4055 and the next day's low of 4053 gives False.

### 10. BH-A11-BPR-lean
- **rule_id / kind:** A11 / missing_rule. Scope: general. judgment = true.
- **Rule:** A 1h BPR formed by a down-up-down sequence in an HTF-bearish context leans the draw to the nearest sell-side low below rather than higher. Reassess at the next session or week open (Sunday). Mirror. Opinion-level, single source (011, DXY).
- **Sources:** 011_w0CYBeFTzcM ~00:01:51.
- **Quote:** "more likely in my opinion to gravitate towards this low"
- **Conflicts:** none.
- **Rulebook fix:** A11: add "Expectation: a down-up-down 1h BPR in a bearish HTF leans to the nearest low (011 ~1:51, opinion). Reassess at the next open."
- **BUILD SPEC (bias_htf):**
  - In `_lock_step`, at lock time, look for a 1h BPR in the last 24 h. Build it from 1h bars with `levels.fvgs`: a bull and a bear FVG overlapping, in down-up-down order.
  - If one exists and `want` / the flip state is -1, prefer the nearest pool below as the lock candidate and tag `bpr_lean`. It expires at the next session open.
  - Params: `bpr_lean: bool = False`.
  - Test: `test_bpr_lean`. A synthetic 1h down-up-down overlap with a bearish state picks the pool below even when a pool above is nearer.

### 11. BH-NWOG-week-open-scenarios
- **rule_id / kind:** B16 / L5, missing_condition. Scope: index. judgment = true.
- **Rule:** No trading on Sunday. These templates are Monday+ expectations: preferences, not hard rules (084).
  - **Bullish + gap up:** expect a draw back toward Friday's close (the NWOG far edge), then require an MSS / LTF bullish structure before longs. Holding at the NWOG CE without a full fill = strong (029).
  - **Bearish + gap down:** a retrace may enter the gap. A partial retrace of less than half is better: it signals weakness (028).
  - **Bearish + open unchanged or above Friday's close:** rally to the nearest daily wick CE, then resume lower (103).
  - **Bullish + open below the prior lower wick:** it must be reclaimed immediately, or the bullish plan is doubtful (101, DXY).
  - **Gap with the bias that fills fully and continues:** confirmation (030; 011 prefers fill-and-go when bullish).
  - The sources conflict on full fill vs partial fill, so treat these as preference flags. The 028 citation is ~1:23:15.
- **Sources:** 011 ~00:06:20; 028 ~01:23:15; 029 ~00:04:32, ~01:06:08; 030 ~00:09:36; 077 ~00:12:10; 084 ~00:03:50; 101 ~00:26:33; 103 ~00:28:05.
- **Quotes:** "leave the Gap open partially it doesn't have to come all the way back to or even halfway it's better if it doesn't"; "if we open relatively unchanged or above the close then I would look for it to trade here and then resume lower"
- **Conflicts:** 011/030 prefer a full fill, while 028/029 say not filling is stronger. 084 calls these preferences, but 103 treats them as a hard void level.
- **Rulebook fix:** B16: replace "write both scenarios" with the five templates above as preference flags. Fix the 028 citation to ~1:23:15.
- **BUILD SPEC (day_week_context):**
  - Where: `day_context` (Monday and later in the week). Classify the week open from the NWOG (`opening_gaps` row: Fri close, Sun open) and the flip state. Tags:
    - `nwog_up_bull`, `nwog_dn_bear`, `nwog_flat_bear`, `nwog_below_wick_bull`.
    - Fill status, computed per session from prior bars only: `nwog_filled` (Friday close traded), `nwog_ce_held` (CE touched, no fill), `nwog_partial` (retrace < 50%).
  - Trade tags only by default. With `p.nwog_templates == "gate"`:
    - `nwog_up_bull`: no longs until the Friday close is traded or the CE holds.
    - `nwog_below_wick_bull`: no longs Monday unless the prior lower-wick low is reclaimed by the first session's close.
    - `nwog_flat_bear`: shorts only after the nearest daily upper-wick CE (`_wick_ces`) is traded.
  - Params: `nwog_templates: str = "off"` ("off" / "tag" / "gate").
  - Test: `test_nwog_templates`. Fri close 4000, Sun open 4010, bullish state: a Monday long before 4005 is traded is blocked under "gate". After a touch at 4005 (CE), the tag `nwog_ce_held` is set and longs are allowed.

### 12. BH-B14-NWOG-flip-edge
- **rule_id / kind:** B14 / unlisted_contradiction. Scope: index. judgment = false.
- **Rule:** A bearish bias holds until price gets back above the NWOG HIGH (030: the previous week's NWOG; 046 and 060: the current NWOG). 058 uses the NWOG low instead, so expose params nwog_flip_edge {high (030/046/060), low (058)} and nwog_ref {current, previous}. Getting above the edge only switches the bias to bullish; a long still needs a retraced FVG that holds (030). Mirror for a bullish bias. Fix B14's citation: 030 ~1:19:54.
- **Sources:** 030_ZdnGlropfmU ~01:19:54; 046_VLis0LcbUaQ ~00:26:00; 060_ZtLMTXv-Dr0 ~00:35:36.
- **Quote:** "we would have to get above the new week opening Gap High"
- **Conflicts:** B14 (058 ~53:46): "back above the NWOG low". 036 ~16:00 is not a flip edge.
- **Rulebook fix:** B14: list both edges as a Decision (high: 030/046/060; low: 058). Fix 030 to ~1:19:54 and drop 036 as a flip citation.
- **BUILD SPEC (bias_htf):**
  - Already in rule_coverage as B14.3 `nwog_bias` with hold-until-reclaim. New: the edge and reference choice.
  - In the `nwog_bias` state (htf.table column `nwog_bias`, from `opening_gaps` "nwog" rows), the reclaim level is the NWOG high (bearish state) or low, per `nwog_flip_edge`. The NWOG is this week's or last week's, per `nwog_ref`. A reclaim is a daily close beyond the edge [our interpretation: close]. Mirror.
  - Params: `nwog_flip_edge: str = "high"` ("high" / "low"), `nwog_ref: str = "current"` ("current" / "previous").
  - Test: `test_nwog_flip_edge`. NWOG 4100-4110, bearish state. A close at 4105 flips under "low" but not under "high". A close at 4112 flips under both.

### 13. BH-B14-NWOG-traverse-large-range
- **rule_id / kind:** B14 / missing_rule. Scope: index. judgment = true.
- **Rule:** If price trades fully through the NWOG during the day, expect a large-range (expansion) day in that direction. Tag 'expansion': allow runners / hold most of the position, and use further targets. Single source (026, ES).
- **Sources:** 026_GFdWahZUNOw ~01:32:09.
- **Quote:** "I told you we would get a big large range day if we got through"
- **Conflicts:** none.
- **[our interpretation]:** "Further targets" = do not cap at the first HTF array; use the next pool beyond.
- **Rulebook fix:** B14: add "A full traverse of the NWOG intraday = expect a large-range day that way; hold runners (026 ~1:32)."
- **BUILD SPEC (management_exits):**
  - In the `run_day` position loop: when the open position's side has traded from one NWOG edge to the other this session, set `pos["expansion"] = True`. Use `_nwogs(ctx, i)` for the current NWOG and bar highs/lows since the session start.
  - With `p.nwog_traverse_hold`, skip the T1 partial (move the whole position to the runner leg) and extend the final target to the next pool beyond (`_targets` next rung). Tag the trade `nwog_traverse`.
  - Params: `nwog_traverse_hold: bool = False`.
  - Test: `test_nwog_traverse_hold`. Long through 4100 -> 4110 (NWOG 4100-4110) during the trade: no T1 partial, and the target moves to the next pool.

### 14. BH-B14-consolidation-week-reversion
- **rule_id / kind:** B14 / missing_rule. Scope: index. judgment = true.
- **Rule:** In the B14 consolidation regime (the current NWOG keeps being revisited, or several NWOGs converge):
  - After a session/daily high or low is run, expect price to be pulled back into the current NWOG.
  - If price trades through the current NWOG, the next target is the nearest old NWOG close by.
  - These are scalp targets only, used in confluence with other draw factors and never alone (051 ~13:00-13:40).
  - Mirror.
- **Sources:** 051_BM1mqQv-ypk ~00:13:12.
- **Quote:** "every decline keeps drawn right back inside of that blue current new week opening Gap"
- **Conflicts:** none.
- **Rulebook fix:** B14: add the reversion targets (current NWOG, then the nearest old NWOG) for the consolidation regime, scalp only, never alone (051 ~13:12).
- **BUILD SPEC (targets_partials):**
  - Depends on B14.1 `nwog_regime` (rule_coverage, bias_htf).
  - In `_targets`: when `p.nwog_revert_targets` and the regime is "consolidation", insert the current NWOG near edge as the first rung. If the entry is already beyond the NWOG, insert the nearest old NWOG from `_nwogs(ctx, i)` instead. Mark the trade `scalp` (single target).
  - A rung only counts if another draw factor sits within `eq_tol_pts`: a pool, an FVG or a wick CE [our interpretation of "never alone"].
  - Params: `nwog_revert_targets: bool = False`.
  - Test: `test_nwog_revert_targets`. In a consolidation regime, a long from 4080 with the NWOG at 4100-4105 and a pool at 4100 gets T = 4100. With no pool there, the NWOG rung is dropped.

### 15. BH-B14-protective-gap-and-low
- **rule_id / kind:** B14 / missing_condition. Scope: general. judgment = true.
- **Rule:**
  - After a sell-side raid below a consolidation, stay bullish and target the current NWOG (any touch is enough; near edge/CE).
  - Turn bearish only if the raid low is taken while the small gap left on the post-raid move is still open/unreclaimed (061 ~2:28:31). Until then, stay bullish.
  - Mirror.
  - Which gap the caption means is ambiguous, so treat this as a judgment item.
- **Sources:** 061_wWvXWmC_gqU ~02:28:31.
- **Quote:** "if this stays open and we take out that low then we're going lower"
- **Conflicts:** none. The claim had the gap condition backwards.
- **Rulebook fix:** B14: "After a sell-side raid under consolidation: bullish toward the current NWOG until the raid low is taken with the post-raid gap still open (061 ~2:28:31)."
- **BUILD SPEC (bias_htf):**
  - In `_lock_step` (draw lock), after a sweep of a session low below a consolidation range (prior-session range), lock side +1 toward the current NWOG near edge (a level from `_nwogs`).
  - Record the first bear FVG formed after the raid low (the "small gap" [our interpretation]). If a later bar trades below the raid low while that FVG is not yet fully traded through, flip the lock to -1 (`lk["side"] = -1`; next pool below). Mirror.
  - Params: `raid_gap_guard: bool = False`.
  - Test: `test_raid_gap_guard`. A raid to 3990 and a bear FVG 4005-4008 left open: trading to 3988 flips to -1. If the FVG is filled first, there is no flip.

### 16. BH-B8-pre-stated-invalidation-price
- **rule_id / kind:** B8 / missing_rule. Scope: general. judgment = true.
- **Rule:**
  - Before the session, write down one invalidation price for the intraday bias, chosen from the HTF/intraday analysis (012 ~27:58; how the level is derived is not specified).
  - If price trades to it (a touch is enough, no close needed), the old-direction narrative is over for the session and the bias flips to the opposite side.
  - This is an exception to B9's 'bias flips use closes'. Mirror.
- **Sources:** 012_HkiPAi1Mdu8 ~00:27:58.
- **Quote:** "that's the end of the line that means it's over"
- **Conflicts:** B9: bias flips use closes.
- **[our interpretation]:** The bot needs a level rule. Default proxy: the far edge of the nearest opposing daily array beyond the session open (test), or a manual per-date input.
- **Rulebook fix:** B9: "Exception: a pre-stated intraday invalidation price flips the session's bias on touch (012 ~27:58)."
- **BUILD SPEC (bias_htf):**
  - In `_lock_step`, at lock, store `lk["inval"]`:
    - `p.inval_src == "array"`: the far edge of the nearest opposing daily array (from the htf row) beyond the lock-time price.
    - `"manual"`: read `data/mentorship/inval_levels.csv` (date, session, price).
  - In the run_day bar loop, the first bar with high >= inval (bearish lock) sets `lk["side"] = +1` for the rest of the session, cancels pending orders of the old side and tags `inval_touch`.
  - Params: `inval_src: str = "off"` ("off" / "array" / "manual").
  - Test: `test_inval_touch_flip`. Bearish lock with inval 4040. A wick to 4040.25 cancels the pending short and sets side +1 without a close above.

### 17. BH-B9-HTF-OB-low-trade-through
- **rule_id / kind:** B9 / unlisted_contradiction. Scope: general. judgment = false.
- **Rule:**
  - While consolidating after an objective is met, the bullish draw on the next buy-side high holds as long as price stays above the low of the last bullish OB candle.
  - Retraces may reach the VI and, at worst, the CE of that candle's lower wick.
  - A trade below the OB candle low (no close needed) drops the bullish draw to neutral, not bearish (062 ~22:39).
  - This is an exception to B9's close rule. Mirror.
- **Sources:** 062_sfRO5LrTgTA ~00:22:39.
- **Quote:** "if it trades below it not doesn't require a close"
- **Conflicts:** B9: bias flips use closes.
- **Rulebook fix:** B9: "Exception (062 ~22:39): after an objective is met, a trade below the last bullish OB candle low drops the bullish draw to neutral (no close needed)." List it in section 3.
- **BUILD SPEC (bias_htf):**
  - New `flip` trigger `ob_low_touch`. While the state is +1 and the B17.3 objective is met (`objective_met` column from rule_coverage B17.3; if that isn't built, any state), a daily low below the low of the last bullish daily OB candle sets the state to 0 (not -1). Mirror.
  - Add to `FLIP_TRIGGERS`.
  - Test: `test_flip_ob_low_touch`. Last bull OB candle low 4000: a daily low at 3999.75 with a close at 4010 sets state 0 from the next session.

### 18. BH-B5-bellwether
- **rule_id / kind:** B5 / unlisted_contradiction. Scope: general. judgment = true.
- **Rule:** Bias comes from the daily, which is the bellwether for directional bias (cc03_001 ~20:13). For intraday work, use a bellwether_tf: either
  - 60m, where the weekly range and intraday highs/lows are defined (cc01_003 ~19:10), or
  - 15m, once the daily draw on liquidity and/or the weekly expansion direction is known (013 ~2:46; 065B).
  
  Then use 5m/1m for execution.
- **Sources:** 013_V1thfpo-R9U ~00:02:46; cc01_003_B7_cjybYQ0g ~00:19:10; cc03_001_UF5J0nEBc0E ~00:20:13.
- **Quotes:** "if I understand where my draw and liquidity is from higher time frame daily ... I can jump right to the 15 minute"; "an hour already charge a really good bellwether chart"
- **Conflicts:** B5 lists 15m only. The three timeframes have different roles more than they contradict.
- **Rulebook fix:** B5: "Bellwether: daily for bias (cc03_001); intraday 60m (cc01_003) or 15m once the daily draw and/or weekly expansion is known (013 ~2:46)."
- **BUILD SPEC (bias_htf):**
  - Already in rule_coverage: B5 `bellwether_15m`. New: the 60m choice and the precondition.
  - Replace it with `bellwether_tf: int = 0` (0 off / 15 / 60). When set, an order needs the last swing break (`levels.pivots` n=1, on `htf_bars(df, tf)` up to i) to be in the trade direction.
  - For 15m, the gate applies only when `want != 0` or the weekly expansion side is known (`weekly_bias` / B13 column). Otherwise fall back to 60m.
  - Test: `test_bellwether_tf`. A long rejected when the last 15m swing break is down. With want = 0 and tf = 15, the 60m structure is used.

### 19. BH-A8-opposing-FVG-inversion-confirms
- **rule_id / kind:** A8 / missing_condition. Scope: general. judgment = false.
- **Rule:** Add to A8 as a narrative gate.
  - While the HTF draw is bullish and unmet, a close above a bearish FVG is not a short. Treat it as a candidate IFVG.
  - Longs are confirmed only when price comes back into it, it holds as support (A8 validity test) and price rallies, followed by a normal entry pattern (e.g. breaker+FVG) toward the draw.
  - If the close-through and the hold do not both happen, there is no trade (015 ~26:19; 061 ~46:50, ~2:33:50).
  - The role switch after the draw is hit stays as in A8 (086). Mirror.
- **Sources:** 015_QKvjPltjsqU ~00:26:19; 061_wWvXWmC_gqU ~00:46:50, ~02:33:50.
- **Quote:** "if a market closes above a fair value Gap that you think should be bearish that's not a good shorting opportunity"
- **Conflicts:** none.
- **Rulebook fix:** A8: add the narrative gate above.
- **BUILD SPEC (setups_models):**
  - Where: `_scan_core`. For a short candidate with `want == +1` (or a lock side of +1, draw not yet hit): reject if the entry FVG was closed through upward earlier this session (`_fvg_state(sd, g, i) == "inverted"`) (`_f("x_inverted_against_draw")`).
  - For longs with `p.ifvg_narrative == "require"`: require that a bear FVG formed after the session start was closed through upward, retested (a later bar's low inside it) and held (no close below its low) before the MSS.
  - Params: `ifvg_narrative: str = "off"` ("off" / "block" / "require").
  - Test: `test_ifvg_narrative`. A bullish draw with a bear FVG 4010-4012 closed through at 4015: a short at 4011 is blocked. A long needs a retest bar with low 4011 and a close above 4012.

### 20. BH-B15-gap-down-ORG-no-shorts
- **rule_id / kind:** B15 / L7, missing_rule. Scope: index. judgment = true.
- **Rule:**
  - If 09:30 opens below the prior RTH close (unfilled ORG), avoid shorts by default.
  - Favour longs from a discount array after the open, targeting the ORG ladder (near edge, CE, prior close); 018 used ~5 handles.
  - Exceptions:
    - A strong HTF bearish narrative with intermarket support (e.g. DXY into a premium array) toward a nearby sell-side objective allows shorts to that objective. An ORG fill is likely after it.
    - B15's 'no attempt within ~30 min' tell also overrides the filter (059 ~14:52; 018 ~3:09).
  - Mirror for gap-ups.
- **Sources:** 059_ZfnY2SH3G24 ~00:14:52; 018_eTMS36H7HA0 ~00:03:09.
- **Quote:** "usually it's a good idea to avoid shorting when there's gap like this"
- **Conflicts:** none.
- **[our interpretation]:** "Strong bearish narrative" = flip state -1 and the INTERMARKET dxy tag +1.
- **Rulebook fix:** B15/L7: add the default "gap down -> avoid shorts, ORG-protocol long" with both exceptions (059 ~14:52; 018 ~3:09).
- **BUILD SPEC (bias_htf):**
  - Where: `run_day` side gate. Use `_org_state` for the ORG and the gap direction at 09:30. With `p.org_gap_filter` on a gap-down day, block shorts unless one of these holds:
    - (a) the flip state is -1 and `ctx.intermarket["dxy"] == +1`;
    - (b) the B15 tell has fired (no trade back to the prior close by 10:00; `_org_break`).
  - Mirror for gap-ups. Longs already target ORG rungs via `org_draw`.
  - Params: `org_gap_filter: bool = False`.
  - Test: `test_org_gap_filter`. A gap down with a neutral state blocks shorts. With state -1 and dxy +1, shorts are allowed. After 10:00 with no attempt, shorts are allowed.

### 21. BH-B15-ORG-tell-details
- **rule_id / kind:** B15 / shortened. Scope: index. judgment = true.
- **Rule:** B15 detail:
  - Ignore the first couple of minutes after 09:30, then judge 09:30-~10:00.
  - The session is bearish if price makes no meaningful attempt back toward the prior close (16:15 ES), then trades through the CE and below the low of the prior day's FVG with speed.
  - Targets: discount arrays on the 15m, then 1h, then daily (030 ~1:29:44-1:31:30).
  - Mirror.
  - The 'meaningful attempt' threshold is a judgment parameter.
- **Sources:** 030_ZdnGlropfmU ~01:29:44.
- **Quote:** "if there is no immediate dire need for it to get back up to it ... we're extremely bearish"
- **Conflicts:** none.
- **[our interpretation]:** "Meaningful attempt" = a retrace of >= `org_attempt_frac` of the gap (test 0.25 / 0.5). "First couple of minutes" = 3 minutes. "With speed" = the displacement test (`displacement_mult`).
- **Rulebook fix:** B15: add "ignore the first couple of minutes; confirmation = through the CE then the low of yesterday's FVG with speed; targets 15m -> 1h -> daily discount (030 ~1:29:44)".
- **BUILD SPEC (bias_htf):**
  - Rule_coverage lists B15 as MISSING with no spec, so this is new.
  - Implement `_org_tell(ctx, p, i)`, evaluated at 10:00 (`org_tell_end`).
  - Bearish when the high from 09:33 to 10:00 retraced < `org_attempt_frac` of the gap (prior 16:15 close - 09:30 open), and a bar has since closed below the CE and then the low of the prior day's last bear-side FVG with a displacement candle. Mirror.
  - Result: `want = -1` for the AM rest, and the target ladder takes 15m, then 60m, then daily discount arrays (`_lv_target_arrays` ordered by TF).
  - Params: `org_tell: bool = False`, `org_attempt_frac: float = 0.25`, `org_tell_skip_min: int = 3`, `org_tell_end: int = 600`.
  - Test: `test_org_tell`. Gap down 10 pts with a max retrace of 2 pts by 10:00 and a displacement close through yesterday's FVG gives want -1. A retrace of 6 pts gives no tell.

### 22. BH-B15-ORG-consolidation-case
- **rule_id / kind:** B15 / missing_condition. Scope: index. judgment = true.
- **Rule:** Third B15 case: if the weekly/HTF objective has already been met or the market is consolidating, expect the ORG to fill and then price to range inside the gap for the rest of the day. Treat the ORG edges (and CE) as the day's range, and trade small and scalp-only, if at all (055 ~18:18).
- **Sources:** 055_qiv8pkcNvGk ~00:18:18.
- **Quote:** "once the Gap fills nothing happens it just uses this entire Gap throughout the day"
- **Conflicts:** none.
- **[our interpretation]:** "Scalp-only".
- **Rulebook fix:** B15: add the third case (055 ~18:18).
- **BUILD SPEC (bias_htf):**
  - In `run_day`, when `p.org_consol_case` and (`objective_met` (B17.3) or `drange == 0` (item 1) or `nwog_regime == "consolidation"`) and the ORG fills (`_org_state` filled) before an entry:
    - set every later order to `scalp`;
    - cap targets at the opposite ORG edge or CE;
    - tag `org_consol`.
  - Params: `org_consol_case: bool = False`.
  - Test: `test_org_consol_case`. With objective_met True and an ORG of 4000-4010 filled at 09:50, a 10:15 long from 4002 gets T = 4010 (or the CE, 4005) and the scalp tag.

### 23. BH-B12-gap-up-short-below-0930
- **rule_id / kind:** B12 / missing_condition. Scope: index. judgment = true.
- **Rule:** Gap up into an HTF premium array (e.g. an old NWOG CE), ideally with index SMT divergence: arm shorts only after price trades below the 09:30 opening price (the ORG high). Take no longs and do not chase above it (044 ~34:06). Targets follow L7's ORG ladder. Mirror for gap-downs into discount.
- **Sources:** 044_LN1nfYp4dBw ~00:34:06.
- **Quote:** "do we get below that I'm not interested in chasing this higher"
- **Conflicts:** none.
- **Rulebook fix:** B12/L7: add "gap up into HTF premium: shorts only after a trade below the 09:30 open; no longs (044 ~34:06)".
- **BUILD SPEC (setups_models):**
  - In `_scan_core`: on a gap-up day (09:30 open > prior close) with the 09:30 price inside or within `eq_tol_pts` of an HTF bear array (`_htf_tag` / conf rows, including old NWOG CE from `_nwog_half`) and `p.gap_premium_arm`:
    - reject longs (`_f("x_gap_premium_long")`);
    - reject shorts until a bar after 09:30 has traded below the 09:30 open (`_open_known(ctx, "0930", i)`).
  - Tag the SMT state of the sweep.
  - Params: `gap_premium_arm: bool = False`.
  - Test: `test_gap_premium_arm`. Gap up to an old NWOG CE at 4100 with a 09:30 open at 4098: a 09:45 short before any trade below 4098 is rejected and accepted after one.

## B. DXY and intermarket

### 24. BH-B19-DXY-soft-filter-for-indices
- **rule_id / kind:** B19 / E9, unlisted_contradiction. Scope: index. judgment = true.
- **Rule:** The B19 DXY filter is soft for index futures and near-absolute for FX.
  - Index trades against the DXY direction are high-resistance. They are allowed only for experienced traders, at reduced size and with short-lived expectations. Beginners stay with the macro read.
  - Brief intraday co-movement of DXY and indices (a crack in the correlation) is normal and is not a signal on its own.
  - Size and targets for counter-DXY index trades are [our interpretation] (063 ~11:40; 028 ~22:50; 046 ~2:13:40; 022 ~1:22:30).
- **Sources:** 063_qA9SCu4gGaU ~00:10:53; 046_VLis0LcbUaQ ~02:13:40; 028_wWvFUW-jY4w ~00:22:53; 022_ALMsQytQ1fg ~01:22:09.
- **Quote:** "index Futures can sometimes fly in the face of what the dollar Index is doing"
- **Conflicts:** B19 is absolute; E9 says size down.
- **Rulebook fix:** B19: "Soft for index futures (063 ~11:40): counter-DXY index trades are high resistance: experienced only, reduced size. Near-absolute for FX." Note brief co-movement is normal (028 ~22:50).
- **BUILD SPEC (bias_htf):**
  - Already in rule_coverage: B19.1 `dxy_gate` (block longs). New: the soft mode.
  - Add `dxy_filter: str = "off"` ("off" / "tag" / "soft" / "hard"), using daily `ctx.intermarket["dxy"]` (prior day, so no look-ahead).
  - "hard" blocks longs when dxy +1 and shorts when dxy -1.
  - "soft" lets counter-DXY orders through with `risk_mult *= dxy_soft_risk`, marks them `scalp` (single target, no adds) and tags `counter_dxy`.
  - Params: `dxy_filter: str = "off"`, `dxy_soft_risk: float = 0.5` [our interpretation].
  - Test: `test_dxy_filter_modes`. With dxy +1, a long is blocked under "hard". Under "soft" it trades at half risk with one target and the counter_dxy tag.

### 25. BH-B19-DXY-three-states
- **rule_id / kind:** B19 / shortened. Scope: needs_unavailable_data (intraday DXY). judgment = true.
- **Rule:** DXY state for ES longs:
  - Falling = risk-on: full participation allowed.
  - Consolidating or mixed: longs are still permitted, but only as small intraday scalps.
  - Rallying: no ES longs. Mirror for shorts (048 ~24:30; 022 ~4:25).
  - The pre-session scoring is not sourced and should be dropped.
- **Sources:** 048_gGxVE8zUIRQ ~00:23:44; 022_ALMsQytQ1fg ~00:04:25.
- **Quote:** "it can consolidate but it just can't rally"
- **Conflicts:** none.
- **Rulebook fix:** B19: add the three states (048 ~24:30; 022 ~4:25). No build spec: it needs intraday DXY.

### 26. BH-B19-DXY-pool-run-must-expand
- **rule_id / kind:** B19 / missing_condition. Scope: needs_unavailable_data. judgment = false.
- **Rule:** For an ES long held to its draw, DXY should trade through its nearest 5m sell-side, keep expanding and show no interest in going back above it. Then the ES draw (e.g. the NWOG) can be trusted. If DXY only pierces the level by a tick or so and rejects, ES upside continuation is suspect: do not hold to the full draw. Mirror for shorts (036 ~59:30; 045 ~14:00, ~22:00).
- **Sources:** 036_n37ozsUreR0 ~00:59:42; 045_DNi9S3_NA44 ~00:13:01, ~00:22:01.
- **Quote:** "if it's just like goes below it and then rejects that's going to be problematic"
- **Conflicts:** none.
- **Rulebook fix:** B19: add the positive confirmation as written. No build spec (5m DXY).

### 27. BH-B19-DXY-SMT
- **rule_id / kind:** B18 / B19, missing_rule. Scope: needs_unavailable_data. judgment = false.
- **Rule:** Add DXY (inverse) SMT.
  - Index lower low (all three agreeing) with no DXY higher high in the same window = possible false break. Don't press shorts; the likely draw is the nearest buy-side.
  - Index higher high into a premium PD array with no DXY lower low = bearish; target sell-side.
  - Qualifier only, at a PD array; never a signal on its own.
  - FX analog: EURUSD vs DXY (031 ~49:30, ~58:30; 032 ~34:21; 035 ~1:07; 103 ~8:24; cc03_005 ~5:19).
- **Sources:** 031_8YSVu51hUWQ ~00:48:51, ~00:58:28; 032_SSWN6YSVyFY ~00:34:21; 035_kFIOp8Tprdc ~01:06:35; 103_IU673ZUGuxI ~00:08:24; cc03_005_GuycI8XubgE ~00:05:19.
- **Quote:** "the dollar Index did not make a higher high I want to see that but because it hasn't done that that makes this potentially a false Breakout"
- **Conflicts:** B18 limits SMT to ES/NQ/YM.
- **Rulebook fix:** B18: add DXY inverse SMT as a qualifier at a PD array; B19: give the consequence of the divergence. No build spec (intraday DXY).

### 28. BH-B19-DXY-turtle-soup-raid
- **rule_id / kind:** B19 / missing_rule. Scope: needs_unavailable_data. judgment = true.
- **Rule:** When ES takes buy-side while DXY pierces an old daily low and rejects back above it (DXY turtle soup), treat ES's buy-side run as a raid and lean bearish. Mirror: ES takes sell-side while DXY false-breaks an old high = ES bullish. Single example (030 ~39:00, ~1:37:28).
- **Sources:** 030_ZdnGlropfmU ~01:37:28.
- **Quote:** "it was a turtle soup scenario going down there and rejecting it"
- **Conflicts:** none.
- **Rulebook fix:** B19: add as a single-example trigger. No build spec.

### 29. BH-B19-DXY-session-gate-levels
- **rule_id / kind:** B19 / missing_condition. Scope: needs_unavailable_data. judgment = true.
- **Rule:** Pre-session: mark the DXY key support and the nearest 15m BISI beneath it (031 used the 07:45 FVG). While DXY holds above them, the ES bias stays bearish (look for lower prices). DXY back below them cancels the bearish bias. ES is decisively bullish only after DXY breaks decisively down through them. Mirror (031 ~9:00, ~11:30, ~16:00).
- **Sources:** 031_8YSVu51hUWQ ~00:07:54, ~00:15:17.
- **Quote:** "it would have to stay above that fair value gap on the 745 candle"
- **Conflicts:** none.
- **Rulebook fix:** B19: add as written. No build spec.

### 30. BH-B19-DXY-5m-EQ-threshold
- **rule_id / kind:** B19 / wrong. Scope: needs_unavailable_data. judgment = true.
- **Rule:** B19 (045 ~42:00): the DXY threshold is the EQ of its intraday 5m dealing range, not the range high. DXY above that EQ = ES upside continuation is problematic: no new longs. An ES short comes only after ES displaces lower with an FVG, targeting the opening-range-gap / 09:30 open. Otherwise stand aside.
- **Sources:** 045_DNi9S3_NA44 ~00:42:00.
- **Quote:** "that range split that in half the equilibrium of that range"
- **Conflicts:** B19's current text says the range high (045 ~42:05).
- **Rulebook fix:** B19: replace "rallies above its dealing-range high" with "trades above the EQ of its 5m dealing range" and fix the 045 ~42:05 citation. No build spec.

### 31. BH-B19-DXY-0915-range-trigger
- **rule_id / kind:** B19 / missing_condition. Scope: needs_unavailable_data. judgment = true.
- **Rule:** For an AM ES short, use DXY as a confirmation filter. DXY should hold its post-09:30 1m FVG and trade above its 09:15-09:30 range high at or before entry. Until then, don't short prematurely. DXY failing below its FVG = no short. Mirror for longs (042 ~19:00, ~23:30, ~41:41, ~1:01:05).
- **Sources:** 042_hQ379EuyNKQ ~01:01:05, ~00:41:41.
- **Quote:** "because I was using the dollar Index to filter it kept me from doing what getting in prematurely"
- **Conflicts:** none.
- **Rulebook fix:** B19: add as written. No build spec.

### 32. BH-B19-DXY-daily-MT-regime
- **rule_id / kind:** B19 / missing_rule. Scope: needs_unavailable_data. judgment = true.
- **Rule:** When DXY is trading into an old daily candle (a premium array), that candle's MT is a regime switch. DXY through and above the MT = expect fast ES expansion lower. DXY below the MT = choppy ES and FX: scalp surgically or skip. Mirror. Single example (031 ~11:30-12:30).
- **Sources:** 031_8YSVu51hUWQ ~00:11:30.
- **Quote:** "as long as we are below that mean threshold it's going to bang around and chop"
- **Conflicts:** none.
- **Rulebook fix:** B19: add as a single-example regime note. No build spec. The scope was set to needs data; a daily-DXY version could later reuse the item 24 loader.

### 33. BH-B19-DXY-in-trade-management
- **rule_id / kind:** B19 / missing_condition. Scope: needs_unavailable_data. judgment = true.
- **Rule:** While short an index, monitor DXY on the 5m, confirmed on the 15m and 60m. If DXY fails to exceed its prior high while ES pushes lower, near-term continuation is suspect (consolidation or short-term reversal risk). Take more of the position off, especially when a sister index also diverges (037 ~32:37-33:30). The mirror for longs is inferred only.
- **Sources:** 037_wu0sQarBRrI ~00:32:37.
- **Quote:** "so far it hasn't made a higher high ... which is problematic"
- **Conflicts:** none.
- **Rulebook fix:** B19 / X: add the in-trade DXY check (037 ~32:37). No build spec.

### 34. BH-B19-DXY-falling-risk-on
- **rule_id / kind:** B19 / shortened. Scope: index. judgment = false.
- **Rule:**
  - DXY falling = risk-on: index and FX rallies can be trusted, and index shorts are disfavoured (low payoff).
  - DXY rising (weekly-bullish) = index rallies are suspect: expect them only to reprice into an FVG/inefficiency or run a short-term high, then reject.
  - Read DXY together with gold (gold qualifies DXY).
  - Never trade DXY itself; it is a barometer.
- **Sources:** 032_SSWN6YSVyFY ~00:32:11; 095_LPmMtq9jLm8 ~00:18:57; 102_uzPM1CuSSx8 ~00:31:27.
- **Quote:** "dollar up everything else bends the knee lower dollar down it allows what risk on"
- **Conflicts:** cc03_006 (Nov 2016): DXY and equities rallied together.
- **Rulebook fix:** B19: add the risk-on side and "under a rising DXY, index rallies only reprice an inefficiency or run a short-term high" (102 ~31:27). Add the gold qualifier.
- **BUILD SPEC (targets_partials):**
  - With `p.dxy_rally_cap` and daily `ctx.intermarket["dxy"] == +1`, long targets are capped at the first rung that is an FVG/inefficiency or a short-term high (the first `_targets` rung of kind array/pool); no runner.
  - With dxy -1, shorts get the same cap (low payoff), and longs keep the normal ladder.
  - Gold is not loaded. Leave a hook `ctx.intermarket.get("gold")` that is unused until data is added.
  - Params: `dxy_rally_cap: bool = False`.
  - Test: `test_dxy_rally_cap`. With dxy +1, a long's ladder is truncated to one rung. With dxy -1, the long keeps the full ladder.

### 35. BH-B17-symmetrical-market-gate
- **rule_id / kind:** B17 / B19 / L4, missing_rule. Scope: needs_unavailable_data. judgment = true.
- **Rule:**
  - Symmetrical market = ES, NQ and YM all confirm each swing extreme in the same direction while DXY moves opposite.
  - FX pairs and gold should move with the indices and against DXY. Gold qualifies DXY: when gold and DXY move in tandem, that is a decoupling.
  - Symmetrical -> low-resistance runs: hold for the draw.
  - Not symmetrical -> high-resistance conditions: scalp only with small targets, or stand aside (new traders stand aside).
- **Sources:** 031 ~00:50:02; 045 ~02:50:01; 046 ~01:23:17; 048 ~00:13:02, ~00:41:01; 093 ~00:05:24; 095 ~00:27:01; 098 ~00:55:06; 102 ~00:31:27.
- **Quotes:** "they all have to agree they have to be in in alignment that's ... a market that's symmetrical"; "when they move in tandem you're in a very very risky scenario that's a decoupling"
- **Conflicts:** L4 uses a swing-overlap definition. 093 says asymmetric is still tradable, while 095/098 say scalp or nothing.
- **Rulebook fix:** B17.5: add the operational symmetry test (three indices confirm + DXY opposite; gold vs DXY tandem = decoupling) and its consequence. No build spec (YM / intraday DXY / gold).

### 36. BH-symmetry-crack
- **rule_id / kind:** B18 / missing_rule. Scope: needs_unavailable_data. judgment = true.
- **Rule:** At each index swing extreme, check that NQ/YM make the same extreme and DXY makes the opposite one.
  - All confirm -> the trend is intact. Avoid counter-trend reversal setups, and treat a run beyond the short-term swing against the trend as a stop raid before continuation.
  - Any one fails (a crack) -> a sentiment shift is unfolding: treat continuation as suspect (consolidation or reversal).
- **Sources:** 032_SSWN6YSVyFY ~00:34:51; cc03_005_GuycI8XubgE ~00:02:53.
- **Quote:** "the idea of stalking reversal patterns in this condition is not highly probable in fact you want to avoid it all together"
- **Conflicts:** none.
- **Rulebook fix:** B18: add both consequences (032 ~34:51; cc03_005 ~2:53, stated for DXY vs FX). No build spec.

### 37. BH-B19-bonds-range-regime
- **rule_id / kind:** B19 / missing_condition. Scope: needs_unavailable_data. judgment = true.
- **Rule:** Add to B19:
  - Compare 5y/10y/30y yields for confirmation of an ES/FX price run. When they don't confirm, expect delay or chop (e.g. until the 09:30 open).
  - When the bond market leaves its range, expect a trending environment across asset classes, more protracted the longer the consolidation lasted.
  - While it is ranging, keep expectations low and take small gains.
- **Sources:** 030_ZdnGlropfmU ~00:51:39; 061_wWvXWmC_gqU ~01:15:21; cc10_008_RgpxhuVp5Xg ~00:25:22.
- **Quotes:** "until the bonds leave that range all markets will be in consolidation"; "the longer the consolidation... when it leaves the range it will have a protractionary state"
- **Conflicts:** B19 says bonds and stocks move together.
- **Rulebook fix:** B19: add the yield-triad confirmation (030 ~52:00) and the breakout duration scaling (cc10_008 ~25:22). The "bonds range -> consolidate" part is already there. No build spec. The B19.3 `bond_range` switch in rule_coverage covers the existing part.

### 38. BH-B19-correlated-target-ends-day
- **rule_id / kind:** B19 / X12, missing_rule. Scope: needs_unavailable_data. judgment = false.
- **Rule:** When ES trades into its target liquidity pool at the same time DXY reaches its HTF target array, the day's move is complete. Take no new trades in that direction and expect consolidation until ~15:00, after which a last-hour retracement may occur (059 ~23:01).
- **Sources:** 059_ZfnY2SH3G24 ~00:23:01.
- **Quote:** "marks the end of the day. We're done."
- **Conflicts:** none.
- **Rulebook fix:** X12: add the cross-market end-of-day signal. No build spec.

### 39. BH-FX-intermarket-pairs
- **rule_id / kind:** new / missing_rule. Scope: fx_only. judgment = false.
- **Rule:** [fx-only] An xxxUSD trade needs DXY showing the opposing setup at a PD array at the same time. DXY falling -> prefer the stronger of EURUSD/GBPUSD (usually cable). DXY consolidating while GBPUSD is running -> consider the cross (GBPJPY long).
- **Sources:** 061_wWvXWmC_gqU ~01:32:41; 067_vuBRMFhFZAY ~01:34:31.
- **Quote:** "if we're trying to go short on Euro you want to see something that would constitute a long in dollar"
- **Conflicts:** none.
- **Rulebook fix:** Add to the [fx-only] notes (M17). No build spec.

## C. Structure tells, draws and index choice

### 40. BH-failed-sweeps-low-in
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** After the AM sell-side target is taken, if later price repeatedly runs short-term buy-side highs while making few or only marginal new lows, the morning low is likely in: target the buy-side above (022 ~2:01:51; observed 4 highs vs 2 lows). Thresholds unspecified. Mirror.
- **Sources:** 022_ALMsQytQ1fg ~02:01:51.
- **Quote:** "looks like we probably rounded out the morning low"
- **Conflicts:** none.
- **[our interpretation]:** The count threshold. Highs taken >= `low_in_ratio` x lows taken, with at least `low_in_min_highs` highs.
- **Rulebook fix:** New rule under B9/T: "After the AM sell-side target, repeated short-term highs taken vs few new lows = morning low in; target buy-side (022 ~2:01:51)."
- **BUILD SPEC (bias_htf):**
  - In `_lock_step`, after the session's locked sell-side draw is hit (session done under owner #9), keep counting 1m short-term pivot highs taken (`levels.pivots` n=1, broken by a later high) and new session lows.
  - When highs >= `low_in_min_highs` and highs >= `low_in_ratio` x lows, re-lock the session to side +1 toward the nearest buy-side pool and tag `low_in`. This lets a second trade happen after the draw.
  - Params: `low_in_relock: bool = False`, `low_in_min_highs: int = 3`, `low_in_ratio: float = 2.0`.
  - Test: `test_low_in_relock`. After the AM low target at 4113, 4 pivot highs taken and 2 marginal lows give a +1 re-lock toward 4121.

### 41. BH-B17-REL-REH-both-intact
- **rule_id / kind:** B17 / missing_condition. Scope: general. judgment = true.
- **Rule:** Neutral (no trade) while both the nearest REL below and the buy-side above remain untaken with price inside an HTF (daily) FVG range. A sweep of the REL followed by delivery the other way establishes the bias (025 ~10:58-12:00). Mirror.
- **Sources:** 025_7RiUUCqQ3SY ~00:10:58.
- **Quote:** "we have left relative equal lows"
- **Conflicts:** none.
- **Rulebook fix:** B17.1: make the 50/50 test concrete as above (025 ~10:58).
- **BUILD SPEC (bias_htf):**
  - Rule_coverage B17 lists `neutral_gate` "fifty_fifty". This gives it its test.
  - In `_lock_step` at lock time, fifty_fifty = True when all of these hold: price is inside a daily FVG (`_htf_tag` / conf rows); the nearest REL below (`_eq_levels(..., lows=True)`) is untaken; the nearest buy-side pool above is untaken.
  - When True: lock side 0 (neutral -> `draw_lock_neutral` handles it).
  - When a later bar sweeps the REL and an MSS up follows: re-lock +1. Mirror.
  - Params: add "fifty_fifty" to `neutral_gate` (tuple, default ()).
  - Test: `test_neutral_fifty_fifty`. Price at 4020 inside a daily FVG 4010-4030, REL at 4005, PDH at 4040: lock side 0. Sweep 4004 + MSS: side +1.

### 42. BH-compressed-higher-highs
- **rule_id / kind:** new / missing_rule. Scope: index. judgment = true.
- **Rule:** A B-tell (judgment, one source: 028 ~1:24-1:26). After a drop, a series of marginal higher highs that stays compressed (small extensions, overlapping back-and-forth) back into equilibrium/premium is buy-side engineering, not bullish structure. Do not count it as a bullish shift, and lean bearish once it fails. Mirror.
- **Coded proxy (our interpretation):** >= 3 consecutive highs, each exceeding the prior by < k x ADR5, inside the upper half of the dealing range, then an MSS lower.
- **Sources:** 028_wWvFUW-jY4w ~01:26:02, ~01:12:40, ~01:24:53.
- **Quote:** "it's just constantly reaching for liquidity"
- **Conflicts:** M-model "three drives into failing liquidity" (line 642) is the nearest existing match.
- **Rulebook fix:** Add a B-tell: compressed marginal higher highs into premium = buy-side engineering (028 ~1:26).
- **BUILD SPEC (setups_models):**
  - Add detector `levels.compressed_highs(h, pivots, adr, k, n)` -> index of the last high of a run of `n` consecutive pivot highs, each exceeding the previous by < k x ADR5 (`strategy.adr5`), with all of them above the dealing-range EQ.
  - In `_scan_core`, with `p.compressed_hh`:
    - a long whose MSS reference is one of those highs is rejected (`_f("x_compressed_hh")`);
    - a short after an MSS below the run is tagged `compressed_hh` and its first target is the leg low.
  - Params: `compressed_hh: bool = False`, `compressed_k: float = 0.1`, `compressed_n: int = 3`.
  - Test: `test_compressed_highs`. Synthetic highs 4010, 4011, 4012.5 with ADR5 = 40 are detected. Highs 4010, 4020, 4035 are not.

### 43. BH-B6-intraday-iof
- **rule_id / kind:** B6 / shortened. Scope: general. judgment = false.
- **Rule:** B6b intraday IOF (1h/15m/5m/1m), OHLC only.
  - Bearish while up-close candles hold as resistance, down-close candles are closed through, and retraces into a SIBI stop at its low or at most its CE and then leave quickly.
  - It ends when price trades and holds above the last up-close candle (099 ~15:03).
  - Use it as a filter against counter-trend entries. In a trade, the existing X8/X9 rules already apply.
  - The linger/close thresholds are our parameters. Mirror.
- **Sources:** 028 ~00:21:27; 085 ~00:10:28; 099 ~00:15:03, ~00:50:15.
- **Quote:** "every single time you see an up close candle think of it as a resistance level"
- **Conflicts:** none.
- **Rulebook fix:** B6: add B6b as above.
- **BUILD SPEC (bias_htf):**
  - Rule_coverage B6 adds a daily `iof` column. This adds the intraday version.
  - Add helper `iof_state(o, h, l, c, end)` on any timeframe's bars:
    - -1 while the last up-close candle's high has not been traded above and held (held = a later close above it), and the last down-close candle's low was closed through.
    - +1 mirror.
    - 0 otherwise.
  - Use it in `_scan_core` with `p.iof_tf` (0 = off; e.g. 15 or 60): reject orders against `iof_state(htf_bars(df, iof_tf))` at i (`_f("x_iof_against")`).
  - Params: `iof_tf: int = 0`.
  - Test: `test_iof_state_intraday`. A 15m sequence of a down-close candle closed through and an up-close candle high unbroken gives -1, and a long is rejected. A close above that high gives 0 / +1.

### 44. BH-B3-counter-bias-modes
- **rule_id / kind:** B3 / unlisted_contradiction. Scope: general. judgment = true.
- **Rule:**
  - Default (learner / bot): one direction toward the weekly/daily draw (019; 067; 098 ~3:46). Drop the 054 cite, or cite 054 ~7:45-9:52 for 'next draw first, not necessarily the bias'.
  - Switch allow_counter_trend (experienced; 095 ~11:56; 030 ~25:11): per window, trade toward the nearest untaken draw.
  - After buy side is taken plus a bearish MSS, a short against the bias may target the nearest sell-side pool / SD projection / old FVG.
  - Management for these trades is our choice (unsourced).
- **Sources:** 030 ~00:25:11; 054 ~00:09:52; 095 ~00:11:56; 098 ~00:03:46. 101 does not support the claim.
- **Quotes:** "you don't need a bias it just means that while you're learning"; "you can be buying and selling in the same day"
- **Conflicts:** B3: one direction per day (miscites 054).
- **Rulebook fix:** B3: "one direction is the learner's default (095 ~11:56)". Fix the 054 citation. Add a Decision: allow_counter_trend.
- **BUILD SPEC (bias_htf):**
  - Where: the `run_day` side gate (`want`) and the draw lock. With `p.allow_counter_trend`, after the session's buy-side draw (lock target) has been taken, allow a short whose MSS formed after that raid even when `want == +1`.
  - Targets = the nearest sell-side pool only (single target, scalp, no adds) [our interpretation]. Tag `counter_trend`. Mirror.
  - Params: `allow_counter_trend: bool = False`.
  - Test: `test_allow_counter_trend`. With want +1, a short after a PDH raid and a bearish MSS is rejected by default. With the switch on, it trades with one target and the counter_trend tag.

### 45. BH-B2-draw-by-proximity
- **rule_id / kind:** B2 / unlisted_contradiction. Scope: index. judgment = true.
- **Rule:**
  - B2 option draw_order in {inefficiency_first (065A ~50:00), nearest (067 ~1:30:55; cc02_008 ~13:11; 054 ~6:38)}.
  - Nearest = the closest untaken FVG/pool/NWOG. Tie-break = the most recent with the least resistance in the path; our proxy is the fewest opposing arrays in between.
  - Skip a pool already raided this session (054 ~6:38).
  - List as a section-3 decision.
- **Sources:** 054_tRq1hyGGtl4 ~00:06:38; 067_vuBRMFhFZAY ~01:30:55; cc02_008_pv2-R-STviA ~00:13:11.
- **Quote:** "which is the most easiest closest proximity PD array it's probably going to go to that one"
- **Conflicts:** B2 (065A): inefficiency first. Partly covered by A22 and P3 #20.
- **Rulebook fix:** B2: add `draw_order` as a Decision with both options and citations.
- **BUILD SPEC (bias_htf):**
  - Rule_coverage B2 adds `draw_ord` (inefficiency first) and `htf_bias='ordered'`. New: the alternative order and the tie-break.
  - In `htf.table`, add `draw_order: str = "nearest"` (current behaviour) / "inefficiency_first". For "nearest" ties (within `eq_tol_pts`), prefer the candidate with fewer opposing arrays between price and it, then the later `known`.
  - In `_lock_step`, drop pools whose `seen` shows them raided earlier this session (the existing `spent` list).
  - Expose `Params.draw_order`, passed to `htf.table`.
  - Test: `test_draw_order_nearest_tiebreak`. Two draws at 4050 and 4050.25: the one with no bear FVG in between wins. A pool raided at 09:40 is skipped at the PM lock.

### 46. BH-B2-wick-CE-draw
- **rule_id / kind:** B2 / shortened. Scope: general. judgment = false.
- **Rule:** B2: if there is no HTF inefficiency in the bias direction, the draw is the nearest opposing wick: its CE (wick midpoint), or its extreme / the old low beyond it (065A ~39:00). Treat the CE as the first objective and the extreme as the full one. Mirror.
- **Sources:** 065_rx15_eN9sxI ~00:39:00.
- **Quote:** "consequent encouragement which is the midpoint of this candle's tail"
- **Conflicts:** none.
- **Rulebook fix:** B2: insert the wick CE between the inefficiency and the old extreme (065A ~39:00).
- **BUILD SPEC (bias_htf):**
  - In `htf.table`'s draw search: when no daily/weekly FVG/VI exists in the bias direction within `lookback`, set `draw_lvl` = the CE of the nearest weekly (else daily) lower wick below (`(min(o,c) + l) / 2`) and `draw_ext_lvl` = that wick's low. Mirror.
  - Switch `wick_ce_draw` passed from Params. The targets ladder already accepts `draw_ext_target`.
  - Params: `wick_ce_draw: bool = False`.
  - Test: `test_wick_ce_draw`. Bearish with no gaps below and a weekly wick 3950-3970 (body low 3970): draw 3960, ext 3950.

### 47. BH-B2-two-HTF-FVGs-farther
- **rule_id / kind:** B2 / missing_rule. Scope: index. judgment = true.
- **Rule:** B2 (judgment, 069 ~1:59): with two daily FVGs stacked in the bias direction, the expected draw is the farther one (both get filled). The level within it follows L9 (near edge, then CE). Using the nearer gap as a partial is our extrapolation.
- **Sources:** 069_Sf_uYZBWTrA ~00:01:59.
- **Quote:** "because there's two fair value gaps on ES I prefer the lower"
- **Conflicts:** L9: the CE is enough; the far edge is a "ringer".
- **Rulebook fix:** B2: add the stacked-gap preference (069 ~1:59).
- **BUILD SPEC (bias_htf):**
  - In `htf.table`, when `stack_far` is set and two daily FVGs of the bias side lie beyond price with no other draw between them, set `draw_lvl` to the farther gap's near edge (L9), and put the nearer gap's near edge in `draw_mid_lvl`.
  - `_targets` uses `draw_mid_lvl` as a partial rung [our interpretation].
  - Params: `stack_far: bool = False`.
  - Test: `test_stack_far_draw`. Bear FVGs at 4420-4430 and 4370-4380 below price 4450: draw 4380, mid 4430.

### 48. BH-D15-sick-sister-laggard
- **rule_id / kind:** D15 / unlisted_contradiction. Scope: index. judgment = true.
- **Rule:** D15: once the leader has met its HTF objective and the laggard has not, route with-bias setups to the laggard (after its own MSS + PD array) toward its own unmet analogous target (056 ~9:10; 070 ~18:41; 099 ~26:53; 063 ~20:57; 090 ~2:07:49). This is not limited to consolidation. 053's consolidation statement is a conflicting source. Move 090 from option A to B. Test smt_pick=laggard with and without the consolidation filter.
- **Sources:** 056_NeZlyG8FZLQ ~00:09:10; 070_1HtRfFYiwO0 ~00:18:41; 063_qA9SCu4gGaU ~00:20:57; 090_bhYcXBI3z9U ~02:07:49; 091_1PkTGkOjoGo ~00:28:45; 099_v_iJlBKYmUc ~00:26:53.
- **Quote:** "even if you missed the best mover which is NASDAQ ... that's fine you can go to the sick sister"
- **Conflicts:** D15/M16 (053 ~8:20): consolidation only. 090 is listed under option A.
- **Rulebook fix:** D15: add the trend-context laggard rule, move 090 to B, and list the 053 conflict.
- **BUILD SPEC (setups_models):**
  - Where: `backtest.combine` (pick) and `run_day` per instrument.
  - Add `smt_pick="laggard_objective"`. For each instrument, compute `objective_met` from its own `htf.table` draw (draw level traded since the draw formed). On a day when one instrument's draw is met and the other's is not, keep only the unmet instrument's with-bias fills.
  - Add `laggard_consol_only: bool = False`. When True, use this only on `nwog_regime == "consolidation"` / `drange == 0` days (the current D15 recommendation).
  - Params: extend `smt_pick` values; add `laggard_consol_only`.
  - Test: `test_smt_pick_laggard_objective`. NQ draw met and ES draw unmet: combine keeps ES fills only. With `laggard_consol_only` on a non-consolidation day, it reverts to "first".

### 49. BH-D15-middle-index
- **rule_id / kind:** D15 / shortened. Scope: index. judgment = true.
- **Rule:** D15 option C (judgment, 048 ~2:16:00): when the leader has largely completed its run, trade the index that lagged the leader but is not the weakest (the middle of three). Avoid the weakest, since it may stay weak all session. Coded proxy: rank ES/NQ/YM by % move toward the draw and take the middle (smt_pick=middle; needs YM data).
- **Sources:** 048_gGxVE8zUIRQ ~02:16:00.
- **Quote:** "I don't want to buy the weakest one"
- **Conflicts:** D15 A vs B.
- **Rulebook fix:** D15: add option C.
- **BUILD SPEC (setups_models):**
  - In `backtest.combine`, `pick="middle"`: needs three runs. Rank the instruments by % move from the session open to the fill bar, in the trade direction, and keep only the middle one's fills. With fewer than three runs, raise ValueError (inert until a DJI/YM series is loaded; `partner2` in `backtest` already allows a third frame).
  - Params: `smt_pick` adds "middle".
  - Test: `test_smt_pick_middle`. Three synthetic runs with moves +1.2%, +0.8%, +0.3% keep the +0.8% one. Two runs raise.

### 50. BH-D15-clean-swing-point
- **rule_id / kind:** D15 / missing_condition. Scope: index. judgment = true.
- **Rule:** D15 tie-breaker (judgment, 072 ~34:33): between correlated indices, prefer the one whose chart shows a clear swing point to break or target for the intended move. Skip the index with no clean swing.
- **Sources:** 072_AKg_r0DIa3k ~00:34:33.
- **Quote:** "the s p doesn't really have a clear swing low"
- **Conflicts:** none.
- **[our interpretation]:** "Clear swing" = a 15m pivot (n = 2) between the entry and the target.
- **Rulebook fix:** D15: add the tie-breaker.
- **BUILD SPEC (setups_models):**
  - At fill, tag `Trade.clean_swing` = a 15m pivot (n = 2, from `htf_bars(df, 15)`) in the target direction between the entry and T1.
  - In `backtest.combine`, `pick="clean_swing"` keeps, of same-session fills, the one with `clean_swing` True (ties -> "first").
  - Test: `test_pick_clean_swing`. Two fills, one with a 15m pivot low between the entry and T1: that one is kept.

### 51. D15-short-index-by-premium-depth
- **rule_id / kind:** D15 / unlisted_contradiction. Scope: index. judgment = true.
- **Rule:** Shorts: when the indices diverge, short the one that has gone deeper into its own HTF premium array (penetration = (high - array low) / array range) and whose bodies respect the array edges and CE cleanly, with organized structure. Ignore which index printed the SMT extreme. Longs mirror this with discount depth. Optional and observational only (100): the strongest index of the prior up-leg often lags on the way down, so use it at most as a soft tie-break, not a ban.
- **Sources:** 086_bDOyDitJZi4 ~00:09:49; 100_GJeEU2oIh24 ~00:25:56.
- **Quote:** "I want to be in the one that has the higher premium"
- **Conflicts:** D15 cites 086 for option A ("weaker / non-extreme").
- **Rulebook fix:** D15: move 086 out of option A and add option "depth" with the formula.
- **BUILD SPEC (setups_models):**
  - At fill, compute `Trade.array_depth` for the HTF array tagged by `_htf_tag` (shorts: (sweep high - array low) / (array high - array low); longs mirrored). Compute `Trade.array_respect` = the share of 15m bodies inside the array that stayed below its high (shorts).
  - In `backtest.combine`, `pick="depth"` keeps the fill with the larger depth; ties are broken by respect, then the earlier fill.
  - Params: `smt_pick` adds "depth".
  - Test: `test_pick_depth`. NQ at 95% into its SIBI and ES at 50% (CE): the NQ short is kept even though ES made the SMT lower low.

### 52. NEW-fx-pair-selection-pd-respect
- **rule_id / kind:** new / missing_rule. Scope: fx_only. judgment = true.
- **Rule:** [fx-only] Between closely correlated pairs read the same way, trade the one that has gone deeper into its HTF PD array and whose bodies respect the array edges and CE most cleanly. This is the same criterion as the index choice in D15.
- **Sources:** 086_bDOyDitJZi4 ~00:09:20.
- **Quote:** "I'm looking for the ones that are showing the respect of the signatures"
- **Conflicts:** none.
- **Rulebook fix:** [fx-only] note under D15. No build spec.

### 53. BH-M16-reference-highs-0800
- **rule_id / kind:** M16 / missing_condition. Scope: needs_unavailable_data. judgment = true.
- **Rule:**
  - Sick sister applies only on expected consolidation days (no medium or high impact news, converging NWOGs).
  - At 08:00, for each index (ES/NQ/YM), count which of two reference highs it has exceeded: the prior session's afternoon high (~14:30) and the most recent overnight swing high. The index with the lowest count is the sick sister.
  - Wait for it to drop into a deep discount (below the equilibrium of its swing, OTE 62-79%, OB/FVG), buy there, and target the untaken highs.
  - Lows mirror this. Needs DJI and ES 1m data.
- **Sources:** 053_VSSwM6rDIg0 ~00:03:47.
- **Quote:** "so you have the high broken here at 8 am"
- **Conflicts:** none.
- **Rulebook fix:** M16: add the reference highs, the 08:00 count and the consolidation condition. No build spec (YM 1m).

### 54. BH-M3-scan-all-indices
- **rule_id / kind:** M3 / unlisted_contradiction. Scope: index. judgment = true.
- **Rule:** Conflict to test. 054 says to specialize in one market (an SB forms daily in every market), while 067 says the model may form in only one index, so watch all three (SPX/NDX/DJI). Test option: scan SPX/NDX(/DJI) and take the first index that qualifies [our interpretation], vs a single index.
- **Sources:** 067_vuBRMFhFZAY ~01:33:29.
- **Quote:** "it might only be in one and that's why I teach you to look at all three"
- **Conflicts:** M3 (054 ~18:18; 046): don't switch markets.
- **Rulebook fix:** M3: list the conflict as a Decision.
- **BUILD SPEC (setups_models):**
  - `backtest.combine(pick="first")` already takes the first fill across the runs passed in. Add `Params.markets: tuple = ("ES",)` and run one market vs ("ES", "NQ") through the same combine. Report the setup count per day and the share of days with a setup in only one market.
  - No engine change. This goes in `report_decisions.py` as decision "M3_scan".
  - Test: `test_m3_scan_report`. Two synthetic runs with setups on disjoint days: the combined run has the union of the days, and the report counts the one-market-only days.

### 55. BH-N10-thursday-not-top-call
- **rule_id / kind:** N10 / missing_condition. Scope: index. judgment = true.
- **Rule:** Thursday after a one-sided, algorithmically delivered week: the 'opposite end of the week' idea is an expectation, not a top call. A counter-trend entry needs a stricter-than-normal reversal: a buy-side sweep at an HTF premium array, then a clear MSS with displacement and an FVG, preferably in the 10:00 hour. Otherwise take no counter-trend trade (mirror for down weeks). The exact pattern is our interpretation.
- **Sources:** 044_LN1nfYp4dBw ~00:16:07, ~01:21:30.
- **Quote:** "I'm not calling the top"
- **Conflicts:** none.
- **Rulebook fix:** N10: "Thursday opposite end = expectation only. Counter-trend needs a sweep at an HTF premium array + displacement MSS + FVG (044 ~16:07)."
- **BUILD SPEC (day_week_context):**
  - In `day_context`: tag `one_sided_week` on Thursday when Mon-Wed closed in the same direction with each close beyond the prior high (or low).
  - In `_scan_core`, on such days with `p.thu_strict`, an order against the week's direction is rejected unless all of these hold: the sweep extreme is inside an HTF array (`_htf_tag` True); the MSS candle passes `displacement_mult` x 1.5 [our interpretation]; the fill time is in 10:00-11:00.
  - Params: `thu_strict: bool = False`.
  - Test: `test_thu_strict`. A one-sided up week on Thursday: a short with no HTF tag is rejected, and one with an HTF tag, displacement and a 10:15 fill passes.

### 56. BH-B17-friday-after-one-sided-week
- **rule_id / kind:** B17 / missing_condition. Scope: index. judgment = true.
- **Rule:** Friday after a one-directional Tue-Thu week, with price already pressed into fresh highs pre-open: be cautious with continuation longs. A near-term sell-side raid may come first; prefer entries after it (for example a 10:00-11:00 SB) with small targets (~5 handles), and don't chase at the premium. Mirror for down weeks. This is a caution or tag, not a hard skip.
- **Sources:** 045_DNi9S3_NA44 ~00:11:00.
- **Quote:** "you got to be real careful on a Friday where the Market's been one-sided"
- **Conflicts:** none.
- **Rulebook fix:** N10 Friday: add the caution (045 ~11:00).
- **BUILD SPEC (day_week_context):**
  - Tag `fri_one_sided` in `day_context` (Tue-Thu same direction and the overnight high above Thursday's high).
  - With `p.fri_one_sided == "raid_first"`, longs need a sweep of a session low (the existing sweep in `_scan`) before their MSS; that is already the model, so additionally require the sweep to be below the 09:30 open. Cap T1 at `fri_t1_pts`.
  - Params: `fri_one_sided: str = "off"` ("off" / "tag" / "raid_first"), `fri_t1_pts: float = 5.0`.
  - Test: `test_fri_one_sided`. On a one-sided Friday, a long whose sweep low is above the 09:30 open is rejected under "raid_first", and the accepted long has T1 <= open + 5.

### 57. BH-no-HTF-top-picking
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = false.
- **Rule:** Don't pick HTF tops in buy programs or HTF bottoms in sell programs, however overbought or oversold price looks. Stay with the HTF bias until the market clearly shows a reversal, then trade the new bias. LTF tops and bottoms in the HTF direction are allowed. A smart money reversal (selling within 1-2 ticks of an extreme) is for bearish markets only and for experts, never in bull markets; bottoms mirror this. Bot mapping (block counter-HTF setups until a bias flip or the draw is delivered) is our interpretation.
- **Sources:** 061 ~01:40:32; 074 ~00:37:14; 076 ~00:05:21; cc06_001 ~00:06:55; 104 ~00:44:07.
- **Quote:** "we do not try to pick tops in buy programs okay and we don't try to pick bottoms and sell programs"
- **Conflicts:** none.
- **Rulebook fix:** New rule in B: the prohibition above, with the SMR exception (104 ~44:07).
- **BUILD SPEC (bias_htf):**
  - With `p.no_htf_top_pick`, while the flip state is +1 and the HTF draw is unmet (`objective_met` False), reject shorts from turtle-soup / M2 three-drives / reversal branches (setup tags `turtle*`, `m2`, `reversal`), whatever the extension. Ordinary MSS shorts follow `want` as before. Mirror.
  - Params: `no_htf_top_pick: bool = False`.
  - Test: `test_no_htf_top_pick`. State +1 with the draw unmet: a turtle-soup short is rejected. After the draw is met or the state flips, it is allowed.

### 58. BH-consolidation-near-highs-before-news
- **rule_id / kind:** new / missing_rule. Scope: index. judgment = true.
- **Rule:** In a bullish weekly run, a tight consolidation near the highs (forming at the range's equilibrium) going into a news driver is not a top. Expect the release to expand price higher (capitulation or blow-off), so take no shorts before or into the news. A reversal (for example TGIF) is considered only after that expansion and a bearish shift. Mirror for bearish. This applies whether or not the HTF draw was already reached.
- **Sources:** 075_vN2BkfyRWE4 ~01:37:16.
- **Quote:** "markets do not top like this folks especially ahead of news drivers"
- **Conflicts:** none.
- **[our interpretation]:** "Tight" = the overnight range < 0.5 x ADR5, with the overnight high within 0.25 x ADR5 of the week high.
- **Rulebook fix:** New note under N5: "consolidation near the highs into news is not a top (075 ~1:37:16)".
- **BUILD SPEC (news_calendar_times):**
  - In `blocked()` / `_setup_news` on 08:30 news days: when the weekly bias is up (`weekly_bias` / flip +1) and the overnight range meets the tight condition, block shorts before the release and until a bearish MSS forms after it (tag `pre_news_coil`).
  - Params: `pre_news_coil: bool = False`.
  - Test: `test_pre_news_coil`. A CPI day with a tight overnight range near the week high: a pre-08:30 short is blocked, and a post-release short after a bearish MSS is allowed.

### 59. BH-B4-HTF-bias-minimum-criteria
- **rule_id / kind:** new (not B4) / missing_rule. Scope: index. judgment = false.
- **Rule:** New rule (not B4). A 1h bullish bias meets the minimum criteria when three things happen in order:
  1. Price reaches the HTF bullish array (here a daily propulsion block).
  2. It sweeps 1h relative equal lows (sell-side).
  3. It trades above the most recent 1h short-term high: the MSS, which needs no close.
  
  After that, retracements into the array's mean threshold are buys as long as the candle bodies respect it. Mirror for bearish.
- **Sources:** 075_vN2BkfyRWE4 ~00:34:50.
- **Quote:** "we have now met the minimum criteria for high probability directional bias"
- **Conflicts:** none.
- **Rulebook fix:** Add as a new B rule ("minimum criteria", 075 ~34:50), not in B4.
- **BUILD SPEC (bias_htf):**
  - Add helper `min_criteria(ctx, sign, i)` on 60m bars, True when all three hold in order since the daily array was first traded into:
    - a bar traded into a daily bull array (conf rows);
    - a 60m REL (`_eq_levels` on 60m lows) was swept;
    - a later 60m high exceeded the last 60m pivot high (n = 1).
  - With `p.min_criteria`, the lock side +1 requires it (else neutral). Entries additionally need the bodies after it to stay above the array MT (`breaker_mt` style 50%).
  - Params: `min_criteria: bool = False`.
  - Test: `test_min_criteria`. A synthetic 60m path through a daily OB, REL sweep and break of the high gives True. Without the REL sweep, it gives False.

## D. Seasonals, weekly profiles and weekly/daily structure

### 60. BH-B23-index-seasonal-windows
- **rule_id / kind:** B23 / unlisted_contradiction. Scope: index. judgment = true.
- **Rule:** Tags only.
  - Regimes (cc10_015):
    - Jan-Apr: high-magnitude and mostly bullish.
    - May-Oct: low-magnitude range (less leverage).
    - Q4: strongly bullish.
  - Long windows:
    - Mid-Sep/Oct to year end, extending to about the first week of Feb (050).
    - Feb to May (cc10_016/018).
  - Short windows:
    - May into the 1st-2nd week of June (050), extendable through July to about Aug 1 (cc10_017) or mid-Sep (cc10_018).
    - January (cc10_017).
  - In bull regimes, the 3rd week of May to the 3rd week of June is a buy window (June low, 074).
  - Start preparing about 1 month before a window.
  - Flag these conflicts:
    - Jan bearish vs the fall long window running into early Feb.
    - Jul bullish into the mid-year high vs the May-Jul short window.
    - The May-June short vs the June-low buy.
- **Sources:** 050 ~00:02:22; 074 ~00:18:21; cc10_015 ~00:02:03; cc10_016 ~00:02:11; cc10_017 ~00:01:54; cc10_018 ~00:23:16.
- **Quote:** "you have this basic rule of buying stocks February to May selling stocks May to mid-september"
- **Conflicts:** Month map vs 050 (Jan bullish), 074 (June low), July bullish vs the cc10_017/018 sell window, January.
- **Rulebook fix:** B23: add the regime layer, the windows and the conflict list above.
- **BUILD SPEC (day_week_context):**
  - Add `calendar.season_tags(day) -> set` with tags `regime_hi_bull` (Jan-Apr), `regime_range` (May-Oct), `regime_q4`, `win_long_fall` (Sep 15-Feb 7), `win_long_spring` (Feb 1-May 31), `win_short_may` (May 1-Jun 14), `win_short_summer` (Jun 15-Sep 15), `win_short_jan` (Jan), `win_buy_june` (3rd week of May to the 3rd week of June).
  - Attach them in `day_context`, and report by tag in `BT.run` (rule_coverage B23: "no map, tag or report"). Tags only, with no gate.
  - Test: `test_season_tags`. 2023-06-01 has `win_short_may`, `win_buy_june` and `regime_range`. 2023-01-10 has `win_long_fall`, `win_short_jan` and `regime_hi_bull`.

### 61. B23-intramonth-detail
- **rule_id / kind:** B23 / shortened. Scope: general. judgment = false.
- **Rule:** Intramonth (Dow/index seasonals, cc10_015):
  - Sep: first half bullish, second half bearish. The seasonal low can form in late Sep or Oct before Q4 rallies hard.
  - Nov: bullish. Dec: Santa Claus rally.
  - Jul: bullish into the mid-year high. Aug: consolidation.
  - Mar: overall consolidation, with the 2nd to 3rd week bearish and a rally toward month end.
  - Apr: opens slightly bearish, then rallies strongly from about mid-month into month end.
  - May: bearish into about the 3rd week (an intramonth low), then a small rally into month end.
- **Sources:** cc10_015_rlTl8QKpqCU ~00:05:47, ~00:05:34, ~00:12:40.
- **Quote:** "July is bullish into the mid-year High"
- **Conflicts:** none.
- **Rulebook fix:** B23: replace the whole-month labels with the intramonth detail above.
- **BUILD SPEC (day_week_context):**
  - Extend `calendar.season_tags` with an intramonth `season_dir` (+1 / -1 / 0) from a table keyed by (month, week of month): Sep wk1-2 +1, wk3-4 -1; Mar wk2-3 -1, wk4 +1; Apr wk1-2 -1, wk3-4 +1; May wk1-3 -1, wk4 +1; Jul +1; Aug 0; Nov/Dec +1.
  - Report only. With `p.season_gate` (default off), block trades against `season_dir` when it is non-zero.
  - Test: `test_season_dir`. 2023-09-05 gives +1, 2023-09-20 gives -1, 2023-05-30 gives +1.

### 62. BH-B23-seasonal-failure
- **rule_id / kind:** B23 / missing_condition. Scope: general. judgment = true.
- **Rule:** Add to B23.
  - Act on a window only when price confirms it technically. For a bearish window: the HTF bias agrees, price is in a premium market, it rallies into a bearish OB or runs an old high, then an MSS (mirror for bullish).
  - Manage by structure, not by holding to the window's end.
  - If the window passes with no setup, read the result:
    - price going the opposite way = strength in that direction (the bias flips);
    - little net movement = consolidation (no swings).
  - If several asset classes are off their seasonals, that is a decoupling: expect no strong one-sided moves.
- **Sources:** 074 ~00:17:36; cc10_003 ~00:41:02; cc10_019 ~00:25:08; cc05_011 ~00:13:22.
- **Quote:** "while I was expecting and looking for it we didn't do anything that would get us short"
- **Conflicts:** B23 currently gives only one failure outcome (a missing seasonal = strength the other way).
- **Rulebook fix:** B23: add the technical checklist, structure management and the three failure outcomes.
- **BUILD SPEC (day_week_context):**
  - After a window from item 60 ends, compute `season_result` from the window's net daily move:
    - "counter" if the move against the window's direction is > `season_move_adr` x ADR5 (`strategy.adr5`) x window length / 5;
    - "consol" if |net| < 0.5 x that amount;
    - otherwise "worked".
  - Tag the next 20 sessions with it. Report only. A gate is optional: with `p.season_gate`, a window acts only when the flip state agrees (the technical-confirmation proxy).
  - Params: `season_move_adr: float = 1.0` [our interpretation].
  - Test: `test_season_result`. A synthetic May that rallies 3 x ADR5 gives "counter". A flat May gives "consol".

### 63. BH-M14-TGIF-preconditions
- **rule_id / kind:** M14 / missing_condition. Scope: index. judgment = true.
- **Rule:** Add to M14. TGIF is strongest when the week has reached a monthly or weekly premium array (e.g. a monthly FVG), the preceding several weeks were bullish with closes above the candle midpoint near the highs, and price has gone up each day of the current week. If no HTF array has been reached, expect a possible close on the high (no TGIF). Mirror for bearish.
- **Sources:** 066_wTR-vhOdMgo ~00:15:52.
- **Quote:** "because we traded up into that monthly fair value Gap"
- **Conflicts:** none.
- **[our interpretation]:** "Several weeks" = >= 2. Monthly arrays need monthly bars (see item 71).
- **Rulebook fix:** M14: add the multi-week strong-close and up-every-day preconditions (066 ~15:52).
- **BUILD SPEC (day_week_context):**
  - In `day_context`'s tgif block (~1952), when `p.tgif_strict` is on, set the tgif tags only if all three hold:
    - this week has traded into a weekly or monthly bear array (htf conf rows with tf in W/M);
    - the prior `tgif_weeks` weeks closed up and above their midpoints;
    - Mon-Thu each closed above the prior close.
  - Mirror.
  - Params: `tgif_strict: bool = False`, `tgif_weeks: int = 2`.
  - Test: `test_tgif_strict`. A one-way week without an HTF array touch gives no tgif tag. With a weekly FVG touch and two strong prior weeks, the tag is set.

### 64. BH-B13-weekly-PO3
- **rule_id / kind:** B13 / T13, missing_rule. Scope: index. judgment = true.
- **Rule:** Extend B13.
  - In a bullish week, an early-week decline below the weekly open into a discount array (sell stops, FVG, old high) is accumulation and usually sets the week's low.
  - After displacement back above the open, buy the first retrace into a bullish FVG or breaker.
  - Target the HTF premium array (the week's high), and expect some distribution off the high into Friday's close (close near but off the high).
  - Mirror for bearish.
  - The weekly high or low can form late in the week (Thu/Fri) on news weeks (072, NFP).
- **Sources:** 066_wTR-vhOdMgo ~00:08:51; 072_AKg_r0DIa3k ~00:07:07; cc07_006_O69iFqP1j7o ~00:08:30.
- **Quote:** "if the Market's bullish the open will be near the low or the range and the close will be near the high"
- **Conflicts:** none.
- **Rulebook fix:** B13: add the weekly PO3 sequence and the NFP-week exception.
- **BUILD SPEC (bias_htf):**
  - Rule_coverage B13 adds the `weekly_open` filter (Mon-Tue below / Wed+ above). New: the accumulation-then-displacement state.
  - Add `htf.table` column `wk_po3` (+1 / -1 / 0): +1 from the day after this week traded below the weekly open into a daily bull array and then closed back above the weekly open. Mirror. Reset on Sunday.
  - When `p.wk_po3` and `wk_po3 == +1`: shorts are blocked for the rest of the week and the lock side is +1 toward the weekly draw.
  - On NFP weeks, `wk_po3` stays 0 until Friday [our interpretation of 072].
  - Params: `wk_po3: bool = False`.
  - Test: `test_wk_po3`. Monday trades below the weekly open into a daily FVG and Tuesday closes above the open: wk_po3 +1 from Wednesday.

### 65. BH-consolidation-takes-run-high
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** A tendency, not a rule: after a price run followed by consolidation, expect the run's high to be taken at minimum (usually, not always), whether price continues or reverses via a breaker. Use it as a tie-breaker lean when the bias is unclear. Mirror for bearish. The timeframe is not specified (the context was 4h/daily ranges).
- **Sources:** 046_VLis0LcbUaQ ~00:09:16.
- **Quote:** "at the very minimum take out the old high"
- **Conflicts:** none.
- **[our interpretation]:** "Run then consolidation" on daily bars = a leg of >= 2 x ADR5 followed by >= 2 inside days.
- **Rulebook fix:** New B note: "run then consolidation -> the run's high is the minimum draw (usually) (046 ~9:16)".
- **BUILD SPEC (bias_htf):**
  - Add `htf.table` column `run_hi_draw`: the leg high when the last leg (pivot to pivot) was >= 2 x ADR5 up and the following >= 2 days stayed inside it. Mirror `run_lo_draw`.
  - When the lock is neutral and `p.run_extreme_lean`, lock toward `run_hi_draw` (side +1 until it is taken).
  - Params: `run_extreme_lean: bool = False`.
  - Test: `test_run_extreme_lean`. A 100-pt up leg then 2 inside days with a neutral lock: the lock side is +1 with the target at the leg high.

### 66. BH-PWH-run-giveback-weekly-gap
- **rule_id / kind:** new / missing_rule. Scope: index. judgment = true.
- **Rule:** A tentative tag, not a hard draw. After the week runs above the previous week's high, if price gives back much of the week's up-move, consider the nearest weekly BISI (its CE, then the full gap) and the sell-side below as the next draw. If price fully closes in that gap, lean bearish and look for lower targets. Mirror. There is no fixed retrace threshold in the source.
- **Sources:** 047_441vklRYYR4 ~00:01:31.
- **Quote:** "we've given up much of the ground gained over the week so far"
- **Conflicts:** B17 (delivered = neutral).
- **[our interpretation]:** "Much of" = > 50% of the week's low-to-high.
- **Rulebook fix:** New B note (047 ~1:31) with the conflict against B17 listed.
- **BUILD SPEC (bias_htf):**
  - Add `htf.table` column `pwh_giveback` (bool): this week traded above the prior week's high, and the prior close is below week_low + (1 - `giveback_frac`) x (week_high - week_low).
  - Tag only. With `p.pwh_giveback_draw`, add the nearest weekly BISI CE below as a lock candidate (side -1). A full close-in of that gap flows into item 7's `wk_bisi` trigger.
  - Params: `pwh_giveback_draw: bool = False`, `giveback_frac: float = 0.5`.
  - Test: `test_pwh_giveback`. Week range 4100-4180 above a PWH of 4170 with a close at 4130: tag True, and the candidate is the weekly BISI CE below.

### 67. BH-three-pool-runs-exhaustion
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** Once a leg has taken three successive sell-side pools, do not take new shorts at premium arrays (FVG/OB) in that leg. Expect consolidation or a run to the nearest buy-side above. Mirror for buy-side runs. The source example is DXY; applying it to indices is [our interpretation].
- **Sources:** 048_gGxVE8zUIRQ ~01:13:41.
- **Quote:** "it's already taken three pools of liquidity"
- **Conflicts:** none.
- **Rulebook fix:** New B note (048 ~1:13:41, DXY).
- **BUILD SPEC (setups_models):**
  - In `_scan_core`, count the pools of the order's direction taken since the leg began. The leg starts at the last opposite MSS; use the session's `spent` / `seen` lists.
  - With `p.pool_runs_max` > 0 and count >= `pool_runs_max`, reject continuation orders (`_f("x_pool_runs_exhausted")`).
  - Params: `pool_runs_max: int = 0` (test 3).
  - Test: `test_pool_runs_exhausted`. Three sell-side pools taken since the last bullish MSS: a short is rejected with max 3 and allowed with 0.

### 68. BH-micro-BPR-tick-match-LOD
- **rule_id / kind:** new / missing_rule. Scope: index. judgment = true.
- **Rule:** AM, 3m chart: inside a micro balanced price range, a later candle's low equals an earlier candle's high exactly, to the tick. If price then moves higher, the low of the day is likely already in (055 ~15:51). Mirror for a high of day. The exact trigger for 'moving higher' (e.g. a break of the retrace high) is our interpretation.
- **Sources:** 055_qiv8pkcNvGk ~00:15:51.
- **Quote:** "it's not one tick short"
- **Conflicts:** none.
- **Rulebook fix:** New A11 note (055 ~15:51, single example).
- **BUILD SPEC (management_exits):**
  - Add detector `levels.tick_match(h, l, i, tick, look)`: on 3m bars, True when bar j's low == bar k's high (|diff| < tick / 2) for some k < j within `look` bars, inside a BPR (A11 detector).
  - When a long is open and a tick-match fires after the entry followed by a 3m close above the retrace high, tag `lod_in` and switch management to hold (skip the X9 time stop) [our interpretation].
  - Params: `tick_match_hold: bool = False`.
  - Test: `test_tick_match`. 3m bars with high 4001.25 at k and low 4001.25 at j are detected. 4001.00 vs 4001.25 is not.

### 69. BH-premium-FVG-CE-vs-far-edge-trap
- **rule_id / kind:** A5 / missing_rule. Scope: general. judgment = true.
- **Rule:**
  - Bearish FVG (premium) retrace where price holds at or below the CE, then breaks down and forms a new SIBI -> expect the sell-side low to be taken.
  - Price that trades to the FVG's far (high) edge and then sells off is a trap: expect the sell-side to hold and price to run buy-side instead. No short; it is a neutral zone (062 ~15:56).
  - Mirror for a BISI.
- **Sources:** 062_sfRO5LrTgTA ~00:15:56.
- **Quote:** "if it does and it starts to sell off this is a trap"
- **Conflicts:** none.
- **Rulebook fix:** A5 "Expected reaction": add the CE-hold continuation vs far-edge trap consequence.
- **BUILD SPEC (setups_models):**
  - In `_scan_core`, for a short whose entry FVG lies inside an HTF bear FVG (60m, the source's timeframe), measure the max high of the retrace into that HTF FVG.
  - With `p.far_edge_trap`, reject the short if that high traded above the HTF FVG's top - 10% of its height [our interpretation of "far edge"] (`_f("x_far_edge_trap")`), and tag `ce_hold` when the high stayed <= its CE.
  - Params: `far_edge_trap: bool = False`.
  - Test: `test_far_edge_trap`. 60m SIBI 4010-4020: a retrace to 4014 then a short is allowed with `ce_hold`. A retrace to 4019.75 gets the short rejected.

### 70. BH-L4-resistance-definitions
- **rule_id / kind:** L4 / unlisted_contradiction. Scope: general. judgment = true.
- **Rule:** Low- vs high-resistance run, used as a strong filter (de-emphasise, paper-trade or skip high-resistance runs).
  - (a) Structure (062 ~8:42; L4 cc01_007): back-and-forth consolidation and overlapping swings between price and target = high resistance. A one-way, immediate run = low resistance.
  - (b) HTF draw (cc04_002 ~31:25): trading against the monthly/weekly draw = high resistance. Trading with it toward short-term highs/lows on daily-1h = low resistance.
  - A valid low-resistance trade should give near-immediate follow-through (062).
- **Sources:** 062_sfRO5LrTgTA ~00:08:42; cc04_002_npL3ZXJ5zOU ~00:31:25.
- **Quote:** "if we're trading against a higher time frame ... it's going to be a high resistance liquidity run"
- **Conflicts:** The L4 overlap definition (cc01_007) and the 048 intermarket definition.
- **Rulebook fix:** L4: add definition (b) and the follow-through expectation. List both definitions as complementary.
- **BUILD SPEC (targets_partials):**
  - Rule_coverage L4 (MISSING: "no resistance count") is in levels_detectors. New: the `resist_def` switch.
  - Compute `Trade.resist`:
    - "struct": the number of 5m swing pivots whose ranges overlap between the entry and T1 >= `resist_overlaps` -> high;
    - "htf": the order is against the weekly flip/draw side -> high;
    - "both": either one.
  - With `p.resist_filter`, skip high-resistance orders. Otherwise tag only.
  - Params: `resist_def: str = "off"` ("off" / "struct" / "htf" / "both"), `resist_overlaps: int = 3`, `resist_filter: bool = False`.
  - Test: `test_resist_def`. A long against a -1 weekly state is high under "htf". A long with 4 overlapping 5m swings to T1 is high under "struct".

### 71. BH-A5-HTF-FVG-own-timeframe
- **rule_id / kind:** A5 / missing_rule. Scope: general. judgment = false.
- **Rule:** Detect weekly/monthly FVGs on weekly/monthly bars resampled from lower-timeframe data, not on daily candles: a weekly FVG may not look like an FVG on the daily. Apply the A5 three-candle test on the HTF bars and project its high/low/CE onto lower timeframes (068 ~3:02). Drop the 066 citation.
- **Sources:** 068_V0uV6lcgobQ ~00:03:02.
- **Quote:** "go to your weekly chart and you'll see right away what that Weekly fair value Gap is"
- **Conflicts:** none.
- **Rulebook fix:** A5: add "HTF FVGs are detected on their own bars (068 ~3:02)".
- **BUILD SPEC (bias_htf):**
  - Weekly is already done: `htf.table` runs `_arrays` on `weeks(d)` bars. New: monthly. Add `months(d)` (same shape as `weeks`, usable from the day after the month's last session) and `_arrays(..., "M", ...)` when `p.htf_monthly`. The tf "M" rows flow to conf/draw like "W".
  - Params: `htf_monthly: bool = False`.
  - Tests:
    - `test_weekly_fvg_on_weekly_bars`: a weekly FVG that shows no daily three-candle gap is present in `_arrays` "W".
    - `test_monthly_arrays_known_next_month`: a monthly FVG becomes usable the session after the month closes.

### 72. BH-mixed-HTF-intraday-only
- **rule_id / kind:** B17 / missing_rule. Scope: general. judgment = true.
- **Rule:** When price is working inside or around a newly formed, unresolved weekly FVG and major world-news uncertainty is flagged: do no longer-term (multi-session) positioning. Trade intraday sessions only (AM/PM) until the Sunday open and Monday's trading show which way the weekly gap resolves (068 ~4:27). The macro-risk flag is a manual/news input.
- **Sources:** 068_V0uV6lcgobQ ~00:04:27.
- **Quote:** "sticking to intraday trading the sessions only"
- **Conflicts:** none.
- **Rulebook fix:** B17: add the note (068 ~4:27).
- **BUILD SPEC (day_week_context):**
  - The bot is intraday-only already, so the effect is on HTF draws.
  - With `p.macro_risk_dates` (a path to a CSV of flagged weeks; default "" = off), on flagged weeks where the price is inside a weekly FVG formed in the last week, set the lock candidates to session pools only (no weekly/daily draws) and mark orders `scalp`.
  - Test: `test_macro_risk_week`. A flagged week inside a fresh weekly FVG: the lock target is a session pool, not the weekly draw.

### 73. BH-weekly-rejection-block-range-proof
- **rule_id / kind:** B8 / missing_rule. Scope: general. judgment = false.
- **Rule:** After an indecisive weekly candle inside or at a weekly FVG, with price mid-range: neutral, no bias.
  - A trade above the rejection-block level (the body close at the top of the swing) -> bullish resumption.
  - A trade below the range low -> bearish; target the sell-side below (070 ~1:01).
  - This applies to that market's weekly range.
- **Sources:** 070_1HtRfFYiwO0 ~00:01:01.
- **Quote:** "to go higher it needs to get above the rejection block"
- **Conflicts:** none.
- **Rulebook fix:** B8: add the weekly rejection-block prove-it rule.
- **BUILD SPEC (bias_htf):**
  - New `flip` trigger `wk_rb`. When the last completed week's body < 30% of its range [our interpretation of "indecisive"] and that week traded into a weekly FVG, set state 0.
  - From then: a daily high above that week's body top (rejection-block level) -> +1; a daily low below that week's low -> -1.
  - Add to `FLIP_TRIGGERS`.
  - Test: `test_flip_wk_rb`. An indecisive week at a weekly FVG: state 0. A later day trading above the body top: +1.

### 74. BH-B8-1h-BISI-CE-hold
- **rule_id / kind:** B8 / missing_condition. Scope: general. judgment = true.
- **Rule:** A bullish bias holds while price stays above the CE of the latest 1h BISI (and its low). Trading through the CE weakens the bias; trading through the BISI low invalidates it (072 ~13:53, ~15:19). Mirror for a SIBI. Close vs trade-through is not specified; choose by test.
- **Sources:** 072_AKg_r0DIa3k ~00:13:53, ~00:15:19.
- **Quote:** "as long as we're above all that I'm bullish"
- **Conflicts:** none.
- **Rulebook fix:** B8: add the intraday 1h BISI hold rule.
- **BUILD SPEC (bias_htf):**
  - In the run_day bar loop under the draw lock: when the lock is +1, track the latest 60m bull FVG formed in the lock direction (`levels.fvgs` on `htf_bars(df, 60)` up to i).
  - With `p.bisi60_hold` ("off" / "trade" / "close"), a trade (or 60m close) below its CE tags `bias_weak`. A trade (or close) below its low sets the lock side to 0 for the session and cancels pending orders. Mirror.
  - Test: `test_bisi60_hold`. Lock +1 with a 60m BISI 4010-4020: a wick to 4014 under "trade" tags weak. A wick to 4009 sets side 0. Under "close", the wicks do nothing.

### 75. BH-B8-daily-breaker-bias
- **rule_id / kind:** B8 / missing_rule. Scope: general. judgment = true.
- **Rule:** After a bearish daily breaker forms (a daily close below the swing low) and is respected on the retest, the daily bias is bearish while price remains below the breaker. The draw is the next daily sell-side low (035 ~51:30). The invalidation level and close basis are our choice (e.g. a daily close above the breaker zone). Mirror.
- **Sources:** 035_kFIOp8Tprdc ~00:51:30.
- **Quote:** "as long as we remain below this breaker we're bearish"
- **Conflicts:** none.
- **Rulebook fix:** B8: add the daily-breaker bias rule.
- **BUILD SPEC (bias_htf):**
  - New `flip` trigger `d_breaker`, using `levels.breaker_zone` on daily bars. After a daily close below the last daily pivot low creates a bearish breaker, and a later day trades into the zone and closes below it (respected): state -1, draw = the next daily pivot low below.
  - A daily close above the zone top: state 0. Mirror.
  - Add to `FLIP_TRIGGERS`.
  - Test: `test_flip_d_breaker`. Daily breaker 4050-4060: a retest close at 4045 gives -1. A close at 4065 gives 0.

### 76. BH-B20-sentiment-contrarian
- **rule_id / kind:** B20 / missing_rule. Scope: needs_unavailable_data. judgment = true.
- **Rule:** An optional contrarian sentiment enhancer (needs a text feed).
  - Extreme one-sided retail sentiment is built from: repeated, emotionally charged headlines; retail forum consensus; live-stream chat consensus; weekly Williams %R at an extreme.
  - Fade it only when the HTF technical draw independently points the other way. Then upgrade the setup.
  - A 'hot market' media focus after a long trend is contrarian.
  - Headlines against an established technical bias are fuel, not a reason to exit.
  - Drop the 70-90% retail threshold unless it is separately sourced.
  - Sources: cc12_002 ~14:18; cc11_001 ~11:45; 101 ~16:44; 033 ~30:33; cc06_007 ~7:17.
- **Sources:** 033 ~00:30:33; 101 ~00:16:44; cc11_001 ~00:11:45; cc06_007 ~00:07:17; cc12_002 ~00:14:18.
- **Quote:** "when all three of these things come together that builds my sentiment"
- **Conflicts:** none.
- **Rulebook fix:** B20: add as written. No build spec.

### 77. B8-weekly-ith-both-indices-close
- **rule_id / kind:** B8 / missing_condition. Scope: index. judgment = false.
- **Rule:** Weekly ITH flag: ES and NQ both close a week below the low of their own last down-close weekly candle. Then favour lower-timeframe sells only, until price shows a return to bullish. If only one index (or neither) closes below, the bullish view stays (077 ~9:44).
- **Sources:** 077_OnFifO44Kzo ~00:09:44.
- **Quote:** "it has to be on a closing basis both s p and NASDAQ"
- **Conflicts:** none.
- **Rulebook fix:** B8c: add the both-indices requirement and the persistence clause.
- **BUILD SPEC (bias_htf):**
  - The `flip` trigger `wk_dc` exists per instrument. New: the joint version.
  - In `backtest` (where both instruments' tables are available), compute `wk_ith_joint` = both instruments' last weekly closes below their own last down-close week's low. It persists until a `wk_dc` +1 on either instrument [our interpretation of "return to bullish"].
  - With `p.wk_dc_joint`, the `wk_dc` -1 flip applies only when it is joint. Pass the joint state to `run_day` via `day_kwargs`.
  - Params: `wk_dc_joint: bool = False`.
  - Test: `test_wk_dc_joint`. ES closes below and NQ does not: no flip. Both close below: -1 for both.

### 78. B9-retrace-above-swing-low
- **rule_id / kind:** B9 / missing_condition. Scope: index. judgment = true.
- **Rule:** In a bullish HTF, a daily retrace down into an unfilled lower inefficiency, even to the wick CE, is still a retracement and not a flip while price stays above the last daily swing low and the lower breakaway FVG stays at least partly open (077 ~11:02). It is a single ES example. The source gives no rule for what happens when the swing low or the gap fails; treat that failure as the B8 close-based flip inputs, not as automatic neutral. Mirror for bearish.
- **Sources:** 077_OnFifO44Kzo ~00:11:02.
- **Quote:** "it could trade down there and still not upset anything"
- **Conflicts:** none.
- **Rulebook fix:** B9: add the retracement-persistence condition (077 ~11:02).
- **BUILD SPEC (bias_htf):**
  - Rule_coverage B9 adds "persistence". This is its concrete test.
  - In `htf._flip`, with `p.b9_persist`, suppress any -1 trigger while the daily low stays above the last daily pivot low and the nearest bull daily FVG below is not fully traded through.
  - Test: `test_b9_persist`. An ob_mt close-through while above the swing low with the FVG partly open: no flip. After the swing low breaks, the flip applies.

### 79. B6-untouched-premium-arrays-heavy
- **rule_id / kind:** B6 / missing_rule. Scope: general. judgment = true.
- **Rule:** Bearish bias: list the premium arrays between price and the swing high (IFVG/breaker high or MT, SIBI, VI, wick CE).
  - Failing to reach them while bodies smash through discount arrays = heavy and strongly bearish: stay with the trade and expect the sell-side to be run.
  - Trading through an array's high end or past its halfway (e.g. the breaker high) = less bearish: scale part off to cut risk.
  - A daily close above the wick CE/halfway flips the view (B8).
  - Mirror for bullish.
  - Sources: 078 ~57:07; 098 ~1:06:52; 102 ~1:28:15; 091 ~2:21 [fx].
- **Sources:** 078 ~00:57:07; 091 ~00:02:21; 098 ~01:06:52, ~01:03:51; 102 ~01:28:15.
- **Quote:** "the failure to get up there is you know it's indicative of heaviness"
- **Conflicts:** none.
- **Rulebook fix:** B6: add the strength gauge.
- **BUILD SPEC (management_exits):**
  - At entry, store the opposing arrays between the entry and the stop side (`_resist_live` already finds live resistance).
  - In the position loop:
    - if price trades past the CE/halfway of any of them, take a partial of `heavy_scale` (once);
    - if none has been touched by T1, tag `heavy` and skip the T1 partial size cut (hold more).
  - Params: `heavy_gauge: bool = False`, `heavy_scale: float = 0.33`.
  - Test: `test_heavy_gauge`. A short with a SIBI 4020-4030 above: a wick to 4026 triggers the partial. No touch until T1 gives the `heavy` tag.

### 80. B11-monthly-five-up-closes
- **rule_id / kind:** B11 / missing_rule. Scope: general. judgment = true.
- **Rule:** After about 5 consecutive up-close monthly candles that trade into a monthly bearish array (e.g. a breaker), anticipate a down-close month or bearish delivery next, as context. It is not certain: the month need not close lower. This is a single NQ journaling example (078 ~16:48; 078 ~57:07). Mirror for bearish.
- **Sources:** 078_FQqwmDJOtxk ~00:16:48.
- **Quote:** "it was long overdue for a down close monthly candle"
- **Conflicts:** none.
- **Rulebook fix:** B11: add the monthly context tag.
- **BUILD SPEC (day_week_context):**
  - In `day_context`, from monthly bars (item 71's `months`), tag `mo_overdue_dn` for the whole next month when the last >= 5 completed months closed up and the last one traded into a monthly bear array (needs `htf_monthly`). Mirror. Tag only.
  - Test: `test_mo_overdue_tag`. Five up months with the fifth touching a monthly bear FVG: the next month's days are tagged.

### 81. NEW-monday-high-of-week-profile
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** Weekly profile (template): with a bearish HTF bias, if Monday trades up into a daily SIBI and rejects, Monday's high can be the high of the week. Expect Tuesday-Wednesday to deliver lower, often with a lower gap open and a large-range down day (078 ~1:07:29, NQ, described after the fact). Bot use: tag only. A sell-below-Monday-high and cancel-above-it rule is our interpretation. This conflicts with T14's 'bearish highs often Tuesday'. Mirror for bullish.
- **Sources:** 078_FQqwmDJOtxk ~01:07:29.
- **Quote:** "an obvious Monday high of the week bearish profile"
- **Conflicts:** T14: bearish highs often form on Tuesday.
- **Rulebook fix:** Add the profile under the weekly profiles (section 2.5) with the T14 conflict.
- **BUILD SPEC (day_week_context):**
  - In `day_context` (Tue-Thu), tag `mon_how` when the flip state is -1, Monday's high traded into a daily bear array and Monday closed below that array's low (or CE).
  - With `p.mon_how == "gate"`, shorts Tue-Thu need entry < Monday's high, and the tag is cleared by any trade above Monday's high. Mirror.
  - Params: `mon_how: str = "off"` ("off" / "tag" / "gate").
  - Test: `test_mon_how`. Bearish state, Monday high at 4050 inside a daily SIBI and a close at 4030: Tuesday is tagged. After a trade at 4051 the tag is gone.

### 82. B17-neutral-htf-monday-close
- **rule_id / kind:** B17 / unlisted_contradiction. Scope: general. judgment = true.
- **Rule:** No HTF bias for the week: wait for Monday's trading, and if needed the middle of the week, for the HTF draw to show. It may not come that week. Until it does, only small intraday scalps are allowed: reduced size, short targets, no runners (084 ~1:26). This refines B16/B17. B17's 'no trade' applies when the setup itself can be framed both ways, not to every week without an HTF draw.
- **Sources:** 084_VdGihxSuSRk ~00:01:26.
- **Quote:** "sometimes I have to wait for Monday's trading"
- **Conflicts:** B17 / B16.
- **Rulebook fix:** B17: split "no trade" (a 50/50 setup) from "no weekly draw" (scalps only until it shows) (084 ~1:26).
- **BUILD SPEC (bias_htf):**
  - In `run_day`: when `want == 0` (or the weekly draw is unset) and `p.bias_neutral == "scalp_week"`, trade both sides but mark every order `scalp` with `risk_mult *= 0.5` [our interpretation].
  - Add "scalp_week" to the `bias_neutral` values. Rule_coverage Ep02.6's `no_narrative_scalp` ("scalp" mode) is the same mechanism; implement it once and alias it.
  - Test: `test_bias_neutral_scalp_week`. A neutral week: orders on both sides at half risk with one target.

### 83. B22-quarterly-shift
- **rule_id / kind:** B22 / shortened. Scope: general. judgment = true.
- **Rule:** Quarterly shift:
  - Every ~3-4 months, HTF structure shifts. This is not calendar-exact; a new quarter is only a loose anchor (cc09_008 vs cc02_006).
  - After an HTF run into a monthly/weekly array, expect a reversal, or a consolidation followed by resumption, lasting ~2-3 months (max ~4). It is likely, not guaranteed.
  - Supporting evidence: seasonals (long and short samples agree), intermarket/yields agreeing, and the COT commercials' 6/12-month hedging-range reading.
  - quarterly_objective = the HTF PD array the shift reaches for, e.g. the deep-discount weekly BISI (mirror: the premium SIBI). Lean LTF ideas toward it and size up nearer it.
  - Enter via daily PD arrays after the shift has started.
  - Sources: 084 ~22:18; 098 ~58:30; 102 ~1:22:58; cc02_006 ~41:28; cc03_006 ~2:49; cc05_011; cc05_018 ~10:28; cc09_008 ~7:46; cc10_001 ~20:53.
- **Sources:** 084 ~00:22:18; 098 ~00:58:30; 102 ~01:22:58; cc02_006 ~00:41:28; cc03_006 ~00:02:49; cc05_011 ~00:05:00; cc05_018 ~00:10:28; cc09_008 ~00:07:46; cc10_001 ~00:20:53.
- **Quote:** "every three or four months there's a shift in Market structure and the market trades in a sustained move for about two and a half months or so"
- **Conflicts:** B22 says 3-4 months; 084/098 say 2-3; 102 says 2-4; cc03_006 says 3-6 (that is the bond outlook).
- **Rulebook fix:** B22: add the horizon, the two forms, the supporting evidence and `quarterly_objective`.
- **BUILD SPEC (bias_htf):**
  - Rule_coverage B22 adds `qshift_tag` / size (60-day turn or consolidation, due window, 252-day trend). New: `quarterly_objective`.
  - When `qshift_tag` fires (a daily MSS against the 60-day trend), set `htf.table` column `q_obj` = the nearest weekly array in the new direction beyond the 60-day range (the weekly bull FVG below for a bearish shift). Keep it until it is traded or 84 sessions (4 months) pass.
  - With `p.q_obj_lean`, the lock side defaults to sign(q_obj - price) when the lock is otherwise neutral.
  - Params: `q_obj_lean: bool = False`.
  - Test: `test_q_obj`. A bearish shift with a weekly BISI 300 pts below: q_obj set and persisting, expiring after 84 sessions.

### 84. B22-timing-tool
- **rule_id / kind:** B22 / wrong. Scope: general. judgment = true.
- **Rule:** The quarterly shift is a time filter, not a direction source.
  - From the last daily MSS S, cast forward so that elapsed time plus the cast equals 60 trading days (marks at S+20/40/60).
  - Expect an intermediate-term swing high or low, or a new daily setup, before S+60 (cc05_001 ~35:25-37:51; cc05_003 ~29:20).
  - Take direction from IOF and PD arrays, not from the window (cc11_002 ~1:13).
  - For indices or stocks, look inside the window for a daily three-index SMT divergence (Nasdaq Composite / S&P / Dow, cc11_003 ~51:52).
  - Window plus aligned bias plus seasonal = a candidate mega trade.
  - Replace B22's 'not timing'.
- **Sources:** cc05_001 ~00:37:51, ~00:35:25; cc05_003 ~00:29:20; cc11_002 ~00:01:13; cc11_003 ~00:51:52.
- **Quote:** "every 3 months or so the marks will tend to form an intermediate term turning point now by itself it doesn't give you directional bias"
- **Conflicts:** B22 (cc05_001 ~5:05; 084; 098): context, not timing.
- **Rulebook fix:** B22: replace "context, not timing" with "a time filter, not a direction source", and add the 20/40/60 cast.
- **BUILD SPEC (bias_htf):**
  - Add `htf.table` column `q_days` = trading days since the last daily MSS (pivot n=1 break against the prior swing). Add `q_window` = `q_days` in [40, 60] [our interpretation: the last third].
  - Report only. With `p.q_window_gate`, the daily-SMT tag of item 119 counts only inside the window. Size up via the existing `risk_mult` only when the window, bias and season (item 60) all agree.
  - Params: `q_window_gate: bool = False`.
  - Test: `test_q_days_cast`. A daily MSS 45 sessions ago: q_days 45, q_window True.

### 85. B6-weekly-iof
- **rule_id / kind:** B6 / shortened. Scope: general. judgment = false.
- **Rule:** B6 can also be scored on weekly bars with the same test (premium arrays broken and discount arrays holding = bullish; mirror for bearish). Setups that agree with both the weekly structure and the monthly bias are favored; this is a weighting, not a hard requirement. Source context is FX profiling (cc12_002 ~16:34); the method is general.
- **Sources:** cc12_002_Ad-votrg6WQ ~00:16:34.
- **Quote:** "looking for premium arrays braking in bullish markets"
- **Conflicts:** none.
- **Rulebook fix:** B6: "also scored on the weekly; agreement with the monthly is favoured".
- **BUILD SPEC (bias_htf):**
  - Rule_coverage B6 adds a daily `iof` column. Add `iof_w` computed by the same function on `weeks(d)` bars (applied the session after the week closes).
  - Tag `Trade.iof_w_agree`. With `p.iof_weekly_weight`, scale `risk_mult` by 1.0 when it agrees and 0.5 when it opposes [our interpretation of "favoured"].
  - Params: `iof_weekly_weight: bool = False`.
  - Test: `test_iof_weekly`. Weekly bars with a bear array broken upward and a bull array holding give iof_w +1.

### 86. NEW-daily-sibi-bias-gate
- **rule_id / kind:** new / missing_rule. Scope: index. judgment = true.
- **Rule:** After a daily sell-side sweep:
  - Stay bearish (intermediate term) while the daily SIBI repels price; a wick slightly outside it is allowed.
  - While price holds above the SIBI's CE = intraday consolidation to modestly bullish. Trading back below the CE = bearish again (no close timeframe given).
  - If price goes above the SIBI and it acts as support, treat the buy-side above as the draw.
  - Mirror for a BISI. Index (NQ) example, 086 ~2:22 and ~12:30.
- **Sources:** 086_bDOyDitJZi4 ~00:02:22, ~00:12:30.
- **Quote:** "if we get back below the consequent encroachment ... we will resume being bearish"
- **Conflicts:** none.
- **Rulebook fix:** New B rule (086 ~2:22, ~12:30).
- **BUILD SPEC (bias_htf):**
  - In the run_day loop, at the lock and each bar: find the nearest daily bear FVG above the session price that formed after the last daily sell-side sweep.
  - With `p.sibi_gate`:
    - below its CE: allowed side -1;
    - above its CE but inside it: allowed side +1 with `scalp`;
    - above its high followed by a bar whose low holds above the high: side +1 toward the buy-side pool above.
  - Mirror.
  - Params: `sibi_gate: bool = False`.
  - Test: `test_sibi_gate`. A daily SIBI 15200-15300 (CE 15250): price 15270 gives scalp longs. 15240 gives shorts.

### 87. A23-intraday-close-line-in-sand
- **rule_id / kind:** A23 / missing_condition. Scope: general. judgment = false.
- **Rule:** Intraday line in the sand: price may tap the CE of the daily upper wick, but a 60m close above it cancels the day's short idea (090 ~19:57). Softer, discretionary read: once price trades above the CE of the session's 15m SIBI, stop anticipating lower prices for that session (092 ~2:10:25; no close type specified). Mirror for longs.
- **Sources:** 090_bhYcXBI3z9U ~00:19:57; 092_9MLRE-n6St8 ~02:10:25.
- **Quote:** "as long as we don't go above on a closing basis on the hourly chart"
- **Conflicts:** 092 uses a trade-through, 090 uses a close.
- **Rulebook fix:** A23: add the 60m-close invalidation (090) and the softer 15m read (092).
- **BUILD SPEC (bias_htf):**
  - Under the draw lock, with `p.wick_ce_60m`: the day's daily upper-wick CE comes from `_wick_ces(ctx, sd, near_side)`.
  - A completed 60m bar closing above it cancels the session's -1 lock (side 0) and pending shorts. Mirror.
  - Optional `p.sibi15_ce_cancel`: a trade above the CE of the session's latest 15m bear FVG does the same.
  - Params: `wick_ce_60m: bool = False`, `sibi15_ce_cancel: bool = False`.
  - Test: `test_wick_ce_60m`. Wick CE 4050: a 60m wick to 4052 with a close at 4048 leaves the lock. A close at 4051 cancels it.

### 88. B3-reversal-after-target
- **rule_id / kind:** B3 / unlisted_contradiction. Scope: index. judgment = true.
- **Rule:** Optional allow_reversal_after_target (default off, commentary-based): once the session's draw is reached, a wick through into a bullish breaker with bodies holding the low may be traded long toward buy-side. A 14:00 Silver Bullet long in the new direction may be taken even after a winning AM short (086 ~10:26; ICT did not take it). Mirror.
- **Sources:** 086_bDOyDitJZi4 ~00:10:26.
- **Quote:** "if I would have been I would have been all over it right there"
- **Conflicts:** B3 (one direction); X14 (skip the PM after an AM win).
- **Rulebook fix:** B3/X14: list as a Decision.
- **BUILD SPEC (bias_htf):**
  - In `_lock_step`, when the session draw is hit and `p.allow_reversal_after_target`, re-lock the opposite side only when a bar wicked into a bullish breaker (`levels.breaker_zone`) and the next 3 bars' bodies stayed above the wick low.
  - In `sb_model.run_sb`, skip the X14 "AM won -> skip PM" check when the PM lock side differs from the AM's.
  - Params: `allow_reversal_after_target: bool = False`.
  - Test: `test_reversal_after_target`. AM short hits the draw, then a breaker wick and holding bodies: a +1 re-lock and the 14:00 SB long is allowed.

### 89. B18-am-smt-window-points
- **rule_id / kind:** B18 / shortened. Scope: index. judgment = true.
- **Rule:** B18 AM window: compare any relative highs/lows inside 05:00-09:30. The points need not sit on the boundaries; the 08:30/09:30 opens can be one point (cc10_011 ~12:50). One example (086 ~5:42) used a 02:00 low vs an ~11:00 low at a bullish breaker. Test an extended 02:00-11:00 window as an option, not as the default.
- **Sources:** 086_bDOyDitJZi4 ~00:05:42; cc10_011_wWCKTEhVp2o ~00:12:50.
- **Quote:** "don't think like they're goal posts"
- **Conflicts:** B18 AM window 05:00-09:30.
- **Rulebook fix:** B18.2: "points anywhere inside the window, opens allowed as points (cc10_011 ~12:50)". Add the 086 extended example.
- **BUILD SPEC (setups_models):**
  - Rule_coverage B18.2 adds the window filter. New: window bounds as params and opens as reference points.
  - In `_smt`, restrict the compared extremes to [`smt_win_a`, `smt_win_b`]. When `p.smt_open_points`, add the 08:30 and 09:30 opening prices as candidate reference points.
  - Params: `smt_win_a: int = 300`, `smt_win_b: int = 570` (test 120 / 660), `smt_open_points: bool = False`.
  - Test: `test_smt_window_points`. A 02:00 low vs a 10:50 low counts only with 120/660.

### 90. B17-unreached-draw-soft-bias
- **rule_id / kind:** B17 / missing_rule. Scope: general. judgment = true.
- **Rule:** A draw not reached today and not invalidated may be kept as a 'soft' bias for the next day (087 ~0:30, DXY). Treating soft as reduced size or no pyramiding, and dropping it when an opposing draw is taken or on a B8 flip, are our interpretation and should be test switches.
- **Sources:** 087_z4GVg3aPnAk ~00:00:30.
- **Quote:** "so a very soft bias"
- **Conflicts:** none.
- **Rulebook fix:** B17: add the next-day soft carry (087 ~0:30).
- **BUILD SPEC (bias_htf):**
  - In `BT.run` day state, store the last session's lock (side, level) if it was not hit. The next day, when its own lock is neutral and `p.soft_carry`, use the carried side with `risk_mult *= 0.5` and no adds (tag `soft_carry`).
  - Drop it if the opposing pool was taken overnight or the flip state changed.
  - Params: `soft_carry: bool = False`.
  - Test: `test_soft_carry`. Day 1 lock +1 at 4100 not hit, day 2 neutral: side +1 at half risk. With the flip changed, no carry.

### 91. B17-inside-daily-range-no-trade
- **rule_id / kind:** B17 / shortened. Scope: index. judgment = true.
- **Rule:** Inside a daily range bounded by arrays that argue both ways (the daily BISI/SIBI 'bookends'), take no trades on that index until price trades definitively above the range high or below the range low (091 ~6:20). Trading only the break direction afterwards is our interpretation.
- **Sources:** 091_1PkTGkOjoGo ~00:06:20.
- **Quote:** "while we're in here I will not be interested in taking any trades"
- **Conflicts:** none.
- **Rulebook fix:** B17 (091 ~6:12): add the release condition.
- **BUILD SPEC (bias_htf):**
  - Rule_coverage B17.4 `inside_bisi` (built, opt-in) blocks the day. New: the intraday release.
  - With `p.inside_bisi_release`, when an inside_bisi day blocks trading, lift the block from the first bar that trades beyond the BISI range high or low by `release_pts`, and allow only that side.
  - Params: `inside_bisi_release: bool = False`, `release_pts: float = 1.0` [our interpretation of "definitively"].
  - Test: `test_inside_bisi_release`. Inside a daily BISI 4000-4040: blocked until a trade at 4041.25, then longs only.

### 92. NEW-low-of-day-zone-tag-first
- **rule_id / kind:** new / missing_condition. Scope: index. judgment = true.
- **Rule:** When a pre-market low-of-day level is defined (093: the CE of an hourly candle's tail, with the 5m discount FVG, a breaker and the daily inversion-FVG levels beneath), take no longs until price trades down to it. Then require SMT + MSS + FVG on the lower timeframe. Mirror for a high of day.
- **Sources:** 093_CcNOk_3O5wk ~00:08:46.
- **Quote:** "it has to drop down to that level first"
- **Conflicts:** none.
- **[our interpretation]:** How the level is defined in code: the nearest 60m wick CE below the 08:30 price that has a 5m bull FVG or daily IFVG within `eq_tol_pts`.
- **Rulebook fix:** New rule under M0/B4 (093 ~8:46).
- **BUILD SPEC (setups_models):**
  - At 08:30, compute `lod_zone` per the definition above.
  - With `p.lod_zone_first`, reject longs until a bar's low <= `lod_zone` + 2 ticks, and require the sweep's SMT tag True. Mirror.
  - Params: `lod_zone_first: bool = False`.
  - Test: `test_lod_zone_first`. Zone 14980: a long before any trade to 14980.5 is rejected and allowed after one.

### 93. NEW-speed-into-weekly-draw
- **rule_id / kind:** new / missing_rule. Scope: index. judgment = true.
- **Rule:** A discretionary HTF read: if price accelerates quickly into the weekly draw, expect the move to extend beyond it (keep the bias and look to the next HTF draw over the following months) (095 ~8:01, index). No speed threshold and no 'slow = end' rule were given; any thresholds are our interpretation.
- **Sources:** 095_LPmMtq9jLm8 ~00:08:01.
- **Quote:** "if they're really trying to get there down there quick"
- **Conflicts:** none.
- **Rulebook fix:** B9 / B17.3: add the speed exception to "draw delivered -> neutral".
- **BUILD SPEC (bias_htf):**
  - When the weekly draw is hit (B17.3 objective_met), compute speed = distance / weeks since the draw formed, vs the prior leg's speed.
  - With `p.fast_draw_extend`, if speed >= 1.5 x [our interpretation], do not set neutral. Set the next weekly array beyond as the new draw.
  - Params: `fast_draw_extend: bool = False`.
  - Test: `test_fast_draw_extend`. A draw hit in 2 weeks after a 6-week prior leg of the same size: the next draw is set rather than neutral.

### 94. NEW-rates-dxy-fx-direction
- **rule_id / kind:** B19 / missing_rule. Scope: general. judgment = false.
- **Rule:** B19 addition:
  - Yield direction = the opposite of the ZN/ZB futures price direction.
  - Rising yields -> DXY bullish -> (fx-only) sell EUR/GBP/AUD/NZD-USD and buy USD-first pairs. Mirror for falling yields.
  - A bond-triad (30/10/5-yr) failure swing at a DXY extreme confirms the turn.
  - Horizon: the month ahead, up to ~3 months (often half).
  - For indices, use it only as a slow HTF tag (feeding B19's DXY risk-off rule) from FRED yields.
- **Sources:** 095 ~00:14:49; cc03_006 ~00:05:35, ~00:14:48; cc04_001 ~00:17:37; cc05_006 ~00:02:34; cc05_007 ~00:06:34.
- **Quote:** "if the interest rate markets are dropping lower that means interest rates are going to go higher which means ... drive the dollar index higher"
- **Conflicts:** none.
- **Rulebook fix:** B19: add the rates -> dollar chain (index use = slow tag only).
- **BUILD SPEC (bias_htf):**
  - `INTERMARKET` already has `tnx` (prior close vs the 20-day mean). Add `tnx_slow` = sign of the 60-day slope of TNX (prior day) and `rates_dxy_agree` = (tnx_slow == dxy).
  - Tag `Trade.rates_tag`. Report only. Optional: feed item 24 `dxy_filter` only when `rates_dxy_agree`.
  - Params: `dxy_needs_rates: bool = False`.
  - Test: `test_intermarket_tnx_slow`. A synthetic rising TNX gives tnx_slow +1, uses the prior day only, and agree is True with dxy +1.

### 95. B8-three-pd-array-abort
- **rule_id / kind:** B8 / missing_condition. Scope: general. judgment = true.
- **Rule:** Stack the adverse arrays above a bearish idea (mirror for bullish).
  - Wicks or trading into them do not change the bias.
  - While price trades above the first array (e.g. the daily wick CE), be more cautious about new shorts.
  - A daily (framing-TF) body close beyond the last of the three arrays (or beyond a key weekly VI) = abandon the bias -> neutral/stand aside, NOT an automatic opposite bias.
  - Expect sideways price. Adopt the opposite bias only after fresh displacement in the new direction.
  - Mirror for bullish.
- **Sources:** 098_PejS-nZTQlE ~01:08:36, ~01:12:34, ~01:19:43.
- **Quote:** "I am not bearish doesn't mean I'm going long but ... I've abandoned bearishness"
- **Conflicts:** B8 lists it as a "flip".
- **Rulebook fix:** B8 bullet 2: move "three PD arrays" from flips to "abandon -> neutral", and add the first-array caution.
- **BUILD SPEC (bias_htf):**
  - Change `flip_pd3`'s output in `htf._flip` to 0 (neutral) when `p.pd3_result == "neutral"` (keep "flip" for the current behaviour). From the neutral state, +1 needs a displacement day (range >= 1.5 x ADR5 and close in the top quarter) [our interpretation].
  - Separately, `p.pd3_first_caution`: while the prior close is above the first adverse array, mark shorts `scalp`.
  - Params: `pd3_result: str = "flip"` ("flip" / "neutral"), `pd3_first_caution: bool = False`.
  - Test: `test_flip_pd3_neutral`. Three arrays closed through give 0 under "neutral" and +1 under "flip". A later displacement day gives +1.

### 96. B8-weekly-wick-quadrant-gate
- **rule_id / kind:** B8 / wrong. Scope: general. judgment = true.
- **Rule:** Mark the prior weekly wick at 0/25/50/75/100%.
  - (a) Adverse gate (already B8d; keep the neutral result): a daily close beyond the adverse CE/upper quadrant -> stand aside and wait; no new trades in the bias direction.
  - (b) Optional confirmation trigger (missing; fix the 103 ~2:29 citation): when set pre-week, take no trades in the bias direction until a daily close beyond the wick's 75% quadrant in the bias direction. If none comes that week, no trades.
  - Use daily closes only. Mirror.
- **Sources:** 102_uzPM1CuSSx8 ~02:11:40; 103_IU673ZUGuxI ~00:02:32.
- **Quote:** "we close above that on a daily chart then to me I'm on the sideline"
- **Conflicts:** B8d lists 103 as a flip trigger.
- **Rulebook fix:** B8d: move 103 ~2:29 to a new confirmation trigger; keep 102 as the adverse gate.
- **BUILD SPEC (bias_htf):**
  - Part (a) is built (`flip_close_above` -> neutral). New: (b).
  - Add `htf.table` column `wk_q75_ok` (bool): from the day after a daily close beyond the prior week's wick 75% level in the state's direction, until the week ends.
  - With `p.wk_q75_confirm`, `want` is set only when `wk_q75_ok`; otherwise it is 0.
  - Params: `wk_q75_confirm: bool = False`.
  - Test: `test_wk_q75_confirm`. Prior weekly upper wick 4100-4140 (75% = 4130), bullish state: a daily close at 4128 leaves want 0. A close at 4132 gives want +1 from the next day.

### 97. NEW-failed-weekly-push-range
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** Last week traded to (or slightly through) a prior weekly wick's CE but neither closed above it nor exceeded the high of two weeks ago. Frame this week as a range from last week's low to that wick's upper quadrant (75%). Expect consolidation and no trend/runner trades until a daily close beyond the upper quadrant; then expect continuation into the next higher-TF inefficiency. The underlying directional preference is kept. Mirror for bearish.
- **Sources:** 102_uzPM1CuSSx8 ~00:11:29.
- **Quote:** "this tends to create a need for consolidation"
- **Conflicts:** none.
- **Rulebook fix:** New B rule (102 ~11:29, DXY applied to indices).
- **BUILD SPEC (day_week_context):**
  - In `BT.run` weekly state, set `wk_range_frame` = (last week's low, prior wick's 75% level) when the condition holds.
  - In `run_day` with `p.wk_push_range`, mark orders `scalp` while no daily close beyond the 75% level has happened this week. After one, clear the frame.
  - Params: `wk_push_range: bool = False`.
  - Test: `test_wk_push_range`. Last week's high 4121 vs a wick CE of 4120, a close of 4110 and a 2-week-ago high of 4130: frame set and orders scalp.

### 98. B18-smt-only-with-bias
- **rule_id / kind:** B18 / missing_condition. Scope: general. judgment = false.
- **Rule:**
  - Bias first: daily IOF -> 4h/1h PD array in the bias direction -> look for SMT only on the matching side (compare lows when bullish, highs when bearish), 05:00-09:30 AM.
  - A divergence against the bias is not a signal. Tag the non-confirming index as a laggard expected to catch up.
  - For commodities/FX, read the DXY's own HTF expectation first.
  - Remove 'bias' from B18's list of uses.
  - With no clear daily IOF, do not trade the SMT (consistent with B17).
- **Sources:** 099 ~00:56:49; cc04_001 ~00:13:14; cc10_011 ~00:11:35; cc10_002 ~00:07:14.
- **Quote:** "normally if I was bullish that would be something I would be interested in going long on but what is my bias it's bearish"
- **Conflicts:** B18 lists "bias" as an SMT use.
- **Rulebook fix:** B18: remove "bias" from the uses, and add the order of operations and the laggard tag.
- **BUILD SPEC (setups_models):**
  - In `_smt_qual` (the SMT qualifier), with `p.smt_with_bias`, an SMT counts only when the order side == `want` (non-zero). Otherwise set the tag to "laggard" and do not qualify.
  - When `want == 0`, SMT-qualified orders are rejected.
  - Params: `smt_with_bias: bool = False`.
  - Test: `test_smt_with_bias`. Want -1 with a bullish SMT on a long: tag "laggard" and not qualified. Want +1: qualified.

### 99. NEW-event-escalation-weekly-path
- **rule_id / kind:** new / missing_rule. Scope: needs_unavailable_data. judgment = true.
- **Rule:** During a live geopolitical/war event, set a manual escalation flag.
  - Escalation = keep the bearish weekly draw: the recent high holds and lower prices continue.
  - No escalation = allow the sell side below to be taken early in the week (Mon-Tue), then a run back up toward the buy side.
  - In both cases use the smallest size (E9).
- **Sources:** 103_IU673ZUGuxI ~00:32:28.
- **Quote:** "if we escalate this will stay in place and we'll just keep going lower"
- **Conflicts:** none.
- **Rulebook fix:** E9: add the conditional path (103 ~32:28). No build spec (news input).

### 100. NEW-interest-rate-divergence
- **rule_id / kind:** B19 / missing_rule. Scope: needs_unavailable_data. judgment = true.
- **Rule:** Swing/HTF context (FX-centric; a DXY tag for indices).
  - Prefer swings when rates support the trade: rising yields favor that currency.
  - Rate triad: when the DXY trades to an HTF array, the 30/10/5-year bond futures should diverge (fail to confirm) at that point. Example: a DXY lower low at a bullish OB while one or more of ZB/ZN/ZF fails to make a higher high = smart money behind a dollar long.
  - ZN vs ZB divergence (one higher high, the other lower high) -> expect both to decline -> rates up -> dollar up.
  - Bonds make a higher high while the DXY fails to make a lower low = a DXY trend shift (roughly every 3-4 months; a 3-6 month outlook).
  - A DXY extreme not matched by the bonds = a likely stop run.
  - Yield divergence = a possible shift or pause: tag it, do not make it a hard block.
  - Data: FRED yields; intraday ZB/ZN/ZF needed.
- **Sources:** cc03_006 ~00:06:39, ~00:11:34, ~00:16:26; cc04_001 ~00:15:30; cc06_002 ~00:01:00; cc05_018 ~00:01:51.
- **Quote:** "if we see Divergence between the yields that may suggest there's going to be a shift or a pause"
- **Conflicts:** none.
- **Rulebook fix:** B19: add as written. No build spec.

### 101. NEW-paired-obs-dxy-bonds
- **rule_id / kind:** new / missing_rule. Scope: fx_only. judgment = true.
- **Rule (full_rule; no correction given):** DXY retraces into a bullish OB while bonds retrace into a bearish OB -> rates up, dollar accelerates. Mirror.
- **Sources:** cc03_006_MJwWUd_FM-k ~00:07:49.
- **Quote:** "it's returning back to an up candle which is a bearish order block and it sells off again"
- **Conflicts:** none.
- **Rulebook fix:** [fx-only] swing note. No build spec.

### 102. NEW-fx-eurgbp-cross-check
- **rule_id / kind:** B18 / B19, missing_rule. Scope: fx_only. judgment = false.
- **Rule:** [fx-only, out of bot scope] When trading EURUSD/GBPUSD, check EURGBP. EURGBP selling = EUR weaker than GBP -> favor EURUSD shorts / GBPUSD longs relative to each other. A EURUSD short needs both a DXY bid from an HTF discount array and EURGBP weakness. Use EURGBP to see which major is being held back and which is being let run, and trade the one being let run. Mirror.
- **Sources:** cc01_002 ~00:19:39; cc07_008 ~00:26:36.
- **Quote:** "if we're looking for weak euro dollar prices we need to see if the Euro pound would support that idea as well"
- **Conflicts:** none.
- **Rulebook fix:** [fx-only] note. No build spec.

### 103. NEW-fx-rate-differential
- **rule_id / kind:** new / missing_rule. Scope: fx_only. judgment = true.
- **Rule:** [fx-only, HTF filter, not a day-trade trigger] Pair a currency with a high central-bank rate against one with a low rate. There is no numeric threshold, only 'a very strong difference'. Lean in the high-yielder's favour on HTF charts; ideally seasonals and the quarterly shift agree (cc05_008 ~4:16, ~15:37; cc12_001 ~21:04). While DXY is held in consolidation, skip USD pairs and trade non-USD crosses, the stronger-rate currency against the weaker (103 ~11:24). Index bot: not applicable; at most an FX note.
- **Sources:** cc05_008 ~00:04:16, ~00:15:37; cc12_001 ~00:21:04; 103 ~00:11:24.
- **Quote:** "you're not using them to day trade"
- **Conflicts:** none.
- **Rulebook fix:** [fx-only] note. No build spec.

### 104. N8-consolidation-breakout-direction
- **rule_id / kind:** N8 / shortened. Scope: general. judgment = true.
- **Rule:**
  - Default (cc01_001): the first impulsive expansion out of the range sets direction. Do not chase; enter on the retrace into the OB left near EQ, or wait for the next retracement or consolidation.
  - Switch (cc01_006): bias comes from the strongest prior HTF move out of consolidation. Inside the current range, buy at a discount below EQ at a bullish OB, aiming for the FVG or buy stops above. Mirror for shorts.
  - Structure-break confirmation comes from cc01_006 ~7:29 (see the B3 EQ item).
- **Sources:** cc01_001_0LhteuLVuDU ~00:09:50; cc01_006_SiVmoeyOWZE ~00:18:37.
- **Quote:** "we always wait for the first expansion that gives us all the Insight"
- **Conflicts:** cc01_001 vs cc01_006.
- **Rulebook fix:** N8: add both modes as a Decision.
- **BUILD SPEC (bias_htf):**
  - Uses item 1's `drange`. Add `consol_dir: str = "off"` ("off" / "first_expansion" / "prior_strongest").
    - "first_expansion": while drange is 0, no trades. On the first breakout, the side is the breakout side, and entries must sit at or below the range EQ + 25% (no chase) [our interpretation].
    - "prior_strongest": the side is the direction of the largest daily-range leg out of the previous consolidation, and entries must be in the range discount below EQ.
  - Test: `test_consol_dir_modes`. A synthetic range followed by an up breakout: first_expansion gives a long only on a retrace. prior_strongest gives longs inside the range below EQ.

### 105. B17-after-draw-retrace-or-reverse
- **rule_id / kind:** B17 / unlisted_contradiction. Scope: general. judgment = true.
- **Rule:** htf_after_draw in {neutral, reverse}. Never add in the expansion direction after the draw.
  - Reverse case:
    - IOF flips at the HTF target to seek the opposite pool (cc03_002).
    - A fast, large Mon/Tue move into an HTF PD array means watching for a Wed/Thu reversal (cc07_007).
    - An AM rally into a 4h/daily premium array means a PM reversal (cc10_013).
  - Otherwise neutral, per B17's 2023 sources.
  - Note that cc01_001 and cc01_002 disagree on whether consolidation can follow expansion.
  - Log which case applied.
- **Sources:** cc01_002 ~00:18:49; cc07_007 ~00:23:55; cc10_013 ~00:06:27; cc03_002 ~00:10:14, ~00:10:32, ~00:17:18.
- **Quotes:** "it does not do consolidation expansion consolidation that does not happen"; "once it gets to this point here we're looking for what the stops below these lows here"
- **Conflicts:** B17/B9 (038; 061; 099; 101; cc10_019).
- **Rulebook fix:** B17.3: add the `htf_after_draw` Decision with both options.
- **BUILD SPEC (bias_htf):**
  - Rule_coverage B17.3 adds `objective_met_stop`. New: `htf_after_draw: str = "neutral"` ("neutral" / "reverse").
  - Under "reverse", when the daily/weekly draw is hit at an HTF array, the flip state becomes the opposite side (draw = the opposite pool) instead of 0. In the same session, a PM lock in the opposite direction is allowed when the AM hit a 4h/daily premium array.
  - Tag `after_draw_case`.
  - Test: `test_htf_after_draw_reverse`. A weekly draw hit at a weekly bear FVG: state -1 under "reverse" and 0 under "neutral".

## E. Ranges, structure regimes and the CC swing material

### 106. A21-two-level-discount
- **rule_id / kind:** A21 / missing_condition. Scope: general. judgment = true.
- **Rule:** Tag htf_discount when a long entry is at or below the EQ of the larger current dealing range, as well as below the leg EQ; the 20-day range is our proxy (cc01_004 ~30:18). Mirror for shorts. Swing-model note, parked per M17: daily buy-stop entries preferably at or below the monthly/weekly-range EQ, and stop re-adding as price nears the M/W premium (cc05_016 ~5:34).
- **Sources:** cc01_004_qC0LogyIk2I ~00:30:18; cc05_016_vb_Yc-gCBfU ~00:05:34.
- **Quote:** "so any buy condition that occurs below this level here is high probability"
- **Conflicts:** none.
- **Rulebook fix:** A21: add the two-level discount.
- **BUILD SPEC (bias_htf):**
  - Rule_coverage A21.2 adds `day_pd='20d'` and a `pd20` column. New: combine it with `leg_pd`.
  - Tag `Trade.htf_discount` = entry <= the 20-day range EQ (bodies, A21.4) for longs, mirrored for shorts.
  - With `p.pd_two_level`, require both the leg discount (existing `leg_pd`) and `htf_discount`.
  - Params: `pd_two_level: bool = False`.
  - Test: `test_pd_two_level`. A leg-discount long above the 20-day EQ is rejected; one below it passes.

### 107. B3-range-trading-without-bias
- **rule_id / kind:** B3 / unlisted_contradiction. Scope: general. judgment = false.
- **Rule:** require_bias=False mode (cc01_005 ~18:51): inside the most recent swing range, sell premium (OTE 62-79%, or above an old high) and buy discount, targeting just beyond the opposite internal swing low or high. The example is FX daily/hourly. List it as a conflict with B3/B4/B17.
- **Sources:** cc01_005_YuefjnUKQdM ~00:18:51.
- **Quote:** "you don't have to trade with a bias"
- **Conflicts:** B3 / B4 / M0 / B17.
- **Rulebook fix:** Section 3: add the Decision require_bias (cc01_005 ~18:51).
- **BUILD SPEC (bias_htf):**
  - The engine already scans both sides when `htf_bias="off"` and `draw_lock="off"`. New: the premium/discount placement for unbiased trades.
  - Add `range_no_bias: bool = False`. When the session side is 0 / unbiased, a short needs an entry >= 62% of the last 60m swing range (the long mirror is <= 38%). Its single target is the opposite internal swing extreme +/- 1 tick.
  - Test: `test_range_no_bias`. A neutral day with a 60m range of 4000-4100: a short at 4070 is accepted with T = 3999.75. A short at 4050 is rejected.

### 108. B3-eq-recent-structure-break
- **rule_id / kind:** B3 / missing_rule. Scope: general. judgment = false.
- **Rule:** When price sits at the EQ of the current range, direction comes from the most recent structure break: a swing high broken means long, a swing low broken means short (cc01_006 ~7:29). At an HTF (monthly) EQ, use monthly market structure to choose the side and target the next monthly PD array (cc05_015 ~5:09). The no-break fallback is our addition (no bias, B17).
- **Sources:** cc01_006_SiVmoeyOWZE ~00:07:29; cc05_015_Y1oxwc354oo ~00:05:09.
- **Quote:** "did it break a swing high or did it break a swing low"
- **Conflicts:** none.
- **Rulebook fix:** B3: add the EQ tie-break.
- **BUILD SPEC (bias_htf):**
  - Add `htf.table` column `last_break` (+1 / -1): the direction of the most recent daily pivot (n=1) broken by a close.
  - With `p.eq_tiebreak`, when the prior close is within 10% of the 20-day range EQ [our interpretation] and the main bias is 0, use `last_break` as the bias. With monthly bars (item 71), the same applies at the monthly-range EQ.
  - Params: `eq_tiebreak: bool = False`.
  - Test: `test_eq_tiebreak`. Price at the range EQ with the last broken pivot a high gives bias +1.

### 109. B6-hrlr-lrlr-structure-regime
- **rule_id / kind:** B6 / missing_rule. Scope: general. judgment = true.
- **Rule:** Regime tag: an intact LTH plus a defended lower intermediate high plus short-term lows being run = bearish high-resistance-rally mode.
  - Treat rallies toward the defended high as high-resistance (no longs targeting above it).
  - Sell retracements, targeting the short-term and old lows below as low-resistance runs (cc01_007 ~19:48).
  - Mirror for an intact LTL.
  - Invalidation (a break above the defended high) is our inference.
- **Sources:** cc01_007_22XkhpJR5eA ~00:19:48.
- **Quote:** "every rally is going to be viewed as a high resistance liquidity run"
- **Conflicts:** none.
- **Rulebook fix:** B6/L4: add the structural regime.
- **BUILD SPEC (bias_htf):**
  - Use `levels.swing_tiers` (built, A1) on daily bars. Column `tier_regime` = -1 when the last LTH is unbroken, the last ITH < the prior ITH, and the last 2 STLs were each broken. Mirror. 0 otherwise. It is cleared by a trade above the last ITH.
  - With `p.tier_regime_gate`, block longs whose targets exceed the last ITH, and set the lock side to -1 when the lock is neutral.
  - Params: `tier_regime_gate: bool = False`.
  - Test: `test_tier_regime`. A synthetic daily path with a lower ITH and broken STLs gives -1, and a long targeting above the ITH is rejected.

### 110. NEW-three-perspectives
- **rule_id / kind:** new / missing_rule. Scope: needs_unavailable_data. judgment = false.
- **Rule:**
  - Big picture: at least 2 of {macro inflation/deflation, rate trend, intermarket CRB vs DXY, seasonal}.
  - Intermediate: at least 2 of {top-down level on any one of M/W/D, COT commercials extreme, sentiment (lowest weight)}.
  - Short-term: preferably one from each of {correlation/SMT/cracking correlation, time & price (quarterly/monthly/weekly/daily range, time of day), IPDA (IOF, liquidity)}.
  - All three aligned = a high-reward setup.
  - Short-term-only is acceptable for experienced scalpers (cc02_006 ~23:00-49:41).
  - Bot: needs unavailable data; tag only.
- **Sources:** cc02_006_bftKgceXqYo ~00:27:28, ~00:49:41, ~00:23:00, ~00:26:29, ~00:43:58.
- **Quote:** "what makes a high reward trade setup is if your big picture perspective your intermediate perspective and your short term perspective is all in agreement"
- **Conflicts:** none.
- **Rulebook fix:** New rule as written. No build spec.

### 111. B20-cot-core-vs-optional
- **rule_id / kind:** B20 / unlisted_contradiction. Scope: needs_unavailable_data. judgment = false.
- **Rule:** Conflict. cc02_006 (and cc12_002's weekly workflow) treat COT and sentiment as core votes, with the intermediate perspective needing 2 of {top-down, COT, sentiment (lowest weight)}. cc06_002 (swing Hallmarks) calls COT an optional enhancer. Bot: tag only (needs COT data); test a filter later.
- **Sources:** cc02_006 ~00:36:17, ~00:36:38; cc12_002 ~00:05:20.
- **Quote:** "out of these three you need to have at least two of them in agreement"
- **Conflicts:** cc06_002 (optional).
- **Rulebook fix:** B20: list the conflict in section 3. No build spec.

### 112. B20-cot-extremes
- **rule_id / kind:** B20 / shortened. Scope: needs_unavailable_data. judgment = true.
- **Rule:**
  - Commercial net at its 26/52/104/208-week max = a long-term low forming (bullish). At its min = a long-term high (bearish).
  - While an extreme is flagged, the short-term hedging-program (midpoint) tag is discounted.
  - Between extremes, trade with the large speculators (non-commercials).
  - Optional: flag a market whose commercial net is extreme compared with its futures-group peers (ICT's example is commodities).
  - The un-flag threshold is our own parameter, not ICT's. Tag only {d: CFTC COT}.
- **Sources:** cc02_006 ~00:35:14; cc10_001 ~00:29:02; cc12_002 ~00:10:54.
- **Quote:** "I look for the commercials to be at a 12 month or six month extreme in net Holdings"
- **Conflicts:** B20 has the midpoint version only.
- **Rulebook fix:** B20: add the extremes as written. No build spec (the scope was set to needs data; the loader is specified in item 148).

### 113. B5-mature-trend-continuation
- **rule_id / kind:** B5 / missing_condition. Scope: general. judgment = true.
- **Rule:** Treat a flag (sharp leg, then a small consolidation) as possibly false, i.e. a reversal, when the trend is mature or price is at an HTF premium/distribution array (bull flag), or at an HTF discount/accumulation array (bear flag). Proxy: a daily close in the premium of the HTF swing (e.g. > 0.62) or inside an opposing daily/4h PD array. Do not take a continuation entry there.
- **Sources:** cc02_007_cRbPS3uxkj4 ~00:01:56.
- **Quote:** "price will post or create or print ... a false bull flag"
- **Conflicts:** none.
- **Rulebook fix:** B5: add the false-flag caution (cc02_007 ~1:56).
- **BUILD SPEC (setups_models):**
  - With `p.mature_flag_block`, reject a with-trend continuation order (MSS in the direction of the prior 5-day trend) when the prior daily close is > `mature_pd` of the 20-day range (longs) or inside an opposing daily array (`_htf_tag` against the side). Mirror.
  - Params: `mature_flag_block: bool = False`, `mature_pd: float = 0.62`.
  - Test: `test_mature_flag_block`. Prior close at 85% of the 20-day range in an uptrend: a long is rejected. At 50%: allowed.

### 114. B6-consolidation-raid-profile
- **rule_id / kind:** B6 / missing_condition. Scope: general. judgment = true.
- **Rule:** When successive consolidations each raid one side first (e.g. sell stops below the range) and then expand the other way, adopt that direction (bullish). Treat the next drop below a consolidation as a false breakout to buy, targeting buy stops above old highs. Mirror for bearish. The number of ranges needed (e.g. 2) is our parameter.
- **Sources:** cc02_008_pv2-R-STviA ~00:14:28.
- **Quote:** "what side of the market they reaching for and then where is the market going"
- **Conflicts:** none.
- **Rulebook fix:** B6: add the raid-profile read.
- **BUILD SPEC (bias_htf):**
  - Detect daily consolidations (item 1's range logic) and record, for each completed one, which side was raided first before the exit. Column `raid_profile` = +1 when the last `raid_profile_n` ranges all raided the low first and then exited up. Mirror.
  - With `p.raid_profile_bias`, use it as the bias when the main bias is 0.
  - Params: `raid_profile_bias: bool = False`, `raid_profile_n: int = 2`.
  - Test: `test_raid_profile`. Two synthetic ranges, each with a low raid then an up exit: +1.

### 115. B5-style-timeframe-mapping
- **rule_id / kind:** B5 / missing_rule. Scope: general. judgment = false.
- **Rule:** Position = monthly. Trend = monthly + weekly direction, long holds. Swing = weekly (1-2 setups per quarter) or daily intermediate-term. Short-term = the weekly range, held ~1-5 days. Day trade = 4h and below, an intraday swing exited by 14:00 NY. Bot: entries <= 4h, bias from daily and above.
- **Sources:** cc03_001_UF5J0nEBc0E ~00:17:11.
- **Quote:** "you're trading the weekly ranges and you're holding for typically about one to five days"
- **Conflicts:** none.
- **Rulebook fix:** B5: add the style/timeframe table. Text-only: the bot already matches (entries <= 4h, bias from htf.table daily/weekly, flat intraday). No build spec.

### 116. B5-monthly-first-hierarchy
- **rule_id / kind:** B5 / unlisted_contradiction. Scope: general. judgment = true.
- **Rule:** htf_bias_tf in {M, W}: take the monthly draw. If the monthly is unclear, use the weekly; if both are unclear, there is no HTF bias. Daily moves against it are retracements. Project monthly/weekly OBs and levels onto the daily/intraday and rank them above daily-only levels. Note the conflict with B5's 2023 'weekly first'.
- **Sources:** cc04_003 ~00:14:07; cc04_002 ~00:29:38; cc03_004 ~00:13:48; cc03_002 ~00:28:08.
- **Quote:** "if you can't ascertain where the Market's going on a monthly you just simply drop down into a weekly chart"
- **Conflicts:** B5 ("weekly first").
- **Rulebook fix:** B5: list monthly-first (CC) vs weekly-first (2023) as a Decision.
- **BUILD SPEC (bias_htf):**
  - Needs item 71's monthly arrays. Add `htf_bias_tf: str = "D"` ("D" current / "W" / "M").
  - For "M": the bias = sign(monthly draw - price) from the monthly arrays. When it is 0, fall back to weekly, then 0.
  - With `htf_rank_tf`, `_targets` sorts equal-distance rungs M > W > D.
  - Test: `test_htf_bias_tf_monthly`. A monthly bull draw with a weekly bear draw: bias +1 under "M" and -1 under "W".

### 117. B17-hold-bias-most-recent-htf-setup
- **rule_id / kind:** B17 / missing_rule. Scope: general. judgment = true.
- **Rule:** Bias = the direction of the most recent monthly/weekly/daily setup; a missed entry does not cancel it. Hold it until the terminus/target is hit (then neutral, B17) or price clearly proves it wrong. Use the existing B8 close-based flips as the codeable invalidation. Expect HTF draws to take up to ~3-6 months.
- **Sources:** cc03_001 ~00:21:17, ~00:42:43; cc05_002 ~00:22:06.
- **Quote:** "you hold on to that bias until clearly ... you're showing that you're wrong"
- **Conflicts:** none.
- **Rulebook fix:** B17/B9: add "latest HTF setup's bias persists; missed entries don't cancel it; 3-6 months horizon".
- **BUILD SPEC (bias_htf):**
  - This is what the `flip` column does (persistent state). New: the terminus.
  - Store `flip_target` = the draw at the time of the last flip. When it is traded, the state becomes 0 (with `p.flip_terminus`).
  - Expiry after `flip_max_days` = 126 sessions (~6 months) [our interpretation].
  - Params: `flip_terminus: bool = False`, `flip_max_days: int = 126`.
  - Test: `test_flip_terminus`. A flip +1 with a target of 4200: state 0 the session after 4200 is traded, and 0 after 126 sessions untouched.

### 118. NEW-no-return-to-origin-ob
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = false.
- **Rule:** After repeated tests of a daily low (sell-side run, lower low, retest held) followed by a daily break above the old high, do not wait for price to return to the origin low/OB. Cancel limits there and buy retracements at the swing's lower grades or equilibrium (OBs/FVGs above the origin), targeting buy-side liquidity above the next old high. Mirror for bearish.
- **Sources:** cc03_003_t2VNzJZ4hK4 ~00:21:37.
- **Quote:** "institutional sponsorship should protect price from ever coming back down"
- **Conflicts:** none.
- **Rulebook fix:** New rule under B10/L14 (cc03_003 ~21:37).
- **BUILD SPEC (entries_stops_sizing):**
  - HTF-array entries (turtle-soup `cc_limit` / `external` variants, ts arrays): with `p.no_origin_retest`, after a daily close above the last daily pivot high that followed >= 2 tests of the same daily low (within `eq_tol_pts` x 4), drop the origin daily OB/low from the candidate entry arrays. Prefer arrays between the swing's 25% and 50%.
  - Params: `no_origin_retest: bool = False`.
  - Test: `test_no_origin_retest`. A double-tested low at 4000 and a break of 4080: the 4000 OB is not an entry array, and an FVG at 4030 is.

### 119. B18-htf-daily-smt
- **rule_id / kind:** B18 / missing_rule. Scope: general. judgment = true.
- **Rule:** Daily index SMT (ES/NQ/YM; SPX/NDX in data):
  - When two indices make a lower low on the daily and one fails to, set a bullish intermediate bias while that low holds.
  - In seasonally bullish windows (Feb-May, Oct-Jan), treat it as a trend change. Between spring and fall (May-Aug), treat it as short-term only.
  - Bearish mirror (one fails to make a higher high) = distribution, strongest in bearish windows (Jan, May-Jul).
  - Bias/context tag only, never a trigger; 'if it's not obvious, it isn't there'.
  - The 90m/15-18 day lookback and 4h/midnight-open execution details come from FX/rates lessons and are optional extrapolations.
- **Sources:** cc03_005 ~00:19:41; cc04_001 ~00:11:04; cc10_016 ~00:03:53; cc11_003 ~00:23:40; cc10_017 ~00:03:38; cc10_015 ~00:11:42; cc12_003 ~00:22:04.
- **Quote:** "when the three averages are making lower lows ... one of those averages are going to fail to make a lower low so that signals the overall Market Trend change"
- **Conflicts:** B18 (intraday / PD array only).
- **Rulebook fix:** B18: add the daily SMT as a context tag with the seasonal weighting.
- **BUILD SPEC (bias_htf):**
  - In `backtest`, with both instruments' daily frames, compute `dsmt` per day: within the last 18 sessions, instrument A's low < its prior pivot low while B's low > B's prior pivot low -> +1, valid while that higher low holds. Mirror.
  - Pass it via `day_kwargs` into `run_day` as `ctx.dsmt`.
  - With `p.dsmt_bias`, use it as `want` when `want == 0`. Tag `dsmt_season` from item 60 (trend vs short-term).
  - Params: `dsmt_bias: bool = False`.
  - Test: `test_daily_smt`. ES makes a lower daily low and NQ a higher low: dsmt +1 until NQ's low breaks.

### 120. B18-benchmark-divergence
- **rule_id / kind:** B18 / B19, missing_rule. Scope: needs_unavailable_data. judgment = true.
- **Rule:** Daily chart or higher only. Benchmark (Dow/YM for stocks, DXY for FX, CRB possible) vs the underlying.
  - Distribution (sell program): the benchmark makes a higher high while the underlying (or ES/NQ) makes a lower high. For an inverse benchmark: the underlying makes a higher high while the benchmark makes a higher low, or the benchmark makes a lower low while the underlying makes a lower high.
  - Accumulation (buy program): the mirror cases.
  - An underlying lower low against an inverse benchmark's lower high is a daily turtle-soup long.
  - A 'higher high' must exceed every institutional reference high in the look-back, not only the last swing.
  - For index futures this needs YM/DJI daily data.
- **Sources:** cc04_001 ~00:06:27; cc05_001 ~00:10:44, ~00:13:41, ~00:49:28.
- **Quote:** "that is a warning sign that you're probably in a distribution cycle"
- **Conflicts:** none.
- **Rulebook fix:** B18: add the benchmark configurations. No build spec (DJI daily not loaded).

### 121. B19-bond-stock-dxy-sign
- **rule_id / kind:** B19 / unlisted_contradiction. Scope: general. judgment = true.
- **Rule:** Record the sign conventions as source-tagged alternatives, not one rule:
  - (a) Bonds move with stocks (B19; cc05_009).
  - (b) Bonds up = risk-off, stocks down (cc10_019).
  - (c) Bonds up -> USD down / bonds down -> USD up (cc10_009; cc03_006).
  - (d) DXY up with stocks and bonds up (cc05_009, the long-term textbook relationship) vs DXY up = risk-off for ES (2023 intraday).
  
  Add a Decision entry. Use these as tags only until tested; note the Nov 2016 election as a documented deviation.
- **Sources:** cc10_019 ~00:02:37; cc10_009 ~00:14:33; cc05_009 ~00:08:31; cc03_006 ~00:09:56.
- **Quote:** "US dollar Index if it's going higher or rallying this is also seen with stocks and bonds moving up"
- **Conflicts:** B19; 095.
- **Rulebook fix:** B19: replace the single convention with (a)-(d) and add a Decision.
- **BUILD SPEC (bias_htf):**
  - In `INTERMARKET`, add `spx_tnx_corr` / `spx_dxy_corr` = the 20-day rolling correlation of daily returns (prior day only; TNX yield inverted to a bond-price proxy). Tag `Trade.im_regime` from their signs.
  - Report outcomes by tag in `report_decisions.py` (decision "B19_sign"). No gate.
  - Test: `test_intermarket_corr_prior_day`. The correlation for date d uses data up to d-1 only.

### 122. E4-daily-one-way-delivery-rebalance
- **rule_id / kind:** E4 / shortened. Scope: general. judgment = true.
- **Rule:** Daily chart: a leg delivered one way (consecutive down-close candles from the last up-close candle U) is an inefficiency. Expect price to rebalance it by trading back up through the leg into U's range (U = the draw / target). Mirror for an up-only leg. Treat it as a draw/target tag (single CC example), not an entry trigger.
- **Sources:** cc03_007_o8NfSK-pUlE ~00:23:41.
- **Quote:** "price has to be efficiently balanced"
- **Conflicts:** none.
- **Rulebook fix:** B1: add the one-way-delivery rebalance draw.
- **BUILD SPEC (bias_htf):**
  - In `htf._arrays` (daily): when >= `oneway_n` consecutive down-close days follow an up-close day U, add an `Arr("bear", "oneway", "D", U.high, U.low, mid, known)` as a draw candidate (the rebalance target). Mirror.
  - It is in the draw list only; nothing gates on it.
  - Params: `oneway_n: int = 0` (0 = off; test 4).
  - Test: `test_oneway_rebalance_array`. Up day U, then 4 down days: an array at U's range, known the day after the 4th.

### 123. M12-classic-patterns-fade
- **rule_id / kind:** M12 / missing_condition. Scope: general. judgment = true.
- **Rule:** Classic H&S / inverse H&S are treated as genuine only at intermediate or long-term extremes.
  - When HTF order flow is bullish, a H&S neckline break = a turtle-soup long at the sell stops under the neckline lows, first target the buy stops above the head.
  - When HTF is bearish, an inverse H&S neckline break = a run on buy stops to short; target the sell stops below the head.
- **Sources:** cc03_008_w8lbrvZXUVY ~00:02:29.
- **Quote:** "our higher time frame premise indicates the opposite direction"
- **Conflicts:** none.
- **Rulebook fix:** M12: add the classic-pattern fade.
- **BUILD SPEC (setups_models):**
  - Add detector `levels.head_shoulders(h, l, pivots)`: three pivot highs with the middle one highest and the shoulders within 25% of the head-to-neckline height [our interpretation]. The neckline is the two intervening lows.
  - In the turtle-soup branch (`_turtle`, `turtle_soup="external"`), with `p.hs_fade` and `want == +1`, the neckline-low cluster is an extra external level. T1 = the head high. Mirror.
  - Params: `hs_fade: bool = False`.
  - Test: `test_hs_fade_level`. A synthetic 15m H&S with the neckline at 4000 and the head at 4030: with want +1, a sweep of 3999.75 arms a turtle long with T1 4030.

### 124. X3-a15-mitblock-bear-context
- **rule_id / kind:** A15 / missing_condition. Scope: general. judgment = true.
- **Rule:** Take a bearish mitigation block only when the longer-term (HTF) expectation is lower and untapped sell-side liquidity (a lower HTF support level) remains below. Target that sell-side / HTF support. Mirror for bullish.
- **Sources:** cc04_004_FOUzW0QmsfI ~00:06:44.
- **Quote:** "there's an unrealized lower support level for sell side liquidity that has not been tapped"
- **Conflicts:** none.
- **Rulebook fix:** A15: add the bias + untapped-draw condition.
- **BUILD SPEC (setups_models):**
  - Wherever mitigation blocks are used as entries/targets (A15 `mit_targets` built in levels_detectors), with `p.mit_needs_bias`, accept a bear mitigation-block entry only when `want == -1` and an untaken daily pool or daily bull array lies below. Its target is that level.
  - Params: `mit_needs_bias: bool = False`.
  - Test: `test_mit_needs_bias`. A bear mit block with want 0 is rejected. With want -1 and a PDL below, it is accepted with T = PDL.

### 125. X3-l8-vb-exhaustion-gap
- **rule_id / kind:** L8 / missing_rule. Scope: index. judgment = true.
- **Rule:** A bullish vacuum block is valid when the bias is bullish and the gap opens up away from a discount, after a retracement within an uptrend. A gap up after a multi-day/week rally (prolonged uptrend) may be an exhaustion gap: tag it and do not treat it as a bullish VB. Mirror for bearish.
- **Sources:** cc04_009_shPGUz9pU-A ~00:02:48.
- **Quote:** "this could potentially be an exhaustion gap"
- **Conflicts:** none.
- **Rulebook fix:** L8: add the validity condition and the exhaustion tag.
- **BUILD SPEC (levels_detectors):**
  - `levels.vacuum_block` / `vacuum_blocks` are built. Add the classification at use. With `p.vb_context`, a bullish VB is used only when `want == +1` and the gap's lower edge is below the 20-day range EQ (discount).
  - When the prior 5 daily closes were all up (or above the 20-day high), tag it `exhaustion` and do not use it.
  - Params: `vb_context: bool = False`.
  - Test: `test_vb_context`. A gap up after 5 up days is tagged exhaustion and dropped. A gap up from below EQ after a pullback is kept.

### 126. X3-graduated-pricing-second-touch
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** Tag: institutional repricing is graduated. After price runs away from a level, the return often tests it more than once (the second pass may poke a few ticks beyond). A second test followed by bearish candles that leave a gap/void = a sell limit inside that gap. Mirror. Use it as a confluence tag from one CC example, not a mandatory touch count.
- **Sources:** cc04_010_HTQgH11W37o ~00:11:24.
- **Quote:** "it can't be done on the first pass"
- **Conflicts:** none.
- **Rulebook fix:** New L note (cc04_010 ~11:24).
- **BUILD SPEC (setups_models):**
  - At the sweep in `_scan_core`, count the earlier touches of the swept level within `eq_tol_pts` x 4 since it formed. Tag `Trade.touch_n`. No gate.
  - Test: `test_touch_count_tag`. A level touched at 09:40 and swept at 10:05: touch_n = 2.

### 127. X3-indicators-contrarian-only
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = false.
- **Rule:** Oscillators (e.g. stochastic divergence) are never entry signals. At most they tag retail expectation, to be faded when institutional order flow points the other way. Note the tension with B20's weekly Williams %R, used as an optional enhancer.
- **Sources:** cc04_013_Xae0VrbkyFk ~00:21:33.
- **Quote:** "only draw a contrasting view"
- **Conflicts:** B20 Williams %R enhancer.
- **Rulebook fix:** New rule as written. Text-only: the engine uses no oscillator as a signal (B20.3 `wpr_tag` stays a tag). No build spec.

### 128. X3-b21-ipda-anchor
- **rule_id / kind:** B21 / unlisted_contradiction. Scope: general. judgment = true.
- **Rule:** ipda_anchor in {rolling (from yesterday; cc09_008, cc05_003 ~1:20:41), last_closed_month (the first trading day of the most recent closed calendar month; cc05_001), swing_date (the intermediate high/low or MSS within the last 60 days; cc05_001 ~26:56), quarterly_shift}. LB20/40/60 are counted in trading days to the left of the anchor and record their extremes, gaps and arrays. 20/40/60 days to the right of the anchor time the next shift. Add as a Decision item; keep rolling as the default until tested.
- **Sources:** cc05_001 ~00:53:44, ~00:23:23, ~00:26:56; cc05_003 ~00:19:10.
- **Quote:** "the 60 the 40 and the 20 trading days left of the most recent calendar month put your vertical line on that"
- **Conflicts:** B21 rolling; cc05_003 ~1:20:41 rolling.
- **Rulebook fix:** B21: add the anchor Decision.
- **BUILD SPEC (levels_detectors):**
  - `ipda_pools` is built (rolling, 61-session history). Add `ipda_anchor: str = "rolling"` ("rolling" / "month" / "swing").
    - "month": the windows end on the session before the first trading day of the last closed month.
    - "swing": they end on the last daily MSS (item 84's `q_days` anchor).
  - Test: `test_ipda_anchor_month`. On 2023-11-14, the "month" windows end on 2023-09-29 (the session before Oct 2).

### 129. B21-ipda-windows-arrays
- **rule_id / kind:** B21 / shortened. Scope: general. judgment = false.
- **Rule:** Windows count trading days, skipping Sunday sessions; yesterday = day 1; they roll forward daily. 60 days is the primary look-back (about average; further look-backs occur at times). Collect PD arrays (OBs, FVGs, voids, breakers, rejection blocks, old highs/lows) inside Range60, tagged by window. Day trading/scalping works in Range20; go to 40 (then 60) only when every 20-day array has already been traded through.
- **Sources:** cc05_001 ~00:22:58; cc07_005 ~00:14:17; cc09_008 ~00:08:47.
- **Quote:** "for day trading you're going to operate in those last 20 days most of the time"
- **Conflicts:** none.
- **Rulebook fix:** B21: add the Sunday rule, the array collection and Range20 first.
- **BUILD SPEC (levels_detectors):**
  - `ipda_pools` / `ipda_next` handle the extremes. New: arrays by window.
  - In `htf.table`, tag each daily array `Arr` with `ipda_w` in {20, 40, 60} by the age of `known` (in trading sessions; the `sessions()` frame already excludes the Sunday session). With `p.ipda_arrays_first20`, the conf/target lists use only `ipda_w == 20` arrays until all of them are traded through, then 40, then 60.
  - Params: `ipda_arrays_first20: bool = False`.
  - Test: `test_ipda_array_windows`. A 30-session-old FVG is excluded while an untraded 10-session-old FVG exists, and included after that one is traded.

### 130. X3-iof-60day-framing-raids
- **rule_id / kind:** B6 / missing_rule. Scope: general. judgment = true.
- **Rule:** Over the last 60 trading days:
  - Net up -> frame off the 60-day low (the sell stops below are the reference). Net down -> frame off the high.
  - Track which side's 20-day highs/lows keep getting taken. Buy stops taken repeatedly and sell stops rarely = bullish IOF: no shorts. Mirror for bearish.
  - Hold until an obvious change in direction.
  - Any numeric raid-count threshold is a bot parameter, not ICT's.
- **Sources:** cc05_001 ~00:26:08; cc05_004 ~00:23:59.
- **Quote:** "you don't want to be selling short in those conditions"
- **Conflicts:** none.
- **Rulebook fix:** B6: add the 60-day raid-side framing.
- **BUILD SPEC (bias_htf):**
  - Add `htf.table` column `raid_side60`: over the last 60 sessions, count daily highs that took a prior 20-day high vs lows that took a prior 20-day low. +1 when highs >= `raid_ratio` x lows and highs >= 2; mirror; else 0.
  - With `p.raid_side_gate`, block orders against it.
  - Params: `raid_side_gate: bool = False`, `raid_ratio: float = 2.0` [our interpretation].
  - Test: `test_raid_side60`. 5 new 20-day highs and 1 new 20-day low: +1, and shorts are blocked.

### 131. X3-b22-shift-trigger-quarter-bias
- **rule_id / kind:** B22 / missing_condition. Scope: general. judgment = true.
- **Rule:** Above the 60-day high: sell stops starting to be taken, or a daily short-term-low break (market structure break), = a probable bearish quarterly shift. Expect a correction or a sideways consolidation for about the next 3 months; rallies are sells. Anchor on the most obvious recent shift only (it may be up to 3 months back). Mirror below the 60-day low.
- **Sources:** cc05_001 ~00:32:36; cc05_004 ~00:16:53; cc05_003 ~00:16:01.
- **Quote:** "if you start seeing cell stops get taken out we're probably making a quarterly shift"
- **Conflicts:** none.
- **Rulebook fix:** B22: add the trigger and the post-shift quarter bias.
- **BUILD SPEC (bias_htf):**
  - Make the trigger of rule_coverage's `qshift_tag` concrete. While the price made a new 60-day high within the last 10 sessions, a daily low below the last daily STL (`levels.swing_tiers` "stl") sets `qshift = -1`. It persists 63 sessions or until a new 60-day high. Mirror.
  - With `p.qshift_bias`, `want` defaults to `qshift` when otherwise 0.
  - Params: `qshift_bias: bool = False`.
  - Test: `test_qshift_trigger`. A new 60-day high, then an STL break 3 days later: qshift -1 for 63 sessions.

### 132. X3-b21-draw-side-and-flip
- **rule_id / kind:** B21 / missing_condition. Scope: general. judgment = false.
- **Rule:** Bearish daily structure: the draw = the 20-, then 40-, then 60-day lows. If price rejects before the next low and breaks daily structure bullish, treat it as a quarterly shift: the new draws are the 20/40/60-day highs and the buy stops above the 3-month high. Mirror. (Drop the 'one major run per quarter' clause; B22 covers cadence.)
- **Sources:** cc05_003 ~01:24:00; cc05_002 ~00:04:10.
- **Quote:** "you have a quarterly shift now it's bullish start finding the highs"
- **Conflicts:** none.
- **Rulebook fix:** B21: tie the draw side to daily structure and add the flip.
- **BUILD SPEC (bias_htf):**
  - `ipda_next` (built) gives the next 20/40/60 extreme. Add `ipda_side` = sign of the last daily MSS (`last_break`, item 108). With `p.ipda_draw_side`, the lock candidate is `ipda_next` on that side.
  - A bullish daily MSS after a 20-day-low raid that stops short of the 40-day low switches the side and sets item 131's `qshift = +1`.
  - Params: `ipda_draw_side: bool = False`.
  - Test: `test_ipda_draw_side`. A bearish structure gives the 20-day low as the draw. After a bullish MSS, the draw is the 20-day high.

### 133. X3-b22-shift-form-strong-trend
- **rule_id / kind:** B22 / missing_condition. Scope: general. judgment = true.
- **Rule:** In a strong primary trend, the quarterly change usually shows as a consolidation/trading range, or at most one run below a daily short-term low (mirror: above a short-term high), then continuation. Otherwise expect an intermediate-term retracement.
- **Sources:** cc05_001_n7SPAK_tpN8 ~00:07:35.
- **Quote:** "you won't see much of a retracement but you will see consolidation"
- **Conflicts:** none.
- **Rulebook fix:** B22: tie the shift's form to trend strength.
- **BUILD SPEC (bias_htf):**
  - When item 131 fires `qshift` against a strong trend (the 252-day trend from rule_coverage B22, with price above the 252-day mean by > 10% [our interpretation]), set `qshift_form = "consol"`: do not change `want`, mark the next 20 sessions `scalp`. Otherwise "retrace" (item 131 behaviour).
  - Params: `qshift_strong_consol: bool = False`.
  - Test: `test_qshift_form`. A shift trigger during a strong uptrend gives "consol" with want unchanged.

### 134. X3-shift-due-six-months
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** Tag shift_due after ~6 months of one-directional movement without a quarterly shift (a single-example observation; context only, it can coincide with seasonals).
- **Sources:** cc05_001_n7SPAK_tpN8 ~00:48:36.
- **Quote:** "that's about when you're going to see the shake-up"
- **Conflicts:** none.
- **Rulebook fix:** B22: add the tag.
- **BUILD SPEC (bias_htf):**
  - Add `htf.table` column `shift_due` = `q_days` (item 84) >= 126 with the 126-day net move in one direction. Tag only.
  - Test: `test_shift_due`. 130 sessions since the last daily MSS on a rising path: True.

### 135. X3-b6-tug-of-war-new-ground
- **rule_id / kind:** B6 / missing_condition. Scope: general. judgment = true.
- **Rule:** Daily: rallies take short-term highs but fail to make new ground (punished at once), intermediate-term highs step lower, and short-term lows keep breaking lower = a bearish bias; the draw = sell-side liquidity below (the lows of the open-float range). Mirror for bullish.
- **Sources:** cc05_002_BkmZgjuYREU ~00:16:12.
- **Quote:** "every time it rallies it fails to make a new high"
- **Conflicts:** none.
- **Rulebook fix:** B6: add the new-ground test.
- **BUILD SPEC (bias_htf):**
  - Shares item 109's tier logic. Add a component: `no_new_ground` = the last 2 daily STH raids each closed back below the raided high within 1 session. Column `tug = -1` when `no_new_ground` and `tier_regime == -1`. Mirror.
  - Feeds the same gate (`tier_regime_gate` with `p.tug_required`).
  - Params: `tug_required: bool = False`.
  - Test: `test_tug_of_war`. Two STH raids, each closing back below, plus lower ITHs: tug -1.

### 136. X3-one-sided-delivery-first-clue
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** While price is being drawn to an HTF buy-side pool, short-term lows hold. After that pool is raided with strong rejection, the first short-term-low break is the first clue of a flip to sell-side. Confirm with the new-ground/tug-of-war test. Mirror.
- **Sources:** cc05_002_BkmZgjuYREU ~00:13:28.
- **Quote:** "there wasn't any significant move on sell stops at all"
- **Conflicts:** none.
- **Rulebook fix:** New B note (cc05_002 ~13:28).
- **BUILD SPEC (bias_htf):**
  - Add `htf.table` column `first_clue` (-1 / +1 / 0): -1 on the first daily STL break after a raid of the HTF draw level (draw hit) when no STL had broken during the run to it. Tag only. With `p.first_clue_neutral`, it sets the state to 0 until item 135 confirms.
  - Params: `first_clue_neutral: bool = False`.
  - Test: `test_first_clue`. A run with no STL breaks into the draw at 115, then an STL break: first_clue -1.

### 137. X3-a21-eq-after-raid
- **rule_id / kind:** A21 / missing_rule. Scope: general. judgment = true.
- **Rule:** After an HTF raid and rejection, once price has failed to make new ground on rallies and is making lower short-term lows, a new extreme beyond the raided high is unlikely, especially once price is back at the range EQ: block longs targeting beyond the raided high. Mirror.
- **Sources:** cc05_002_BkmZgjuYREU ~00:15:30.
- **Quote:** "the chances of this creating a higher ... is not likely"
- **Conflicts:** none.
- **Rulebook fix:** A21: add the post-raid EQ note.
- **BUILD SPEC (targets_partials):**
  - With `p.post_raid_cap`, when `first_clue == -1` or `tug == -1` (items 135-136) and the price is at or below the EQ of the range ending at the raided high, drop long target rungs above the raided high. Mirror.
  - Test: `test_post_raid_cap`. Raided high 115, range EQ 110, price 109, tug -1: a long's ladder ends below 115.

### 138. X3-60day-low-deep-discount-bounce
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** In bearish IOF, price at the 60-day low is in deep discount: avoid fresh shorts there and expect a sizeable bounce (size not given beyond an FX example of 150-200 pips). Re-sell once the bounce rolls over if sell-side raids continue. Mirror.
- **Sources:** cc05_004_vqtA1S9JH34 ~00:24:29.
- **Quote:** "we're going to be in deep discount"
- **Conflicts:** none.
- **Rulebook fix:** New B note (cc05_004 ~24:29).
- **BUILD SPEC (bias_htf):**
  - With `p.ipda_extreme_pause`, on days whose prior low was within 0.25 x ADR5 of (or below) the prior 60-day low, block shorts for that session. Mirror. Uses `ipda_pools` levels.
  - Test: `test_ipda_extreme_pause`. Prior low at the 60-day low: shorts are blocked the next day.

### 139. B19-four-asset-risk-map
- **rule_id / kind:** B19 / shortened. Scope: general. judgment = true.
- **Rule:**
  - Risk-on: stocks up, DXY down, foreign currencies up, commodities up. Risk-off is the mirror.
  - When the four asset classes are not moving in harmony, treat it as a decoupling (uncertainty: expect smaller moves, hold for less).
  - [fx-only] DXY moves with USDCHF, USDJPY and USDCAD (ignore USDCAD when oil is the driver) and against EURUSD and GBPUSD. Gold up means AUD/NZD up and DXY down. Oil up means USDCAD down; gold down means USDCAD up.
  - Caveat: the USD-commodity inverse can fail for periods of up to a year, so treat it as a soft confirmation, not a hard gate.
- **Sources:** cc10_019 ~00:06:41; cc11_001 ~00:15:40; cc05_001 ~00:17:35; cc05_009 ~00:15:12.
- **Quote:** "there can and will be periods lasting as long as a year when commodity prices and the US dollar move in tandem"
- **Conflicts:** none.
- **Rulebook fix:** B19: add the four-asset map and the decoupling consequence. Add the FX links under [fx-only].
- **BUILD SPEC (bias_htf):**
  - The available legs are stocks (the instrument's daily), DXY and TNX. Commodities are not loaded; leave a hook `ctx.intermarket.get("crb")`.
  - Compute `im_harmony` = the instrument's 20-day trend sign == -dxy (and == crb when present). When False, tag `decoupled`. With `p.decoupled_scalp`, mark orders `scalp`.
  - This complements rule_coverage B17.5 "decoupled tag/scalp/skip" (an index-vs-index measure) with the cross-asset version.
  - Params: `decoupled_scalp: bool = False`.
  - Test: `test_im_harmony`. SPX up with DXY up: decoupled and scalp-tagged.

### 140. X3-fx-vs-dxy-smt
- **rule_id / kind:** B18 / missing_rule. Scope: fx_only. judgment = false.
- **Rule:** [fx-only] Long a foreign currency or metal at a discount array when DXY is bearish, or when DXY makes a higher high while the pair or metal holds above its prior low (SMT). Shorting a USD-base pair is the mirror (DXY higher high while USDCHF makes a lower high). Elsewhere (cc05_008, cc06_002) this is a qualifier. In the swing model (cc06_008) it is a required gate: without DXY support, day trade only.
- **Sources:** cc05_008 ~00:11:22; cc06_002 ~00:04:18; cc06_008 ~00:08:37.
- **Quote:** "we had a higher high in the dollar index when we fail to make a lower low in the australian dollar"
- **Conflicts:** cc06_008 (gate) vs qualifier.
- **Rulebook fix:** [fx-only] note. No build spec.

## F. COT, open interest and sentiment

### 141. B20-oi-signal
- **rule_id / kind:** B20 / shortened. Scope: needs_unavailable_data. judgment = true.
- **Rule:** Daily only.
  - Bullish: price consolidating at or near an HTF discount array (ideally after sell stops below an old low are run), OI drops 10-15% or more, and the commercial net line rises (shorts covering).
  - Bearish mirror: consolidating at an HTF premium array, OI rises 10-15% or more, and commercials add net shorts.
  - Otherwise OI is not used.
  - It is a required gate in the FX/metal swing model (cc06_008) and an optional enhancer elsewhere (cc06_002).
  - There is no specified lookback for measuring the % change, so that is [our interpretation].
  - Do not dismiss OI moves around contract roll as artifacts.
- **Sources:** cc05_003 ~00:58:00; cc05_004 ~00:22:42; cc05_007 ~00:05:58; cc06_007 ~00:19:37; cc06_008 ~00:11:55; cc10_005 ~00:07:58, ~00:08:21, ~00:07:09; cc12_003 ~00:11:12.
- **Quote:** "open interest will decline or drop while price is consolidating at or near a higher time frame support"
- **Conflicts:** 10-15% vs 15%; required (cc06_008) vs optional (B20).
- **Rulebook fix:** B20: add the bearish mirror, the consolidation and array conditions, the COT pairing, the daily-only rule and the roll note. No build spec. Rule_coverage B20.2 `oi_tag` is the loader; note there that roll drops are not removed.

### 142. B20-oi-vs-seasonal-average
- **rule_id / kind:** B20 / missing_condition. Scope: needs_unavailable_data. judgment = true.
- **Rule:** An optional OI intensity check: compare OI to its multi-year seasonal average for the same date (ICT says 'the last few years'; 3-5 years is our interpretation). Bullish: OI falls below that average while price consolidates at an HTF discount array and commercials are net long or buying. Bearish: OI above the average while price consolidates at an HTF premium array.
- **Sources:** cc10_005_qRYkTWePXF0 ~00:17:18.
- **Quote:** "it drops down below the seasonal average of open interest"
- **Conflicts:** the % threshold.
- **Rulebook fix:** B20: add as written. No build spec.

### 143. B20-oi-own-market-only
- **rule_id / kind:** B20 / missing_rule. Scope: general. judgment = false.
- **Rule:** Open interest is read only for the market it belongs to. Never infer the bias of market X from OI changes in a related market Y.
- **Sources:** cc10_003_R2NjnYozhdw ~00:39:38.
- **Quote:** "not something that can be shared"
- **Conflicts:** ICT's retracted older teaching.
- **Rulebook fix:** B20: add the rule.
- **BUILD SPEC (bias_htf):**
  - In the B20.2 `oi_tag` loader (rule_coverage), key the OI series by the traded symbol's root (ES -> ES, NQ -> NQ). `run_day` reads only `oi_tag[symbol]`. Add an assert that no cross-symbol lookup exists.
  - Test: `test_oi_tag_own_symbol`. The ES run reads the ES OI only. An NQ-only OI series gives no tag on ES.

### 144. B20-oi-williams-matrix
- **rule_id / kind:** new / missing_rule. Scope: needs_unavailable_data. judgment = false.
- **Rule:** From Williams (cc10_005), daily OI vs price:
  - Trend with rising OI = continuation (both directions).
  - Uptrend with falling OI = a bearish warning.
  - Downtrend with falling OI = bullish (short covering).
  - Range with rising OI = bearish. Range with falling OI = bullish.
  
  Conflict: cc05_003 ~57:50 calls 'rising OI confirms the trend' a misnomer, at least for down markets, so the continuation rows are low confidence. The range rows, at HTF arrays, are the ones ICT actually uses.
- **Sources:** cc10_005_qRYkTWePXF0 ~00:04:16.
- **Quote:** "as long as the open interest is increasing in a major Trend it will have the necessary sponsorship"
- **Conflicts:** cc05_003 ~57:50.
- **Rulebook fix:** B20: add the matrix with the confidence note. No build spec.

### 145. B20-oi-swing-filter
- **rule_id / kind:** B20 / missing_rule. Scope: needs_unavailable_data. judgment = true.
- **Rule:** An OI signal at an HTF array sets the swing/position bias toward the next weekly premium (discount) array. Until that target is reached, favour day trades in the same direction (e.g. bullish days that open near the low, weekly expansion for a higher close). It never triggers a day trade by itself.
- **Sources:** cc10_005_qRYkTWePXF0 ~00:18:29.
- **Quote:** "these open interest ideas are not day trades"
- **Conflicts:** none.
- **Rulebook fix:** B20: add as written. No build spec.

### 146. B20-cot-midpoint
- **rule_id / kind:** B20 / shortened. Scope: needs_unavailable_data. judgment = true.
- **Rule:**
  - MID = (max + min) / 2 of the commercials-only net position over the last 12 months (52 weekly reports), or 6 months (26) if the 12-month range is too narrow to read.
  - Net above MID: favour discount arrays and longs. Below MID: favour premium arrays and shorts.
  - A trade against it waits until the net line crosses back over MID.
  - In the cc06_008 swing checklist, the bearish side also passes when commercials are net short (net < 0). That checklist makes COT a required gate for FX/metal swings; elsewhere it is an optional enhancer (cc06_002).
  - Ignore the cc12_003 ~10:31 'below -> discount' slip.
- **Sources:** cc12_003 ~00:09:38; cc06_007 ~00:17:49; cc06_008 ~00:10:46.
- **Quote:** "you'd have to wait for that red line to go back down below that new zero basis line"
- **Conflicts:** the cc12_003 ~10:31 slip; optional vs required.
- **Rulebook fix:** B20: add the details. No build spec here. Rule_coverage B20.1 already specifies `cot_tag` with the 52-week midpoint; add the 26-week fallback there.

### 147. B20-cot-zero-line-vs-hedging
- **rule_id / kind:** B20 / wrong. Scope: general. judgment = true.
- **Rule:** Store two separate COT states.
  1. program = sign(commercial net): above zero = buy program, below = sell program (macro).
  2. hedging = commercial net vs the midpoint of its 12-month range (6-month fallback if narrow).
  
  A hedging reading against the program (e.g. net below zero but above MID and rising) still permits trades in the hedging direction when daily institutional order flow agrees.
- **Sources:** cc10_001_9H4iaaQXV5Y ~00:08:48.
- **Quote:** "there's a buy program when they're above the zero line"
- **Conflicts:** B20 (cc12_003) merges them.
- **Rulebook fix:** B20: separate "program" (zero line) from "hedging program" (midpoint).
- **BUILD SPEC (bias_htf):**
  - Extend rule_coverage B20.1's `cot_tag` loader to return two columns, `cot_program` (sign of net) and `cot_hedge` (sign of net - MID52, with the MID26 fallback when the 52-week range < 10% of the mean |net| [our interpretation]).
  - Tag both on trades. With `p.cot_gate == "hedge_iof"`, allow an order when `cot_hedge` agrees and the daily `iof` agrees, whatever `cot_program` is.
  - Params: `cot_gate: str = "off"` ("off" / "hedge_iof").
  - Test: `test_cot_two_states`. Net -20k with a 52-week range of -60k..-10k (MID -35k): program -1 and hedge +1.

### 148. B20-cot-data-spec
- **rule_id / kind:** B20 / missing_rule. Scope: general. judgment = false.
- **Rule:**
  - Source: CFTC Commitments of Traders, legacy futures-only short format (exclude options).
  - Net = commercial long - commercial short. Use commercials only, ignoring large and small speculators.
  - Keep at least 12 months of weekly history for the range and midpoint.
  - [our interpretation]: date each report by its public release (Friday, for Tuesday positions) to avoid look-ahead.
- **Sources:** cc10_001_9H4iaaQXV5Y ~00:01:20.
- **Quote:** "you want to be looking at the Futures Contract only in the short format"
- **Conflicts:** none.
- **Rulebook fix:** B20: add the data spec.
- **BUILD SPEC (bias_htf):**
  - Add a new loader `mentorship/cot.py`. It reads the CFTC legacy futures-only annual files (deacot{year}.zip; download is an owner step, data/mentorship/cot/). It filters by the CFTC market code (E-mini S&P 500 13874A, E-mini Nasdaq-100 209742) and keeps `report_date`, `comm_long`, `comm_short`.
  - `known` = report_date + 3 days (the Friday release); the tag is usable from the next session.
  - It feeds B20.1 `cot_tag` and item 147.
  - Test: `test_cot_loader_known_date`. A Tuesday 2023-03-07 report is first usable on 2023-03-13 (the session after Friday 03-10).

### 149. B20-cot-blend-and-grade
- **rule_id / kind:** B20 / missing_condition. Scope: needs_unavailable_data. judgment = false.
- **Rule:** B20 addition: never use COT alone. Blend:
  - (a) program = commercials above (buy) or below (sell) the net zero line;
  - (b) hedging = the commercials' reading inside their own 6- or 12-month high-low range (net-long nodule = buying, net-short = selling);
  - (c) IOF and PD arrays.
  
  Longs: bullish IOF + a discount array + a net-long reading in the 6/12-month range. Shorts: the mirror. Best case: program, hedging and IOF all agree at a matching array. Hedging can run against the program (e.g. short-term selling while above zero), so either side can be traded. Tag only. {d: CFTC COT}
- **Sources:** cc10_001 ~00:32:10, ~00:32:42. The cc07_001 citation does not support it.
- **Quote:** "the best conditions are seen when both net sum basis agree with institutional order flow"
- **Conflicts:** change vs midpoint definitions.
- **Rulebook fix:** B20: add the blend and best case; drop the cc07_001 citation. No build spec (item 147 supplies the tags once data exists).

### 150. B20-cot-divergence-new-high
- **rule_id / kind:** B20 / shortened. Scope: needs_unavailable_data. judgment = false.
- **Rule:** B20 addition: price makes a higher high while commercials sell aggressively into the rally (the net reading falling within its adjusted 6/12-month range, even if still net long on a standard COT chart), and a bearish seasonal agrees -> a bearish premise; the commercial selling caps the rally. Mirror for lows. Optional enhancer, tag only. {d: CFTC COT}
- **Sources:** cc07_008_LBlK6JB0QS0 ~00:19:10.
- **Quote:** "the commercials are actually selling aggressively in that rally"
- **Conflicts:** B20 (optional).
- **Rulebook fix:** B20: add as written. No build spec.

## G. Timeframes, rates regimes and seasonal qualification

### 151. X3-b5-15m-pools-5m-gaps
- **rule_id / kind:** B5 / shortened. Scope: general. judgment = true.
- **Rule:** B5 addition: the daily chart is where institutional orders are read. Liquidity pools are mapped on the 15m. Use the 5m only to find small FVGs that are not visible on the 15m or 1h. Do not map pools from the 1m (cc05_003 ~1:27:21) [CC].
- **Sources:** cc05_003_LRKtiysz4nA ~01:27:21.
- **Quote:** "it's a 15-minute time frame they're looking for liquidity pools"
- **Conflicts:** none.
- **Rulebook fix:** B5: add the timeframe roles.
- **BUILD SPEC (levels_detectors):**
  - Session pools are built from 1m pivots in `DayCtx` / `_sell_side`. Add `pool_tf: int = 1` (test 15). When set, intraday swing pools (not session H/L, PDH/PDL) come from `levels.pivots` on `htf_bars(df, pool_tf)` and are mapped to their 1m extreme price.
  - Test: `test_pool_tf_15`. A 1m micro-pivot that is not a 15m pivot is not a pool with pool_tf=15.

### 152. X3-notes-dollar-regime
- **rule_id / kind:** B22 / missing_rule. Scope: general. judgment = true.
- **Rule:** B22 addition: compare 10Y note futures with DXY.
  - Moving in tandem (same direction) -> a large consolidation regime: expect raids on both ends of the range and back to the middle; short-term and day trades only; no position trades; currencies range too.
  - Notes moving with their seasonal tendency while DXY moves opposite -> a trending regime (multi-week one-direction moves).
  - Classify per quarter.
  - Implementation proxy (ours): the sign of the 20-day slope.
  - Tag only. {d: ZN/FRED 10Y, DXY daily}
- **Sources:** cc05_006_z-7ypchAMDE ~00:10:16, ~00:15:57, ~00:07:11.
- **Quote:** "ten year treasuries and the dollar are moving in the same direction ... long-term indecisiveness"
- **Conflicts:** B19's bonds-ranging test.
- **Rulebook fix:** B22: add the notes-vs-dollar regime.
- **BUILD SPEC (bias_htf):**
  - In `INTERMARKET`, note price direction = -sign(20-day TNX slope) (yield inverse) and dollar direction = sign(20-day DXY slope), both from the prior day.
  - `notes_dxy = "tandem"` when equal, else "opposed". Store it in `ctx.intermarket`. Tag on trades. With `p.tandem_scalp`, mark orders `scalp` on tandem days.
  - Params: `tandem_scalp: bool = False`.
  - Test: `test_notes_dxy_regime`. TNX falling (notes up) with DXY rising: "opposed". TNX rising with DXY falling: "tandem".

### 153. X3-10y-dxy-smt-qualifier
- **rule_id / kind:** B18 / missing_rule. Scope: bonds_only. judgment = true.
- **Rule:** B18 addition (bonds/DXY): 10Y notes and DXY should mirror each other (notes lower low <-> DXY higher high). If one fails to mirror at a swing (e.g. notes make lower lows while DXY makes lower highs), that crack in correlation confirms a reversal in the notes (long notes, bearish DXY). Confirm with yields moving opposite to the note price. Qualifier only, best inside a seasonal window.
- **Sources:** cc05_007_N8_8tEw2_44 ~00:00:54, ~00:02:24.
- **Quote:** "this is a crack and correlation and we have confirmation"
- **Conflicts:** none.
- **Rulebook fix:** B18: add as written (bonds). No build spec.

### 154. X3-seasonal-quarterly-qualifier
- **rule_id / kind:** B23 / missing_condition. Scope: general. judgment = true.
- **Rule:** B23 addition: a seasonal or quarterly-shift idea is qualified by any ONE of: an SMT between DXY and 10Y notes, an interest-rate triad SMT, or an FX pair vs DXY SMT. Once qualified, align swing, short-term, day trades and scalps with that HTF direction (a high-probability filter, not a guarantee).
- **Sources:** cc05_007_N8_8tEw2_44 ~00:08:04, ~00:08:22, ~00:09:04.
- **Quote:** "not that you need both"
- **Conflicts:** none.
- **Rulebook fix:** B23: add the qualification step.
- **BUILD SPEC (bias_htf):**
  - Of the three qualifiers, only the index-relevant proxies can be computed: item 119's daily index SMT (`dsmt`) and item 152's notes/DXY "opposed". Set `season_qualified` = an active window (item 60) whose direction agrees with `dsmt` or with "opposed".
  - With `p.season_gate == "qualified"`, block trades against a qualified window's direction.
  - Params: extend `season_gate` (item 61) with "qualified".
  - Test: `test_season_qualified`. A spring long window with dsmt +1: qualified, and shorts are blocked.

### 155. X3-bond-seasonal
- **rule_id / kind:** B23 / missing_rule. Scope: bonds_only. judgment = true.
- **Rule:** B23 addition (bonds): the 10Y/30Y seasonal.
  - High in Jan-Feb, then weakness into a May-June (10Y: June-July) low = the primary annual long (mega trade). Qualify it with an interest-rate SMT. Target the Sep-Oct intermediate highs (cc05_006 shows a rally into Dec highs), and take day trades in the same direction meanwhile.
  - Sep-Nov: short-term rallies only.
  - If no June-July buy forms, be a bearish note trader and sell the seasonal highs (e.g. November).
  - Not guaranteed every year. {d: ZN/ZB daily}
- **Sources:** cc05_006 ~00:00:44, ~00:16:47; cc11_004 ~00:01:09, ~00:03:08, ~00:08:02.
- **Quote:** "sometime during may and or June every year there's a seasonal low of forms"
- **Conflicts:** none.
- **Rulebook fix:** B23: add as written (bonds). No build spec.

### 156. X3-fx-dxy-crude-seasonal-calendar
- **rule_id / kind:** B23 / missing_rule. Scope: fx_only. judgment = true.
- **Rule:** B23 addition (FX/commodity, tag only; the HTF trend governs):
  - DXY: a Jan-Feb rally into Mar. Either a Mar/Apr high -> May low (cc05_012) or a significant Jun-Jul high (cc05_006). A decline into a late-Oct/early-Nov low. Bull years: buy Jan/May/Nov and sell Mar/Jun-Jul/Sep.
  - AUD, JPY, CAD futures: low Mar-Apr, high May.
  - EUR, CHF futures: low Jun-Jul.
  - NZD: bull years buy Mar-Apr, Jun-Jul, Sep-Oct; bear years sell mid-Feb to mid-Mar, May, Aug.
  - CAD futures: bearish Sep to ~Christmas (USDCAD bullish).
  - Crude: bullish mid-Feb into May-June, with CAD tending to rally alongside.
  - {d: DXY/FX/CL daily}
- **Sources:** cc05_006 ~00:05:51; cc05_012 ~00:02:02; cc05_010 ~00:13:40; cc05_011 ~00:18:24.
- **Quote:** "march april june july september october are really strong buying opportunities when it's bullish"
- **Conflicts:** cc05_006 vs cc05_012 on DXY; CAD dates.
- **Rulebook fix:** [fx-only] B23 note. No build spec.

### 157. X3-seasonal-pair-inversion
- **rule_id / kind:** B23 / missing_rule. Scope: fx_only. judgment = false.
- **Rule:** B23 addition (FX): seasonal charts are futures prices of the non-USD currency. For USD-first pairs (USDCAD, USDJPY, USDCHF), apply the inverse of the currency futures seasonal. For USD-quote pairs (AUDUSD, NZDUSD, EURUSD, GBPUSD), apply it directly. Combined: pair bias = base seasonal minus quote seasonal (with DXY as USD).
- **Sources:** cc05_010 ~00:07:27; cc05_011 ~00:01:33; cc05_012 ~00:09:39.
- **Quote:** "the U.S CAD pair is an inversion of what the Futures Contract shows"
- **Conflicts:** none.
- **Rulebook fix:** [fx-only] note. No build spec.

### 158. X3-ideal-seasonal-opposed-dxy
- **rule_id / kind:** B23 / missing_rule. Scope: fx_only. judgment = true.
- **Rule:** B23 addition (FX): treat a currency seasonal window as 'ideal' only when the currency futures seasonal and the DXY seasonal are diametrically opposed over the same window (one rallies while the other declines). It is still a road map: it does not come true every year, and the HTF trend governs.
- **Sources:** cc05_012_O2Sio7opKxo ~00:01:13.
- **Quote:** "we're looking for the most diametrically opposed price action between the two"
- **Conflicts:** none.
- **Rulebook fix:** [fx-only] note. No build spec.

### 159. X3-seasonal-trend-condition
- **rule_id / kind:** B23 / missing_condition. Scope: general. judgment = true.
- **Rule:** B23 add-on:
  - (a) For a pair, the trend in either leg is enough: either the DXY is in a downtrend or the counter-currency is in an uptrend; both are not required. This is FX-specific; for index futures the analogue is the instrument's own HTF trend.
  - (b) A suspected fresh long-term turn may be tested with a trade. ICT does not specify a smaller size.
  - (c) A bearish window only gives a large decline when the weekly tone and institutional order flow are already bearish (e.g. the index makes higher highs while the stock makes lower highs). In a bullish weekly tone, expect only a minor dip.
  - (d) Prime: bearish months in bear markets and bullish months in bull markets.
  - When they conflict, the underlying trend outweighs the seasonal.
- **Sources:** cc05_012 ~00:12:08, ~00:07:30; cc10_017 ~00:08:49; cc10_015 ~00:09:42.
- **Quotes:** "you only really need one"; "it has to be a bearish market tone on a weekly basis"
- **Conflicts:** none.
- **Rulebook fix:** B23: add (a)-(d).
- **BUILD SPEC (day_week_context):**
  - Tag `season_prime` when an active window's direction (item 60) equals the weekly flip state (computed on weekly bars; item 85 `iof_w` if built, else `wk_dc`). Tag `season_minor` when they differ: expect only a minor move; with `p.season_gate`, the window gives no gate. Report by tag.
  - Test: `test_season_prime`. A May short window with a bearish weekly state gives prime. With a bullish weekly state it gives minor.

### 160. X3-seasonal-strength-grading
- **rule_id / kind:** B23 / shortened. Scope: general. judgment = true.
- **Rule:** B23 add-on: beyond line agreement (already in B23), take only seasonal windows whose composite shows a sizable price swing. Be selective and trade only the highest-probability, strongest windows, not every window in every market. ICT gives no numeric threshold; any cutoff such as the top third is an owner choice.
- **Sources:** cc05_010 ~00:17:14; cc05_011 ~00:11:29; cc05_012 ~00:06:56.
- **Quote:** "I loaded up the boat and traded way too many things"
- **Conflicts:** gate vs grade.
- **Rulebook fix:** B23: add the sizable-swing and selectivity requirement.
- **BUILD SPEC (day_week_context):**
  - Build a composite from the instrument's own history (`BT` daily closes, all years before the test year only, so there is no look-ahead): the mean % move per window. Grade each window by its composite size rank.
  - With `p.season_min_rank` (0 = off; e.g. 0.67 = top third), windows below it give no tag/gate.
  - Test: `test_season_strength_rank`. The composite uses only years < the test year, and a weak window is dropped with min_rank 0.67.

### 161. X3-seasonal-regime-picks-window
- **rule_id / kind:** B23 / missing_condition. Scope: general. judgment = false.
- **Rule:** B23 add-on: the HTF regime decides which windows are favored. In a bullish regime, bullish windows are the trades. Opposing (bearish) windows are either skipped or used as the expected pullback that leads into the next bullish window / quarterly-shift low, where you buy. Mirror in a bearish regime.
- **Sources:** cc05_011_Vb6ueaPqut0 ~00:17:37, ~00:15:45.
- **Quote:** "one seasonal tendency is going to be favored over the other"
- **Conflicts:** none.
- **Rulebook fix:** B23: add as written.
- **BUILD SPEC (day_week_context):**
  - With `p.season_gate`, a window acts only when its direction equals the 252-day trend (rule_coverage B22's trend). An opposing window is tagged `season_pullback` (no gate; report the next window's outcome).
  - Test: `test_season_regime_pick`. A bull regime with a May short window gives season_pullback and no gate.

### 162. X3-seasonal-macro-override
- **rule_id / kind:** B23 / missing_condition. Scope: general. judgment = true.
- **Rule:** B23 add-on: a dominant big-picture macro regime (e.g. the 2008 crisis, with one-way risk-off) overrides seasonal expectations. Do not take seasonal windows that oppose it.
- **Sources:** cc05_011_Vb6ueaPqut0 ~00:22:19.
- **Quote:** "larger big picture macro events that are going to take precedence"
- **Conflicts:** none.
- **Rulebook fix:** B23: add the override.
- **BUILD SPEC (day_week_context):**
  - Use the same manual flag file as item 72 (`macro_risk_dates`, with a direction column). Seasonal windows opposing a flagged direction are disabled (no tag/gate).
  - Test: `test_season_macro_override`. A flagged risk-off period disables a long window.

### 163. X3-seasonal-consolidation-breakout
- **rule_id / kind:** B23 / missing_rule. Scope: general. judgment = true.
- **Rule:** B23 add-on: if price consolidates through a bearish seasonal window and then breaks up out of the range, the bearish seasonal has failed. Expect upside continuation and look for the next bullish window. Mirror for bullish windows. Retracement depth is not specified.
- **Sources:** cc05_011_Vb6ueaPqut0 ~00:27:33.
- **Quote:** "we're looking for continuation on the upside"
- **Conflicts:** none.
- **Rulebook fix:** B23: add as written.
- **BUILD SPEC (day_week_context):**
  - Extend item 62's `season_result`: "consol" followed by a daily close above the window's range high within 10 sessions after the window ends gives "failed_up". Tag the next 20 sessions; with `p.season_gate`, longs are favoured (no shorts on those days).
  - Test: `test_season_failed_up`. A flat May window, then a June close above the May high: failed_up.

### 164. X3-full-confluence-stack
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** New rule: the highest-quality HTF/position trade is one where the seasonal window, the HTF trend, the time of day, rates/yields and the DXY all agree. Restrict position trades to this full stack and accept few trades per year.
- **Sources:** cc05_011_Vb6ueaPqut0 ~00:30:51.
- **Quote:** "interest rates are supporting that bullish idea"
- **Conflicts:** none.
- **Rulebook fix:** New rule as written.
- **BUILD SPEC (bias_htf):**
  - Add `Trade.stack` = count of agreeing factors: the season window (item 60), the flip state, kill-zone timing (existing session tags), `rates_tag` (item 94) and `dxy` (inverse). Report by stack count.
  - With `p.stack_min` (0 = off), skip orders below it.
  - Test: `test_stack_count`. A long in a spring window with flip +1 in the AM kill zone, tnx falling and dxy -1: stack 5.

### 165. X3-macro-bias-few-factors
- **rule_id / kind:** B20 / missing_condition. Scope: fx_only. judgment = true.
- **Rule:** B20 add-on (FX): reaching HTF support is not by itself a reason to buy. Require a few (roughly 2+) macro confirmations in agreement: OI drop / short covering, seasonal, rate differential (weighted highest), COT commercials, intermarket/SMT. All of them are not required. Mirror at resistance.
- **Sources:** cc05_008 ~00:09:24; cc06_003 ~00:11:26.
- **Quote:** "you just need a small sample size of a few things in agreement"
- **Conflicts:** none.
- **Rulebook fix:** [fx-only] B20 note. No build spec.

## H. Intermarket regimes, swing checklists and MWD

### 166. X3-intermarket-alignment-count
- **rule_id / kind:** B19 / missing_condition. Scope: needs_unavailable_data. judgment = true.
- **Rule (full_rule; no correction given):** Score stocks / rates / commodities / currencies.
  - Position trades need >= 3 of 4, plus yields.
  - Sync levels: <= 2 = decoupled; 3 = emerging; 4 = harmony (explosive).
  - Never use it for timing.
- **Sources:** cc05_009 ~00:16:24; cc05_018 ~00:02:26; cc10_019 ~00:21:10.
- **Quote:** "if you're getting three to indicate that your directional bias ... you probably got a pretty good trade idea"
- **Conflicts:** none.
- **Rulebook fix:** B19: add the alignment count. No build spec (commodities data).

### 167. X3-swing-two-group-trending-gate
- **rule_id / kind:** B19 / missing_rule. Scope: general. judgment = true.
- **Rule:** Swing gate: classify rates, the DXY/currencies, stocks and commodities as trending or consolidating. A new swing trade needs at least one trending in {rates, DXY} and at least one in {stocks, commodities}. If this fails, no new swings; drop to short-term/day trades until it passes.
- **Sources:** cc06_007 ~00:09:14; cc06_008 ~00:05:31.
- **Quote:** "you only need one from each group"
- **Conflicts:** B19 (bonds range -> all consolidate); not a real conflict.
- **Rulebook fix:** B19 / M17 swing: add the gate.
- **BUILD SPEC (bias_htf):**
  - The bot does not swing-trade. Use the gate as a regime tag for runner holds.
  - `trend_ok` = (TNX or DXY 20-day |slope| / ATR above `trend_slope_min`) and (the instrument's own 20-day slope above it). Commodities are not loaded, so stocks stand in for that group.
  - With `p.swing_gate_runners`, when `trend_ok` is False, drop runners (single target).
  - Params: `swing_gate_runners: bool = False`, `trend_slope_min: float = 0.5` [our interpretation].
  - Test: `test_swing_gate_runners`. Flat TNX and DXY: runners dropped.

### 168. X3-bonds-lead-stocks
- **rule_id / kind:** B19 / shortened. Scope: general. judgment = true.
- **Rule:** Long-term tag:
  - A 30-yr bond price uptrend supports stocks; a bond downtrend weighs on them (stocks eventually correct back into line).
  - Bonds lead stock trend changes by up to 6-12 months, so expect a delayed effect, not a lockstep one.
  - Exception: in a deflation regime (rare), bonds rise while stocks and commodities fall, so suspend the positive bond-stock link.
- **Sources:** cc05_009_4i_hnoEk6lw ~00:13:48, ~00:05:14, ~00:14:18.
- **Quote:** "the lead in lag time ... can be 6 to 12 months"
- **Conflicts:** none.
- **Rulebook fix:** B19: add the lead time and the deflation exception.
- **BUILD SPEC (bias_htf):**
  - In `INTERMARKET`, add `bond_lt` = -sign(the 126-day TNX change) (bond-price proxy, prior day). Tag `Trade.bond_lt`. Report only.
  - Test: `test_bond_lt_tag`. A falling TNX over 126 days gives bond_lt +1, using prior-day data only.

### 169. X3-commodities-inverse-bonds
- **rule_id / kind:** new / missing_rule. Scope: needs_unavailable_data. judgment = true.
- **Rule:** Long-term tags:
  - Commodity indices (CRB, GSCI, GS industrial metals) move inversely to bond prices, so rising yields lift commodities and falling yields drop them. Trend changes between the two can lag 6-12 months.
  - If the majority of commodities are trending higher, the regime is inflationary; if most are falling, it is deflationary. This is context for the monthly bias, not a lead indicator.
- **Sources:** cc05_009 ~00:12:55; cc12_001 ~00:14:24.
- **Quote:** "bond yields when they're going higher ... that's going to push Commodities up"
- **Conflicts:** none.
- **Rulebook fix:** B19: add as written. No build spec.

### 170. X3-dow-nikkei
- **rule_id / kind:** new / missing_rule. Scope: needs_unavailable_data. judgment = true.
- **Rule:** Long-term confirmation tags only: Dow bullish -> Nikkei bullish (a direct relationship); Nikkei bearish -> USDJPY bearish. Most key intermarket relationships lining up with the long-term analysis confirms it.
- **Sources:** cc05_009_4i_hnoEk6lw ~00:15:40.
- **Quote:** "Dow when it's up or bullish that's knee K index is bullish as well"
- **Conflicts:** none.
- **Rulebook fix:** B19: add as a tag note. No build spec.

### 171. X3-dollar-commodity-turtle-confirm
- **rule_id / kind:** B19 / missing_rule. Scope: needs_unavailable_data. judgment = true.
- **Rule:** Swing confluence tag (dollar/FX context).
  - Bullish DXY is confirmed when commodities (the CRB and individual sectors such as grains) fail at resistance, reject higher highs quickly, and break their lows in a trend lower.
  - Bearish DXY is confirmed when commodities break old highs with little resistance, and lows taken out act as turtle-soup longs (false breaks followed by higher prices).
  - Pair dollar strength with weak foreign currencies, and the mirror.
- **Sources:** cc06_007_Hoo_wTMgdcY ~00:11:21.
- **Quote:** "many times you can expect turtle soup scenarios"
- **Conflicts:** none.
- **Rulebook fix:** B19: add as written. No build spec.

### 172. B20-williams-r
- **rule_id / kind:** B20 / unlisted_contradiction. Scope: general. judgment = true.
- **Rule:** Sentiment tags only.
  - Weekly %R: use period 20, 14 or 10, whichever best fits past important highs/lows. Read it alongside contrarian headline and retail-forum sentiment (no numeric thresholds given).
  - Daily %R(15): at or below the 50 level = oversold/buy area; above 50 = overbought/sell area. When hovering at 50, favour the side of the condition most recently left.
- **Sources:** cc12_002 ~00:13:41; cc06_007 ~00:25:49.
- **Quote:** "I plot a 15 period uh Williams percent are on a daily basis"
- **Conflicts:** B20 (weekly extremes); cc04_013.
- **Rulebook fix:** B20: add the period choice and the daily %R(15) at 50 variant; drop "extremes" as the 12_002 reading.
- **BUILD SPEC (bias_htf):**
  - Rule_coverage B20.3 adds `wpr_tag` (weekly %R(14)). New: the period choice and the daily variant.
  - `wpr_period: int = 14` (10 / 14 / 20) for the weekly tag. `wpr_daily_tag` = the sign of (50 - %R(15) on daily bars, in 0..100 scale) from the prior day, with the hysteresis "side most recently left" when |%R - 50| < 5 [our interpretation]. Tags only.
  - Test: `test_wpr_daily_15`. A daily close near a 15-day low gives %R(15) < 50 -> +1 (buy area), using prior-day data.

### 173. X3-swing-checklist-pipeline
- **rule_id / kind:** M17 / missing_rule. Scope: general. judgment = true.
- **Rule:**
  - Swing hallmarks (cc06_002): an HTF trend or departure from consolidation; clear HTF IOF (required); rates supportive; COT (optional); obvious opposing M/W/D PD arrays; seasonal (optional); supporting intermarket. No minimum count is given, only that more is better.
  - Strict pipeline (cc06_008, stated for FX/metal swings), in order:
    1. A seasonal tendency is present.
    2. One trending market in each group (rates/currencies and commodities/stocks).
    3. COT commercials buying vs the 12-month midpoint.
    4. DXY supporting (SMT).
    5. Commodities breaking highs / rejecting lows.
    6. OI down 10-15%+.
    7. Top-down M/W/D levels.
    8. Setup.
    9. Management.
  - Any failed gate = no swing: wait or trade short-term.
- **Sources:** cc06_002 ~00:00:45; cc06_008 ~00:30:27, ~00:03:23.
- **Quote:** "if we do not get it we have to sit on our hands and wait"
- **Conflicts:** cc06_002 vs cc06_008; B23.
- **Rulebook fix:** M17: add both lists (the hallmarks as general; the strict pipeline as FX/metal).
- **BUILD SPEC (bias_htf):**
  - The bot is intraday. Implement the hallmarks as a report-only score. `Trade.hallmarks` = the count of {trend (item 167 `trend_ok`), iof (B6 daily `iof` agrees), rates (item 94), season (item 60 window agrees), opposing array present (`draw_lvl` set)}. COT is excluded until item 148 exists.
  - Report by count in `report_decisions.py` (decision "M17_hallmarks"). No gate.
  - Test: `test_hallmarks_count`. A trade meeting 3 of the 5 tags has hallmarks = 3.

### 174. X3-htf-market-profile
- **rule_id / kind:** B17 / missing_rule. Scope: general. judgment = true.
- **Rule:** On the monthly then the weekly (a 9-18 month view), ask in order:
  1. Consolidating? If yes, avoid swings in the range and use intermarket/SMT to judge which side breaks. Follow aggressive departures (displacement).
  2. Trending? If yes, take continuation trades only, no top/bottom picks. A trend near stiff resistance implies a retracement.
  3. Retracing? If yes, look for continuation once the retracement reaches an HTF array (e.g. a monthly OB).
  
  The draw = the next monthly/weekly PD array. Prefer trending or freshly broken-out markets and avoid lethargic ones.
- **Sources:** cc06_001 ~00:02:43, ~00:05:34, ~00:03:52; cc06_003 ~00:18:51; cc12_001 ~00:29:30; cc12_002 ~00:15:01.
- **Quote:** "the first thing I want to know is are we consolidating"
- **Conflicts:** none.
- **Rulebook fix:** B17 (or a new B rule): add the profile decision tree.
- **BUILD SPEC (bias_htf):**
  - Add `htf.table` column `profile` in {"consol", "trend", "retrace"}, computed on weekly bars over 52 weeks [our interpretation of 9-18 months]:
    - "consol" when the 26-week range < 1.5 x the 52-week mean weekly range x 6 [our interpretation];
    - "trend" when the last 13 weekly closes slope one way and the price is beyond the 26-week EQ that way;
    - "retrace" when the trend holds but the last 4 weeks moved against it.
  - With `p.profile_gate`: consol -> runners off and `scalp`; trend -> counter-trend orders blocked; retrace -> with-trend orders need the price inside a weekly/monthly array.
  - Params: `profile_gate: bool = False`.
  - Test: `test_weekly_profile`. A synthetic 52-week uptrend with a 4-week pullback gives "retrace".

### 175. X3-hedge-retrace-correlated
- **rule_id / kind:** new / missing_rule. Scope: fx_only. judgment = true.
- **Rule:** [fx-only] Position trading: allocate about 30% of equity to long-term positions. During an expected retracement against a long-term position, take short-term trades that profit from that retracement, using an inversely correlated pair (e.g. a USDJPY short retracing up -> short EURUSD/GBPUSD), and stop once the retracement completes.
- **Sources:** cc05_013_crPpMwgwa7k ~00:13:34.
- **Quote:** "you can actually go short euro dollar"
- **Conflicts:** none.
- **Rulebook fix:** [fx-only] note. No build spec.

### 176. X3-a21-rebalance-to-eq
- **rule_id / kind:** A21 / B2, missing_rule. Scope: general. judgment = true.
- **Rule:** From a discount (or premium) of the recent range, the first expected draw is the range's equilibrium (0.5); a trade aiming only for EQ is valid. At EQ, reassess the next leg (into premium arrays or back into deeper discount) using monthly market structure, the IPDA 20/40/60-day ranges and the PD-array matrix. Mirror.
- **Sources:** cc05_015 ~00:04:03; cc07_008 ~00:25:42.
- **Quote:** "they're always going to initially look to rebalance"
- **Conflicts:** none.
- **Rulebook fix:** A21/B2: add EQ as the first draw from a discount/premium.
- **BUILD SPEC (targets_partials):**
  - With `p.eq_first_rung`, when the entry is in the discount of the 20-day range (A21.2 `pd20`), insert the 20-day EQ as a target rung (kind "eq20"). With `draw_lock_partials`, it is a partial; when no other rung lies before it, it is T1. Mirror.
  - Test: `test_eq_first_rung`. A long at 25% of a 20-day range 4000-4200: the 4100 rung is in the ladder.

### 177. X3-b10-tf-test
- **rule_id / kind:** B10 / shortened. Scope: general. judgment = true.
- **Rule:** B10: a timeframe is bullish when a discernible discount array (a bullish OB, old low or high, FVG or void, breaker, rejection block or mitigation block) has produced displacement higher. When month, week and day are all bullish, down-close candles act as new support on every timeframe, little weakness shows, and price makes higher highs and higher lows. Then buy every daily and 4h discount array. Bearish mirror (cc06_005 ~0:50).
- **Sources:** cc06_004 ~00:03:13; cc06_005 ~00:01:15.
- **Quote:** "all candles provide new resistance to price and little to no strength is seen"
- **Conflicts:** displacement vs moving away.
- **Rulebook fix:** B10: add the candle-support and HH/HL parts of the test.
- **BUILD SPEC (bias_htf):**
  - Rule_coverage B10 adds `mwd` (M/W/D displacement state, cases A/B/C). New: the per-timeframe test. For each of M/W/D:
    - `tf_state` = +1 when the last array touch was followed by a displacement bar (range >= 1.5 x the TF's 10-bar mean range, close in the top third);
    - for case A, also require the last two pivots HH/HL and the B6 `iof` agreeing on that TF.
  - Reuse the item 43 `iof_state` on M/W/D bars.
  - Test: `test_mwd_tf_state`. Weekly bars with a displacement off a weekly FVG and HH/HL: +1. Without HH/HL: +1 but not case A.

### 178. X3-b10-4h-correction-cases
- **rule_id / kind:** B10 / missing_condition. Scope: general. judgment = false.
- **Rule:**
  - A (M/W/D bullish): buy all daily and 4h discount arrays.
  - B (daily correcting): buy daily arrays at or nested in weekly arrays. Buy 4h arrays at daily and/or nested weekly arrays: the weekly level is required, the daily nest optional.
  - C (weekly and daily correcting): buy daily arrays at or nested in monthly arrays. Buy 4h arrays at weekly and/or nested monthly arrays; no daily turn is needed first.
  - Bearish mirror.
- **Sources:** cc06_004 ~00:05:07, ~00:15:22; cc06_005 ~00:02:42; cc06_003 ~00:07:57.
- **Quote:** "it may nest with an old daily discount array but it doesn't have to"
- **Conflicts:** none.
- **Rulebook fix:** B10: add the 4h execution rules per case.
- **Already in rule_coverage:** B10 `mwd` "cases A/B/C" (bias_htf) is the same content. No new build spec; when building `mwd`, use the nesting rules above as the case definitions.

### 179. X3-b10-cancel-condition
- **rule_id / kind:** B10 / wrong. Scope: general. judgment = true.
- **Rule:**
  - Case B: if the daily makes a higher high that is rejected and breaks market structure (a bearish breaker forming), stop buying daily discount arrays; the bullish sequential is negated.
  - Case C: if the weekly makes a higher high and rejects it (a weekly bearish breaker), stop buying weekly discount arrays and don't trade the sequential.
  - Bearish mirror, with lower lows and bullish breakers.
- **Sources:** cc06_004 ~00:05:51; cc06_005 ~00:02:52.
- **Quote:** "you're probably looking at a development of a bearish breaker"
- **Conflicts:** none.
- **Rulebook fix:** B10: replace "only a bearish breaker on a timeframe cancels it" with the case-specific timeframe.
- **BUILD SPEC (bias_htf):**
  - Rule_coverage B10 `mwd` has a "breaker-only cancel". Make it case-specific: in case B, the cancel is a bearish breaker (`levels.breaker_zone` on daily bars) formed after a new daily high; in case C, the same on weekly bars. The cancel sets `mwd = 0` (no sequential), not -1.
  - Test: `test_mwd_cancel_case`. Case B with a daily HH rejected and a daily close below the prior pivot low: mwd 0. The same pattern on the 4h does not cancel.

### 180. X3-b10-case-c-to-b-upgrade
- **rule_id / kind:** B10 / missing_rule. Scope: general. judgment = false.
- **Rule:** When a monthly discount array that is being traded into also holds a weekly bullish OB that reacts, month and week agree (case C becomes B). While the daily corrects, mark every daily down-close candle's open and high as specific buy levels, not zones, and carry them to the 4h for entries. Bearish mirror. Cancel per B10 (daily bearish breaker).
- **Sources:** cc06_004_osRUnIpGIJ0 ~00:17:29.
- **Quote:** "now we have the monthly chart and the weekly chart in agreement"
- **Conflicts:** none.
- **Rulebook fix:** B10: add the upgrade and the down-candle levels.
- **BUILD SPEC (bias_htf):**
  - In the `mwd` state: case C -> B when the price is inside a monthly bull array and a weekly bull OB inside it produced a weekly up-close.
  - In case B, export `mwd_levels` = the open and high of each daily down-close candle since the correction began, as conf rows (kind "dcandle") usable as entry arrays by the HTF-array entries (`_ts_arrays` src).
  - Test: `test_mwd_c_to_b`. A monthly array plus a reacting weekly OB give case B, and three daily down candles give 6 levels.

### 181. X3-b10-topdown-transposition
- **rule_id / kind:** B10 / missing_rule. Scope: general. judgment = false.
- **Rule:** Swing top-down:
  - Check the 9-18 month monthly/weekly profile for trend or range (an aggressive exit from a range = displacement).
  - List the active monthly arrays and transpose them to the weekly; list the weekly arrays and transpose them to the daily; then to the 4h.
  - Buy 4h discount arrays (turtle soup below old lows or rejection-block bodies), and scale out at the transposed daily, weekly and monthly premium arrays.
  - Bearish mirror.
- **Sources:** cc06_003_g--tikwaupk ~00:20:01.
- **Quote:** "transpose those monthly levels over to your weekly chart"
- **Conflicts:** none.
- **Rulebook fix:** B10: add the transposition procedure.
- **BUILD SPEC (levels_detectors):**
  - `confluence._zones` / the htf conf rows already carry D and W arrays to intraday. Add M (item 71) and 4h arrays (`htf_bars(df, 240)` + `_arrays`) as conf sources, each with `tf`.
  - With `p.topdown_targets`, the long ladder includes transposed D/W/M bear arrays in distance order.
  - Params: `topdown_targets: bool = False`.
  - Test: `test_topdown_transposed_rows`. A monthly bear FVG appears in the conf rows with tf "M" and as a target rung.

### 182. B20-commodity-basket-gate
- **rule_id / kind:** new / missing_rule. Scope: fx_only. judgment = true.
- **Rule:** [fx-only] For an FX or metal swing long, commodities must be bullish (breaking old highs and holding old lows) while DXY is bearish. If not, take only short-term or day trades and wait. This is step 3 of the gate, after the COT program and the DXY correlation and before the OI drop and top-down analysis. Bearish mirror. Thresholds are our interpretation.
- **Sources:** cc06_008_VL4YLTRerHY ~00:09:07.
- **Quote:** "are Commodities rallying higher breaking old highs or rejecting old lows"
- **Conflicts:** none.
- **Rulebook fix:** [fx-only] note. No build spec.

### 183. L14-monthly-to-weekly-range
- **rule_id / kind:** L14 / shortened. Scope: general. judgment = false.
- **Rule:** L14 addition: the span from the monthly origin array to the opposing weekly array is the trade's range. Frame R:R on it, take partials along the way, and hold a small final portion to the weekly array. It may not be reached, but don't cut the range to a small fixed target.
- **Sources:** cc07_001_mQA8jCem9d0 ~00:09:47.
- **Quote:** "from that monthly array you're going to look for an opposing weekly array"
- **Conflicts:** none.
- **Rulebook fix:** L14: add the range framing.
- **BUILD SPEC (targets_partials):**
  - Rule_coverage L14c adds `matrix_tf_lower` (react TF, then the opposing array one TF down as the draw). New: hold a final slice to it.
  - With `p.htf_range_runner` and a `matrix_tf_lower` draw beyond the session ladder, keep `htf_runner_frac` of the position open past the session ladder to that level (still subject to the session flat time).
  - Params: `htf_range_runner: bool = False`, `htf_runner_frac: float = 0.1`.
  - Test: `test_htf_range_runner`. With a weekly opposing array beyond the last rung, 10% remains after the last rung until the flat time.

### 184. B17-no-active-array
- **rule_id / kind:** B17 / missing_condition. Scope: general. judgment = true.
- **Rule:** B17 addition: if the next HTF PD array price will reach for can't be identified, or all candidate arrays have expired (already traded to), stay out and wait for a new array to form.
- **Sources:** cc07_001_mQA8jCem9d0 ~00:10:33.
- **Quote:** "the PD arrays have been expired"
- **Conflicts:** none.
- **Rulebook fix:** B17: add "no identifiable / all expired next array = no trade".
- **BUILD SPEC (bias_htf):**
  - Rule_coverage B1 built `no_draw` / `skip_no_draw` (off). That covers "no draw". New: expiry. In `htf.table`, an array is expired once traded to its far edge (L14d "arrays never retired" is the gap).
  - Add `retire_arrays: bool = False`. When on, traded-through arrays are dropped from the draw candidates, so `skip_no_draw` then fires when none remain.
  - Test: `test_retire_arrays`. A daily FVG traded through is no longer a draw, and with no others the day is skipped under skip_no_draw.

### 185. B9-ltf-arrays-break-in-succession
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** With an HTF origin array and an opposing weekly target, the opposing (discount, for a short) arrays on the monthly, weekly, daily and 4h between price and the target should break one after another on the way. Treating a holding array as a reason to pause is our interpretation. Bullish mirror.
- **Sources:** cc07_001_mQA8jCem9d0 ~00:14:48.
- **Quote:** "we want to see them continuously keep breaking"
- **Conflicts:** none.
- **Rulebook fix:** New B9 note (cc07_001 ~14:48).
- **BUILD SPEC (bias_htf):**
  - Add `htf.table` column `held_arrays`: the number of arrays between the draw start and the price that were touched and produced a daily close back on the bias-opposing side (held), since the state began.
  - With `p.pause_on_hold`, when it increments, set `want = 0` for the next session (pause).
  - Params: `pause_on_hold: bool = False`.
  - Test: `test_pause_on_hold`. A bearish state with a daily BISI touched and a daily close above it: want 0 the next session.

### 186. B5-monthly-weekly-range-bookkeeping
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** Each week, record the current monthly and weekly high, low and premium/discount position, and the likely draw on each. Use the weekly range to frame daily trades. Treat weekly candles that keep expanding in the monthly bias direction as confirmation of the monthly idea. Weeks that fail to expand weaken the confirmation, but ICT gives no rule to cancel the bias and no count of failed weeks. Use it as a tag or confidence score, not a flip.
- **Sources:** cc07_001_mQA8jCem9d0 ~00:34:13, ~00:35:56.
- **Quote:** "we're watching to see if the weeklies continuously expand"
- **Conflicts:** none.
- **Rulebook fix:** New B5 note (cc07_001 ~34:13).
- **BUILD SPEC (bias_htf):**
  - Add `htf.table` columns `mo_pd` / `wk_pd` (the prior close position in the current month's / week's range, 0..1) and `wk_expand` = the count of consecutive completed weeks in this month that made a new extreme in the monthly bias direction. Tags only on trades.
  - Test: `test_mw_bookkeeping`. A month with two weeks making new highs: wk_expand 2, with mo_pd computed from prior data.

### 187. M17-weekly-profiles-selection
- **rule_id / kind:** M17 / missing_rule. Scope: general. judgment = true.
- **Rule:** Decide the weekly bias first, then consider only the weekly profiles in that direction. Tag the candidate profile from its stated precursors (which HTF array is reached or not reached on Mon/Tue, news-driven runs, the Mon-Wed range). If no profile's characteristics are obvious, take no One Shot One Kill weekly trade; day trades and scalps are still allowed. FX-derived, so test as a tag first.
- **Sources:** cc07_002 ~00:00:50; cc07_003 ~00:38:19.
- **Quote:** "we go to our profiles that are bullish"
- **Conflicts:** M17 (statistics only).
- **Rulebook fix:** M17: add the selection order.
- **BUILD SPEC (day_week_context):**
  - Add a weekly profile classifier in `BT.run` weekly state, evaluated each day from prior data:
    - "classic_tue_low": Mon/Tue traded into a daily bull array with the weekly bias +1;
    - "wed_low": no array by Tue, array on Wed;
    - "consol_thu_reversal": Mon-Wed inside ADR;
    - "mon_how" (item 81); else "none".
  - Filter to profiles matching the weekly bias. Tag `Trade.wk_profile`. Report only.
  - Test: `test_weekly_profile_tag`. A bullish week where Tuesday trades into a daily FVG: classic_tue_low from Wednesday.

### 188. B8-tuesday-failure-swing-flip
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** With a bullish weekly bias: if Tuesday trades slightly above Monday's high into an old monthly, weekly or daily high and then rejects and breaks down on Tuesday (a failure swing), flip to bearish for the rest of the week. Sell the premium PD arrays and target a lower-timeframe (4h/1h) discount array or void. Mirror for bearish. Taken from one FX example, so start as a tag.
- **Sources:** cc07_004_YV4fEF4d2wA ~00:11:30.
- **Quote:** "once Tuesday broke down"
- **Conflicts:** none.
- **Rulebook fix:** New B8 trigger (cc07_004 ~11:30, single FX example).
- **BUILD SPEC (bias_htf):**
  - New `flip` trigger `tue_fail`: on Tuesday's close, if Tuesday's high > Monday's high, Tuesday's high is within `eq_tol_pts` x 4 of a prior daily/weekly pivot high or monthly high, and Tuesday closed below Monday's close and in its own lower third [our interpretation of "broke down"], the state becomes -1 for Wed-Fri. Mirror.
  - Add to `FLIP_TRIGGERS`.
  - Test: `test_flip_tue_fail`. Monday high 4100, Tuesday high 4103 at an old weekly high of 4102, Tuesday close 4080 (range 4078-4103): -1 from Wednesday.

### 189. A21-trend-vs-consolidation-first
- **rule_id / kind:** A21 / missing_condition. Scope: general. judgment = true.
- **Rule:** Before framing the 60-day range, classify the daily chart as trending or consolidating. When it is consolidating (range-bound over about 60 trading days), frame the range from the highest and lowest candle bodies and use its 50% line and quadrants for premium/discount. ICT does not say how to treat a trending market in this passage.
- **Sources:** cc07_005_y0lVKWLsZeM ~00:02:14.
- **Quote:** "we Define a market whether that it's it's trending or it's in consolidation"
- **Conflicts:** none.
- **Rulebook fix:** A21: add the classification step.
- **BUILD SPEC (bias_htf):**
  - Rule_coverage A21.4 adds `pd_bodies` and the 20-day range. Add `pd60_consol` = True when the 60-day net move (|last close - close 60 sessions ago|) < `consol_ratio` x the 60-day body range [our interpretation of "range-bound"].
  - With `p.pd60_only_consol`, the 60-day body-range premium/discount (`pd60`) is used only when `pd60_consol`.
  - Params: `pd60_only_consol: bool = False`, `consol_ratio: float = 0.25`.
  - Test: `test_pd60_consol`. A range-bound 60 days gives True; a 60-day trend gives False, and pd60 is unused.

### 190. B13-weekly-bias-from-daily-arrays
- **rule_id / kind:** B13 / missing_condition. Scope: general. judgment = true.
- **Rule:** Before Sunday's open: if the last HTF (monthly, weekly or daily) array price traded into was a premium array, the weekly bias is bearish; if a discount array, bullish. The weekly objective is the nearest opposing PD array on the 4h chart (using M/W/D arrays) that price can reasonably reach Mon-Fri. Mark it [CC]. It conflicts with B16 [2023].
- **Sources:** cc08_001 ~00:26:26; cc07_006 ~00:16:09.
- **Quote:** "it has already fulfilled a premium level so therefore we're expecting expansion on the downside"
- **Conflicts:** B16 (no bias pre-Sunday).
- **Rulebook fix:** B13: add the pre-week rule [CC] with the B16 conflict.
- **BUILD SPEC (bias_htf):**
  - Add `htf.table` column `wk_pre_bias`, set on the first session of each week from the last array touched (bear -> -1, bull -> +1) among D/W/M arrays. Add `wk_obj` = the nearest opposing array within 2 x ADR5 x 5 [our interpretation of "reasonably reach"].
  - With `p.htf_bias == "week_pre"`, `want = wk_pre_bias` for the whole week.
  - Params: extend the `htf_bias` values with "week_pre".
  - Test: `test_wk_pre_bias`. The last touch was a daily SIBI on Friday: Monday-Friday want -1 and wk_obj = the nearest bull array below.

### 191. B17-intraweek-reversal-profile
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** If Monday or Tuesday covers a range well above ADR5 (ICT gives no multiple; the multiple k is a parameter to test), look for an HTF PD array that may trigger a Wednesday/Thursday intraweek reversal. Do not project an equal second leg in the same direction. If an open trade stalls after such a move, take profit early. Tag only.
- **Sources:** cc07_007 ~00:20:55, ~00:21:24, ~00:14:24.
- **Quote:** "if it gets well above chances are you're probably going to see a market reversal profile"
- **Conflicts:** A20.
- **Rulebook fix:** New note under the weekly profiles.
- **BUILD SPEC (day_week_context):**
  - In `day_context`, tag `iw_reversal_watch` on Wed/Thu when the Mon or Tue range > `iw_k` x ADR5 (`strategy.adr5`) and that day closed inside or at an HTF array. Tag only. With `p.iw_no_measured`, drop measured-move (equal-leg) targets on those days.
  - Params: `iw_k: float = 1.5`, `iw_no_measured: bool = False`.
  - Test: `test_iw_reversal_watch`. Monday range 2 x ADR5 into a weekly FVG: Wednesday is tagged.

### 192. B12-judas-depth-adr
- **rule_id / kind:** B12 / missing_rule. Scope: general. judgment = true.
- **Rule:** [fx-derived, translated by ADR ratio] On a bullish day, the ideal Judas drop below the opening price is about 0.2-0.3 x ADR, at most about 0.33 x ADR. A drop beyond about 0.4 x ADR is lower probability ('doesn't mean it can't'). Mirror for bearish days. Use it as a tag to test on index data, not a filter.
- **Sources:** cc08_003_nI1AMOC1pro ~00:12:59.
- **Quote:** "ideally no more than 33 Pips"
- **Conflicts:** none.
- **Rulebook fix:** B12: add the depth tag (cc08_003 ~12:59, FX).
- **BUILD SPEC (setups_models):**
  - At fill, tag `Trade.judas_depth` = (`ref_open` - session extreme before the MSS) / ADR5 for longs (mirror). With `p.judas_max_adr` (0 = off), reject orders whose depth > it.
  - Params: `judas_max_adr: float = 0.0` (test 0.4).
  - Test: `test_judas_depth`. Open 4000, low 3985, ADR5 40: depth 0.375; rejected with max 0.33.

### 193. M17-london-models
- **rule_id / kind:** L13 / missing_condition. Scope: fx_only. judgment = true.
- **Rule:** [fx-only, outside the bot's scope under M17] Set the daily bias before London. Project CBDR (14:00-20:00, ideally 20-30 pips, under 40) standard deviations against the bias to locate the London low (bullish) or high (bearish). Look first for the 00:00-02:00 protraction/Judas. If it does not appear, look for the delayed Judas at 02:00-03:00. If neither appears, take no London trade.
- **Sources:** cc08_003 ~00:06:28; cc08_005 ~00:20:00.
- **Quote:** "we need to know directional bias for this to be any of any assistance to us"
- **Conflicts:** M17 (out of scope).
- **Rulebook fix:** [fx-only] L13 note. No build spec.

### 194. B11-three-closes-day4
- **rule_id / kind:** B11 / shortened. Scope: general. judgment = true.
- **Rule:** After 3 consecutive up (down) daily closes, avoid London-session longs (shorts) on day 4. Expect a pause or a deep retracement (a down-close day or a long wick), possibly followed by continuation in the original direction. A big range day is unlikely on day 4, so treat it as a no-expansion day (small targets). ICT gives no ADR5 threshold.
- **Sources:** cc08_006_stK2gNqhLaM ~00:02:07.
- **Quote:** "you want to avoid trading longs at least in the London session"
- **Conflicts:** none.
- **Rulebook fix:** B11a: narrow to "at least London" and add the no-expansion expectation.
- **BUILD SPEC (day_week_context):**
  - `three_day_rule` (FULL) blocks the 3-close direction on day 4. New: with `p.three_day_small`, all day-4 orders are `scalp` (single target, no runners); tag `day4`.
  - Params: `three_day_small: bool = False`.
  - Test: `test_three_day_small`. Day 4 after three up closes: a short gets one target and the day4 tag.

### 195. B5-htf-arrays-respected-and-in-play
- **rule_id / kind:** B5 / missing_condition. Scope: general. judgment = true.
- **Rule:** A precondition for a day trade: on the daily and/or 4h, price has recently traded into a PD array in the trade direction (discount for longs) and reacted from it; the daily is clearly respecting PD arrays (non-ambiguous reactions); and IOF agrees. Also require enough room to the opposing daily/4h array. If any of these fail, skip or tag. Mirror for shorts.
- **Sources:** cc09_001 ~00:03:30; cc08_006 ~00:21:14.
- **Quote:** "it has to be respecting a PD array Matrix"
- **Conflicts:** none.
- **Rulebook fix:** B5: add the "in play" precondition.
- **BUILD SPEC (bias_htf):**
  - Add `htf.table` column `in_play` (+1 / -1 / 0): +1 when, within the last `in_play_days` sessions, a daily or 4h bull array was traded into and a later daily close was above its top (the reaction), and the daily `iof` (B6) is not -1. Mirror.
  - With `p.in_play_gate`, orders need `in_play` == side, and room to the opposing array >= `min_room_pts` (owner #2's 5-point minimum room is reused).
  - Params: `in_play_gate: bool = False`, `in_play_days: int = 3`.
  - Test: `test_in_play_gate`. A daily BISI tagged 2 days ago with a close above it: longs pass. No touch: longs are rejected.

### 196. B5-prior-day-ny-range-retracement
- **rule_id / kind:** B5 / missing_rule. Scope: general. judgment = false.
- **Rule:** With the daily/4h bullish, frame retracement entries in the discount of the previous day's low-to-high range and of the previous NY session's low-to-high range (London's range is an extra frame), and use a raid below the previous day's low to accumulate longs, aiming from the HTF discount array toward the HTF premium array. Mirror when bearish.
- **Sources:** cc08_007_5Z_3NbclMSY ~00:00:40.
- **Quote:** "use previous days low to high for retracement entries"
- **Conflicts:** none.
- **Rulebook fix:** A21/B5: add the prior-day and prior-NY frames.
- **BUILD SPEC (entries_stops_sizing):**
  - Add `entry_pd_frame: str = "leg"` ("leg" current / "prev_day" / "prev_ny" / "any"). The `leg_pd` check (~3993) measures the entry against the chosen frame's range (the previous RTH day H/L from hist; the previous NY session 08:30-16:00 [our interpretation]); "any" passes if either one is in discount.
  - Test: `test_entry_pd_frame`. A long at 4045 with the previous day 4000-4100: passes under prev_day (45%) and is rejected if the leg discount fails under "leg".

### 197. B6-iof-checklist-extended
- **rule_id / kind:** B6 / shortened. Scope: general. judgment = true.
- **Rule:** Bullish IOF on the daily/4h: price bounces off bullish OBs, rejects old lows, fills gaps below and then rallies, and violates short-term premium arrays (bearish OBs and highs above). Mirror for bearish. Optional strength tell, borrowed from the cc10_002 commodity relative-strength lesson: short-term highs broken, shallow declines, and up swings larger than down swings. Drop the '<50% pullback' item, which has no source.
- **Sources:** cc08_007 ~00:06:10; cc10_002 ~00:05:58.
- **Quote:** "declines are going to be shallow in nature"
- **Conflicts:** none.
- **Rulebook fix:** B6: add the checklist items.
- **BUILD SPEC (bias_htf):**
  - Rule_coverage B6 adds the daily `iof` column (held down-closes, run up-closes, reversed pivot raids). Add the components as separate columns, each +1/-1/0 over the last 10 sessions, and `iof_score` = their sum:
    - `iof_ob_bounce`: a bull OB touched and closed above;
    - `iof_gap_fill_rally`: a bull FVG filled, then a close above its top;
    - `iof_premium_broken`: a bear OB/FVG closed through.
  - With `p.iof_mode == "score"`, the bias = sign(iof_score) when |score| >= 2.
  - Params: `iof_mode: str = "basic"` ("basic" / "score").
  - Test: `test_iof_score`. Two bullish components: score 2 and bias +1.

### 198. B5-daily-and-4h-bias
- **rule_id / kind:** B6 / shortened. Scope: general. judgment = true.
- **Rule:** Read bias from daily IOF, using the 4h as the minimum ('last line of defense'). Prefer the daily and 4h both pointing the same way. ICT's 'daily and/or 4h' wording allows one of them alone. What to do when they conflict is our interpretation (for example, tag or skip); it is not stated.
- **Sources:** cc09_001 ~00:02:12; cc09_004 ~00:00:57.
- **Quote:** "the 4our chart is your last line of defense"
- **Conflicts:** none.
- **Rulebook fix:** B5/B6: add the daily + 4h preference.
- **BUILD SPEC (bias_htf):**
  - Compute `iof_4h` with the item 43 `iof_state` on `htf_bars(df, 240)` (prior bars only). Tag `Trade.bias_dh` = "both" / "daily_only" / "4h_only" / "conflict".
  - With `p.bias_dh` ("off" / "both" / "either"): "both" needs the daily `iof` and `iof_4h` to agree with the side; "either" needs one agreeing and none opposing.
  - Test: `test_bias_dh`. Daily +1 and 4h -1: conflict, rejected under both modes.

### 199. T3-london-close-multiday-reversal
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** A reversal at the London close (10:00-12:00 NY) from an HTF PD array can mark a multi-day turn (several one-sided days), judged with the weekly templates and structure, so tag it as a possible multi-day flip. After an expected NY-session reversal, the London close may run that reversal's stops one more time at the HTF array: a re-entry chance in the reversal direction.
- **Sources:** cc09_005_KrGTimL3YRQ ~00:32:44.
- **Quote:** "the London close can time a market reversal"
- **Conflicts:** none.
- **Rulebook fix:** T3: add the multi-day reversal and re-entry notes.
- **BUILD SPEC (setups_models):**
  - Tag `Trade.lc_reversal` for fills between 10:00 and 12:00 whose sweep extreme was inside an HTF array (`_htf_tag`) and against the morning's direction.
  - With `p.lc_reentry`, after a stopped-out reversal trade, allow one re-entry in the same direction in 10:00-12:00 when the new sweep is beyond the first extreme at the same HTF array (bypassing the one-trade-per-session `done` flag for this case only).
  - Params: `lc_reentry: bool = False`.
  - Test: `test_lc_reentry`. A 09:45 reversal long stopped at 10:20, then a 10:40 sweep of a lower low inside the same daily FVG: a second long is allowed.

### 200. N9-ny-continues-london
- **rule_id / kind:** new / missing_condition. Scope: general. judgment = false.
- **Rule:** If London (02:00-05:00) makes the high of the day with bearish IOF, expect the NY session to continue lower and short premium arrays in the NY kill zone, unless an HTF discount array was already hit intraday and/or the ADR5 low was already reached. Targets: the ADR5 low and the next 4h/60m discount array. Mirror for longs.
- **Sources:** cc09_007_-oMtfDvc18Y ~00:07:58.
- **Quote:** "unless a higher time frame discount array has been hit"
- **Conflicts:** none.
- **Rulebook fix:** N9: add the NY-continues-London rule.
- **BUILD SPEC (bias_htf):**
  - In `_lock_step` at the AM lock: when the overnight high was set in 02:00-05:00 and is still the day's high, the daily `iof` is -1, no daily/4h bull array has been touched since 00:00, and the price is above the open-of-day minus ADR5, lock side -1. Add the ADR5 low (day open high - ADR5) as a target rung (kind "adr5").
  - With `p.ny_continue_london`.
  - Test: `test_ny_continue_london`. London high at 03:10 with bearish IOF: AM lock -1 with the adr5 rung. If a daily BISI was touched at 06:00, there is no lock.

### 201. A21-discount-not-buy-signal
- **rule_id / kind:** A21 / missing_condition. Scope: general. judgment = false.
- **Rule:** Position in the 20/40/60-day range (premium or discount) is not by itself a buy or sell signal. It frames context and lists the PD arrays price could reach (targets). Direction comes from daily IOF. A discount reading with bearish IOF stays bearish.
- **Sources:** cc09_008_cqf8nH54bb8 ~00:13:20.
- **Quote:** "it doesn't mean that's going to buy it"
- **Conflicts:** none.
- **Rulebook fix:** A21: add the caveat.
- **BUILD SPEC (bias_htf):**
  - A guard: htf_bias "pd" (range position as bias) exists. With `p.pd_needs_iof`, the "pd" bias is used only when the B6 `iof` agrees; otherwise it is 0. Combo modes inherit this.
  - Test: `test_pd_needs_iof`. pd +1 (discount) with iof -1: bias 0.

### 202. B3-countertrend-from-range-extreme
- **rule_id / kind:** B3 / missing_rule. Scope: general. judgment = true.
- **Rule:** A day-trade exception to B3: against daily IOF, a counter-trend day trade is allowed only when price sits at a defined extreme of the 20-day range (a discount for counter-trend longs) after sweeping an old low. Expect only a partial retracement and target the nearest opposing PD array within the 20-day range (the target choice is our reading). Mirror at a premium extreme. Lower probability than trading with IOF.
- **Sources:** cc09_008_cqf8nH54bb8 ~00:16:57.
- **Quote:** "we can counter Trend trade that if we have the ranges defined"
- **Conflicts:** B3.
- **Rulebook fix:** B3: add the exception.
- **BUILD SPEC (bias_htf):**
  - Extends item 44 `allow_counter_trend` with mode "range_extreme": a counter-`want` order is allowed only when the sweep took a daily pivot low and the entry is in the bottom 25% of the 20-day range (mirror). The target is the nearest bear array inside the 20-day range; scalp, half risk.
  - Params: make `allow_counter_trend` a str: "off" / "after_draw" (item 44) / "range_extreme".
  - Test: `test_counter_trend_range_extreme`. Want -1, a long at 10% of the 20-day range after a PDL sweep: allowed with one target.

### 203. B6-bullish-iof-at-premium-wait
- **rule_id / kind:** B6 / missing_rule. Scope: general. judgment = true.
- **Rule:** When daily IOF is bullish but price is at a premium of the 20/40/60-day ranges, don't buy at the premium. Look on the 4h for reasons price could drop to take sell-side stops below recent lows into a daily/4h discount array (4h OTE overlapping a bullish OB, an unfilled FVG, a retest of an old high), and arm longs there. Mirror for bearish IOF at a discount.
- **Sources:** cc09_008_cqf8nH54bb8 ~00:23:43.
- **Quote:** "I want to First make a case and argue that there's reasons for them to want to take it down"
- **Conflicts:** none.
- **Rulebook fix:** B6/A21: add the wait-for-discount rule.
- **BUILD SPEC (bias_htf):**
  - With `p.iof_premium_wait`, when `iof == +1` and the prior close is > 75% of the 20-day range, longs need the sweep low to be inside a daily/4h bull array (`_htf_tag` True with tf in D/4h). Otherwise reject (`_f("x_iof_premium_wait")`). Mirror.
  - Test: `test_iof_premium_wait`. IOF +1 at 90% of the range: a long whose sweep is not in an array is rejected; one whose sweep is inside a 4h bull OB passes.

### 204. B19-dxy-reference-first-fx
- **rule_id / kind:** B19 / missing_rule. Scope: fx_only. judgment = true.
- **Rule:** [fx-only] Analyse DXY before the pair (cc09_008 ~3:30). An FX mega trade (ICT's term, not 'swing') qualifies only when DXY shows the opposite condition: a bullish foreign currency needs DXY in a sell condition, and the reverse (cc11_002 ~4:05-5:00). Intraday FX trades may go ahead while DXY merely consolidates.
- **Sources:** cc09_008 ~00:02:49; cc11_002 ~00:04:05.
- **Quote:** "or it is not a qualified Mega trade setup"
- **Conflicts:** none.
- **Rulebook fix:** [fx-only] note. No build spec.

### 205. D15-leader-and-relative-strength
- **rule_id / kind:** D15 / shortened. Scope: general. judgment = true.
- **Rule:** Cross-asset relative-strength ranking for weekly market selection [CC; commodities/FX futures/stocks].
  - With DXY weak, rank markets by: higher lows vs peers (the leader), closes through premium arrays, held retraces, larger up-legs than down-legs, and which breaks short-term highs or bearish OBs first. Mirror for weakness.
  - Cross out ranging or faltering markets, and keep the stronger of a correlated pair (AUD over NZD).
  - Sympathetic markets move slower and smaller.
  - Do this at the start of the weekly analysis, especially when the monthly is unclear (cc12_002 ~8:43).
  - D15's intraday index pick already has the basic leader test; at most, add these sources as supporting citations.
- **Sources:** cc10_002 ~00:05:20, ~00:11:34; cc11_003 ~00:48:46; cc12_002 ~00:08:43; cc11_002 ~00:07:54, ~00:17:23; cc11_001 ~00:28:47; cc10_019 ~00:19:26.
- **Quote:** "markets lead in strength by failing to make lower lows and lead in weakness by failing to make higher highs"
- **Conflicts:** D15 B; cc10_011/014.
- **Rulebook fix:** D15: add the CC sources to option A's leader test, and add the cross-asset ranking as a weekly step (outside the bot's markets).
- **Already in rule_coverage:** D15 `smt_pick` "leader" covers the index part with the same content. The cross-asset ranking is outside ES/NQ. No new build spec.

### 206. D15-which-index-contradiction
- **rule_id / kind:** D15 / unlisted_contradiction. Scope: index. judgment = false.
- **Rule:** D15 options should be: stronger (A), laggard/sick sister (B), swept index (turtle soup; cc10_011 says it often moves fastest), and fixed ES (cc10_012/cc10_014: the crack in any index signals the trade in ES). cc10_011 calls the stronger and swept choices equal. Drop cc10_011 from A's citations, then test all four smt_pick values.
- **Sources:** cc10_011 ~00:16:48; cc10_014 ~00:02:49.
- **Quote:** "either one is fine there's not one over in the other"
- **Conflicts:** D15 A.
- **Rulebook fix:** D15: add the options, drop the cc10_011 citation from A.
- **BUILD SPEC (setups_models):**
  - In `backtest.combine`, add `pick="swept"` (keep the fill of the instrument whose sweep made the new extreme, i.e. the smt tag is True: the same as "laggard" in the current code; alias it explicitly and document it) and `pick="fixed_es"` (keep only ES fills, but an ES fill qualifies when either instrument's SMT tag shows divergence at that sweep).
  - Params: `smt_pick` adds "swept" and "fixed_es".
  - Test: `test_smt_pick_fixed_es`. An NQ-only divergence with an ES fill: kept under fixed_es. An NQ fill: dropped.

### 207. B18-pm-smt-reference-points
- **rule_id / kind:** B18 / shortened. Scope: index. judgment = false.
- **Rule:** PM SMT reference points (bullish): compare each index's lunch-hour low (12:00-13:00) with the low formed right after 13:00. A failure to make the lower low in any index qualifies the PM long in ES. For bearish, mirror with highs (the mirror is our inference).
- **Sources:** cc10_014_yWBxZsbmK1U ~00:02:18.
- **Quote:** "the low that forms immediately after one o'clock"
- **Conflicts:** none.
- **Rulebook fix:** B18.2: add the PM reference points.
- **BUILD SPEC (setups_models):**
  - In `_smt` for session "PM" with `p.smt_pm_points`, compare the 12:00-13:00 low with the first post-13:00 pivot low (n=1) per instrument, instead of the generic sweep pair.
  - Params: `smt_pm_points: bool = False`.
  - Test: `test_smt_pm_points`. ES lunch low 4000 and post-13:00 low 3998; NQ lunch low 13000 and post-13:00 low 13005: SMT True.

### 208. T4-or-needs-bias-iof
- **rule_id / kind:** T4 / missing_condition. Scope: index. judgment = false.
- **Rule:** OR30/OR60 highs and lows are used as support/resistance (entry and target levels) together with a defined daily bias and HTF institutional order flow (cc10_010 ~11:25). Without bias and IOF, treat them as tags only [our interpretation; ICT does not say 'only'].
- **Sources:** cc10_010_ORbtHOUzAIM ~00:11:25.
- **Quote:** "When we have the opening range idea defined, and we have bias"
- **Conflicts:** none.
- **Rulebook fix:** T4: add the condition.
- **BUILD SPEC (targets_partials):**
  - `or_extra` (built, off) adds OR levels. With `p.or_needs_bias`, OR levels enter the ladder / the turtle-soup or60 variant only when `want` (or the lock side) is non-zero and the daily `iof` agrees.
  - Test: `test_or_needs_bias`. Want 0: no OR rung. Want +1 with iof +1: an OR60 high rung is present.

### 209. T9-strong-am-no-lunch-retrace
- **rule_id / kind:** new / missing_rule. Scope: index. judgment = true.
- **Rule:** If the AM made the day's low with a strong rally, lunch shows no retracement, and the PM resumes higher, hold AM-direction trades into the last hour. Expect the HOD shortly after the 15:00 bond close, in 15:00-16:00 (cc10_012 ~11:54). Mirror for bearish days. Any number for 'no retracement' (e.g. < 25-30%) and a 'PM break of the lunch high' as the trigger are our interpretation.
- **Sources:** cc10_012_qZg_5bac518 ~00:11:54.
- **Quote:** "during lunch we've seen no retracement"
- **Conflicts:** X11.
- **Rulebook fix:** T9/X11: add the conditional hold.
- **BUILD SPEC (management_exits):**
  - With `p.no_lunch_retrace_hold`, at 13:00, for an open AM long: if the 12:00-13:00 low retraced < `lunch_retr_max` of the AM leg (the day low -> the AM high), override the owner #8 12:00 close / `am_exit` for this position, trail the stop to the lunch low, and exit at 15:50 or the target.
  - New PM entries in the same direction after a break of the lunch high get final targets extended to the last-hour window (no 15:00 cut).
  - Params: `no_lunch_retrace_hold: bool = False`, `lunch_retr_max: float = 0.3`.
  - Test: `test_no_lunch_retrace_hold`. AM leg 4000->4040, lunch low 4032 (20%): the position is still open at 13:01 with the stop at 4032.

### 210. T13-day-profile-selection
- **rule_id / kind:** T13 / missing_condition. Scope: index. judgment = true.
- **Rule:** Profile selection:
  - Daily/4h IOF in the bias with no opposing 4h/daily/weekly array nearby -> a two-session close in the bias direction.
  - IOF in the bias but an opposing 4h/daily array 'very close' (proxy: within ADR5, our interpretation) -> the AM moves into the array, then a PM reversal.
  - NY continues London's direction until a 4h opposing array is reached, then reverses (cc10_013 ~4:22-6:20; cc12_004 ~16:40).
- **Sources:** cc10_013 ~00:04:22; cc12_004 ~00:15:52.
- **Quote:** "when I'm bearish in the four hour has not yet traded to a discount array I expect New York open to continue lower"
- **Conflicts:** none.
- **Rulebook fix:** T13: replace "discretionary" with the selection criteria.
- **BUILD SPEC (day_week_context):**
  - In `day_context`, tag `profile_day`:
    - "two_session" when the `iof` side has no opposing D/4h/W array within ADR5 of the prior close;
    - "am_pm_reversal" when one is within ADR5.
  - With `p.day_profile_gate`, on "am_pm_reversal" days the PM lock side is the opposite of the AM's once the array is touched (combines with item 105's same-session PM reversal). On "two_session" days, PM orders are with the AM side only.
  - Params: `day_profile_gate: bool = False`.
  - Test: `test_day_profile_tag`. IOF +1 with a daily SIBI 20 pts above (ADR5 50): am_pm_reversal. 200 pts above: two_session.

### 211. N8-overnight-not-precursor
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = false.
- **Rule:** Trending-day classification (N8) [CC]: overnight price action, trending or ranging, is not a precursor. Leave overnight features out of the trending-day recipe. This conflicts with N9's 2023 rule on a narrow overnight range.
- **Sources:** cc10_009_S0ouOvtjV2I ~00:00:55.
- **Quote:** "it's never a precursor"
- **Conflicts:** N9 (015 ~11:58).
- **Rulebook fix:** N8: add the note; list the N9 conflict.
- **BUILD SPEC (day_week_context):**
  - Where N8 trending-day logic is built (rule_coverage N8 / owner #10 sloppy tests), add `n8_use_overnight: bool = True`. When False, the trending-day classification ignores the overnight range/direction features (the N9 narrow-overnight skip stays as its own switch).
  - Test: `test_n8_no_overnight`. With False, changing the overnight range does not change the trending-day tag.

### 212. B19-bond-trending-day
- **rule_id / kind:** B19 / missing_rule. Scope: needs_unavailable_data. judgment = false.
- **Rule:** Trending-day sponsorship [CC] {needs: ZF/ZN/ZB intraday}: bonds in small ranges at a daily/4h/2h array, with high/medium 08:30 news. A divergence in lows (bullish) among the 5-, 10- and 30-year contracts between 08:00 and 08:30 NY triggers the NY expansion (cc10_009 ~7:43, ~14:00). Without bond sponsorship, don't expect a trending day. 'No trade' is our strict reading.
- **Sources:** cc10_009_S0ouOvtjV2I ~00:14:00, ~00:07:43.
- **Quote:** "you have to have the sponsorship behind it by way of interest rate markets"
- **Conflicts:** none.
- **Rulebook fix:** N8/B19: add the bond sponsorship requirement. No build spec.

### 213. B23-seasonal-trade-procedure
- **rule_id / kind:** B23 / missing_condition. Scope: needs_unavailable_data. judgment = false.
- **Rule:** Commodities: on the first day of each month, list the seasonals due that month and look for confirming reasons, without forcing a trade. Entry: wait for commercials to be in the hedging buy program (COT, B20), then buy at discount arrays. If the market runs opposite to its seasonal, read that as strength that way (or consolidation), and check the COT for commercial net longs.
- **Sources:** cc10_003_R2NjnYozhdw ~00:41:27.
- **Quote:** "wait for them to go into our hedging buy program"
- **Conflicts:** none.
- **Rulebook fix:** B23: add as written (commodities). No build spec.

### 214. B23-commodity-seasonal-windows
- **rule_id / kind:** B23 / missing_rule. Scope: needs_unavailable_data. judgment = false.
- **Rule:** Commodity seasonal map (cc10_003):
  - Soybeans: long Feb -> Jun/Jul, short Jun/Jul -> Sep/Oct, long Sep/Oct -> summer.
  - Wheat: weak Jan -> late-Jun/Aug low.
  - Corn: short May/Jun -> Sep/Oct low.
  - Crude: rally Jan -> Sep/Oct high.
  - Gold and silver: buy the Jul/Aug low.
  - Also cattle, hogs, cocoa, OJ, coffee, cotton and copper per the lesson.
  - A road map only, used with trend/COT/arrays (the B23 conditions).
- **Sources:** cc10_003_R2NjnYozhdw ~00:09:27.
- **Quote:** "look for longs from February going into June July"
- **Conflicts:** none.
- **Rulebook fix:** B23: add the commodity map. No build spec.

### 215. B23-fall-seasonal-low-setup
- **rule_id / kind:** new / missing_rule. Scope: index. judgment = true.
- **Rule:** In seasonally bullish windows (the Sep-Nov fall low; also Feb-May), when NASDAQ/S&P/Dow decline and one fails to make a lower low (three-index SMT) while the market is in a discount, take a swing long bias (the source uses it for stock-buying swing trades). Context/bias only, not an intraday trigger.
- **Sources:** cc10_018_cv-fwKKXrwQ ~00:34:58.
- **Quote:** "we wait for the September to November time period"
- **Conflicts:** none.
- **Rulebook fix:** B23: add the fall-low setup.
- **BUILD SPEC (bias_htf):**
  - Combine item 119 `dsmt` (two indices; DJI not loaded) with item 60's `win_long_fall` / `win_long_spring` and a prior close below the 60-day EQ. Set `fall_low_bias = +1`, which persists until the 60-day high is taken.
  - With `p.fall_low_bias`, use it as `want` when `want == 0`.
  - Params: `fall_low_bias: bool = False`.
  - Test: `test_fall_low_bias`. October with ES making a lower daily low, NQ a higher low, and the price below the 60-day EQ: want +1.

### 216. B23-market-poised-first
- **rule_id / kind:** B23 / missing_condition. Scope: index. judgment = true.
- **Rule:** Before acting on a seasonal long (stock-buying context), first require that the broad market is technically poised to rally: NASDAQ/S&P/Dow moving up collectively, or a bullish three-index SMT at a discount. Then use the seasonal window. No specific timeframe is stated (weekly/daily structure).
- **Sources:** cc10_016 ~00:01:51; cc11_003 ~00:04:37.
- **Quote:** "is the stock market poised the rally"
- **Conflicts:** none.
- **Rulebook fix:** B23: add the prerequisite.
- **BUILD SPEC (bias_htf):**
  - With `p.season_gate` active (item 61), a long window only gates or tags when `poised` = both instruments' 20-day slopes > 0, or item 119 `dsmt == +1` with the price below the 60-day EQ. Mirror for short windows.
  - Test: `test_season_poised`. A spring window with ES and NQ both falling and no dsmt: the window is inactive.

### 217. B20-commodity-term-structure
- **rule_id / kind:** new / missing_rule. Scope: needs_unavailable_data. judgment = true.
- **Rule:** Commodities: if the nearby contract trades above the next contract(s), and stays so across the next few months, there is a premium (a commercial bull market). Rank it first and hold runners, because moves are fast and parabolic. A carrying-charge market (rising forward prices) can still be bullish, just less explosive. A premium is never required and never a veto.
- **Sources:** cc11_001 ~00:14:10; cc10_004 ~00:03:51, ~00:04:48.
- **Quote:** "it merely adds to the likelihood of a strong price rally"
- **Conflicts:** none.
- **Rulebook fix:** B20: add as a commodities note. No build spec.

### 218. D15-fx-carry-bonus
- **rule_id / kind:** new / missing_rule. Scope: fx_only. judgment = true.
- **Rule:** FX only: among currencies showing relative-strength leadership (higher lows vs DXY highs), a favorable interest-rate differential is a supporting bonus, consistent with cc12_001's rate-differential step. A weak tiebreaker, not a filter.
- **Sources:** cc10_002_ygtvWKyOzHQ ~00:29:26.
- **Quote:** "the interest rate differential was a bonus"
- **Conflicts:** none.
- **Rulebook fix:** [fx-only] note. No build spec.

### 219. D15-mt4-overlay-inverted
- **rule_id / kind:** new / missing_rule. Scope: fx_only. judgment = true.
- **Rule:** FX relative strength: either compare highs/lows on currency futures charts, or line-overlay the pairs (invert USD-base pairs so all are quoted vs USD) and read SMT. Either method alone is acceptable. Ideally use both; agreement increases confidence but is not mandatory.
- **Sources:** cc11_002_CxwFON8MLB0 ~00:09:21.
- **Quote:** "you have to invert it when you do the overlay"
- **Conflicts:** none.
- **Rulebook fix:** [fx-only] note. No build spec.

### 220. stocks-selection-long-only
- **rule_id / kind:** new / missing_rule. Scope: stocks. judgment = false.
- **Rule:** Stock swings: select strong stocks from IBD's top 30 industry groups, on the buy side by default. Short selling exists but is deferred to a separate teaching and is described as quicker and harder. Commodities: the long candidate is the futures-group member that makes a higher low while its peers don't.
- **Sources:** cc11_003 ~00:52:05; cc12_002 ~00:08:50.
- **Quote:** "I look for stocks in the top 30 industry groups"
- **Conflicts:** none.
- **Rulebook fix:** Add a [stocks] note (selection and long-only default).
- **BUILD SPEC (no package; parked):**
  - None of the nine work packages covers stocks. Park it in a future `mentorship/stocks.py` swing module.
  - Inputs:
    - a group-rank file (IBD top 30 groups, manual weekly CSV `data/mentorship/ibd_groups.csv`: date, group, rank);
    - daily bars for the stock universe (Alpaca daily, `alpaca_data`).
  - Select stocks whose group rank <= 30 on the last list published before the date. Long side only (`allow_short=False` default). Within a group, prefer the member with a higher daily low while the group's other members made lower lows (item 119 logic applied pairwise).
  - Params: `StockParams(group_rank_max=30, allow_short=False)`.
  - Test: `test_stock_select_long_only`. A ranked-group file and synthetic bars: only rank <= 30 members, longs only, the higher-low member first.

### 221. MB-monthly-bias-routine
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule (full_rule; no correction given):**
  - After the month closes, work through: seasonal -> quarterly shift -> rates -> profile -> intermarket -> structure + SMT -> PD matrix -> levels -> bias.
  - Hold the bias 3 (up to 4) months.
  - Intraday trades only in its direction. When fully aligned, no counter scalps.
- **Sources:** cc12_001_eIdnsgq-G7A ~00:11:22, ~00:12:08, ~00:27:01, ~00:52:52.
- **Quote:** "if that all these things are together I will never want to fade that"
- **Conflicts:** B5 (soft downgrade).
- **Rulebook fix:** New B rule: the monthly routine, its order and the hard side filter when fully aligned.
- **BUILD SPEC (bias_htf):**
  - Add `htf.table` column `mo_bias`, computed on the first session of each month from the prior month-end data:
    - the sign of the monthly draw (item 116 "M" logic);
    - plus `mo_aligned` = the season window (item 60), q_obj direction (item 83), the rates tag (item 94) and dsmt/structure (item 119 / `last_break`) all equal to it.
  - It is held for 63 sessions (84 max) unless the flip state opposes it.
  - With `p.mo_bias_gate`, when `mo_aligned`, block every order against `mo_bias` (including scalps). When it is not aligned, tag only.
  - Params: `mo_bias_gate: bool = False`.
  - Test: `test_mo_bias_gate`. All four components +1: shorts are blocked all month. One disagrees: no block.

### 222. B22-quarterly-shift-direction
- **rule_id / kind:** B22 / shortened. Scope: general. judgment = true.
- **Rule:** Quarterly shift direction: read the last 9-18 monthly candles. If they trend, expect the next shift to continue that trend (don't pick its top or bottom). If they are unclear or consolidating, expect a retracement or reversal of the last 3-4 months' direction over the next 1-2 months.
- **Sources:** cc12_001_eIdnsgq-G7A ~00:20:16.
- **Quote:** "I will elect to anticipate the direction of the previous three to four months direction to reverse"
- **Conflicts:** none.
- **Rulebook fix:** B22: add the direction rule.
- **BUILD SPEC (bias_htf):**
  - Add `htf.table` column `q_dir`. From the monthly bars: when the last 12 monthly closes trend (item 174 "trend" logic applied to monthly bars), `q_dir` = the trend sign. Otherwise `q_dir` = -sign(the net change over the last 4 months).
  - It feeds item 83 `q_obj` (the side of the objective). Tag only unless `q_obj_lean`.
  - Test: `test_q_dir`. 12 rising months: +1. A flat year with the last 4 months up: -1.

### 223. B19-intermarket-cracked-correlation
- **rule_id / kind:** B19 / missing_condition. Scope: needs_unavailable_data. judgment = true.
- **Rule:** On the monthly and weekly (and on the daily via SMT), a bullish structure in the market of interest needs confirmation: positively correlated markets should agree and negatively correlated ones should oppose (e.g. bullish AUD/GBP with a technically weak DXY). A disparity is a 'crack' in correlation and counts against the idea. When safe-haven / flight-to-quality flows drive gold, drop gold as a confirming market.
- **Sources:** cc12_001 ~00:28:40; cc12_002 ~00:24:40.
- **Quote:** "we didn't see any cracking correlation there"
- **Conflicts:** none.
- **Rulebook fix:** B19: add as written. No build spec.

### 224. WB-weekly-checklist-order
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = false.
- **Rule:** Weekly analysis order, carried into the daily analysis:
  1. Relative strength (leaders/laggards; this is the starting point when the monthly is unclear).
  2. COT commercials (12-month net range midpoint).
  3. Market sentiment.
  4. Market profile (consolidating vs trending).
  5. Intermarket confirmation.
  6. Weekly market structure with IOF and SMT.
  7. PD array matrix on the selected range.
  8. Key levels rounded to the 5/10 level toward price.
  9. Weekly bias.
- **Sources:** cc12_002_Ad-votrg6WQ ~00:03:17.
- **Quote:** "after I do my relative strength analysis I go into the commitment of Traders"
- **Conflicts:** none.
- **Rulebook fix:** New B rule: the weekly checklist.
- **BUILD SPEC (bias_htf):**
  - Implement it as an ordered composer in `htf.table`: `wk_bias` = the first non-zero of the available components in ICT's order, each from its own item:
    1. relative strength (item 119 `dsmt` as the index proxy);
    2. `cot_hedge` (item 147, when loaded);
    3. skip sentiment (no data);
    4. `profile` (item 174: consol -> 0, which stops the cascade with a neutral result);
    5. `im_harmony` (item 139);
    6. weekly `iof_w` (item 85);
    7. weekly draw (existing).
  - With `p.htf_bias == "week_check"`, `want = wk_bias`.
  - Round the key levels via `round_step_pts` (built, L17).
  - Params: extend the `htf_bias` values with "week_check".
  - Test: `test_week_check_order`. A consol profile gives 0 regardless of later components. Trend with iof_w +1 gives +1.

### 225. B10-weekly-structure-control
- **rule_id / kind:** B10 / missing_condition. Scope: general. judgment = true.
- **Rule:** On the weekly, classify each swing high/low as short-, intermediate- or long-term (A1), checking it against SMT vs DXY or a correlated market. Then determine which tier of high/low currently controls price. Favour trades that agree with both the current weekly market structure and the monthly directional bias. Treating the controlling swing as the most recent unbroken ITH/ITL is our operationalisation (judgment).
- **Sources:** cc12_002_Ad-votrg6WQ ~00:17:43.
- **Quote:** "trade selected in the direction of the current market structure and monthly directional bias are going to be favored"
- **Conflicts:** none.
- **Rulebook fix:** B10: add the controlling-swing read and the favour rule.
- **BUILD SPEC (bias_htf):**
  - Apply `levels.swing_tiers` (built) to weekly bars. `wk_control` = +1 when the most recent unbroken weekly ITL is below the price and the last ITH was broken; -1 for the mirror; 0 otherwise.
  - Tag `Trade.wk_struct_agree` = (`wk_control` == side == `mo_bias` from item 221). With `p.wk_struct_weight`, `risk_mult *= 0.5` when it does not agree.
  - Params: `wk_struct_weight: bool = False`.
  - Test: `test_wk_control`. Weekly bars with a broken ITH and an intact ITL: +1.

### 226. B6-daily-iof-htf-relative
- **rule_id / kind:** B6 / missing_condition. Scope: general. judgment = true.
- **Rule:** Score daily IOF relative to the monthly/weekly bias. With M/W bearish, the daily should find resistance at up-close candles and break through down-close candles. With M/W bullish, it should find support at down-close candles and break through up-close candles. If the daily shows no institutional sponsorship in the bias direction, treat the setup as low probability (skip or tag). Any sizing response is our own choice, not ICT's.
- **Sources:** cc12_003_3B7Reg2Yiqs ~00:06:01.
- **Quote:** "am I seeing sponsorship and price action"
- **Conflicts:** none.
- **Rulebook fix:** B6: tie the daily IOF reading to the M/W bias.
- **BUILD SPEC (bias_htf):**
  - Add `iof_sponsor` = (the daily `iof` == the weekly bias (item 224 `wk_bias`, else the flip state)). With `p.iof_sponsor_gate` ("off" / "tag" / "skip"), "skip" rejects orders on days where the M/W bias is non-zero and `iof_sponsor` is False.
  - Test: `test_iof_sponsor_gate`. Weekly -1 and daily iof 0: skipped under "skip".

### 227. B5-daily-checklist-fallback
- **rule_id / kind:** B5 / missing_rule. Scope: general. judgment = true.
- **Rule:** Daily analysis order:
  1. COT commercials.
  2. Open interest (used only at a 15%+ change at an HTF array).
  3. Daily IOF.
  4. Expected weekly profile.
  5. Intermarket/SMT (daily into 4h).
  6. Market structure (breakers, mitigation blocks).
  7. PD array matrix.
  8. Key levels.
  9. Daily bias, then transpose it to the 4h.
  
  M/W analysis carries into the daily, and the daily should preferably confirm it. If M/W are unclear, neutral or conflicted, base the bias on the daily alone, and never on less than the daily.
- **Sources:** cc12_003_3B7Reg2Yiqs ~00:13:20.
- **Quote:** "starting with just a daily time frame"
- **Conflicts:** none.
- **Rulebook fix:** B5: add the daily checklist and the daily-only fallback.
- **BUILD SPEC (bias_htf):**
  - Add an ordered daily composer `d_bias`, the same pattern as item 224:
    - COT and OI are skipped until loaded;
    - daily `iof` (B6);
    - weekly profile tag (item 187) as context only;
    - `dsmt` (item 119);
    - `d_breaker` / flip state (items 75, B8);
    - draw.
  - Fallback: when `wk_bias` (item 224) is 0, `want = d_bias`. When `wk_bias` is non-zero, `want = wk_bias` only if `d_bias` agrees or is 0, and orders are tagged `daily_unconfirmed` when `d_bias` is 0.
  - With `p.htf_bias == "wd_check"`.
  - Params: extend the `htf_bias` values with "wd_check".
  - Test: `test_wd_check_fallback`. wk_bias 0 and d_bias -1: want -1. wk_bias +1 and d_bias -1: want 0.
