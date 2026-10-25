# Rulebook gaps: definitions, PD arrays, structure

Topic `definitions_pd_arrays_structure`. 214 verified gaps between ICT's captions and `mentorship_rules.md`. Where the verifier gave a `corrected_rule`, it is the rule used here. Quotes are short caption fragments (caption spelling kept).

How to read each entry:
- **Rule** is the operational rule to build or record.
- **Fix** is the change to make in the rulebook text.
- **Build** gives the work package (from `rule_coverage.md` section 3), where the code acts, the Params switch and its default, and the test. New switches default off unless stated. Build specs are written only for index, general and stocks scope. Items scoped `fx_only`, `bonds_only` or `needs_unavailable_data` get no build spec.
- **[our interpretation]** marks judgment calls (judgment=true items, plus any threshold ICT does not state).

Items not given a new build spec:
- **Already in `rule_coverage.md` with the same content:** A12-disp-gate (= A12 `ob_disp_mult`), L8-vacuum-block-levels (= L8 `vacuum_block`, built), B11-contraction-details (= B11 `inside_bar_body` / `nr_expansion`), E9-bpr-fvg-size (= E9 `size_rules` BPR size-up).
- **Scope gives no spec:** 7 `fx_only`, 2 `bonds_only`, 8 `needs_unavailable_data`.
- **Documentation only:** A5-cc-fvg-term-ob, M3-silver-bullet-name-collision.

Package keys: LD = levels_detectors, SM = setups_models, ESS = entries_stops_sizing, TP = targets_partials, ME = management_exits, NCT = news_calendar_times, DWC = day_week_context, BH = bias_htf, SB = silver_bullet.

---

### 1. A11-bpr-one-pass-definition
- A11 | unlisted_contradiction | general | judgment
- **Rule:** `bpr_def` = `overlap` (Type 1: overlap of a bullish and a bearish FVG) | `single_range` (Type 2), and tag which one applies.
  - **Type 2 definition:** a gap Z=[lo,hi] (an FVG, a void, or one candle's low to the adjacent candle's high) that price crossed fully in one direction and then fully in the other in one pass, then left.
  - **Touch vs balance:** a touch only = repricing, not balancing (032).
  - **Variants:** (a) two-candle: zone = [max(low_i,low_i+1), min(high_i,high_i+1)], extended right, midpoint = EQ; (b) range form (075): swing H, sell-side delivery to L, then a trade above H, so [L,H] is the BPR.
  - **When balanced:** once a later bar's range lies fully outside Z on the far side, Z is balanced and protected. A bullish BPR below price is support and a bearish one above is resistance. A long's stop may sit below its low. A body close below EQ or the low = idea wrong.
  - **No re-use:** do not use a spent gap for new entries in its original direction, and do not wait for its revisit; the next pullback uses a newer FVG.
  - **Continuation trigger (056):** a retrace into a bullish FVG to at least high[c1]/CE, then a trade above the FVG high = permission toward the next buy-side draw.
  - **Trail (003):** move the stop to lo - 1 tick once a new bullish FVG forms above hi.
  - **Targets:** open SIBIs above are valid targets alongside buy-side pools (032). A 1m/3m AM balanced zone can mark the low of the day (055).
  - All timeframes. Bearish mirror.
- **Sources:** 001 ~15:17/~20:43, 003 ~29:37, 010 ~48:27, 012 ~22:34, 026 ~1:05:40, 032 ~51:23, 046 ~50:02, 055 ~15:26, 056 ~7:24, 065 ~4:23:01, 075 ~54:50, 085 ~16:47, 102 ~1:09:31, 101 ~54:46.
- **Quotes:** "one single pass one single pass"; "that's not rebalancing it's repricing".
- **Conflicts:** 010 counts a touched SIBI as balanced, while 032 needs a trade-through. 101 rejects the term for a daily FX FVG; treat that as terminology only.
- **[our interpretation]:** the "fully outside on the far side" test, and the 1-tick trail.
- **Fix:** add Type 2 to A11 and list the conflict in section 3. Re-cite 046 ~50:02 as Type 2 (it shows a single BISI offered on both sides), not as the overlap source.
- **Build (LD):**
  - **Detector:** `levels.single_pass_bprs(o,h,l,c)`, returning Zone(kind="bpr2") with a `balanced_i` index.
  - **Engine:** in `strategy.py`, wire it into DayCtx arrays and `_targets`.
  - **Params:** `bpr_def="overlap"` ("single_range" / "both"); `bpr2_trail=False`; `bpr2_cont_trigger=False`.
  - **Test:** a synthetic down-pass then up-pass bar sequence sets `balanced_i` only after a bar sits fully beyond. A touch-only sequence sets nothing.

### 2. A11-bpr-retrace-allowance
- A11 | unlisted_contradiction | index | judgment
- **Rule:** `bpr_limit` sets how deep a return into a BPR may go:
  - `no_reentry` (001 ~20:43)
  - `ce_touch` (012 ~22:34: CE is the last line of defense)
  - `mt_body_close_abort` (065 ~4:28: wicks may reach the midpoint; a body close beyond EQ = abort)
  - `mt_warn_far_exit` (026 ~1:05:53/~1:54:37: a return to the body MT is fine; reaching the far edge = bail)
  - `far_edge` (024 ~6:18: a full revisit is possible; a trade-through is unlikely, especially with an unfilled FVG beyond)
- **Sources:** 001 ~20:43, 012 ~22:34, 024 ~6:18, 026 ~1:05:53, 026 ~1:54:37, 065 ~4:28.
- **Quotes:** "it can go back up into the midpoint ... I allow for that"; "come back in consequent encroachment that's the last line of defense".
- **Conflicts:** five tolerances across 001/012/026/024/065 against the single A11 abort rule.
- **[our interpretation]:** the default choice of mode. Drop the 003 shallow-probe clause.
- **Fix:** keep 065 as A11's source for the midpoint abort. Re-cite 026 as the "midpoint allowed, far edge = bail" variant. Add a note to Appendix Ep 01.
- **Build (ME):**
  - **Engine:** `run_day` management loop, the existing `bpr_abort` hook.
  - **Params:** `bpr_limit="mt_body_close_abort"` (matches the current `bpr_abort`), with values no_reentry / ce_touch / mt_warn_far_exit / far_edge.
  - **Test:** a 026-style bar path (wick to MT, then to the far edge) exits only in `mt_warn_far_exit` and `far_edge`. Under `mt_body_close_abort`, a body close past MT exits.

### 3. X-efficient-delivery-two-pass
- A5 | missing_rule | general | judgment
- **Rule:** for every gap band (FVG, VI, NDOG, NWOG, wick-only area, void), track `up_pass` and `down_pass` on the band's own TF (wicks count).
  - **Pass states:** no pass = open draw. One pass = one-sided: still a target and S/R, and the missing side is the next expected delivery. Both passes = efficient: not a target.
  - **Execution TF:** a band crossed by a single candle = an unbalanced pocket and a retrace target (exact edge). A band crossed by both up-close and down-close candles = balanced.
  - **After the close:** once price closes above a balanced band's high, that high is support.
  - **Shield:** if the band between price and an array has been crossed both ways several times, do not expect the array beyond it. Use the nearest array in a one-way band; the balanced band's near edge caps the retrace, with the stop beyond the band.
  - **Keep:** NDOG/NWOG stay as references after both passes (050). Bearish mirror.
- **Sources:** 026 ~1:58:21, 050 ~30:29, 055 ~7:24, 060 ~1:06:21, 061 ~1:35:24 (shielded), 061 ~40:20, 078 ~1:13:50.
- **Quotes:** "every price is offered at least two times"; "it's shielded by all of this up and down movement".
- **Conflicts:** 078 judges a daily gap from 4h candles; 061 ~40:20 says LTF back-and-forth does not balance an HTF gap (see item 75).
- **[our interpretation]:** ">= 3 two-way passes" for the shield (078 uses >= 2 opposite LTF candles).
- **Fix:** A5 already separates repriced (touch) from rebalanced (trade through and leave). Add direction-aware pass counts, apply them to VI/NDOG/NWOG/wicks/voids, and add the one-way-draw / two-way-shield consequence. Cite 061 ~1:35:24, not ~35:21.
- **Build (LD):**
  - **Detector:** `levels.pass_state(h,l,z,a,b)` -> (up, down).
  - **Engine:** used in `strategy._targets` (skip efficient bands) and the `_scan` gap pick (retrace cap).
  - **Params:** `two_pass_state=False`; `shield_passes=3`.
  - **Test:** a band crossed up then down is removed from targets. A band crossed once stays a target.

### 4. A12-ob-requires-signatures
- A12 | shortened | general | judgment
- **Rule:** bullish OB = the last down-close candle (or run) before an up move AND that move displaces and leaves a bullish FVG (022).
  - Until the displacement/FVG prints it is only a "potential OB" (022 ~1:37:52).
  - On the return into it, price must not trade below its MT (036; bodies per D4).
  - Note in the rulebook that ICT calls the bare "last opposite candle" definition incomplete (001 ~57:02). Bearish mirror.
- **Sources:** 001 ~57:02, 022 ~13:12, 022 ~1:37:52, 036 ~1:00:14.
- **Quotes:** "There has to be signatures"; "it's not the last down closed candle before the up move".
- **Conflicts:** A12 lists the FVG only under Quality; 022 makes it defining.
- **[our interpretation]:** drop the "short-term high taken first" step.
- **Fix:** move "displacement leaves an FVG" from A12 Quality into the definition. Add the potential-OB state.
- **Build (ESS):**
  - **Engine:** `_scan` OB-entry branch (`ob_entry` path ~3705). Require that an FVG with c1 in {OB index, OB index+1} exists before arming.
  - **Params:** `ob_need_fvg=False`.
  - **Test:** an OB candle followed by a move with no FVG does not arm; the same with an FVG arms after c3 closes.

### 5. A12-ob-candle-selection
- A12 | unlisted_contradiction | general | judgment
- **Rule:** `ob_pick`:
  - `blend` (A12, 032): blend a consecutive run. 065 variant: blend only if the whole run lies inside a pre-called HTF array; level = open of the first candle; MT = (low first + high last)/2; wicks may pass MT, a body close beyond = invalid.
  - `original` (012): first/highest candle of the run; a later candidate is valid only if its body low is not below the chosen body low.
  - `largest_body` (cc03_004/cc04_003): the lowest down candle at or through HTF support S, tie-break on the largest |o-c|.
  - **All modes:** skip a last candle whose body sits fully inside the previous same-colour body and is clearly smaller (cc06_005).
  - Bearish mirror.
- **Sources:** 012 ~14:06, cc04_003 ~1:00, cc03_004 ~10:30, cc06_005 ~19:10, 065 ~1:21:02, 032 ~53:04.
- **Quotes:** "go back to that original High candle extend it forward"; "use the big beefier body candle".
- **Conflicts:** A12 blend vs 012 original vs cc03/cc04 largest body vs 065 blend-only-inside-array.
- **[our interpretation]:** S tolerance (S inside the candle's range or within 1 body height); "clearly smaller".
- **Fix:** make `ob_pick` a listed decision in section 3. A12 Quality already carries 012.
- **Build (LD):**
  - **Detector:** `levels.order_block` / `order_block_blend` gain `pick=`.
  - **Params:** `ob_pick="blend"` ("original" / "largest_body" / "blend_in_htf"); `ob_skip_encapsulated=False`.
  - **Test:** a fixture with three down candles (first highest, last tiny inside) gives a different anchor per mode.

### 6. A12-consolidation-ob-open-level
- A12 | missing_condition | general | judgment
- **Rule:** on 1h, the last down-close candle before a consolidation range (bullish context): extend its open right as support.
  - Pullbacks there are long areas.
  - Bearish mirror: the open of the last up-close candle before the consolidation = resistance.
- **Sources:** 008 ~4:09 (EUR/USD 1h, single example).
- **Quote:** "the opening price extend that through".
- **Conflicts:** none.
- **[our interpretation]:** invalidation on a body close below the open; combining with an intraday OB/FVG entry; consolidation detection.
- **Fix:** add as an A12 note (one FX example).
- **Build (LD):**
  - **Detector:** `levels.consolidation_ob_opens(o,h,l,c,tf=60)`.
  - **Engine:** feeds `strategy._targets` / entry arrays as kind "cons_ob_open".
  - **Params:** `cons_ob_open=False`.
  - **Test:** a 1h fixture of range bars preceded by a down candle yields one level at that candle's open.

### 7. A12-cisd-open-buy-level
- A12 | shortened | index
- **Rule:** bullish case:
  - open_ref = the open of the first (highest) candle of the down-close run.
  - CISD is confirmed when high >= open_ref + 1 tick. Then rest a buy limit at open_ref (fill on a 1-tick print through, E3).
  - Valid while no body closes below the run low.
  - Each later down-close run that gets its own CISD before the draw gives a new open_ref for an add (E12 sizes; no adds after partials).
  - Bearish mirror.
- **Sources:** 032 ~53:04, ~55:30.
- **Quote:** "one tick above it that becomes an order block".
- **Conflicts:** M11 buys at or below the EQ of the post-CISD range; 032 buys at the series open.
- **Fix:** A12 CISD: add the 1-tick trigger, the open as the buy level on every return, and an add per new CISD. Note the M11 conflict.
- **Build (ESS):**
  - **Engine:** `_scan` `cisd_ob_entries` branch (M11b), plus the add-arming block in `run_day`.
  - **Params:** `cisd_ob_px="eq"` ("open"); `cisd_adds=False`.
  - **Test:** a fixture with two down runs and two CISDs fills an entry plus one add at the two opens.

### 8. A8-inversion-any-pd-array
- A8 | missing_rule | general | judgment
- **Rule:** when a body closes through any PD array (FVG, OB, breaker, VI, ORG, NWOG), flag it inverted with the opposite role.
  - Store only three prices: high, low and MT/CE (per D4 for OBs; 50% of high-low for breakers). Touches use E3 1-tick fills.
  - **OB:** a body close below a bullish OB's low makes it bearish. On the retrace up, expect resistance at its low and MT, and look for shorts once displacement lower follows. A body close above its MT invalidates the new role.
  - **Breaker:** a bearish breaker traded back above has its MT as support; a body close below the MT invalidates.
  - The A8 depth rules pick which of the three levels applies. Mirror.
- **Sources:** 090 ~2:11:45, 068 ~13:37, 086 ~11:30, 035 ~1:02:55.
- **Quotes:** "any PD array can be inversion levels but they're not zones".
- **Conflicts:** A13 treats a breaker only as sweep-then-break; A8 inversion is FVG-only.
- **[our interpretation]:** which three prices per array type.
- **Fix:** generalise A8 to all PD arrays, stored as three exact levels.
- **Build (LD):**
  - **Detector:** `levels.invert(zone, i_close)` -> Zone(kind="inv_<k>", levels=(lo,mt,hi)).
  - **Engine:** `strategy._targets`, plus the `_scan` entry arrays for `ifvg_entry`-style entries.
  - **Params:** `inversions=()` (subset of "ob", "breaker", "vi", "org", "nwog").
  - **Test:** a bullish OB closed below then retraced to its MT produces a short array at exactly lo/mt.

### 9. A12-ob-overshoot-to-vi
- A12 | missing_rule | index | judgment
- **Rule:** price may trade through a bearish OB as far as an adjacent lower-TF VI just above it.
  - Zone = [OB level, VI far edge].
  - A wick into the VI does not invalidate.
  - Mirror for bullish.
- **Sources:** 050 ~33:56 (ES, single source).
- **Quote:** "it's going to go right in that inefficiency".
- **Conflicts:** none.
- **[our interpretation]:** a close above the VI far edge invalidates; stop = VI far edge + 1 tick; short entries at the VI.
- **Fix:** add to A12 as an overshoot allowance.
- **Build (ESS):**
  - **Engine:** `_scan` OB stop calc. If a VI (from `levels.volume_imbalances`) touches the OB's far side, extend stop/invalidation to VI far + 1 tick.
  - **Params:** `ob_vi_overshoot=False`.
  - **Test:** a fixture OB with a VI above it: a wick into the VI keeps the trade, and a close above the VI exits.

### 10. A12-mt-all-blocks-ce-all-gaps
- A12 | shortened | general
- **Rule:** add MT = 50% of the mitigation-block zone (per D4) to A15, and apply the "bodies must not close through MT" invalidation (E6/X8) to mitigation blocks (021 ~21:06).
  - Extend CE explicitly to VIs and liquidity voids.
  - Wick CE (A23) and FVG CE (A5) already exist.
- **Sources:** 021 ~21:06.
- **Quote:** "whether it be a breaker mitigation block or just a standard order block".
- **Conflicts:** none.
- **Fix:** A15 gains an MT. A9/A10 gain a CE.
- **Build (LD):**
  - **Detector:** add `.mt` to `levels.mitigation_blocks` zones and `.mid` (CE) to `volume_imbalances` / `voids` zones (Zone.mid exists).
  - **Engine:** `mit_body_respect` uses MT.
  - **Params:** `mit_mt_invalid=False`.
  - **Test:** a mitigation block with a body close below MT is dropped when the switch is on.

### 11. D4-mt-source-tally
- D4 | unlisted_contradiction | general | judgment
- **Rule:**
  - **Option A (range):** add 028 ~1:04:42, 036 ~1:00:21, 058 ~6:31, and 065A ~1:21 (multi-candle blocks only). 101 ~33:03 is unspecified.
  - **Option B (body):** add 065A ~40:00/~1:39 (single candles), 100 ~49:02, cc04_013 ~17:01.
  - **Sensitive-range variant:** MT = (high+open)/2 (cc04_013 ~07:02).
  - **Switches:** `mt_mode` = body | range | body_single_range_blended. `mt_break` = trade (028, 036) | close (B7, 058, 065A ~1:21, 101 ~33:03).
  - **Default:** a trade below MT is a warning; a close below it is the failure.
  - **Pullback read (028):** a bullish pullback that stops at or above the wick CE implies a return up into the gap above.
  - Carry the daily OB open and MT for the week.
- **Sources:** 028, 036, 058, 065 (~40:00, ~1:21, ~1:39), 100, cc04_013 (~07:02, ~17:01), 101.
- **Quotes:** "if we close below the mean threshold half of that candle's body".
- **Conflicts:** B7 close-based vs 028/036 trade-based; body vs range across sources.
- **[our interpretation]:** the default warning/failure split.
- **Fix:** update the D4 tally with these sources. Add `mt_break` as a decision.
- **Build (ESS):**
  - **Engine:** `_scan` MT computation (~3563) and the MT stop/exit in `run_day`.
  - **Params:** `mt_mode` gains "sensitive" and "body_single_range_blended"; `mt_break="close"` ("trade" / "warn").
  - **Test:** a wick below MT then a recovery: "close" holds, "trade" exits, "warn" tags only.

### 12. A13-breaker-candle-selection
- A13 | unlisted_contradiction | general
- **Rule:** `breaker_candle`:
  - `last` (015 ~21:17, 043 ~18:03; bot default)
  - `extreme_close` (032 ~41:26, 063 ~3:49, 081 ~12:52)
  - `extreme_body` (029/048/096)
  - Never pick by largest body alone (032).
  - The swing pattern must hold on bodies; discard wick-only extremes (060, 081).
  - Bearish extreme_close = the lowest close among the down-close candles at the swing low; 081 pairs it with the biggest body.
  - Weekly breaker: find the candle on the daily (063).
- **Sources:** 015 ~21:17, 032 ~41:26, 043 ~18:03, 060 ~26:39, 063 ~3:49, 081 ~12:52.
- **Quotes:** "you got to look for where the highest closing price is"; "the Wicks do the damage".
- **Conflicts:** 015/043 last vs 032/063/081 extreme close vs A13 "by body".
- **Fix:** A13/D6: replace "by body" with the switch. Cite 015/043. Add the bearish selection and the body-swing requirement.
- **Build (LD):**
  - **Detector:** `levels.breaker_candle(o,c,a0,ext_i,kind, pick=)`.
  - **Params:** `breaker_candle="last"` ("extreme_close" / "extreme_body"); `breaker_body_swing=False`.
  - **Test:** a fixture with two up-close candles (later one larger body, earlier one higher close) picks a different index per mode.

### 13. A13-breaker-zone-extent
- D6 | unlisted_contradiction | general | judgment
- **Rule:** the swing is the outer H1-L-H2; ignore minor highs inside [L,H1] (044). Zone options:
  - `body`
  - `range` (031, 032, cc04_005, 072, 078, 084)
  - `blend` (025, 044, 042: union of the consecutive candles at the swing low)
  - `leg_from_disruptor` (070: from the opposite candle that disrupts the A->B run to B)
  - **Overshoot:** a 1-tick overshoot of the zone high still counts (042 ~58:37).
  - **Tests and tags:** test `range` for HTF breakers projected onto the daily. Also tag breakers as mitigation (078).
- **Sources:** 025 ~12:13, 032 ~41:26, 042 ~46:29/~58:37, 044 ~37:47, 070 ~46:45, 072 ~2:37, 078 ~13:36, 084 ~25:11.
- **Quotes:** "these two down closed candles together it's all one".
- **Conflicts:** D6 recommends body vs the range sources; D6 option C misdescribes 070.
- **[our interpretation]:** default choice.
- **Fix:** D6: add blend. Re-describe option C as leg_from_disruptor (070). Drop the whole-leg attribution to 042.
- **Build (LD):**
  - **Detector:** `levels.breaker_zone(... mode=)` gains "blend"; the existing "leg" is renamed or aliased to start at the disruptor candle.
  - **Params:** `breaker_zone` adds "blend" and "leg_disruptor".
  - **Test:** two consecutive down candles at the swing produce the union zone in "blend".

### 14. A13-breaker-fvg-refinement
- A13 | shortened | index
- **Rule:** bullish breaker zone = [low, high] of the breaker candle, extended right. Refinement = any FVG or VI inside it; enter there.
  - The idea holds while bodies stay inside or above the refinement; wicks may reach the zone low (031 ~1:02:29; 032 ~41:26).
  - Then expect expansion toward buy-side. Bearish mirror.
- **Sources:** 031 ~1:02:29, 032 ~41:26.
- **Quote:** "the bodies are staying inside that fair value Gap the Wicks can go outside".
- **Conflicts:** none.
- **Fix:** add the refinement procedure to A13.
- **Build (ESS):**
  - **Engine:** `_scan` `breaker_entry` path. Search FVG/VI inside `bz`, set entry at its near edge, cancel on a body close below its low.
  - **Params:** `breaker_refine=False`.
  - **Test:** a breaker with an inner FVG enters at the FVG edge, not at bz.top.

### 15. A13-breaker-needs-rebalance-and-fvg
- A13 | missing_condition | general | judgment
- **Rule:** a bullish breaker is confirmed only when the break above H is a fast repricing or range expansion right after the sell-stop run (cc04_005 ~4:31, ~6:42).
  - Measure "leaving" as a close above the BODY high of the breaker candle (001 ~56:19).
  - Price should not trade back into the rebalanced range (001 ~45:39). Bearish mirror.
- **Sources:** 001 ~45:39/~56:19, cc04_005 ~4:31/~6:42.
- **Quote:** "repricing lower after buy stops are taken that is a confirmation".
- **Conflicts:** none.
- **[our interpretation]:** require A20 displacement (an FVG) on the breaking leg as a testable param, not as an ICT rule; also the speed window.
- **Fix:** add the confirmation condition to A13.
- **Build (SM):**
  - **Engine:** `_scan` breaker branch.
  - **Params:** `breaker_needs_disp=False` (FVG on the break leg within `breaker_disp_bars=3`); `breaker_break_ref="wick"` ("body_high").
  - **Test:** a slow overlapping break leg with no FVG gives no breaker when on.

### 16. A13-breaker-close-vs-wick
- A13 | missing_condition | general
- **Rule:** bearish case, after high-low-higher-high:
  - If a candle BODY closes below the swing low, mark the bearish breaker. The expected retrace stops at the breaker, so there is no need to wait for the higher imbalance.
  - If the low is only wicked through, it is an MSS without a breaker; use the FVG/imbalance above for the entry (035 ~42:44).
  - Bullish mirror.
- **Sources:** 035 ~42:44.
- **Quote:** "you won't need to think about coming back up into here".
- **Conflicts:** none.
- **Fix:** A13: add the close condition and the array choice.
- **Build (SM):**
  - **Engine:** `_scan` array choice after the MSS. Body close beyond the swing -> breaker entry first; wick only -> FVG entry.
  - **Params:** `breaker_by_close=False`.
  - **Test:** two fixtures (wick break vs body break) pick different entry arrays.

### 17. A13-breaker-mt-trade-test
- A13 | wrong | index | judgment
- **Rule:** bullish breaker MT = 50% of the breaker range (018: ~4053.25).
  - Price may trade into the breaker, and adds are allowed above the MT.
  - Price trading below the MT (beyond the A4 1-2 tick allowance) = idea wrong (018 ~1:56).
  - `breaker_mt_test` = trade (018) | close (070 ~56:01 if confirmed). Bearish mirror.
- **Sources:** 018 ~1:56.
- **Quote:** "I don't want to see it Go below that level right there".
- **Conflicts:** A13 cites 018 ~1:22 for a close test; M4 has it trade-based.
- **[our interpretation]:** default. Drop the 09:30 wick claim.
- **Fix:** A13: re-word as trade-based to match M4.
- **Build (ME):**
  - **Engine:** the existing `breaker_mt_respect` exit in `run_day`.
  - **Params:** `breaker_mt_test="close"` ("trade" uses low < MT - `mohawk_ticks`).
  - **Test:** a 2-tick wick under MT exits only in "trade".

### 18. A13-breaker-lifetime
- A13 | missing_condition | index
- **Rule:** extend a breaker zone to at least the 16:00 close.
  - It stays eligible for repeat retests that day, including the PM last hour (043 ~4:43, ~16:07).
  - A later stop hunt that forms a newer low-high-low on top of it does not replace the original breaker (015 ~22:43).
  - Entries may accumulate inside it without waiting for a break and retest (015).
  - Invalidation per the breaker MT rule.
- **Sources:** 015 ~22:43, 043 ~4:43/~16:07.
- **Quote:** "extended it throughout the day to the last hour".
- **Conflicts:** none.
- **Fix:** A13: replace "first touch is valid" with a day lifetime.
- **Build (SM):**
  - **Engine:** keep breakers in a per-day list in `run_day` state. `_scan` re-arms on each retest. Keep the original when a newer one forms on top.
  - **Params:** `breaker_day_life=False`; `breaker_keep_original=False`.
  - **Test:** an AM breaker retested at 15:10 arms a PM-last-hour short.

### 19. A19-break-against-htf-stop-run
- A19 | missing_condition | general | judgment
- **Rule:** count an intraday MSS or breaker only when it agrees with the HTF (daily/4h) order flow and draw.
  - A break of a short-term low while HTF flow is bullish = a sell-stop run, so arm longs (cc09_004 ~9:01; 102 ~39:11).
  - A bearish-breaker shape below an untaken upside draw is a speed bump: do not short it (020 ~0:28, ~7:36).
  - False breakouts of a consolidation come against the primary trend: in bearish markets fade breaks above the range; in bullish markets fade breaks below (cc02_008 ~0:58; cc09_004).
  - Keep A19's existing FVG requirement.
- **Sources:** 102 ~39:11, cc02_008 ~0:58, cc09_004 ~9:01, 020 ~0:28/~7:36.
- **Quote:** "it's not a breaker it's just a speed bump".
- **Conflicts:** none.
- **[our interpretation]:** HTF flow source = the `htf.table` bias column.
- **Fix:** A19/A13: add the HTF agreement condition. M12: tie the false-break side to the primary trend.
- **Build (SM):**
  - **Engine:** `_scan` MSS block gate on `want`.
  - **Params:** `mss_requires_htf_agreement=False`; `stoprun_rearm=False` (a counter-HTF break arms the opposite side's sweep).
  - **Test:** with bias long, a bearish MSS fixture produces no short and, with `stoprun_rearm`, arms a long sweep.

### 20. N-opposing-fvg-speed-bump
- new | missing_rule | index | judgment
- **Rule:** with bias D, an opposing FVG (5m+) between price and the draw is a speed bump, not a barrier, target or exit.
  - Expect a trade through it, possibly after a brief stall inside (019 ~11:08), or straight through with no respect (089 ~4:52).
  - Once bodies close beyond it in D, it acts as S/R under A8; retraces go to its near edge or CE (019 ~7:30, ~19:21).
  - If it is closed back through against D, it is resistance for the next return.
- **Sources:** 019 ~7:30/~11:08/~14:55/~19:21, 089 ~4:52.
- **Quote:** "it'll act as a speed bump but it's not a barrier".
- **Conflicts:** owner #7 `htf_resist_cap` treats an overhead 15m FVG as resistance. This is a direct tension; record it as an owner question.
- **[our interpretation]:** which TFs count as a speed bump vs the owner #7 cap.
- **Fix:** add a new rule; cross-reference owner #7 / Ep02.10.
- **Build (TP):**
  - **Engine:** `_targets` / `_resist_live`. Do not cap or exit at an opposing FVG of TF in `speed_bump_tfs` when bias agrees.
  - **Params:** `speed_bump_tfs=()`.
  - **Test:** with `(5,)`, a long's ladder ignores an overhead 5m SIBI; with `()`, the current behaviour.

### 21. A6-breakaway-identification
- A6 | wrong | general | judgment
- **Rule:** a breakaway candidate needs HTF context: price leaves a pre-marked level expected to hold (an HTF FVG edge held by bodies, a BPR, or an HTF level respected earlier in the week). No context = common gap. Forms (bearish shown):
  - (a) 001: the first FVG formed as price accelerates away from the held level, with or without an MSS.
  - (b) 062: buy-side run into the HTF level; the FVG of the first MSS = common gap; the SIBI of the second MSS = breakaway.
  - (c) 060: the FVG right after a blow-off run through the target pool is LIKE a breakaway gap (an analogue, not a labelled breakaway).
  - **Confirmation:** at the open of the candle after c3, if that candle stays outside the gap.
  - **If price returns into it:** it may be traded with the stop beyond the bodies of its candles. A body close beyond CE = not breakaway, exit.
  - Part of the gap is normally left unfilled.
- **Sources:** 001 ~42:50/~44:20, 062 ~34:53/~35:59, 060 ~1:14:06.
- **Quote:** "Breakaway gaps must it must have some context".
- **Conflicts:** A6 "first FVG after an MSS, may retrace to half" vs 001 (no MSS) vs 062 (second MSS).
- **[our interpretation]:** the "held level" detection and the analogue form (c).
- **Fix:** rewrite A6 breakaway. Re-cite 001 correctly.
- **Build (LD):**
  - **Engine:** extend the existing `breakaway` tag (Ep01.5) with `breakaway_def="first_after_mss"` (current) | "context" (needs an HTF level within `breakaway_ctx_pts` of the leg origin) | "second_mss".
  - **Test:** a 062-style fixture tags only the second-MSS SIBI under "second_mss".

### 22. A6-measuring-gap-confirmation
- A6 | missing_condition | general
- **Rule:** a measuring candidate is a later FVG in the same swing after a breakaway gap (A6).
  - **Qualified** only when the next pullback leaves its far portion unfilled and price continues. A shallow IOFED dip into it is allowed and can be an add (003).
  - **Projection, bearish:** anchor from the swing high to the LOW of the SIBI and take -1 SD. **Bullish:** from the swing low to the HIGH of the BISI, -1 SD.
  - **Target validity:** only when the -1 SD lies beyond an old liquidity pool (062 ~44:24).
  - **Fill:** bodies filling the gap drop the label and the projection.
- **Sources:** 003 ~31:51/~1:02:31, 011 ~6:37, 062 ~44:24.
- **Quote:** "that confirms and qualifies it as a measuring Gap".
- **Conflicts:** none.
- **Fix:** A6: add the qualification step, the anchor and the pool condition.
- **Build (TP):**
  - **Engine:** `_targets` measuring projection (`measuring_target`, Ep03.5) gains a state.
  - **Params:** `measuring_qualify=False` (project only after a pullback leaves the far edge untouched and a new extreme prints); `measuring_need_pool=False`.
  - **Test:** a fixture whose pullback fills the gap gets no measuring rung.

### 23. E2-iofed-full-definition
- E2 | shortened | general
- **Rule:** IOFED long, in order:
  - (1) a sell-side pool is swept;
  - (2) an MSS up prints;
  - (3) displacement leaves a BISI expected to stay open (breakaway-type, 047);
  - (4) price retraces into the BISI without reaching CE, and the retrace low is a 3-candle swing low inside it.
  - Entry at the BISI near edge or 1 tick in. A retrace to CE or beyond is not an IOFED. Mirror.
- **Sources:** 015 ~18:57, 047 ~10:40.
- **Quote:** "a swing low inside of a buy side imbalance sell side inefficiency".
- **Conflicts:** none.
- **[our interpretation]:** stop below the swing low or the BISI.
- **Fix:** E2: add the sequence and the swing-low signature.
- **Build (ESS):**
  - **Engine:** `_scan` entry block, `entry="iofed"` (E2 item).
  - **Params:** `iofed_strict=False` (requires sweep+MSS context, low > CE, and a confirmed 3-bar swing low inside the gap).
  - **Test:** a retrace that tags CE is rejected.

### 24. A5-caffeine-bar-bisi
- A5 | shortened | index | judgment
- **Rule:** for a bullish FVG whose c2 is a single large displacement candle, the gap is a significant array.
  - On the retrace it is valid while price does not trade through its low (c1 high). On a normal day any trade below the low = failed.
  - On NFP/FOMC days price can overshoot such arrays, so do not judge validity then (they are no-trade days, N1/N3). Mirror.
- **Sources:** 006 ~12:34.
- **Quote:** "any time you have a big one single candle".
- **Conflicts:** none.
- **[our interpretation]:** "large" = c2 range >= 2x the average range of the prior 20 bars.
- **Fix:** add to A5.
- **Build (LD):**
  - **Detector:** `levels.fvgs` adds a `single_bar` tag (c2 range test).
  - **Engine:** `_scan` treats a trade below the low as invalid (not CE) for tagged gaps.
  - **Params:** `single_bar_fvg_strict=False`.
  - **Test:** a 1-tick trade below the low kills only tagged gaps.

### 25. A5-partial-fill-strength-read
- A5 | missing_condition | general
- **Rule:** while bearish, after a SIBI forms (intraday after entry, or the governing HTF SIBI), the upper half (CE to top) should stay unfilled.
  - A retrace that leaves part of the gap open, with no body close up into c1's low = heavy/decisively weak (confirms the short). Keep the bearish view while the upper half is open.
  - Price trading into the upper half = no new positions. If it reprices there without taking the relevant opposite liquidity, hold only if price drops aggressively right away.
  - Upper half filled (body close to the top) = the HTF read shifts to consolidation or a deeper retracement; re-evaluate.
  - Bullish mirror: the lower half of a BISI stays open.
- **Sources:** 007 ~10:00, 028 ~37:40, 103 ~26:08, 092 ~1:09:46, 100 ~15:37.
- **Quote:** "if I'm bearish I want to see the upper half stay open".
- **Conflicts:** none.
- **Fix:** A5: add the bearish mirror and the failure handling.
- **Build (ME):**
  - **Engine:** `run_day` add block. Block adds when price trades beyond the CE of the newest post-entry FVG; tag `strength_read` on the Trade.
  - **Params:** `far_half_no_adds=False`.
  - **Test:** a SIBI formed after entry and retraced past CE blocks the next add.

### 26. A5-ob-in-vi-over-newer-fvg
- A5 | unlisted_contradiction | index | judgment
- **Rule:** while adding to an open long after sell-side is already cleared: if a down-close candle (bullish OB) traded into a volume imbalance, add at that OB's MT, not at a later small FVG in the same pullback.
  - The VI below must not be pierced (a touch is allowed) and is the stop reference.
  - This differs from 065B (FVG overlapping an OB -> FVG near edge first) because the arrays are separate. Mirror.
- **Sources:** 009 ~12:07.
- **Quote:** "I'm looking at the down closed candle".
- **Conflicts:** 065B ~3:02:40.
- **[our interpretation]:** "already cleared" = the sweep happened before the first fill.
- **Fix:** add a precedence note to A5/E12.
- **Build (ESS):**
  - **Engine:** `_ob_add`. Prefer an OB whose low touches a VI over a newer FVG.
  - **Params:** `add_pref_ob_in_vi=False`.
  - **Test:** a fixture with both arrays adds at the OB MT.

### 27. A5-ltf-fvgs-inside-daily-bisi
- A5 | missing_rule | general | judgment
- **Rule:** bullish HTF bias with price inside a daily BISI Z (CE = midpoint).
  - 1h/15m FVGs inside Z above CE: a fill is acceptable, and holding without a fill is stronger. Those below CE should stay open.
  - Continuation case = reactions stay in the upper half and no lower-half LTF FVG is filled.
  - If one is filled (bodies through), downgrade and wait for new structure. Mirror.
- **Sources:** 012 ~19:16.
- **Quote:** "the ones in the lower half they are likely to stay open".
- **Conflicts:** none.
- **[our interpretation]:** no new longs off Z that session after a lower-half fill.
- **Fix:** add a new A5 sub-rule.
- **Build (BH):**
  - **Engine:** `htf.table` column `dbisi_state` (upper_ok / lower_filled) from 1h bars; the `_scan` gate blocks longs off Z when lower_filled.
  - **Params:** `dbisi_lower_half=False`.
  - **Test:** a 1h FVG below the daily CE filled at 10:00 blocks a later long.

### 28. A21-htf-fvg-upper-half-and-discount
- A21 | missing_condition | general | judgment
- **Rule:** long location filter when bullish: the entry sits in the upper half of the active daily BISI (>= its CE; "premium becomes discount", not an A8 IFVG) AND below the 50% EQ of the larger multi-day dealing range.
  - Both must hold. Mirror for shorts.
- **Sources:** 012 ~18:29/~21:04.
- **Quote:** "premium becomes discount".
- **Conflicts:** none.
- **[our interpretation]:** the whole filter (ICT will revisit the concept); the multi-day swing choice.
- **Fix:** add to A21. Drop the 3912.25-4056.75 numbers.
- **Build (BH):**
  - **Engine:** `_scan` bias gate using the `htf.table` daily BISI and the A21 multi-day range.
  - **Params:** `dbisi_upper_and_discount=False`.
  - **Test:** an entry above the multi-day EQ is blocked even inside the BISI upper half.

### 29. A5-pd-array-lookback-priority
- A5 | shortened | general
- **Rule:** W20/W40/W60 = the last 20/40/60 trading days, ending yesterday.
  - Tag each daily level (FVG edges/CE, OB, breaker, rejection block, mitigation block, wick CE, old highs/lows) priority 1 (<=20), 2 (21-40), 3 (41-60); ignore older (HTF weekly+ exception: item 113).
  - Pick draws/targets from W20 first. Extend to W40, then W60, only if price is beyond W20's extreme or no unused array remains on that side.
- **Sources:** 015 ~4:35, cc07_004 ~3:50.
- **Quote:** "the highest form of sensitivity ... within the last 20 days".
- **Conflicts:** none.
- **[our interpretation]:** the escalation trigger (by analogy with B21).
- **Fix:** A5: replace "up to 60 days, equal" with the priority.
- **Build (BH):**
  - **Engine:** `htf._arrays` adds an `age_days` field; the `htf.table` draw pick sorts by age tier.
  - **Params:** `array_age_tiers=False`.
  - **Test:** with a 15-day and a 45-day array on the same side, the 15-day one is the draw.

### 30. A5-quadrants-any-gap-ladder
- A5 | wrong | general | judgment
- **Rule:** for every FVG, VI, NWOG, NDOG, ORG or other gap: primary levels = low, CE, high; secondary = 25% and 75%.
  - **Switch `quad_mode`:** all (055/092) | min_size (101: FX ~9-10 pips; any ES threshold is ours).
  - **Use:** levels on the gap's own TF, transposed down. Bodies respect, wicks may pierce. A reaction a few ticks short of a quadrant counts.
  - **030 ladder (bullish):** entry at the FVG high, then at the midpoint between high and CE, then at CE; stop below the FVG low.
  - **Kill:** discretionary, once price trades through the midpoint/CE (trade-based). NWOG always carries all five levels. Bearish mirror.
- **Sources:** 055 ~8:10, 030 ~58:34, 036 ~1:19:14, 101 ~53:12, 092 ~1:08:57.
- **Quote:** "any fair value Gap or a gap of any kind".
- **Conflicts:** A5 "large only" vs 055/092; X8 close vs 030 trade; L5 "optional" vs 036.
- **[our interpretation]:** ES threshold; the shortfall tolerance (1-2 ticks).
- **Fix:** A5: remove 055 from the "large only" citation. L5: NWOG quarters standard.
- **Build (ME):**
  - Already present: quadrants (`fvg_quadrants`, `fvg_quad_min_pts=4.0`; "all" = 0; `gap_quarters`/`nwog_quarters`) and the E2 ladder (in coverage).
  - **New:** `ce_exit="close"` ("trade") in the `run_day` CE exit (X8 path).
  - **Test:** a wick through CE after the CE fill exits only in "trade".

### 31. A5-reclaimed-fvg-full-revisit
- A5 | missing_rule | index | judgment
- **Rule:** bearish: a SIBI with a BPR behind it (above it) can be revisited to its far edge and still be resistance.
  - Do not exit while price is inside the SIBI and below the BPR.
  - Invalidation follows the BPR rule (A11 midpoint body close), not the FVG far edge. Mirror.
- **Sources:** 026 ~1:08:48.
- **Quote:** "all this is is a reclaimed fair value Gap".
- **Conflicts:** none.
- **[our interpretation]:** "behind" = the BPR overlaps or abuts the SIBI's far side within 1 tick.
- **Fix:** add to A5. Drop the older/newer ordering.
- **Build (ME):**
  - **Engine:** `run_day` FVG-far-edge exit. Skip it when a BPR sits behind the gap; use `bpr_abort` instead.
  - **Params:** `fvg_bpr_backstop=False`.
  - **Test:** a far-edge tag with a BPR behind does not exit.

### 32. A5-broken-fvg-reclaim
- A5 | missing_condition | general | judgment
- **Rule:** a broken bullish FVG = invalid. It is reclaimed as a bullish discount array only if:
  - (1) price first moves away below it;
  - (2) price later comes back above the FVG high;
  - (3) bias is bullish (not in premium).
  - Then its retest is a long. Chop across it does not reclaim (027).
  - In bearish/premium context treat it as an IFVG (A8) (091). Mirror.
- **Sources:** 027 ~22:24, 091 ~20:18.
- **Quote:** "then it can be reclaimed".
- **Conflicts:** overlaps A8; bias decides.
- **[our interpretation]:** "moves away" = at least one swing beyond; a body close above the high.
- **Fix:** add to A5. Remove the "or above CE" variant.
- **Build (LD):**
  - **Detector:** `levels.reclaimed_fvgs(h,l,c,zones)`, feeding the entry arrays.
  - **Params:** `fvg_reclaim=False`.
  - **Test:** break-chop-close-above within 3 bars is not reclaimed; after a swing away it is.

### 33. A5-short-into-htf-sibi
- A5 | missing_condition | general
- **Rule:** daily SIBI above price, quartered.
  - Valid short zone = its low up to its CE. Best where a 60m (or 15m) bearish FVG sits at the lower 25% quadrant.
  - Enter on the LTF FVG with SMT confirmation (035: index vs DXY; ES/NQ SMT as substitute = our interpretation).
  - If price trades above the daily CE before entry, skip. If already short, a body close above CE = exit warning.
- **Sources:** 035 ~1:05:16.
- **Quote:** "I don't want to see it go above the halfway point".
- **Conflicts:** none.
- **Fix:** add the bearish construction to A5.
- **Build (SM):**
  - **Engine:** `_scan` short gate. Inside a daily SIBI require entry <= its CE; skip once the CE has traded.
  - **Params:** `htf_sibi_short_zone=False`; `htf_sibi_need_smt=False`.
  - **Test:** a fill above the daily CE is skipped.

### 34. A5-mtf-gap-refinement
- A5 | missing_rule | general | judgment
- **Rule:**
  - **Entry use (044/046):** when the entry/target array is an HTF imbalance, look for an LTF FVG of the same displacement inside or overlapping it. If found, use its edges/CE as the operative level and keep the HTF zone as context. For a short, the refined gap must still be beyond the targeted liquidity.
  - **Target use (024):** a 5m target FVG overlapping a 15m FVG of the same move may extend to the 15m far edge.
  - `gap_tf_mode = refine_down | widen_up`.
- **Sources:** 044 ~45:31, 046 ~19:32, 024 ~21:39.
- **Quote:** "that's the refined one".
- **Conflicts:** 024 widens vs 044/046 refine.
- **[our interpretation]:** overlap = any price overlap.
- **Fix:** add to A5.
- **Build (ESS):**
  - **Engine:** `_scan` entry block (refine) and `_targets` (widen), using `htf_bars()`.
  - **Params:** `gap_tf_mode=""` ("refine_down" / "widen_up").
  - **Test:** a 5m entry FVG containing a 1m FVG enters at the 1m edge.

### 35. B5-htf-arrays-anchor-transpose
- B5 | missing_rule | general | judgment
- **Rule:** detect FVGs, VIs, IFVGs, OBs, breakers, rejection blocks and wicks on each HTF (W, D, 4h, 1h, 15m) from that TF's own bars.
  - Store edges, CE and quarters, and project them unchanged onto LTF charts as fixed zones. Do not require an LTF 3-candle gap.
  - On the LTF look only for the trigger and refinement: LTF body gaps inside it, or an LTF rebalance (break above short-term high H with one-sided delivery, a later low back to <= H; refined zone = H down to that low). Weekly -> daily likewise.
- **Sources:** 043 ~3:13, 072 ~1:45, 074 ~7:00, 080 ~11:28, cc04_012 ~0:37/~5:25, cc12_002 ~26:04.
- **Quote:** "anchored PD arrays on the higher time frame".
- **Conflicts:** A10 void vs cc04_012.
- **[our interpretation]:** the HTF level governs stop/invalidation when arrays overlap.
- **Fix:** add the transpose rule to B5; note the A10 conflict.
- **Build (LD):**
  - **Engine:** `htf._arrays` already detects per TF. Expose them in DayCtx as fixed zones usable as entry arrays in `_scan`.
  - **Params:** `htf_entry_arrays=()` (TFs, e.g. (15, 60)).
  - **Test:** a 1h FVG with no 1m gap inside still arms an entry when 60 is listed.

### 36. N-initial-fvg-reference
- new | missing_rule | index | judgment
- **Rule:** reference arrays, tagged respected/disrespected later. Confluence and a narrative tag only, not a stand-alone entry.
  - `initial_fvg_day` = the first 5m FVG whose c3 closes 09:30-10:00, extended to 16:00.
  - `initial_fvg_week` = the first FVG of Monday's session (048: a 5m FVG at Monday 14:50), extended to Friday's close.
  - `monday_10am_1h_fvg` = if Monday's 10:00 1h candle is c2 of a 1h FVG: high/low/CE as a weekly array (082: a BISI used as resistance later in the week).
- **Sources:** 048 ~5:40, 082 ~5:13.
- **Quote:** "a very influential reference point throughout the day".
- **Conflicts:** none.
- **[our interpretation]:** "first FVG of Monday's session".
- **Fix:** add a new L-section rule.
- **Build (LD):**
  - **Engine:** DayCtx fields built in `mark_levels` from 5m/60m `htf_bars`; weekly state in BT.run.
  - **Params:** `initial_fvg=()` (subset "day", "week", "mon10").
  - **Test:** a day fixture yields one zone; Trade gets `init_fvg_respected`.

### 37. A9-vi-definition-no-wick-condition
- A9 | wrong | general
- **Rule:** bullish VI between candle i-k and i (k >= 1): bodies across the run do not overlap or touch at that price.
  - Two candles: min(o,c)[i] > max(o,c)[i-1]. Do not check wicks.
  - Zone = [max(o,c)[i-1], min(o,c)[i]].
  - If the wicks also do not overlap, tag it as both a VI and a liquidity void.
  - Expect a revisit; a body across it is the preferred confirmation (not required in fast markets). Mirror.
- **Sources:** 009 ~7:18, 036 ~22:55, 027 ~22:24.
- **Quote:** "there may or may not be an overlap between two candles with their Wicks".
- **Conflicts:** A9 requires wick overlap.
- **Fix:** A9: remove the wick condition; allow multi-candle runs.
- **Build (LD):**
  - **Detector:** `levels.volume_imbalances` drops the wick-overlap test under a switch and adds a multi-candle scan.
  - **Params:** `vi_wick_overlap=True` (current; False = ICT); `vi_multi=False`.
  - **Test:** a gap-up bar with no wick overlap is found when False.

### 38. A9-vi-delivery-state
- A9 | unlisted_contradiction | general
- **Rule:** parent_tf = the highest TF on which the VI exists; ignore lower-TF bodies (046). States:
  - (a) **reached** = a later high >= the earlier candle's close + 1 tick (bearish VI; mirror) (050).
  - (b) **target_hit** = a later parent_tf body overlaps the zone (035; wicks don't count).
  - (c) **dead** = a parent_tf body lays over the whole zone (046/090).
  - Until dead, an open daily/weekly VI is a two-sided draw and may be revisited many times (090); wicks don't change state (077).
  - `vi_dead_rule = overlap | full_span`.
- **Sources:** 035 ~21:01, 046 ~28:33, 050 ~33:20, 077 ~3:23, 090 ~14:07.
- **Quote:** "until there's a body that lays over top".
- **Conflicts:** 035 overlap vs 046 full span.
- **Fix:** A9: add the states and the parent TF.
- **Build (LD):**
  - **Detector:** `levels.vi_body_dead` gains `rule=`; parent-TF check in `htf._arrays` (vi=True).
  - **Params:** `vi_dead_rule="full_span"` (= current `vi_body_death`); `vi_two_sided_draw=False`.
  - **Test:** a partial body overlap marks target_hit but not dead.

### 39. A9-vi-retest-tolerance
- A9 | shortened | general | judgment
- **Rule:**
  - **Rejecting VI (bearish):** later retests up to its CE are allowed. Invalidation = above the marked high (026, ambiguous).
  - **Small VI between i-1 and i:** it may overshoot to the adjacent candle's extreme (027); beyond that = failed, so expect the next PD array.
  - Small VIs only; FVGs stay strict. Mirror.
- **Sources:** 026 ~1:34:23, 027 ~16:27.
- **Quote:** "how far can it overshoot to this candle's low".
- **Conflicts:** A9 "touched but not pierced".
- **[our interpretation]:** stop at max(VI high, rejecting high) + 1 tick; "small" = <= 2 pts.
- **Fix:** A9: add the tolerance.
- **Build (ESS):**
  - **Engine:** `vi_stop` path in `_scan`.
  - **Params:** `vi_tol="none"` ("ce" / "adjacent_extreme").
  - **Test:** a wick to the VI CE keeps the trade under "ce".

### 40. A9-broken-vi-retrace-midpoint
- A9 | missing_rule | general | judgment
- **Rule:** bearish: a retrace up into a VI that price is expected to reject from may overshoot (to the overshooting candle's low, at most to the midpoint of the range being retraced).
  - A full retrace to the midpoint is rare and must reject immediately. Otherwise the idea is in doubt: reduce or exit. Mirror.
- **Sources:** 027 ~16:40-18:20.
- **Quote:** "it's rare that it comes all the way back up".
- **Conflicts:** none.
- **[our interpretation]:** "immediately" = within 2 one-minute bars.
- **Fix:** add to A9.
- **Build (ME):**
  - **Engine:** `run_day` exit. After a midpoint touch, exit if there is no close back below within `vi_mid_bars`.
  - **Params:** `vi_mid_exit=False`; `vi_mid_bars=2`.
  - **Test:** a midpoint touch then 3 bars holding exits.

### 41. A9-daily-vi-forward-levels
- A9 | missing_rule | general | judgment
- **Rule:** mark each daily VI on its own (both body edges plus the midpoint); never merge nearby VIs. Extend each through the rest of the week and treat its edges like NWOG edges.
  - A VI above price that is reached becomes a support candidate on a later retrace from above, best with an hourly FVG (007). Mirror.
- **Sources:** 025 ~23:19, 007 ~3:40/~8:59.
- **Quote:** "do them individually".
- **Conflicts:** none.
- **[our interpretation]:** invalid on a 60m body close below the VI low.
- **Fix:** add to A9.
- **Build (LD):**
  - **Engine:** `vi_arrays` daily rows keep per-VI levels; add a reached -> support state in DayCtx.
  - **Params:** `vi_flip_support=False`.
  - **Test:** a daily VI reached Tuesday is a support array Wednesday.

### 42. A16-propulsion-block-full
- A16 | shortened | general
- **Rule:** bullish PB:
  - **Definition:** K = an earlier bullish OB. P = a later down-close candle that trades into K without closing below K's MT (078). PB zone = [open_P, high_P]; PB_CE = (high_P+open_P)/2 (073).
  - **Return:** expect a tag of high_P (a pip or two over) and an immediate move away (cc04_008). PB_CE is the deepest acceptable reaction.
  - **Invalidation:** `close` = a body close below the PB MT (019, 075, 079) | `wick` = any trade through (027, cc04_008).
  - **On invalidation:** abandon longs, flip that TF bearish, target the next unfilled VI/FVG below (027), and treat the PB as a reclaimed bearish block (079).
  - **Daily hold:** a daily PB held into the close favours higher the next day (073).
  - A breaker as host (033) is ours. Mirror.
- **Sources:** 019 ~10:06, 027 ~12:53, 033 ~57:00, 073 ~2:47/~9:44, 075 ~28:20, 078 ~29:22, 079 ~10:48, cc04_008 ~1:24.
- **Quote:** "you never want to see a closing price below mean threshold".
- **Conflicts:** wick vs close; which candle's MT.
- **Fix:** expand A16.
- **Build (ESS):**
  - **Context:** `levels.propulsion_blocks` exists; coverage A16 has `prop_entry`/`prop_mt_exit`/`prop_zone`.
  - **New:** `prop_mt_test="close"` ("wick"); `prop_fail_flip=False` (on failure block longs for the session and add the PB as a bearish array).
  - **Test:** a wick under the PB MT exits only in "wick".

### 43. A16-propulsion-context-sequence
- A16 | missing_condition | general | judgment
- **Rule:**
  - **cc04_008:** (1) bullish context; (2) a bullish OB (consecutive down candles blend); (3) the OB is confirmed when a later candle trades above its highest high; (4) price moves higher; (5) a later down-close candle trades back into the OB and is the PB at its close.
  - **cc09_008 (looser):** a down-close candle adjacent to the prior OB, followed by a higher high; level = its open; valid once a later candle trades above its high.
  - `pb_def`. Mirror.
- **Sources:** cc04_008 ~3:58, cc09_008 ~14:45.
- **Quote:** "when the underlying context is bullish".
- **Conflicts:** A16 vs the looser cc09_008.
- **[our interpretation]:** prefer the separated case.
- **Fix:** A16: add the context and the event order.
- **Build (LD):**
  - **Detector:** `levels.propulsion_blocks(..., need_confirm=, bias=)`.
  - **Params:** `pb_def="a16"` ("cc04_008" / "cc09_008").
  - **Test:** an unconfirmed OB yields no PB under cc04_008.

### 44. A16-propulsion-depth-grade
- A16 | missing_rule | index | judgment
- **Rule:** depth = (K_high - P_low)/(K_high - K_low).
  - <= ~0.5 = clean PB.
  - > 0.5 (especially with an FVG below) = weak, more prone to fail: lower confidence or size, expect a possible trade-through. Mirror.
- **Sources:** 079 ~12:00.
- **Quote:** "these are more prone to fail".
- **Conflicts:** none.
- **[our interpretation]:** the 0.5 cut and the size action.
- **Fix:** add the grade to A16.
- **Build (ESS):**
  - **Engine:** a `depth` field on the PB Zone; risk_mult in `_scan`.
  - **Params:** `prop_deep_mult=1.0` (test 0.5 / 0 = skip).
  - **Test:** a deep PB gets half size at 0.5.

### 45. A15-mitigation-definition-and-iofed
- A15 | shortened | general
- **Rule:** mitigation = an offside trader reducing drawdown; candles do not "mitigate".
  - 012: a would-be breaker candle that price trades back to and above while stretched away from the high is a mitigation block, not a breaker.
  - Afterwards expect an IOFED: a partial fill into the FVG just below (near edge, leaving part open). Entry at the near edge, not CE. Mirror.
- **Sources:** 012 ~11:39.
- **Quote:** "when we trade back to it and above it it's mitigation".
- **Conflicts:** none.
- **Fix:** A15: add the meaning and the expected retrace.
- **Build (ESS):**
  - **Engine:** in `_scan`, when the arming context is a mitigation block, use `entry="edge"` for the next FVG below.
  - **Params:** `mit_iofed_edge=False`.
  - **Test:** the entry price equals the FVG near edge after a mitigation tag.

### 46. A15-mitigation-block-entry
- A15 | unlisted_contradiction | general | judgment
- **Rule:** switch `mitigation_entry`:
  - **True:** 033 01:04:05, 041, cc04_004, cc06_005.
  - **False:** 075, where a mitigation block is a target only, can be traded through, and an HTF weekly MB acts as a draw.
  - **Entry use:** requires order flow and narrative in the trade direction, ideally stacked with other arrays (FVG low, OB open; 033).
  - **Bearish (cc04_004):** after the break below the swing low (no expiry), zone = full range of the last down-close candle in that low; sell anywhere in it; stop above the candle high.
  - **cc06_005:** 4h MB in premium.
  - **Bullish mirror (033):** low, high, higher low; target nearby buy-side (~5 handles).
  - **041:** up-close candles of a pre-open consolidation used as a bullish MB entry.
  - **Rank:** below breakers.
- **Sources:** 033 01:04:05, 041 ~0:00, cc06_005 ~12:22, cc04_004 ~4:37/~5:01/~13:51, 075 ~22:10.
- **Quote:** "the whole entire candle is used".
- **Conflicts:** A15/075 target-only vs entry use.
- **[our interpretation]:** the 041 window (09:00-09:30) and its stop; the order-flow test (= `want`).
- **Fix:** A15: list the conflict; re-cite 033 at 01:04:05.
- **Build (SM):**
  - **Where:** a new branch in `_scan` using `levels.mitigation_blocks` with `mitigation_alive`; a limit anywhere in the zone (default zone top for longs).
  - **Params:** `mitigation_entry=False`, `mit_entry_px="near"` ("mid").
  - **Test:** a cc04_004-style fixture fills a short inside the down-close candle range, stop above its high.

### 47. A17-rejection-block-levels
- A17 | shortened | general
- **Rule:** bearish RB (a target when bullish), from the swing-high candles on the trading TF.
  - **level1** = max(close) of the up-close candles (015/038/059/090) or max(open,close) of any candle (cc04_006; `rb_level`).
  - **W** = the highest high. **level2** = wick CE = (level1 + W)/2.
  - **Valid** only if wicks extend beyond the body.
  - **Targets in order:** level1, level2, W.
  - **As an entry:** price may trade a little through level1; level2 should hold (080); stop beyond W (ours).
  - **Bullish mirror:** min(close) of the down-close candles, or min(open,close).
- **Sources:** 015 ~2:18, 038 ~4:15, 059 ~10:11, 080 ~5:41, 090 ~34:21, cc04_006 ~9:23/~12:47.
- **Quote:** "the lowest wick and the lowest open or the lowest close".
- **Conflicts:** same-colour extreme close vs any-colour open/close.
- **Fix:** A17: add the bullish case, the wick CE level and the wick requirement.
- **Build (LD):**
  - **Where:** `levels.rejection_blocks` returns level1, level2 and W (coverage A17 already lists the window/wick fix plus `rej_targets`).
  - **Params:** `rb_level="close"` ("open_close"), `rb_ce_level=False`.
  - **Test:** bullish fixture: level1 = the lowest down-close close; level2 = the midpoint to the low.

### 48. A18-reclaimed-ob-codeable
- A18 | wrong | general | judgment
- **Rule:** A18 is codeable with a confirmation lag. Switch `reclaimed_def`:
  - **Loose (006/Ep 02):** an OB that price leaves, re-trades and leaves again; the next return (high to MT) is an entry, i.e. an ordinary A12 retest.
  - **Strict (cc04_007):** while price falls to HTF support, record each down-close candle followed by a short-term bounce. Once price reaches HTF support and breaks the latest short-term high (MSS), fix the curve low and buy retraces into each recorded block above it.
  - **Stop:** below the curve low or the block MT (ours).
  - **Bearish mirror:** up-close candles before a short-term decline.
  - Tag which definition was used.
- **Sources:** 006 ~49:57/~55:24, cc04_007 ~4:07/~5:05/~8:38.
- **Quote:** "it becomes what a reclaimed order block".
- **Conflicts:** Ep 02 loose vs cc04_007 strict; A18 "not codeable".
- **[our interpretation]:** one entry per block on its first retrace.
- **Fix:** A18: remove "not codeable"; add the decision.
- **Build (SM):**
  - **Where:** `levels.reclaimed_obs` and `reclaimed_ob` (strict) already exist; add the loose mode.
  - **Params:** `reclaimed_def="strict"` ("loose").
  - **Test:** the loose fixture (leave/retrade/leave) arms on the third touch.

### 49. A19-mss-when-raid-missing
- A19 | wrong (verifier: missing_condition) | index | judgment
- **Rule:** before the session, define the expected raid level R (010: the prior day's high).
  - **Case A, R taken:** MSS reference = the short-term swing low that started the leg into the raid high; a displacement body close below it = MSS.
  - **Case B, R not taken:** a break of a short-term low inside the range is not an MSS, even with an FVG. Reference = the swing low that launched the leg making the session high (the leg that took out a prior intraday spike high). Only a displacement break of it is an MSS.
  - Mirror for longs.
- **Sources:** 010 ~41:31.
- **Quote:** "I wanted this one to break down more specifically".
- **Conflicts:** A19/Ep08: no shift trusted until the run; this is the conditional branch.
- **[our interpretation]:** R = the PDH/PDL on the bias side.
- **Fix:** A19: add the R-taken / R-not-taken branch.
- **Build (SM):**
  - **Where:** `_scan` MSS reference (`mss_ref`).
  - **Params:** `mss_ref_raid=False`. When R (`raid_level="pdh"`) is untaken, mss_ref switches to the leg-origin low (like Ep08.4 `origin`).
  - **Test:** a fixture without a PDH raid ignores the short-term-low break.

### 50. A19-mss-no-rel-sweep-with-htf-draw
- A19 | unlisted_contradiction | index
- **Rule:**
  - **No pre-set HTF draw:** prefer waiting for the lower REL to be run (044). The short-term-high break is allowed but "aggressive".
  - **Pre-session draw in direction D (019: NWOG above):** an MSS needs only a short-term swing low taken plus a displacement break of the short-term high that leaves an FVG. The REL need not be swept.
- **Sources:** 019 ~8:34/~9:25, 044 ~42:55.
- **Quote:** "why didn't it Go below that it doesn't need to".
- **Conflicts:** 044 vs 019, reconciled by the HTF draw.
- **Fix:** A19: cite 019 and add the condition.
- **Build (SM):**
  - **Where:** `mss_eq_wait` (exists) becomes conditional.
  - **Params:** `mss_eq_wait_unless_draw=False`. Skip the REL wait when the session draw is locked (`draw_lock`) in direction D.
  - **Test:** a REL fixture with a locked draw arms on the short-term break.

### 51. A19-reh-short-term-low-trap
- A19 | missing_condition | index | judgment
- **Rule:** long bias, HTF objective above not yet reached, last two swing highs relatively equal. A break of the short-term low under them is not a bearish MSS; it is bait that builds buy-side above the REH.
  - **Targets:** REH, then the HTF objective.
  - **Entry:** long on the retrace into the nearest bullish FVG below. A retrace that fails to reach CE = strength (IOFED).
- **Sources:** 029 ~48:29.
- **Quote:** "what do they see that as a market structure shift".
- **Conflicts:** none.
- **[our interpretation]:** invalidate on a body close below the FVG low.
- **Fix:** add to A19.
- **Build (SM):**
  - **Where:** `_scan` bearish MSS gate.
  - **Params:** `reh_trap=False`. With `want`=long, an untaken HTF draw and REH (A3 eq_tol) above, suppress the short and arm a long on the next bullish FVG.
  - **Test:** the 029-style fixture produces a long, not a short.

### 52. N-micro-structure-regime
- new | missing_rule | index | judgment
- **Rule:** inside a small intraday consolidation (narrow range since 09:30, >= 2 alternating short-term runs, no displacement), reject 1m/sub-1m MSS signals.
  - Read structure on a higher TF (e.g. 5m; our interpretation of "zoom out") and wait for the next window.
  - Accept 1m MSS triggers only when the preceding leg is displacement.
- **Sources:** 024 ~10:08.
- **Quote:** "when the market is moving when it's Dynamic".
- **Conflicts:** overlaps N8/N9.
- **[our interpretation]:** range threshold X ES pts (test 0.25 x ADR5).
- **Fix:** add a new rule; cross-reference N8/N9.
- **Build (SM):**
  - **Where:** `_scan` MSS block.
  - **Params:** `micro_regime=False`, `micro_range_adr=0.25`. While the session range < k x `adr5()` with >= 2 alternating pivots, set `mss_ref_tf=5`.
  - **Test:** a choppy fixture yields no 1m MSS trade.

### 53. M12-second-takeout-turtle-soup
- M12 | unlisted_contradiction (verifier: missing_condition) | index (verifier) | judgment
- **Rule (046):** sell-side at a low was already swept, then price rallied (without taking the opposing high).
  - Do not take a turtle-soup long on a later break of that low; continuation should break it decisively with displacement.
  - A shallow break and recovery = a likely deeper retracement: protect shorts (partial), not a long trigger. Mirror.
  - **FX-only note (cc08_007, London KZ, out of scope):** with no upside protraction, a second take-out can be bought. This is consistent with 046.
- **Sources:** 046 ~1:01:58, cc08_007 ~11:28.
- **Quote:** "I don't think it's um something to build a framework on".
- **Conflicts:** none real (verifier).
- **[our interpretation]:** "shallow" = less than `ts_max_pts`.
- **Fix:** M12: add the second-break rule; mark cc08_007 as fx-only.
- **Build (SM):**
  - **Where:** turtle-soup core `levels.turtle_soup`.
  - **Params:** `ts_skip_reswept=True` (new; skip a level whose pool was already swept today and followed by a rally); `second_break_partial=False` (ME: shorts take a partial on a failed second break).
  - **Test:** the second sweep of a run low produces no turtle long.

### 54. A21-dealing-range-energetic-swing
- A21 | missing_rule | general | judgment
- **Rule:**
  - **Pick the low:** among candidate swing lows below the current high, choose the most recent 3-candle swing low followed by displacement (consecutive same-direction candles leaving >= 1 FVG within N bars). If two are close, take the one with more bars clustered around it.
  - **Skip:** older rounded lows and pivots inside a consolidation; anchor where the impulse departs.
  - **Impulsive leg:** >= 60% of bars close in direction, and/or a displacement FVG, and/or size >= 1x ATR(14).
  - **60m weekly planning:** the largest, fastest one-directional leg of the last ~2 weeks.
  - **Range:** that low to the leg high (wicks); EQ = 50%. Sub-ranges do not override it. MSS reference stays per A19. Mirror.
- **Sources:** 028 ~1:07:33, 044 ~40:26, cc01_005 ~2:20/~9:40/~19:23, cc04_002 ~18:44.
- **Quote:** "obvious price swings are the ones we look at".
- **Conflicts:** "parent" terminology (028 vs 044).
- **[our interpretation]:** the numeric thresholds.
- **Fix:** add anchor selection to A21/M13.
- **Build (LD):**
  - **Where:** new `levels.dealing_range(h,l,o,c,i,mode="energetic")`, used by `leg_pd`/`ote` in `_scan`.
  - **Params:** `leg_anchor="mss_leg"` ("energetic").
  - **Test:** a fixture with an old rounded low and a newer displaced low anchors on the newer.

### 55. A21-implied-range-to-target
- A21 | missing_condition | general
- **Rule (short):** range high = the high that ran buy-side; range low = the stated draw/target (025: 4146, Friday close / NWOG). EQ = (high + target)/2.
  - Sell PD arrays above EQ. EQ is also the add cutoff (E12). Mirror.
- **Sources:** 025 ~41:59.
- **Quote:** "map out a premium to Discount Market in a implied dealing range".
- **Conflicts:** none.
- **Fix:** A21: add the implied range.
- **Build (ESS):**
  - **Where:** `_scan` leg_pd and the add cutoff.
  - **Params:** `leg_pd_anchor="displacement_leg"` ("target"; uses the first ladder target).
  - **Test:** an entry below the implied EQ is rejected for a short.

### 56. A21-pre-trigger-dealing-range
- A21 | missing_rule | index
- **Rule:** range high = the latest 3-candle swing high before the retrace; range low = the low of the bar that tapped the bullish breaker.
  - **While inside:** no action, however long it chops; time does not invalidate.
  - **Invalid:** if price trades deeper than the bullish breaker.
  - **Trigger:** an up-close body above the bearish FVG in the upper half of the range that also takes out the internal highs (MSS). Then 1m: take the first bullish FVG / immediate rebalance, preferably 10:00-11:00.
- **Sources:** 048 ~1:20:40.
- **Quote:** "I don't care how much time it spends inside".
- **Conflicts:** none.
- **Fix:** add to A21.
- **Build (SM):**
  - **Where:** `_scan` breaker branch. After a breaker tap, hold the setup armed without expiry until the range breaks.
  - **Params:** `breaker_range_hold=False`.
  - **Test:** a 40-minute chop inside the range keeps the setup armed; a trade below the breaker low cancels it.

### 57. A23-wick-quarter-strength
- A23 | wrong | general | judgment
- **Rule:** for a wick (upper: body_top to high; lower: low to body_bottom; any TF), compute q25 (25% from the body edge), CE and q75.
  - **Retrace into an upper wick used as resistance:**
    - turns at q25 = very bearish;
    - turns at CE = normal;
    - overshoots CE but stays <= q75 = still valid (103);
    - trades through q75, or a body closes above CE = failed [our tiers].
  - **Heavy bearish stance:** use q25 as the reaction/entry level (025/028).
  - **Bias line (065/075, lower wick 1h+):** bullish intact while no body closes at or below CE. Bodies in the upper quarter = best. A body close at or below CE = stop adding, reduce or exit.
  - **Judas cap (072):** wickCE = (high + max(open,close))/2; bearish intact while rallies fail to close above it.
  - **Use:** wick entries only at CE or a quarter; full wick extremes for range measurement. Mirror.
- **Sources:** 025 ~34:43, 028 ~15:24-16:43, 029 ~36:40, 103 ~24:07/~27:23, 065 ~4:19:02, 075 ~1:05:07, 072 ~5:27.
- **Quote:** "we do gradients on wicks 75 of the wick 50 of the wick".
- **Conflicts:** A23 cites 025 for CE stop, but 025 says q25 in a heavy stance.
- **[our interpretation]:** the strength tiers beyond "CE normal / q25 very bearish"; the q75 failure.
- **Fix:** A23: re-cite 028 for the CE stop; add quarters and gradients.
- **Build (LD + ME):**
  - **Where:** `levels.wick_midpoints` adds q25/q75; `wick_read` (coverage A23) reads them in `run_day`.
  - **Params:** `wick_quarters=False`, `wick_bias_line=False` (no adds after a body close through the 1h tail CE), `judas_wick_cap=False`.
  - **Test:** a retrace to q25 is tagged "very_bearish".

### 58. A23-stubby-wick-first-approach
- A23 | missing_rule | general | judgment
- **Rule:** stubby wick = wick length / (high-low) small.
  - **First approach:** set the target/partial at its CE (a few ticks beyond allowed) and expect a retrace.
  - Do not expect the extreme to break until a later approach. Mirror.
- **Sources:** 028 ~15:24.
- **Quote:** "it'll stop at consequent encroachment ... and then retrace".
- **Conflicts:** none.
- **[our interpretation]:** stubby <= 20% of the candle range; "first approach".
- **Fix:** add to A23.
- **Build (TP):**
  - **Where:** `_targets`. For a stubby-wick extreme on its first approach, replace the extreme rung with the wick CE.
  - **Params:** `stubby_wick_ce=False`, `stubby_frac=0.2`.
  - **Test:** a 10%-wick PDL target becomes its CE.

### 59. A23-broken-wick-ce-inversion
- A23 | missing_rule | general
- **Rule (bearish):** after price breaks a swing low, mark the CE of that low's lower wick (CE = (min(open,close)+low)/2) as an inversion level.
  - The expected retrace goes to the CE, not to the old low, and may stop above the old low without voiding the short.
  - A short entry or partial at the CE is allowed (043, 044). In 044 the nearby SIBI should stay at least partly open.
  - Mirror: a broken upper-wick CE becomes support.
- **Sources:** 043 ~10:45/~17:20, 044 ~46:41.
- **Quote:** "consequent encroachment would be the level".
- **Conflicts:** none.
- **[our interpretation]:** invalid on a body close above the wick's body edge (test).
- **Fix:** add to A23/A8.
- **Build (ESS):**
  - **Where:** `entry_arrays` adds "broken_wick_ce" in `_scan` (the swing low broken by the MSS supplies the wick).
  - **Params:** `entry_arrays` value "broken_wick_ce"; `broken_wick_stop="body_edge"`.
  - **Test:** a fixture retrace stops at the wick CE and fills.

### 60. confluence-stacked-arrays
- new | missing_rule | general | judgment
- **Rule:** tag a PD-array level "converged" when (a) an OB also contains an FVG and/or a VI (100), or (b) a wick's CE lies inside an FVG, especially near its CE (103, 011).
  - Rank converged levels above single arrays for entries, partials and targets.
  - A counter-trend retrace may spike to a converged level but should stop there (103).
- **Sources:** 100 ~6:05, 103 ~4:38/~25:04, 011 ~7:19.
- **Quote:** "that's three PD arrays then you see the reaction".
- **Conflicts:** none.
- **[our interpretation]:** "near CE" = within 2 ticks; the ranking weight.
- **Fix:** add a new rule.
- **Build (LD):**
  - **Where:** a `converged` count on Zone in `strategy.py` array merge (the confluence rows); `_scan` gap pick prefers a higher count.
  - **Params:** `converge_rank=False`.
  - **Test:** between two equal-distance arrays, the one with an inner wick CE is picked.

### 61. A8-ce-line-bearish-read
- A8 | unlisted_contradiction | index | judgment
- **Rule:** once price trades through a bullish FVG's CE (with speed) and then retraces up into the gap:
  - **While below the CE:** stay bearish and target sell-side (session lows, then the current NWOG).
  - **If price trades back above the CE and it holds as support with a rally:** the bearish read is off; target the prior session close (030 CPI day).
  - Mirror. This is a bias read separate from the A8 IFVG protocol.
- **Sources:** 030 ~1:38:43.
- **Quote:** "as long as we remain below 4128".
- **Conflicts:** A8 needs a full close beyond plus a retest.
- **[our interpretation]:** "holds" = two closes above CE.
- **Fix:** add as a bias read in A8.
- **Build (BH):**
  - **Where:** a `_scan` side gate using the prior day's daily FVG from `htf.table`.
  - **Params:** `ce_line_bias=False`.
  - **Test:** below the CE, longs are blocked; after two closes above it, shorts are blocked.

### 62. A8-rip-through-ce-signature
- A8 | missing_rule | index | judgment
- **Rule:** for a run toward a draw with an opposing/old FVG or large wick in the path:
  - **Strong-run signature:** a candle trades through its CE and the next candle(s) continue through the far edge, preferably with no return (031).
  - **Stall/meander at CE:** weak delivery, so no adds and favour partials.
  - A preference, not a hard invalidation. Mirror.
- **Sources:** 031 ~51:52/~32:15.
- **Quote:** "rips right through it".
- **Conflicts:** A8 retest expectation; A23 wick CE stop.
- **[our interpretation]:** stall = >= 3 bars within 1 pt of CE.
- **Fix:** add to A8 as a quality signature.
- **Build (ME):**
  - **Where:** `run_day` add block / partial trigger.
  - **Params:** `rip_through=False` (tag `rip` / `stall`; on stall, block adds and take `stall_partial=0.5`).
  - **Test:** a 3-bar stall at an opposing CE triggers a partial.

### 63. X9-entry-fvg-immediate-rejection
- X9 | missing_condition | index
- **Rule (add to X9):** an entry FVG that price trades into must reject on that candle or the next (already in X9) and must stay partly unfilled.
  - If price trades through its far edge (full fill), the idea is void: cancel or exit (013).
  - Stop = 1 tick beyond the extreme of the FVG-forming candle. Mirror.
- **Sources:** 013 ~17:55.
- **Quote:** "reject that fair value Gap immediately or it is no good".
- **Conflicts:** X9's 2-3 candle allowance.
- **Fix:** X9: add the full-fill void.
- **Build (ME):**
  - **Where:** `run_day` pending-fill and position loop.
  - **Params:** `fvg_full_fill_void=False` (cancel the pending order or exit when a trade prints beyond the far edge).
  - **Test:** a fill then a print through the far edge exits at once.

### 64. A3-diagonal-support-is-liquidity
- A3 | missing_rule | general | judgment
- **Rule:** never use diagonal trendlines or pattern breakouts as S/R, bias, entry or stop references (cc03_007).
  - A smooth diagonal run of higher lows (lower highs) on the execution TF = retail stops beneath (above): expect a spike through it (045).
  - A trendline/pattern break against daily order flow is a trap; price continues toward the HTF draw.
- **Sources:** 045 ~26:02, cc03_007 ~2:12/~23:18.
- **Quote:** "diagonal support which I don't have any faith in".
- **Conflicts:** none.
- **[our interpretation]:** >= 3 swings within a tolerance of a line.
- **Fix:** add to A3.
- **Build (LD):**
  - **Where:** new `levels.diagonal_lows(lows, tol)` -> pool level (the extrapolated line at bar i) as a sweep pool kind "diag".
  - **Params:** `diag_pools=False`, `diag_min_swings=3`.
  - **Test:** three rising lows produce a pool at the projected line.

### 65. L4-resistance-is-delivery-speed
- L4 | wrong | index | judgment
- **Rule:** record two definitions.
  - **CC (cc01_007):** resistance = old highs/lows in the path (current L4 proxy; the pre-trade forecast).
  - **2023 (036):** resistance = delivery speed. Low = the target is reached within ~2-3 bars of the entry TF; high = repeated deep retraces and consolidations.
  - Use the 2023 definition for live or after-the-fact classification (e.g. X3 full pull vs partials).
- **Sources:** 036 ~1:21:17.
- **Quote:** "it's being resisted in the scope of price speed delivery".
- **Conflicts:** CC vs 2023 definitions.
- **[our interpretation]:** the bar counts.
- **Fix:** L4: record both.
- **Build (ME):**
  - **Where:** a `run_day` speed tag (bars from fill to the first rung) and a switch for `resistance_mode` (X3f).
  - **Params:** `resistance_def="swings"` ("speed"), `speed_bars=3`.
  - **Test:** a fast fixture classifies as low resistance.

### 66. L5-nwog-friday-reference
- L5 | unlisted_contradiction | needs_unavailable_data
- **Rule:** keep Friday 16:59 last print to Sunday 18:00 first print as the default (039).
  - **Variants:** Friday RTH close 16:00 (036, CFD calibration), "settlement" wording (038, loose), 15m chart (022) vs 1m/5m.
  - **Optional:** `nwog_fri = last_1659 | rth_close_1600`.
- **Sources:** 022 ~27:37, 036 ~1:32:17, 038 ~27:40.
- **Quote:** "Friday closing price regular trading hours".
- **Conflicts:** as listed.
- **Fix:** L5: note the variants.
- **Build:** none (needs Sunday-evening futures bars).

### 67. L5-nwog-high-low-labelling
- L5 | shortened | index
- **Rule:**
  - nwog_high = max(fri_close, sun_open); nwog_low = min(...).
  - gap_dir = "down" if fri_close > sun_open else "up".
  - Friday close = the last print before the Friday session ends (16:59; on 5m bars, the 16:55 bar close).
- **Sources:** 051 ~5:38.
- **Quote:** "Friday's closing price is the new week opening gap high".
- **Conflicts:** none.
- **Fix:** L5: state the labels.
- **Build (LD):**
  - **Where:** `htf.opening_gaps` adds a `dir` column; `gaps_for_day` passes it on.
  - **Params:** none (always on; tag only).
  - **Test:** a Friday close above the Sunday open gives dir="down", high = the Friday close.

### 68. L5-cfd-nwog-mapping
- L5 | missing_condition | index
- **Rule:** SPX/NDX CFD: NWOG = the CFD close of the bar at the futures' Friday close time and the CFD open of the first bar at or after Sunday 18:00 (ICT: approximate; futures data preferred).
  - If those bars are missing, flag the NWOG unavailable or fall back to the L5 Friday close -> Monday 09:30 variant (039) as a tested option.
- **Sources:** 036 ~1:32:40.
- **Quote:** "it's not going to be perfect".
- **Conflicts:** none.
- **Fix:** L5/D21: add the mapping.
- **Build (LD):**
  - **Where:** `htf.opening_gaps`.
  - **Params:** `nwog_cfd_src="auto"` ("sunday_bars" / "monday_0930" / "none").
  - **Test:** CFD data without Sunday bars gives NaN under "sunday_bars".

### 69. L6-ndog-min-size
- L6 | unlisted_contradiction | needs_unavailable_data | judgment
- **Rule:** `ndog_min_pts` = 0 (032: annotate even a 1-tick NDOG) | 1.0 (052 and current L6).
  - Optionally test 0.5 (ours). Use both edges, plus the midpoint if wider than 1 tick.
- **Sources:** 032 ~17:41, 052 ~4:31.
- **Quote:** "it could be one tick just like this".
- **Conflicts:** 032 vs 052.
- **[our interpretation]:** the 0.5 middle value.
- **Fix:** L6: list the conflict.
- **Build:** none (needs 17:00-18:00 futures bars). The `ndog_min_pts` param already exists in `htf.opening_gaps`.

### 70. L6-ndog-persistence
- L6 | missing_condition | needs_unavailable_data
- **Rule:** NDOG = [min, max] of (17:00 close, 18:00 open) plus the midpoint.
  - Do not invalidate it on a fill; keep high, low and midpoint as reaction levels for its L6 lifetime.
  - Whether tiny or no-separation gaps are drawn follows `ndog_min_pts`.
- **Sources:** 033 ~3:35, 052 ~5:50.
- **Quote:** "once it closes the gap that's not a point of abandoning the gap".
- **Conflicts:** none.
- **Fix:** L6: no fill invalidation.
- **Build:** none.

### 71. L6-first-ndog-of-week
- L6 | missing_condition | needs_unavailable_data | judgment
- **Rule:** each week, scan Mon-Thu in order; the first NDOG > 1 ES handle becomes the week's NDOG (high, low, midpoint) from 18:00 that day to Friday 17:00.
  - Ignore later NDOGs. `ndog_mode = first_of_week | daily`.
- **Sources:** 052 ~5:26.
- **Quote:** "the very first new day opening Gap".
- **Conflicts:** 033 (each day's NDOG through that day).
- **[our interpretation]:** the first one passing the size filter.
- **Fix:** L6: add the mode.
- **Build:** none.

### 72. A2-open-float
- A2 | missing_rule | general | judgment
- **Rule:** open float = all resting stop orders around price, not only at old highs/lows, possibly just beyond price (cc05_002).
  - **After a down move:** short-term highs/REH formed during the decline hold shorts' trailed stops. If price is denied continuation (small, choppy range), set the draw to the nearest such pool above (033). Mirror.
  - **In a consolidation:** pools sit just beyond its high/low and at its internal highs/lows. Pool weight rises with duration (L4); day-trade consolidations are brief (cc09_004).
- **Sources:** 033 ~24:26, cc05_002 ~1:10, cc09_004 ~4:02.
- **Quote:** "the current open interest above and below current market price".
- **Conflicts:** none.
- **[our interpretation]:** "denied continuation" = no new low for N bars with range < k x ADR5.
- **Fix:** add the definition to A2.
- **Build (LD + BH):**
  - **Where:** DayCtx pools add `float_highs` (short-term highs formed after the session's leg start); `pool_rank` weight by consolidation bar count.
  - **Params:** `open_float_pools=False`, `float_denied_bars=20`.
  - **Test:** a denied-continuation fixture draws to the nearest trailed-stop high.

### 73. N-retrade-ob-mt-breaker-fallback
- new | missing_rule | fx_only
- **Rule [FX daily, 012]:** the bullish draw stays active while price has not traded below the MT of the last daily down-close candle.
  - If it does, switch the objective to the nearest daily bullish breaker below as an equilibrium retrace target.
  - Retrade = a brief return-and-leave (distinct from a retest).
- **Sources:** 012 ~2:54.
- **Quote:** "then look for the breaker".
- **Conflicts:** B7 uses a daily close below the MT.
- **Fix:** note under B7 as FX.
- **Build:** none (fx_only).

### 74. A24-implied-fvg-defined
- A24 | wrong | general | judgment
- **Rule (035, single mention):** implied FVG = the range between the CEs (A23) of two wicks, extended forward and used like an FVG.
  - Trading through it in the bias direction = strong continuation.
  - **[ours]:** the wicks are c1 and c3 facing a large c2 whose wicks overlap (so no true FVG exists); bullish = c1 upper-wick CE to c3 lower-wick CE.
- **Sources:** 035 ~29:49.
- **Quote:** "the consequent encouragement of this Wick in this Wick".
- **Conflicts:** none.
- **[our interpretation]:** the three-candle construction.
- **Fix:** move it out of A24's "never defined" list; tag it low-confidence.
- **Build (LD):**
  - **Where:** `levels.implied_fvgs(o,h,l,c)` -> Zone(kind="ifvg_implied"), optional target array.
  - **Params:** `implied_fvgs=False`.
  - **Test:** an overlapping-wick 3-bar fixture yields the CE-to-CE zone.

### 75. A11-htf-gap-own-tf
- A11 | missing_rule | general
- **Rule:** an FVG on TF T stays inefficient (an open draw) until bodies on T or higher close across it.
  - Ignore LTF oscillation inside it when deciding filled/balanced/BPR.
- **Sources:** 061 ~40:20.
- **Quote:** "on the weekly time frame it's inefficient still".
- **Conflicts:** 078 ~1:13:50 (4h back-and-forth balances part of a daily gap). Switch `balance_tf = own | next_lower`.
- **Fix:** A5/A11: state the timeframe of the fill test.
- **Build (LD):**
  - **Where:** `htf._arrays` fill/death test uses only same-TF bars (check the current resampling).
  - **Params:** `balance_tf="own"` ("next_lower").
  - **Test:** a daily FVG with 4h bodies inside stays open under "own".

### 76. A5-far-edge-reach-conditions
- A5 | missing_rule | general | judgment
- **Rule:** for an HTF FVG entry array, drop to a TF ~4-5x lower.
  - **(1) Layering (058 ~25:40-28:40):** if ~3 overlapping back-and-forth swings already printed near the near edge, set the retrace limit to the CE of the most recent small nested LTF FVG.
  - **(2) Inner BPR (058 ~29:46):** if the gap area was already crossed one pass each way, expect no full fill.
  - **After (1) or (2):** the far edge is protected (a valid stop location) and the gap should stay open.
  - **(3) Residual sub-gap (080 ~12:22):** an untraded LTF sub-gap at the far edge makes the far edge a valid entry/target. Without it, enter at the nested LTF FVG.
  - **None of these:** the A5 default. Mirror.
- **Sources:** 058 ~27:22/~29:46, 080 ~12:22.
- **Quote:** "that's layering".
- **Conflicts:** none.
- **[our interpretation]:** the swing count; the TF ratio. Drop the unsourced daily-BPR sentence.
- **Fix:** replace the rulebook's "discretionary" entry (line ~1234) with this rule.
- **Build (ESS):**
  - **Where:** `_scan` entry/stop block for HTF entry arrays (`htf_entry_arrays`).
  - **Params:** `far_edge_reach=False`.
  - **Test:** a layered fixture limits the entry to the nested LTF FVG CE.

### 77. A5-partial-reprice-shrink
- A5 | shortened | general
- **Rule:** for a bullish FVG, track the part not yet traded through (wicks into the zone from above shrink its top).
  - On the next retrace, expect support at the top of the remaining part and place the limit there. Mirror.
  - Single example, so make it a switch: `fvg_edge = original | remaining`.
- **Sources:** 056 ~16:13.
- **Quote:** "this is only inefficient so it needs only to that level".
- **Conflicts:** none.
- **Fix:** A5, with a cross-reference to L9.
- **Build (ESS):**
  - **Where:** `_scan` entry price for FVG entries (Zone gains a `rem_top`).
  - **Params:** `fvg_edge="original"` ("remaining").
  - **Test:** after a wick 1 pt into the gap, the entry is 1 pt lower.

### 78. A12-ob-edge-at-fvg-ce
- A12 | missing_condition | general | judgment
- **Rule (short):** on the parent TF (15m), take the run of consecutive up-close candles before the down move and mark its LOW.
  - If |OB low - FVG CE| <= tolerance, set the retrace limit to that level, place the limit there, and expect the FVG's upper half to stay unfilled.
  - 5m/1m signatures must line up with the 15m level.
  - Mirror for longs (the HIGH of the down-close run vs the BISI CE).
- **Sources:** 058 ~32:02 (EURUSD).
- **Quote:** "in close proximity to the halfway point".
- **Conflicts:** the A12 open anchor (the run low approximates the open; a refinement).
- **[our interpretation]:** the tolerance (~1 ES pt).
- **Fix:** add to A12.
- **Build (ESS):**
  - **Where:** `_scan` entry pick. When a 15m OB edge sits near the entry FVG CE, enter at that level.
  - **Params:** `ob_ce_confluence=False`, `ob_ce_tol_pts=1.0`.
  - **Test:** a fixture with an OB low 0.5 pt from the CE enters at the OB low.

### 79. A21-intraday-fib-bodies
- A21 | wrong | general
- **Rule:** remove 058 from the "wicks for intraday legs" citation.
  - 058 anchors the 1m post-MSS swing fib on bodies (lowest min(o,c) to highest max(o,c)), EQ = 50% of the body range.
  - Switch `leg_fib = wick | body`.
- **Sources:** 058 ~41:48.
- **Quote:** "using the bodies not the Wicks because the bodies tell the story".
- **Conflicts:** 014/cc07_005 use wicks intraday.
- **Fix:** A21 citation.
- **Build (ESS):**
  - **Where:** `_scan` leg_pd computation.
  - **Params:** `leg_fib="wick"` ("body").
  - **Test:** a body-anchored EQ differs from the wick EQ on a long-wick fixture.

### 80. A8-ifvg-bias-without-retest
- A8 | missing_condition | general
- **Rule:**
  - **Bias:** once a candle closes beyond an FVG, mark it an IFVG for bias at once.
  - **Support:** later bodies holding at or beyond its edge (wicks may poke) = support and an add point. A trade into it is allowed but not required; unfilled is stronger.
  - **HTF:** a gap traded fully both ways with price now on its original far side = a candidate IFVG reaction level.
  - **Entry:** an IFVG entry at the zone itself still needs A8's retest-and-hold. No retest = no IFVG entry, but the bias stands.
- **Sources:** 072 ~9:18, 070 ~13:02, 058 ~4:51.
- **Quote:** "it doesn't need to come back down and touch it again".
- **Conflicts:** A8 "valid only when retested and held".
- **Fix:** A8: split bias use from entry use.
- **Build (BH):**
  - **Where:** `htf.table` adds an `ifvg_bias` column from HTF inversions; `_scan` add block uses body-hold at the edge.
  - **Params:** `ifvg_bias=False`, `ifvg_edge_add=False`.
  - **Test:** a daily IFVG close sets the bias the next day without a retest.

### 81. A8-ifvg-narrative-liquidity-run
- A8 | missing_condition | general
- **Rule (bullish IFVG):**
  - **(a) Bias:** HTF bias is bullish (a discount array has been reached).
  - **(b) Liquidity run:** an old low L carrying sell-side is taken. Prefer a bearish FVG whose range contains L.
  - **(c) Inversion:** an MSS closes back above the FVG high. Only then tag the IFVG.
  - **Levels:** H, upper quadrant, CE, low. Long entries at H, the quadrant or CE; stop below the low plus padding.
  - **No short:** do not short a bearish FVG overhead once sell-side is taken and a bullish OB/FVG has held. Buy its retest as an IFVG.
  - **Without (a):** it is just an FVG in its original direction.
  - **Bearish mirror (078):** the far edge H is unlikely to be reached if an FVG just beyond it is still open, or if the range beyond it is balanced (tie this to the `balance_tf` switch).
- **Sources:** 078 ~51:00, 084 ~19:43, 073 ~12:56.
- **Quote:** "an inversion fair value Gap is narrative based".
- **Conflicts:** 078 ~1:13:50 vs 061 ~40:20 on judging balance.
- **Fix:** A8: add the narrative and liquidity preconditions.
- **Build (SM):**
  - **Where:** `_scan` IFVG path (`ifvg_entry`).
  - **Params:** `ifvg_need_run=False` (needs a pool swept inside or just beyond the FVG plus `want` agreement); `ifvg_over_pool_pref=False`.
  - **Test:** an IFVG without a prior pool sweep does not arm.

### 82. A8-ifvg-stacked-tails-exclusion
- A8 | missing_condition | index | judgment
- **Rule:** a bearish FVG that has been closed through upward would act as IFVG support. Do not trust it if a cluster of long lower tails sits just below it.
  - Expect those tail lows to be run first; the IFVG is valid support only after that. Mirror.
- **Sources:** 090 ~21:24.
- **Quote:** "I like to see these things fail".
- **Conflicts:** none.
- **[our interpretation]:** cluster = 2+ candles whose lower wicks end within a few ticks of each other.
- **Fix:** add to A8.
- **Build (SM):**
  - **Where:** IFVG arming in `_scan`.
  - **Params:** `ifvg_tails_block=False`, `tails_tol_ticks=3`. Arm only after a low below the tail cluster.
  - **Test:** a tails fixture arms only after the tail lows are taken.

### 83. A8-ifvg-15m-body-failure
- A8 | missing_condition | general
- **Rule:** a bearish IFVG (from a bullish FVG) stays valid while no 15m body closes back above the FVG high after the break.
  - On such a close, drop the short idea; the zone may act again as a bullish FVG. Wicks above do not cancel it. Mirror.
- **Sources:** 084 ~12:08.
- **Quote:** "with the Candlestick bodies on the 15 minute time frame".
- **Conflicts:** none.
- **Fix:** A8: define "holds".
- **Build (ME):**
  - **Where:** `run_day` uses 15m bars from `htf_bars` for the IFVG invalidation.
  - **Params:** `ifvg_fail_tf=0` (0 = execution TF; 15 = ICT).
  - **Test:** a 1m body above with no 15m body above keeps the trade at 15.

### 84. A8-htf-gap-resistance-grade
- A8 | shortened | general | judgment
- **Rule (bearish setup from an HTF FVG/IFVG used as resistance):** better when price reacts at or below its CE without trading to the high (breakaway analogy, A6). Trading to the far edge = a weaker setup.
  - Bullish mirror.
- **Sources:** 065 ~1:27:00.
- **Quote:** "we don't want to see the high end of a old fair value Gap".
- **Conflicts:** none.
- **[our interpretation]:** the tiering.
- **Fix:** add a grade to A8.
- **Build (ESS):**
  - **Where:** a Trade tag `htf_depth` (near / ce / far) set at entry; risk_mult by tier.
  - **Params:** `htf_depth_mult=(1.0, 1.0, 1.0)`; test (1, 1, 0.5).
  - **Test:** a fill after a far-edge tag gets 0.5 risk.

### 85. A7-immediate-rebalance-definition
- A7 | wrong | general | judgment
- **Rule:** switch `ir_def`.
  - **`open_space` (059 family, bullish):** candle i+1 (or i+2) trades down to the high of the most recent candle that bounds the open space (yesterday's if it overlaps, otherwise the older candle). It reaches it within a tick up to a ~1-2 tick overshoot, with no body close through, then reverses in the bias direction. Stopping short = breakaway gap (060).
  - **`zero_width` (100):** in a displacement leg, take window c1, c2, c3 with c2 a large bias-direction candle (body >= 1.5x the average body of the last 20 bars). It counts when high[c3] == low[c1] to the tick (bearish), or low[c3] == high[c1] (bullish).
  - **Both modes:**
    - need a known draw in that direction;
    - tag `fast delivery expected`;
    - the level is a PD array on that TF;
    - with bias, enter or add with a tight stop beyond c3's extreme;
    - first partial at the nearest opposing pool;
    - exit on a retrace back through the range EQ (X8).
  - Mirror.
- **Sources:** 059 ~4:16, 060 ~7:29, 061 ~1:23:38, 078 ~1:15:05, 100 ~44:46, 099 ~1:04:01.
- **Quote:** "it doesn't mean it's the previous day immediately to the left".
- **Conflicts:** A7 (yesterday, exact, next candle) vs the 059 family vs 100.
- **[our interpretation]:** the 1.5x average body, the 1-2 tick overshoot, and the open-space edge.
- **Fix:** rewrite A7.
- **Build (LD):**
  - **Where:** `levels.immediate_rebalances` gains `mode=`.
  - **Params:** `ir_def="a7"` ("open_space" / "zero_width"), `ir_overshoot_ticks=2`, `ir_body_mult=1.5`.
  - **Test:** a Wed-to-Mon-high fixture is found only under open_space.

### 86. A7-immediate-rebalance-gates
- A7 | missing_condition | general | judgment
- **Rule:** an immediate rebalance is a continuation trigger only if:
  - (a) the draw on liquidity / HTF bias was known beforehand and the rebalance points toward it;
  - (b) it occurs in a window where volatility is expected (existing kill zone / macro windows).
  - Otherwise do not act on it.
- **Sources:** 059 ~4:50, 060 ~7:29, 080 ~9:41.
- **Quote:** "the immediate rebalance isn't going to help you all that much".
- **Conflicts:** none.
- **[our interpretation]:** the window list = `macro` + am/pm sessions.
- **Fix:** A7/M11: add the gates.
- **Build (SM):**
  - **Where:** `ir_entries` / `sb_rebalance_ext` gating in `_scan` and `sb_model.py`.
  - **Params:** `ir_need_draw=True`, `ir_need_window=True` (new gates; True only affects the existing opt-in IR paths).
  - **Test:** an IR outside the windows does not trigger.

### 87. A12-ob-requires-narrative
- A12 | missing_condition | general | judgment
- **Rule:** a bullish OB qualifies only if all of these hold:
  - (1) the session bias/draw is up;
  - (2) price reached a predefined HTF discount array and the OB candles lie inside it;
  - (3) a transitional event happened before or by the OB (sell-side taken, or an unfilled discount array traded into);
  - (4) the OB is the last down-close candle (or run) before the rotation up; level = the open of the run; no engulfing or body-size requirement;
  - (5) a CISD/MSS follows;
  - (6) the retrace into it puts price in a short-term discount.
  - **High probability:** (3) plus an FVG on the move away.
  - Otherwise a down-close candle is just a candle. Mirror.
  - **Rulebook:** remove or downgrade the "larger body" quality factor (092).
- **Sources:** 059 ~19:00, 064 ~51:56, 065 ~1:28:02, 085 ~40:10, 061 ~25:13, 073 ~12:07, 092 ~2:02:31.
- **Quote:** "There has to be a narrative."
- **Conflicts:** none.
- **[our interpretation]:** how (2) is detected (HTF array within the zone).
- **Fix:** A12: add the narrative/transition requirement; drop "larger body".
- **Build (ESS):**
  - **Where:** the `_scan` OB-entry branch (the default `ob_entry="pre_break"` path).
  - **Params:** `ob_need_narrative=False`. It requires `want` to agree, a swept pool or a touched HTF array before the OB, and the OB inside an HTF discount array when `ob_need_htf_array=True`.
  - **Test:** an OB with no prior sweep does not arm.

### 88. A12-ob-open-anchor-ltf-wick
- A12 | shortened | general | judgment
- **Rule:** with a stubby wick, the open is the HTF anchor, but trading into the wick between the open and the extreme does not invalidate the OB.
  - Look on the LTF for a PD array inside that wick for the entry.
  - Invalidation stays at the OB extreme / MT rules.
- **Sources:** 061 ~26:10.
- **Quote:** "generally as a rule of thumb but not always".
- **Conflicts:** none.
- **[our interpretation]:** stubby = wick < 25% of the candle range.
- **Fix:** add to A12.
- **Build (ESS):**
  - **Where:** HTF OB entries (`htf_entry_arrays`). Search for an LTF FVG/OB inside [open, low] of the HTF OB.
  - **Params:** `ob_wick_ltf_entry=False`.
  - **Test:** an LTF FVG inside the wick is used as the entry.

### 89. A12-ob-anchor-level
- A12 | unlisted_contradiction | general | judgment
- **Rule:** switch `ob_anchor`:
  - `open_first` (A12 default, 2023);
  - `extreme` (CC swing: bullish = the high of the down-close candle or the highest high of a consecutive HTF series; bearish = the low of the up-close candle; the open is the conservative level).
  - First touch = setup; stop beyond the far extreme. Drop `close_last` (072 returns to the open). Mirror.
- **Sources:** cc03_001 ~28:18, cc06_004 ~13:07, cc10_005 ~16:40, 072 ~7:43.
- **Quote:** "this level begins at the high".
- **Conflicts:** A12 open vs CC extreme.
- **[our interpretation]:** which mode applies to HTF/swing vs intraday.
- **Fix:** list the decision in section 3.
- **Build (ESS):**
  - **Where:** `ob_entry_px` exists (body_top / mt / range_top). "range_top" = the extreme.
  - **Change:** document the mapping; no new param. For HTF arrays add `htf_ob_anchor="open"` ("extreme").
  - **Test:** an HTF OB target level moves to the high under "extreme".

### 90. A12-open-vs-wick-gap-criterion
- A12 | missing_condition | general | judgment
- **Rule:** if the range between an OB candle's body and its wick extreme has been traded through at least twice ("closed in", no FVG remains), anchor on the body.
  - Level = the open; zone = the body; a small probe beyond the open is allowed (cc05_015: ~5 pips); invalidation = a trade beyond the body midpoint (cc04_013).
  - If the wick area still holds an untraded gap, use the wick extreme/gap. Otherwise use the A12 stubby/long rule.
- **Sources:** cc05_015 ~11:32, cc04_013 ~16:17.
- **Quote:** "there's an absence of a gap".
- **Conflicts:** A12 decides by wick length.
- **[our interpretation]:** the "twice" count = 2 bars whose ranges cover the wick area.
- **Fix:** add the criterion to A12.
- **Build (LD):**
  - **Where:** `levels.order_block` gains `anchor_rule="wick_len"` ("gap_presence"); a helper counts passes over [body edge, wick tip].
  - **Params:** `ob_anchor_rule="wick_len"`.
  - **Test:** a wick area overlapped by the prior bar's wick anchors on the open.

### 91. A12-tf-relative-ob
- A12 | missing_rule | general
- **Rule:** if the HTF swing-extreme candle has the "wrong" colour, look inside it on a lower TF.
  - Take the last up-close LTF candle before the displacement as the bearish OB (open, MT, high), labelled at the HTF location.
  - It gains weight when it is also the high of an inefficiency. Mirror.
- **Sources:** 079 ~15:06.
- **Quote:** "don't get thrown off that this is the down closed candle".
- **Conflicts:** none.
- **Fix:** add to A12.
- **Build (LD):**
  - **Where:** `htf._arrays` OB detection. When the extreme candle has the wrong colour, resample the lower TF (D -> 1h) inside it.
  - **Params:** `htf_ob_ltf_drill=False`.
  - **Test:** a down-close daily swing-high candle yields an OB from its last up-close 1h bar.

### 92. new-multi-tf-scan
- new | missing_rule | general | judgment
- **Rule:** resample to 1m, 2m, 3m, 4m, 5m (and 2h; sub-minute where data allow). Detect FVGs/OBs on each and project all onto the 1m chart as entry arrays or targets.
  - Accept an OB only at a meaningful point in delivery (after a liquidity run, before displacement toward the draw).
- **Sources:** 070 ~30:37, 072 ~11:09.
- **Quote:** "toggling through all the time frames".
- **Conflicts:** none.
- **[our interpretation]:** the TF list; sub-minute is out of reach (1m data).
- **Fix:** add a new rule.
- **Build (ESS):**
  - **Where:** `_scan` gap pick; `htf_bars(df, m)` for m in the list.
  - **Params:** `scan_tfs=(1,)`; test (1, 2, 3, 4, 5).
  - **Test:** a gap visible only on 3m is found.

### 93. A6-breakaway-depth-qualification
- A6 | unlisted_contradiction | general | judgment
- **Rule:** state machine (bearish):
  - candidate -> retraced (price trades in, far edge untouched) -> QUALIFIED when price then trades below the lowest low since the gap formed with the far edge still untouched.
  - Only a qualified gap is a protected/trail level.
  - **Depth switch `bk_depth`:** ce (A6, max 50%) | any_open (062, cc04_009: any portion left open, then a move away = breakaway; the open sliver is a protected FVG). A full fill = not breakaway.
  - **BPR beyond:** if a BPR sits directly beyond the gap, require the retrace to stay on the near side of CE (065); past CE = downgrade and cancel adds.
  - **IFVG as breakaway (084):** if [gap low, CE] stays untouched, also treat it as measuring: target = CE - (swing high - CE). If it fills, the bias may stand but drop that target.
  - **075 variant:** if price closes into it, keep the short while no body closes above the highest body of the swing high; stop above the wick.
  - Mirror.
- **Sources:** 062 ~37:12/~39:01, 075 ~1:39:36, 065 ~4:39:02, 084 ~29:16, cc04_009 ~13:37.
- **Quote:** "it leaves and goes lower to another new low and leaves that portion open".
- **Conflicts:** A6 vs 062 vs 065 vs 075 vs cc04_009.
- **[our interpretation]:** default any_open.
- **Fix:** A6: replace "at most half" with the switch; list the conflict.
- **Build (LD + ME):**
  - **Where:** the `breakaway` tag gains `bk_state`; `ladder_trail="breakaway"` (X5a) uses only qualified gaps.
  - **Params:** `bk_depth="ce"` ("any_open"), `bk_bpr_ce=False`.
  - **Test:** a 90% fill followed by a new low qualifies under any_open, not ce.

### 94. A6-breakaway-by-refusal
- A6 | missing_rule | index | judgment
- **Rule:** after entry and shift, list the add levels in order (e.g. the IFVG just traded through, then the HTF VI high); add on a 1-tick touch (E12).
  - If price runs without touching level 1 and then level 2, label the most recent FVG below a breakaway gap.
  - Do not wait for a retrace into it, do not trail stops inside it, and hold toward the draw.
- **Sources:** 090 ~2:03:43.
- **Quote:** "it doesn't deliver to it doesn't mean it's failure it's insightful".
- **Conflicts:** none.
- **[our interpretation]:** "runs past" = price exceeds the entry by the distance to level 2.
- **Fix:** add to A6.
- **Build (ME):**
  - **Where:** `run_day` add block. When armed adds are skipped by the run, set `pos["breakaway_refusal"]`, then hold the runner (skip `ladder_trail` inside that FVG).
  - **Params:** `refusal_breakaway=False`.
  - **Test:** two missed adds switch the trail off.

### 95. A9-vi-breakaway
- A9 | missing_rule | general | judgment
- **Rule:** a VI on the candle(s) leaving a consolidation, right after an MSS, or inside a displacement leg beyond the current retrace limit, in the bias direction, is a `breakaway_vi`.
  - Exclude it from retrace targets and entry zones; expect bodies not to close across it; the range it leaves is protected.
  - A body close through it weakens the bias; a later full body across it = it was not breakaway. Mirror.
- **Sources:** 079 ~14:20, 103 ~25:18.
- **Quote:** "the volume imbalance can act much like a breakaway Gap".
- **Conflicts:** none.
- **[our interpretation]:** the context tests.
- **Fix:** add to A9/A6.
- **Build (LD):**
  - **Where:** a VI Zone tag `breakaway`; `_scan` skips tagged VIs in entry_arrays vi.
  - **Params:** `vi_breakaway=False`.
  - **Test:** a VI on the MSS candle is not used as the entry.

### 96. A6-gap-hierarchy-common
- A6 | missing_rule | general | judgment
- **Rule:** for each swing away from an expected HTF level (2 MSSs, 062):
  - breakaway = the gap that leaves the level and stays partly open (trail level);
  - measuring = the gap near the middle that holds on the retrace (projection source);
  - other FVGs = common.
  - **Common gaps:** may be retested many times and act as S/R after being traded through. Bodies at or beyond the edge with wicks piercing = respected (valid add/entry).
  - **Trails:** partials, adds and trails reference breakaway/measuring gaps (062 ~44:40).
  - **CC definition (cc04_010), tag separately:** bearish common gap = open[i] < close[i-1] with no range closing the space; zone [open[i], close[i-1]]; expect bodies to close it; use it as a limit zone in the trend direction. Mirror.
- **Sources:** 062 ~39:41/~43:58, cc04_010 ~12:25.
- **Quote:** "gaps are just like a pdra matrix they have an hierarchy".
- **Conflicts:** 062 common = ordinary FVG vs the CC body gap.
- **[our interpretation]:** "never trail behind a common gap" (extrapolation, made a switch).
- **Fix:** A6: add the procedure and the naming conflict.
- **Build (LD):**
  - **Where:** a `gap_class` tag on FVG zones (breakaway / measuring / common) from items 21, 22, 93; plus `levels.common_gaps_cc(o,c)`.
  - **Params:** `gap_classes=False`, `trail_skip_common=False`.
  - **Test:** the second FVG of a leg that held is tagged measuring.

### 97. new-2m-fvg-ce
- new | missing_rule | general
- **Rule:** when a 1m FVG's displacement is two consecutive same-direction 1m candles, view it on a 2m chart (one candle).
  - The expected retrace limit and entry = the CE of the 2m FVG (062 ~40:09); this can be the measuring gap.
  - Invalidation per A5.
- **Sources:** 062 ~40:09.
- **Quote:** "consequent correction of the two minute range".
- **Conflicts:** none.
- **Fix:** add a new rule.
- **Build (ESS):**
  - **Where:** `_scan` entry price. If the FVG c2 and its neighbour are same-direction 1m bars, compute the FVG on 2m (`htf_bars(df,2)`) and use its CE.
  - **Params:** `two_min_ce=False`.
  - **Test:** a two-candle displacement enters at the 2m CE.

### 98. A11-bpr-levels-ce-rejection
- A11 | shortened | general
- **Rule:** BPR (including one built from a single-candle BISI and SIBI): levels = high, CE, low, extended right indefinitely.
  - **Bearish:** sell at the CE on each revisit from below, stop above the high; valid while no body closes above CE. Once price has left, the far edge is the invalidation. Mirror.
- **Sources:** 062 ~3:47, 082 ~3:55, 077 ~13:48.
- **Quote:** "hits it like a brick wall sells off".
- **Conflicts:** none.
- **Fix:** A11: add the reaction levels and the CE entry.
- **Build (SM):**
  - **Where:** a `_scan` entry_arrays value "bpr_ce", using `levels.balanced_ranges` (+ bpr2 from item 1); repeat retests allowed.
  - **Params:** `entry_arrays` + "bpr_ce".
  - **Test:** two revisits to the BPR CE both arm.

### 99. E9-bpr-fvg-size
- A11/E9 | shortened | general | judgment
- **Rule:** a SIBI overlapped by one adjacent up-close candle with continuous delivery = an FVG inside a BPR, a high-grade array. Max size about 1.5-2x normal (15-20 vs about 10 contracts). Mirror.
- **Sources:** 092 ~10:06.
- **Quote:** "I could build that to you know 15 to 20 contracts".
- **Already covered:** E9 `size_rules` lists a test-only BPR size-up. Only the multiplier value (1.5-2.0) and the single-adjacent-candle form are new: record them in E9's spec. No separate build spec.
- **Fix:** E9: add the figures.

### 100. A5-skip-fvg-near-stop-pool
- A5 | wrong | general | judgment
- **Rule (short):** reject an entry FVG that sits just below a nearby untaken short-term high that itself lies below the protective high; price can run that buy side without reaching your protective high.
  - Instead drop to a lower TF (e.g. 10s; for us 1m/2m) to find a higher FVG/OB at or above that short-term high.
  - ICT gives no distance threshold. Mirror.
- **Sources:** 060 ~1:11:00.
- **Quote:** "this is too close in proximity".
- **Conflicts:** the A5 geometry ("right above a liquidity pool") is reversed for this case.
- **[our interpretation]:** distance <= 2 pts.
- **Fix:** A5: correct the geometry.
- **Build (ESS):**
  - **Where:** `fvg_skip_above_pool` (exists) gains a short-side mirror check in `_scan`.
  - **Params:** `fvg_skip_below_pool_short=False`, `fvg_pool_gap_pts` (exists).
  - **Test:** a short FVG 1 pt under an untaken high is skipped.

### 101. A12-range-internal-ignore
- A12 | missing_rule | general | judgment
- **Rule:** after an MSS plus the return to the OB defines a dealing range (064: post-OB candle high to the OB low; 066: sweep high to the post-displacement low):
  - ignore all FVGs, OBs and structure made by candles strictly inside it;
  - keep the setup armed through any number of retests, especially over lunch;
  - valid while no body closes below the OB MT / beyond the invalidation extreme;
  - a trade beyond the far extreme = expansion toward the first draw.
- **Sources:** 064 ~56:17, 066 ~32:01.
- **Quote:** "all of these candles in between are all time distortion".
- **Conflicts:** none.
- **[our interpretation]:** "strictly inside" uses wicks.
- **Fix:** add to A12.
- **Build (SM):**
  - **Where:** `_scan`. While a range lock is active, suppress new sweeps/MSS/FVG arming from bars inside it; keep the armed order with no `pending_minutes` expiry.
  - **Params:** `range_lock=False`.
  - **Test:** lunch chop inside the range does not cancel the order.

### 102. A5-multitf-hold-test
- A5 | missing_condition | general | judgment
- **Rule:** for a 5m BISI being retested, look at the 1-4m charts.
  - Wicks entering the gap while bodies mostly stay above its high = holding: favour the continuation long. Bodies closing inside = a weaker hold.
  - Discretionary confirmation.
- **Sources:** 064 ~1:32:01.
- **Quote:** "the wicks and bodies are not both inside that fair value gap".
- **Conflicts:** none.
- **[our interpretation]:** "mostly" = no 2+ bar closes inside on any of 1-4m.
- **Fix:** add to A5.
- **Build (ESS):**
  - **Where:** `_scan` fill check for 5m entry arrays.
  - **Params:** `mtf_hold=False`.
  - **Test:** two 2m closes inside the gap cancel the entry.

### 103. A10-void-levels-persistence
- A10 | shortened | general | judgment
- **Rule:** liquidity void zone = [high[i-1], low[i]] (or mirror), CE = midpoint, extended right.
  - On a reprice expect a reaction at CE more than at the far edge. In bearish delivery the upper part should not be retraded.
  - A void left untouched can stay open a long time; keep it as a longer-term level, not an assumed same-session fill.
- **Sources:** 065 ~1:58:00, 077 ~2:24.
- **Quote:** "this can be something that can stay open for a long time".
- **Conflicts:** none.
- **[our interpretation]:** drop the near-term target after a far-side swing.
- **Fix:** A10: add the levels and the persistence.
- **Build (TP):**
  - **Where:** `void_targets` (coverage A10) rung at CE; voids persist in DayCtx across days via `htf._arrays`.
  - **Params:** `void_ce_rung=False`.
  - **Test:** a void target rung equals its CE.

### 104. A19-second-mss-no-new-low
- A19 | missing_condition | index
- **Rule:** after a valid bearish MSS, if the retrace makes a lower high (the pre-MSS high is not pierced), a later displacement down leaving FVG(s) is a valid entry leg even without breaking the latest low.
  - Stop just above the CE of the higher FVG when there are two (or above the lower high). Mirror.
- **Sources:** 069 ~14:41.
- **Quote:** "it didn't need to for me to enter".
- **Conflicts:** A19 requires a fresh break.
- **Fix:** add to A19.
- **Build (SM):**
  - **Where:** `_scan`. After an MSS, keep the side armed while highs stay below the pre-MSS high; a new displacement FVG arms an entry.
  - **Params:** `mss_rearm_lower_high=False`.
  - **Test:** the 069-style fixture enters on the second leg.

### 105. L7-org-close-and-direction
- L7 | wrong | index
- **Rule:** ORG = the close of the prior day's last RTH 1m bar (ES: stamped 16:14; SPX/SPY: 15:59) to the 09:30 1m open.
  - Use the last-trade close, not exchange settlement.
  - org_dir = discount if open < prior close (high = prior close, low = open), premium if above. CE = midpoint.
- **Sources:** 069 ~10:03/~11:05.
- **Quote:** "we are opening with a discount opening range Gap".
- **Conflicts:** L7 "16:15 settlement".
- **Fix:** L7: last-trade close, plus the direction label.
- **Build (LD):**
  - **Where:** `org_close` per symbol (built; 0 = auto). Verify that auto = the last RTH 1m bar close; add `org_dir` to DayCtx/Trade tags.
  - **Params:** none new.
  - **Test:** an ES day gives the ORG high = the 16:14-bar close when the open is lower.

### 106. new-ignore-dojis
- new | missing_rule | index | judgment
- **Rule:** doji/indecision candles against the expected draw are not reversal signals. Do not exit or flip on them; manage only on defined invalidations (X7/X8).
- **Sources:** 071 ~22:54.
- **Quote:** "I don't trust those doji's".
- **Conflicts:** none.
- **[our interpretation]:** "never exit" (extrapolation).
- **Fix:** add a guard rule.
- **Build (ME):**
  - **Where:** none needed (no doji logic exists). Add a regression test only.
  - **Test:** a fixture of dojis against the position produces no exit and no flip.

### 107. A9-vi-quarters
- A9 | shortened | general | judgment
- **Rule:** for each weekly VI, measured over the actual weekly candles forming it, mark 0/25/50/75/100 as LTF reaction, entry and partial levels. Study homework; untested.
- **Sources:** 074 ~16:08.
- **Quote:** "0.25 0.50 0.75".
- **Conflicts:** none.
- **[our interpretation]:** use in the ladder.
- **Fix:** A9: add quarters.
- **Build (TP):**
  - **Where:** `vi_arrays` weekly rows get `.q()` levels; `_targets` adds them when on.
  - **Params:** `vi_quarters=False`.
  - **Test:** a weekly VI adds 3 inner rungs.

### 108. A9-settlement-vs-last-trade
- A9 | missing_rule | needs_unavailable_data
- **Rule:** detect VIs and the Friday close on both settlement-based and last-trade daily bars; either is valid.
- **Sources:** 076 ~3:51.
- **Quote:** "I like to use the settlement price toggled on".
- **Conflicts:** none.
- **Fix:** A9 note.
- **Build:** none (needs settlement data).

### 109. A21-post-cisd-range-retrace
- A21 | unlisted_contradiction | general
- **Rule (bullish):** after a CISD validates the OB, dealing range = [the low the CISD protects, the swing high from which the down move into that low began].
  - EQ and 25/50/75 gradients; all buying at or below EQ.
  - Add as a D12 option. Bearish mirror.
- **Sources:** 075 ~1:23:41.
- **Quote:** "a premium relative to what the range which is this High to that low".
- **Conflicts:** A21 uses the MSS displacement leg.
- **Fix:** D12: add the option.
- **Build (ESS):**
  - **Where:** `leg_pd` anchor in `_scan`.
  - **Params:** `leg_pd_anchor` value "retrace_range" (the swing high that started the decline -> the sweep low).
  - **Test:** EQ = the midpoint of that range.

### 110. A21-salient-dealing-ranges
- A21 | missing_rule | general | judgment
- **Rule:** before each kill zone, on D, 4h, 1h and 15m, take the latest intermediate-term run (a significant swing high to swing low).
  - Compute EQ and list the PD arrays in premium (for shorts) or discount (for longs). Any array type qualifies.
- **Sources:** 061 ~1:38:11.
- **Quote:** "all the ranges that are Salient".
- **Conflicts:** none.
- **[our interpretation]:** "intermediate run" = the ITH/ITL pair from `levels.swing_tiers`.
- **Fix:** add to A21.
- **Build (BH):**
  - **Where:** `htf.table` adds per-TF eq_d/eq_4h/eq_1h/eq_15m columns; `_scan` gate `pd_all_tfs`.
  - **Params:** `salient_pd=()` (TFs that must agree).
  - **Test:** a long above the 1h EQ is blocked with (60,).

### 111. B6-intraday-iof
- B6 | shortened | general | judgment
- **Rule:** intraday IOF on 1-5m after a CISD/MSS. Extend the open of each down-close candle.
  - Bullish IOF holds while price supports at those opens (no body close below), each support leads to a new short-term high, and any short-term low taken reverses right away. A failed open = IOF no longer bullish. Mirror.
- **Sources:** 075 ~1:21:58.
- **Quote:** "we want to see down closed candles support price".
- **Conflicts:** none.
- **[our interpretation]:** the 1-3 bar reversal tolerance.
- **Fix:** B6: add the intraday form.
- **Build (ME):**
  - **Where:** `run_day` position loop. Track the down-close opens after the fill; exit or tighten on a body close below the latest one.
  - **Params:** `iof_intraday_exit=False`.
  - **Test:** a body close below the last down-close open exits.

### 112. A24-reaper-definition
- A24 | missing_rule | general | judgment
- **Rule:**
  - **Option A (076, bullish):** breaker L1 < H, then L2 < L1, then a break above H. The Reaper = a bullish FVG in the discount half of the L1->H leg that was traded through on the way to L2.
    - Gate: HTF bias plus a retail pattern broken down before the touch.
    - Bodies respect its CE. Enter on the confirming candle or at a limit inside.
    - Target = the draw (any measured-move target is ours).
  - **Option B (081, bearish):** a high-low-higher-high breaker whose zone (biggest-body, lowest-close down candle) coincides with a bearish OB; short the return.
  - Mirror both.
- **Sources:** 076 ~21:44/~22:10, 081 ~11:49.
- **Quote:** "a Reaper is a fair value Gap in a discount of the impulsive price leg".
- **Conflicts:** 076 vs 081 definitions.
- **[our interpretation]:** the retail-pattern gate is not coded.
- **Fix:** A24: remove "not codeable"; list both definitions.
- **Build (SM):**
  - **Context:** Option A = `levels.reaper` + `reaper` (built, A24.2).
  - **New:** `reaper_def="fvg"` ("ob_overlap": the breaker zone overlaps an OB from `levels.order_block`).
  - **Test:** an 081-style fixture arms under ob_overlap.

### 113. A5-A10-htf-lifetime
- A5 | unlisted_contradiction | general | judgment
- **Rule:** lifetime scales with TF.
  - **Daily/intraday:** 60 trading days.
  - **Weekly-and-higher FVGs, VIs and voids:** valid as draws until rebalanced (A5 state rules), with no age cap.
  - **HTF (M/W) OBs:** valid until first traded back into (cc03_001: the first touch is the setup) or a body closes through the MT.
  - Whether one is the current draw is judged from price action, not age. Keep a separate HTF array list built from D/W/M bars.
- **Sources:** 077 ~3:59, 099 ~4:14, cc04_010 ~2:19, cc03_001 ~28:41.
- **Quote:** "a fair buy Gap can stay open for a number of days months weeks years".
- **Conflicts:** A5/B1 ~60-day cap.
- **[our interpretation]:** no cap.
- **Fix:** A5/B1: limit the 60-day cap to daily/intraday.
- **Build (BH):**
  - **Where:** `htf._arrays` lookback per TF; `htf.table(lookback=60)` applies to D only.
  - **Params:** `htf_lifetime_wm=0` (0 = no cap; else days). Needs >= 2 years of history loaded.
  - **Test:** an 8-month-old weekly FVG stays a draw.

### 114. A22-array-reuse
- A22 | unlisted_contradiction | general | judgment
- **Rule:** while the HTF narrative is intact and the draw is unreached, a touched PD array stays valid for re-entry unless a body closes through its MT/CE or the bias flips.
  - **FVGs:** prior visits are not a filter; the FVG must be engaged in a valid time window.
  - **W/M arrays and HTF EQ:** can be retested several times and may pause there. The first failure to react is not invalidation, and 1m X9 time stops do not apply to trades based on them.
  - Keep "prefer untested" as a tiebreaker. Any retest/expiry count limit is ours.
- **Sources:** 061 ~2:11:51, 095 ~34:40, cc04_001 ~14:22, cc04_002 ~17:46, cc06_005 ~29:36, cc10_008 ~6:09.
- **Quote:** "their sponsorship doesn't expire simply because it's traded to it before".
- **Conflicts:** A22/L14 skip exhausted, prefer untested (cc07_004). A13 is not in conflict.
- **[our interpretation]:** the defaults.
- **Fix:** A22/L14: list the conflict.
- **Build (TP + ME):**
  - **Where:** `skip_exhausted` (coverage A22) becomes a mode.
  - **Params:** `array_reuse="first_touch"` ("reuse" / "tiebreak"); `htf_no_time_stop=False` (skip `time_stop_min` when the entry array TF >= W).
  - **Test:** a second touch of a daily FVG arms under "reuse".

### 115. A4-wick-poke-vi-invalidation
- A4 | shortened | index
- **Rule:** after a wick-only poke above a daily VI/level (no body close above), keep the short idea and record H = the poke high.
  - A trade back above H cancels AM shorts; re-evaluate at the 13:30 PM session. Mirror.
- **Sources:** 090 ~1:05:53.
- **Quote:** "if it goes back Above This High here ... I'm not interested".
- **Conflicts:** none.
- **Fix:** add to A4.
- **Build (SM):**
  - **Where:** `run_day` side state. After a poke of an HTF level, store H; a trade above H sets AM done for shorts.
  - **Params:** `poke_high_cancel=False`.
  - **Test:** a trade above the poke high blocks AM shorts and allows PM.

### 116. new-single-candle-daily-inefficiency
- new | missing_rule | index | judgment
- **Rule:** single-pass inefficiency = a large up-close candle whose range (low to high) no other candle has traded through.
  - Levels at 0/25/50/75/100%. Until price trades back down through it, flag "needs sell-side delivery": expect CE, then the lower quadrant.
  - Fuller targets: LTF BISI lows inside it; the candle low is the extreme case. Mirror.
- **Sources:** 091 ~25:37.
- **Quote:** "only one candle went higher".
- **Conflicts:** none (M15 uses it).
- **[our interpretation]:** the exact edges; "large".
- **Fix:** add a generic definition (M15 uses it).
- **Build (LD):**
  - **Where:** `levels.single_pass_ranges(o,h,l,c)` on daily bars in `htf._arrays`, as kind "spr" with quarters.
  - **Params:** `single_pass_draw=False`.
  - **Test:** a daily candle untouched by its neighbours yields an spr zone.

### 117. A5-vi-extended-ce
- A5 | missing_condition | general
- **Rule:** when an FVG's forming candles include a VI on the far side (including a wick-only link), extend the zone to the VI's far body edge.
  - CE = the midpoint of (near edge, extended far edge). Use it as the reaction/target level and allow a small overshoot (~2 pts on ES weekly).
- **Sources:** 098 ~1:09:26/~1:09:42.
- **Quote:** "you have to incorporate the entirety of that".
- **Conflicts:** none.
- **Fix:** A5: recompute CE on the extension.
- **Build (LD):**
  - **Where:** `fvg_vi_extend` (built). Check that Zone.mid uses the extended edges and covers the wick-linked case.
  - **Params:** `fvg_vi_extend_ce=True` when `fvg_vi_extend` is on (fix, not a new behaviour switch).
  - **Test:** an extended zone CE equals (near + VI far)/2.

### 118. A11-balanced-range-body-filled
- A11 | unlisted_contradiction | general | judgment
- **Rule:** midpoint naming: bodies cover the zone height (OB or two-way range) = equilibrium; no bodies (FVG/VI/void/wick) = CE.
  - **Body-filled balanced range:** several consecutive overlapping candles traded both ways, then left by displacement.
  - **On return:** price is redelivered, not rebalanced; expect slowdown at its edge/EQ and do not target its far side without fresh displacement.
  - In code keep the A11 BPR separate; tag this as `balanced_range` with an EQ.
- **Sources:** 098 ~34:57/~1:00:35, 099 ~11:14.
- **Quote:** "its range is balanced so a midpoint of that is equilibrium".
- **Conflicts:** A11 FVG-overlap vs the body-filled range.
- **[our interpretation]:** >= 3 candles, >= 50% overlap.
- **Fix:** A11: list the naming conflict.
- **Build (LD):**
  - **Where:** `levels.balanced_bodies(o,h,l,c,n=3,ovl=0.5)`; `_targets` drops far-side targets beyond such a range.
  - **Params:** `balanced_range=False`.
  - **Test:** a 4-bar overlapping cluster yields a zone with an EQ.

### 119. A11-trapped-trader-bpr
- A11 | missing_condition | general | judgment
- **Rule:** a large-range down candle leaves a SIBI; within a handful of candles a large-range up candle leaves an overlapping BISI.
  - The overlap is the BPR, with trapped shorts below. Bullish narrative: draws above. Mirror. Example on 15m.
- **Sources:** 104 ~26:09.
- **Quote:** "someone that's been caught their short".
- **Conflicts:** none.
- **[our interpretation]:** <= 5-10 bars apart.
- **Fix:** add to A11.
- **Build (BH):**
  - **Where:** `levels.balanced_ranges(max_gap_bars=)` (built) on 15m in `htf._arrays`; tag `trapped` sets a bias hint.
  - **Params:** `trapped_bpr_bias=False`, `bpr_max_gap_bars` (exists).
  - **Test:** a fast down-up pair on 15m sets the bias up.

### 120. A8-ifvg-before-pool
- A8 | missing_condition | general
- **Rule:** a bearish IFVG (from a failed BISI) is armed only while the nearest swing low below has not been traded through.
  - If that low is taken before the return, cancel (the draw is spent). Mirror. Single example (102).
- **Sources:** 102 ~1:08:45.
- **Quote:** "because that sell side's still there".
- **Conflicts:** none.
- **Fix:** add to A8.
- **Build (SM):**
  - **Where:** `_scan` IFVG arming.
  - **Params:** `ifvg_pool_intact=False`.
  - **Test:** taking the low before the retrace cancels the IFVG short.

### 121. A8-ifvg-depth-tolerances
- A8 | shortened | general | judgment
- **Rule:** failed bullish FVG [L,H], short side.
  - **(a) Partly re-traded:** a candle printed low W inside the gap before the failure. After the close below L, the retrace should stop at L, CE or W (cap = min(CE,W)), with only a small mohawk above. Reaching the upper portion toward H = skip. Holding there = strong confirmation.
  - **(b) No prior re-trade:** the retrace may go to H.
  - **(c) Traded H -> past CE, then closed below:** valid only while highs stay <= CE + 1 tick, with the stop just above CE. Reaching the high end kills it.
  - Mirror.
- **Sources:** 102 ~1:11:04/~1:55:46.
- **Quote:** "only be high probability if it stayed below consequent encouragement".
- **Conflicts:** A8 collapses this to "near edge to CE".
- **[our interpretation]:** the cap formula; mohawk = 2 ticks.
- **Fix:** A8: replace the depth rule.
- **Build (SM):**
  - **Where:** `ifvg_depth` (exists, bool). Turn it into modes, using `levels.ifvg_passes`.
  - **Params:** `ifvg_depth` gains "w_cap" (cases a/b/c); keep True = the current behaviour.
  - **Test:** case (a) with W below CE caps the entry and stop at W.

### 122. A2-delivery-vs-liquidity
- A2 | missing_rule | general
- **Rule:** buy-side delivery = a leg moving higher; sell-side delivery = a leg moving lower. Buy-side/sell-side liquidity = static stop pools (A2).
  - MM sell model: buy-side delivery runs into BSL (REH), then sell-side delivery runs to the new SSL below the rally's lows.
- **Sources:** 104 ~11:24.
- **Quote:** "buy side delivery is the actual animated movement of price".
- **Conflicts:** none.
- **Fix:** A2: add the definitions.
- **Build (SM):**
  - **Where:** Trade/state tag `delivery` = up/down for the current leg (sign of the last displacement leg in `_scan`); the MM model (Ep05.8 `mmxm_ctx`) targets the SSL engineered under the rally.
  - **Params:** `mm_ssl_target=False`.
  - **Test:** after an REH run, the target is the lowest low of the rally leg.

### 123. M1-original-consolidation
- M1 | missing_rule | general | judgment
- **Rule:** original consolidation (bullish example):
  - upper bound = a smooth-edge level that bodies/highs touch repeatedly;
  - lower bound = the range's lowest low.
  - Bearish mirror.
- **Sources:** 104 ~27:53.
- **Quote:** "a repetitive overlapping or reoccurrence of a level".
- **Conflicts:** none.
- **[our interpretation]:** >= 3 body tops/highs within a tolerance inside N bars.
- **Fix:** M1: define the bounds.
- **Build (LD):**
  - **Where:** `levels.smooth_edge_range(o,h,l,c,tol,n)` used by `mmxm_ctx`.
  - **Params:** `orig_consol_touches=3`, `orig_consol_tol_pts=0.5`.
  - **Test:** three equal body tops yield a range with the high = that level.

### 124. A4-ltf-body-qualification
- A4 | missing_condition | general
- **Rule:** a 60m FVG reached by a run is a qualified reversal level when LTF (15m, also 5m) bodies stay inside it / do not close beyond its far edge, even if wicks pierce by more than 1-2 ticks.
  - Then expect delivery toward the opposing draw.
- **Sources:** 104 ~21:53/~34:55.
- **Quote:** "only the candlesticks Wicks are piercing it".
- **Conflicts:** A4's 1-2 tick mohawk cap.
- **Fix:** A4: add the LTF body test for HTF arrays.
- **Build (SM):**
  - **Where:** `_scan` HTF array reaction (`htf_entry_arrays` / turtle external). Check 15m and 5m closes from `htf_bars`.
  - **Params:** `htf_body_qual=False`.
  - **Test:** a 15m wick 3 pts beyond with bodies inside still qualifies.

### 125. new-delivery-states-machine
- new | missing_rule | general | judgment
- **Rule:** label the current leg as one of four states:
  - **CONSOLIDATION:** a clear range.
  - **EXPANSION:** a quick move away from the range EQ.
  - **RETRACEMENT:** back inside the recently created range.
  - **REVERSAL:** a run just beyond an old high/low, then rejection.
  - **Transitions:** C -> E only. E -> R(etracement) or R(eversal), eventually C. cc01_001 also allows E -> C and Rev -> Ret; cc01_002 forbids C -> E -> C.
  - Applies intraday. Bot: no entry in CONSOLIDATION.
- **Sources:** cc01_001 ~2:33/~7:51, cc01_002 ~18:35, cc01_003 ~9:15.
- **Quote:** "it's always consolidation expansion".
- **Conflicts:** cc01_001 vs cc01_002 transitions.
- **[our interpretation]:** all thresholds (consolidation = N bars inside < k x ADR5; expansion = A20 displacement).
- **Fix:** add a new rule.
- **Build (DWC):**
  - **Where:** `levels.delivery_state(o,h,l,c,i,adr)` is called in `run_day`; `_scan` skips while CONSOLIDATION.
  - **Params:** `state_machine=False`, `consol_bars=20`, `consol_adr=0.3`.
  - **Test:** a flat 30-bar fixture labels CONSOLIDATION and blocks entries.

### 126. new-state-to-array-map
- new | missing_rule | general | judgment
- **Rule:** setup = delivery state + ICT tool.
  - EXPANSION <-> OB: wait for the return to the OB left near EQ; do not chase.
  - RETRACEMENT <-> FVG/void inside the recent range.
  - REVERSAL <-> liquidity pool / stop run beyond an old high/low.
  - CONSOLIDATION <-> EQ: wait for the impulse away.
  - Use the tool that fits; specialising in one pair is acceptable.
- **Sources:** cc01_001 ~2:33, cc01_002 ~12:42.
- **Quote:** "applying them to respectively order blocks fair value gaps".
- **Conflicts:** none.
- **[our interpretation]:** the mapping as an entry filter.
- **Fix:** add a new rule.
- **Build (SM):**
  - **Where:** `_scan` entry_arrays filter keyed by `delivery_state` (item 125).
  - **Params:** `state_tool_map=False`.
  - **Test:** in RETRACEMENT only FVG/void entries arm.

### 127. A21-consolidation-range-def
- A21 | missing_condition | general | judgment
- **Rule:** consolidation range: high = max body, low = min body over the range candles; EQ = midpoint. It needs a clear high and low.
  - ICT's "check yourself" sanity test: EQ touched or crossed from both sides several times while price stays in the range. Impulse legs keep the A21 wick rule.
- **Sources:** cc01_001 ~11:50/~17:54.
- **Quote:** "defined specifically by the bodies of the candles not the Wicks".
- **Conflicts:** none.
- **[our interpretation]:** >= 2 touches each side.
- **Fix:** add to A21.
- **Build (LD):**
  - **Where:** the `delivery_state` consolidation box uses bodies; `range_eq_touches` check.
  - **Params:** `consol_body_range=True` (only used when `state_machine` is on), `consol_eq_touches=2`.
  - **Test:** the range high equals the max body, not the max wick.

### 128. A3-clean-high
- A3 | missing_condition | general | judgment
- **Rule:** clean high = swing high H1, then price trades away for a while, then H2 with |H2-H1| <= tolerance (slightly below or above).
  - Buy stops sit above max(H1,H2); expect a run through. Continuation vs reversal is decided by other conditions. Mirror.
- **Sources:** cc01_003 ~15:33.
- **Quote:** "it trades away from that for a little while and comes right back to it".
- **Conflicts:** none.
- **[our interpretation]:** "away" = at least one opposite pivot between them / >= N bars.
- **Fix:** A3: add the separation and the "slightly above" allowance.
- **Build (LD):**
  - **Where:** `levels.equal_clusters` gains `min_sep_bars` and uses the max of the cluster as the pool.
  - **Params:** `eq_min_sep_bars=0` (current), test 3.
  - **Test:** two adjacent equal bars do not form a pool at 3.

### 129. M13-swing-confirm-gate
- M13 | missing_condition | general
- **Rule:** bullish leg L to H.
  - **Swing high:** H must be a 3-candle swing high. The arming candle is the 4th, h+2, which must be lower than high[h].
  - **Watch:** only then check for price <= EQ and the 62-79% zone; ignore earlier dips.
  - **Short mirror:** swing low L, then l+2 above low[l].
  - **Reset:** a new extreme before EQ re-anchors and redoes the gate. Candles are counted on the leg's TF.
- **Sources:** cc01_004 ~13:58/~21:38/~28:18, cc01_005 ~8:05/~13:30.
- **Quote:** "the fourth candle has to move lower".
- **Conflicts:** none.
- **Fix:** M13: add the far-extreme gate.
- **Build (ESS):**
  - **Where:** the `ote` path in `_scan` (coverage A21.3/M13).
  - **Params:** `ote_gate_4th=False`.
  - **Test:** a dip to EQ on candle h+1 is ignored.

### 130. M13-reanchor-parent
- M13 | missing_rule | general
- **Rule:** keep the active bullish leg (L,H). On each new swing high above H with no trade below L, set H = the new high, recompute EQ/62/70.5/79 and redo the gate.
  - A trade below L invalidates the leg. Always track the parent leg (L to the latest H). Bearish mirror.
- **Sources:** cc01_004 ~13:58/~21:38/~37:30.
- **Quote:** "keeping it off the same low ... because this price low has not been violated".
- **Conflicts:** none.
- **Fix:** M13: add the re-anchor rule.
- **Build (ESS):**
  - **Where:** the `ote` leg state in `_scan`.
  - **Params:** `ote_reanchor=False`.
  - **Test:** after a new high, the OTE band moves up with the low kept.

### 131. M13-nested-ranges
- M13 | missing_rule | general | judgment
- **Rule:** keep candidate ranges: the parent impulse swing plus child legs that start from an expected reaction level and make a new high. Apply the gate/OTE to each.
  - When price runs beyond a small range's 100%, drop it and check whether price is now at 62-79% of a larger valid range. If an old high/low was just taken there, it is a turtle-soup candidate.
  - **High-probability long location (cc01_006):** the lower third of the parent swing (deep below ~21%) AND below EQ of the current small range, with buy-side above as the target.
  - The parent choice is discretionary. Mirror.
- **Sources:** cc01_004 ~23:31, cc01_005 ~8:28, cc01_006 ~13:16.
- **Quote:** "you would never see this optimal trade entry".
- **Conflicts:** none.
- **[our interpretation]:** the child-leg detection.
- **Fix:** add to M13.
- **Build (ESS):**
  - **Where:** the `ote` path keeps a list of (L,H) legs; a fallback to the parent on child invalidation.
  - **Params:** `ote_nested=False`, `ote_parent_third=False`.
  - **Test:** a child stop-out followed by a parent OTE produces an entry.

### 132. M13-short-ote-mirror
- M13 | wrong | general
- **Rule (short OTE):** H = swing high, L = the later swing low (3-candle, confirmed by the 4th candle trading higher). R = H-L, EQ = L+0.5R.
  - Short only above EQ; zone L+0.62R to L+0.79R; sweet spot L+0.705R; never at EQ; no rally above EQ = no trade.
  - Stop above H; target below old lows. A run through 79% that takes an old high in premium = turtle-soup sell.
- **Sources:** cc01_005 ~7:00/~9:28.
- **Quote:** "we're always looking to sell at a premium".
- **Conflicts:** none.
- **Fix:** M13: add the short side.
- **Build (ESS):**
  - **Where:** `levels.ote_band(ext, hi)` and the `ote` path. Make sure the short side is mirrored for both sides.
  - **Params:** none (bug-class fix behind the existing `ote`).
  - **Test:** a short fixture computes the band above EQ.

### 133. A1-sunday-candle
- A1 | missing_rule | fx_only
- **Rule:** when building daily bars for swing detection, drop Sunday-only sessions (merge them into Monday or exclude them). Not needed for index RTH dailies built from 1m data.
- **Sources:** cc01_004 ~14:20.
- **Quote:** "you don't want to count sundays".
- **Conflicts:** none.
- **Fix:** A1 FX note.
- **Build:** none (fx_only). Futures ETH dailies already roll Sunday into Monday.

### 134. A1-impulse-swing-unit
- A1 | missing_rule | general | judgment
- **Rule:** impulse swing = a clear one-directional leg between alternating swing extremes; keep only clear swings.
  - The fib reference is the active parent leg (re-anchored per item 130), not the latest minor leg.
  - FX only: protraction-time manipulation legs.
- **Sources:** cc01_008 ~1:52.
- **Quote:** "you need to be thinking in terms of impulse price swings".
- **Conflicts:** none.
- **[our interpretation]:** "clear" = item 54's impulsive test.
- **Fix:** A1: define the impulse leg.
- **Build (LD):**
  - **Where:** `levels.impulse_legs(h,l,o,c)` returns legs from `pivots` filtered by the item-54 impulse test; shared by `ote`/`leg_pd`.
  - **Params:** none (helper).
  - **Test:** an overlapping leg is excluded.

### 135. L4-lrlr-bounds
- L4 | missing_rule | general | judgment
- **Rule (bullish LRLR):**
  - (1) From an old high, a fast one-directional down leg with few retracements breaks old low L_b.
  - (2) After the leg low, a higher low then a break of a short-term high (MSS up).
  - (3) Zone = from that break up to L_b. Longs inside it target the buy stops above each new short-term high. At or above L_b it is high resistance: lower the odds or take profit.
  - Bearish mirror.
- **Sources:** cc01_007 ~12:03.
- **Quote:** "this area of price action is deemed low resistance".
- **Conflicts:** none.
- **[our interpretation]:** the "fast" proxy (FVGs left or max retrace).
- **Fix:** L4: add the bounds.
- **Build (TP):**
  - **Where:** `lrlr_max` (coverage L4). Compute the zone in `_targets`; the rung at L_b becomes a partial or final.
  - **Params:** `lrlr_zone=False`.
  - **Test:** a long's ladder ends at L_b with a partial.

### 136. A12-ltf-ob-upper-half
- A12 | shortened | general | judgment
- **Rule:** bullish OB entry zone = [MT, high] of the last down-close candle; entries are acceptable anywhere from high/open down to MT.
  - The OB qualifies after a later candle trades above its high. Stop below the OB low. Mirror [low, MT].
- **Sources:** cc02_002 ~6:24.
- **Quote:** "the midpoint of that candle up to its high".
- **Conflicts:** none.
- **[our interpretation]:** the limit price within the zone (open vs MT) is a parameter.
- **Fix:** A12: state the zone.
- **Build (ESS):**
  - **Where:** `ob_entry_px` already offers body_top / mt / range_top.
  - **New:** `ob_mt_range="body"` ("range": MT = (high+low)/2 for this entry).
  - **Test:** under "range", the mt entry equals the candle midpoint.

### 137. A5-cc-fvg-term-ob
- A5 | unlisted_contradiction | general
- **Rule:** when a CC source says "fair value gap" in an order-block context, map it to the A12 sensitive range [OB open, OB high] (bearish [low, open]), not to the A5 3-candle FVG. Treat it as the most probable support.
- **Sources:** cc02_004 ~2:57.
- **Quote:** "high to open price defines the fair value gap".
- **Conflicts:** A5 3-candle FVG vs the CC usage.
- **Fix:** add a terminology note to A5/A12.
- **Build:** documentation only. The sensitive range already exists (`mt_mode` / item 11 "sensitive").

### 138. A4-sweep-body-cluster
- A4 | unlisted_contradiction | general | judgment
- **Rule:** decision `sweep_ref = wick | body`.
  - **body:** low < min(min(open,close)) over the cluster (2+ candles with bodies ending at about the same price).
  - **cc02_007 (daily):** when price runs below a body-low cluster and it is the first return to that zone in about 1.5-2 months, treat it as HTF accumulation. On the LTF ignore bearish continuation patterns there and buy after a swing high forms and is broken.
- **Sources:** cc03_002 ~11:36, cc02_007 ~21:51.
- **Quote:** "we only need it to reach below the bodies of the candle".
- **Conflicts:** bot wick sweep vs CC body.
- **[our interpretation]:** the 30-45 trading-day window.
- **Fix:** list the decision; add the daily first-return context.
- **Build (SM):**
  - **Where:** `_scan` sweep test (`sweep_ticks` built); A4 `sweep_body` is listed in coverage but unranked.
  - **Params:** `sweep_ref="wick"` ("body"); `daily_first_return=False` (htf.table tag).
  - **Test:** a sweep of the body low without the wick low counts under "body".

### 139. A4-event-wick-ignore
- A4 | missing_rule | general | judgment
- **Rule:** when judging HTF/intermarket swing structure (SMT, correlation), ignore the wick of a candle made by an extraordinary one-off event; use its body extreme.
- **Sources:** cc05_007 ~4:42.
- **Quote:** "without that Wick we have lower high".
- **Conflicts:** none.
- **[our interpretation]:** flag a daily candle whose wick beyond the body is > 2x the 20-day average range, or a known event date.
- **Fix:** add to A4.
- **Build (BH):**
  - **Where:** `htf.table` daily pivots and SMT. Replace flagged wicks with the body extreme.
  - **Params:** `event_wick_ignore=False`, `event_wick_mult=2.0`.
  - **Test:** a spike-wick day does not create the higher high.

### 140. A12-void-up-down-ob
- A12 | missing_rule | general | judgment
- **Rule:** on 4h+, a one-sided rally (void up) followed immediately by a one-sided drop (void down) through the same range = one bearish OB with MT = 50%.
  - A later rally into it in daily premium is a short zone. Refine on the LTF to the last up candles' body range and its 50% EQ (cc02_007 ~14:00-15:00). Bullish mirror.
- **Sources:** cc02_007 ~13:33.
- **Quote:** "this entire range okay is going to be viewed in the scope of a bearish order block".
- **Conflicts:** none.
- **[our interpretation]:** the one-sided run test (>= 3 same-colour bars, no overlap).
- **Fix:** add to A12/A10.
- **Build (LD):**
  - **Where:** `levels.void_round_trip_obs(o,h,l,c)` on 4h in `htf._arrays`.
  - **Params:** `void_rt_ob=False`.
  - **Test:** an up-void then down-void fixture produces one zone.

### 141. A12-ob-reached-body
- A12 | missing_rule | general
- **Rule:** bullish OB [ob_low, ob_high] is reached on the first later candle whose body enters it: min(open,close) <= ob_high.
  - A wick through the whole OB does not cancel it; validity follows the A12 MT rule. Bearish mirror.
- **Sources:** cc03_002 ~8:33.
- **Quote:** "that's all it's required to trade into order block".
- **Conflicts:** none.
- **Fix:** A12: define "reached".
- **Build (ESS):**
  - **Where:** OB touch test in `_scan` / `htf.table` react.
  - **Params:** `ob_reach="wick"` ("body").
  - **Test:** a wick-only touch does not count under "body".

### 142. A15-stoprun-variant
- A15 | unlisted_contradiction | general | judgment
- **Rule (bullish MB, cc03_002):** U = the last up-close candle before a down leg that runs a prior low's sell stops. Price later trades back above U.
  - Zone = U.high down to U's body top (the upper wick; optionally include the body).
  - Buy the first return and expect explosive expansion. Bearish mirror.
- **Sources:** cc03_002 ~19:11.
- **Quote:** "this wick down to the body is a mitigation block".
- **Conflicts:** A15 (cc04_004: failure swing, no stop run, last down-close candle).
- **[our interpretation]:** stop below U's body.
- **Fix:** A15: list both definitions.
- **Build (LD):**
  - **Where:** `levels.mitigation_blocks(..., variant=)`.
  - **Params:** `mit_def="a15"` ("stoprun").
  - **Test:** a stop-run fixture yields the wick zone of U.

### 143. A15-htf-ob-as-mitigation
- A15 | missing_rule | general | judgment
- **Rule:** if a monthly (or weekly) bullish OB has been broken to the downside and daily/HTF order flow is bearish, a daily retrace back into it acts as a mitigation block/breaker (resistance); sell the return. Mirror.
- **Sources:** cc03_002 ~25:51.
- **Quote:** "it becomes a mitigation block on the daily chart".
- **Conflicts:** none.
- **[our interpretation]:** broken = a body close below its low.
- **Fix:** add to A15.
- **Build (BH):**
  - **Where:** `htf._arrays` W/M OBs with an inversion flag (item 8 `invert`); use them as daily premium arrays.
  - **Params:** `htf_ob_mitigation=False`.
  - **Test:** a broken monthly OB becomes a daily resistance array.

### 144. A10-one-sided-leg-levels
- A10 | unlisted_contradiction | general | judgment
- **Rule:** A10 already has the start (first open) as a fill target. New:
  - (a) after a one-sided leg, expect an opposite candle to close back inside the leg before the next opposing pool, unless the range breaks;
  - (b) the body MT = (first open + last close)/2 is the primary target (cc04_004, 1.1148);
  - (c) list the conflict: ICT (cc02-cc04) calls this a "liquidity void".
  - The to-the-pip example (cc04_014) is not coded as a tolerance.
- **Sources:** cc03_002 ~3:38/~7:18, cc04_004 ~10:17, cc04_014 ~6:38.
- **Quote:** "wherever there is a black candle there must be a green candle".
- **Conflicts:** A10 vs CC void naming.
- **[our interpretation]:** a leg = >= 2 consecutive same-direction bars.
- **Fix:** A10: add (a)-(c).
- **Build (TP):**
  - **Where:** `leg_start_target` (coverage A10). Add an MT rung.
  - **Params:** `leg_mt_target=False`.
  - **Test:** the ladder contains the body MT before the leg start.

### 145. A12-sponsorship-origin-ob
- A12 | missing_rule | general
- **Rule:** after a daily displacement leg, mark the last down-close daily candle at its origin; zone = its body (open to close), ignoring the wick.
  - On a return, expect an immediate dynamic upside response and look for LTF longs. A lethargic response = cut size or exit (X9). Mirror.
- **Sources:** cc03_003 ~12:43.
- **Quote:** "we're using the body of that candle here not so much the wick".
- **Conflicts:** none.
- **Fix:** add to A12.
- **Build (BH):**
  - **Where:** `htf._arrays` adds an "origin_ob" (daily, body zone) as a discount array.
  - **Params:** `origin_ob=False`.
  - **Test:** a daily leg fixture yields the body zone of its origin candle.

### 146. new-ob-session-filter
- new | missing_rule | general
- **Rule:** while bullish with the HTF target unmet, valid retracement entries are:
  - (a) bullish OBs formed in the London or NY session of the prior day or last few sessions;
  - (b) a run below a prior London/NY session low, then a rally.
  - Prefer these over OBs from other hours. Mirror.
- **Sources:** cc03_003 ~41:41.
- **Quote:** "every order block that we refer to here is linked to a london session or a new york session".
- **Conflicts:** none.
- **[our interpretation]:** windows London 02:00-05:00, NY 07:00-11:00 ET.
- **Fix:** add a new rule.
- **Build (ESS):**
  - **Where:** an OB tag `session_block` (`levels.session_block`); `_scan` ranks or filters by it.
  - **Params:** `ob_session_filter=False`.
  - **Test:** a 12:30 OB is skipped when on.

### 147. new-monthly-dealing-range
- new | missing_rule | general | judgment
- **Rule (monthly, bullish):** from the most recent down-close candle D, search left for the nearest up-close candle U that trades above high[D].
  - Range = D (bullish OB) up to U (bearish OB / objective). Bearish mirror. Refine down to W/D/H.
- **Sources:** cc03_004 ~8:15.
- **Quote:** "find the most recent down candle and most recent up candle".
- **Conflicts:** none.
- **[our interpretation]:** which edge price to use; the low[U] > high[D] option.
- **Fix:** add a new rule.
- **Build (BH):**
  - **Where:** `htf.table` monthly columns m_rng_lo / m_rng_hi from `htf.sessions`-resampled monthly bars.
  - **Params:** `monthly_range=False`.
  - **Test:** a monthly fixture picks the expected D/U pair.

### 148. A12-bearish-activation
- A12 | missing_condition | general
- **Rule:** an up-close candle U becomes an active bearish OB only after a later low < low[U]; only activated OBs are traded.
  - The side most recently activated (monthly) defines HTF order flow: bullish if a down candle's high was violated, bearish if an up candle's low was violated.
- **Sources:** cc03_004 ~14:23.
- **Quote:** "violating its low which then activates that as a bearish order block".
- **Conflicts:** none.
- **Fix:** A12: add the bearish activation and the order-flow link.
- **Build (BH):**
  - **Where:** `htf.table` column `m_flow` = the last activation side on monthly bars; optional `_scan` gate.
  - **Params:** `monthly_flow_gate=False`.
  - **Test:** a monthly up candle broken low sets m_flow=-1.

### 149. A12-disp-gate
- A12 | shortened | general
- **Rule:** h = |open-close| of the (blended) OB. The retrace entry at the OB open is armed only once max(high since OB) - OB open >= 2h (strict 3h).
- **Sources:** cc04_003 ~27:56/~29:03.
- **Quote:** "at least two to three times that as a rally away".
- **Already covered:** `rule_coverage.md` A12 lists `ob_disp_mult` with the same content. No new build spec.

### 150. A12-stepping-ob
- A12 | missing_rule | general | judgment
- **Rule:** when the M/W draw is above price, start from the HTF swing low (buy side of the curve).
  - **Store:** for each daily/4h down-close candle followed by a higher high (cc04_003 also wants >= 2-3x displacement), store its high and open.
  - **Active OB:** the newest/highest; keep older ones as fallbacks.
  - **Entry:** its open (cc04_003) or its high (cc05_003); small wick probes allowed; a close below its open/MT invalidates.
  - **cc05_016:** uses a buy stop at the open.
  - **Before the low (sell side of the curve):** do not buy down candles. Mirror.
- **Sources:** cc04_003 ~28:30/~29:53, cc05_003 ~1:06:00, cc05_016 ~1:36, cc06_004 ~18:06.
- **Quote:** "every down candle promotes new buying opportunity".
- **Conflicts:** A12 (012) original/highest; open vs high.
- **[our interpretation]:** the drop rule for far fallbacks.
- **Fix:** add to A12/B10.
- **Build (BH):**
  - **Where:** `htf.table` keeps a ladder of D/4h bullish OB levels when `mwd` (B10) is bullish; `_scan` treats the active one as an HTF entry array.
  - **Params:** `ob_ladder=False`, `ob_ladder_px="open"` ("high").
  - **Test:** after a new HH, the active OB moves up.

### 151. A12-mt-grading
- A12 | shortened | general | judgment
- **Rule:** tag OB retests on the body MT:
  - A = retest low >= MT;
  - B = slightly below MT with no body close below;
  - invalid = a body close below MT, or the tolerance exceeded.
- **Sources:** cc04_003 ~9:59/~10:35/~24:21.
- **Quote:** "the best order blocks will not see price trade down below the midway point".
- **Conflicts:** none.
- **[our interpretation]:** tolerance <= 10% of body height.
- **Fix:** A12: add the grade.
- **Build (ESS):**
  - **Where:** a Trade tag `ob_grade` at fill; risk_mult per grade.
  - **Params:** `ob_grade_mult=(1.0, 1.0)`.
  - **Test:** a 5% stab below MT is tagged B.

### 152. B18-smt-accum-distrib
- B18 | shortened | general
- **Rule:** before treating a break of an old high (low) as strength, check the correlated asset over the same window.
  - If it fails to confirm, label the breakout false (an M12 turtle-soup candidate): the breaking asset = distribution, the refusing asset = accumulation.
  - For the index trio, apply directly.
- **Sources:** cc03_005 ~10:20.
- **Quote:** "otherwise it would have been permitted to go lower".
- **Conflicts:** none.
- **Fix:** B18: add the false-breakout reading.
- **Build (SM):**
  - **Where:** turtle-soup core. Require or tag SMT at the swept level (`_smt` helper).
  - **Params:** `ts_need_smt=False`.
  - **Test:** an ES high broken while NQ fails tags the sweep "smt" and arms the turtle.

### 153. L14-dealing-range-redefine
- L14 | missing_rule | general
- **Rule:** ERL/IRL is relative to the range referenced (cc04_002). Redefine the current range per TF after each new swing.
  - **Our mechanics:** on a break of range_high, range_high = the new swing high and range_low = the swing low that started the leg.
  - ERL = pools beyond the extremes; IRL = FVGs/voids/OBs inside. Enter on IRL, target ERL of the same range. The cross-TF example is ours.
- **Sources:** cc04_002 ~5:59.
- **Quote:** "from this low to this high its external range liquidity".
- **Conflicts:** none.
- **Fix:** L14: state the reference range.
- **Build (TP):**
  - **Where:** `irl_entries`/`erl_range_swings` (coverage L14b) use a rolling `current_range` updated in `run_day`.
  - **Params:** `erl_range_update="swing"`.
  - **Test:** after a new high, ERL targets move to the new range.

### 154. A6-voids-fill-holding-range
- A6 | missing_condition | general | judgment
- **Rule:** if the current range is not expected to break (consolidating, no displacement beyond its extremes), treat unfilled voids/FVGs inside it as likely fill targets.
  - For a long with a void/FVG between entry and stop or just below the stop: put the stop below the gap (E6) or skip. Mirror.
- **Sources:** cc04_002 ~1:41.
- **Quote:** "liquidity voids will fill in and this is associated with gap risk".
- **Conflicts:** none.
- **[our interpretation]:** "holding" = `delivery_state`==CONSOLIDATION; the stop/skip action.
- **Fix:** add to A6.
- **Build (ESS):**
  - **Where:** `stop_all_ineff` (coverage E6d) gated by the range state.
  - **Params:** `gap_risk="off"` ("widen" / "skip").
  - **Test:** a void under the stop in a consolidation widens the stop.

### 155. A17-rb-trend-context
- A17 | missing_condition | general | judgment
- **Rule:** take a bearish RB ideally when the HTF bias is bearish, preferably with the swing high at HTF resistance (bearish OB, old high). Otherwise grade it lower. Mirror.
- **Sources:** cc04_006 ~5:14.
- **Quote:** "the ideal setups are found in major to intermediate term downtrends".
- **Conflicts:** none.
- **[our interpretation]:** grade lower = half size.
- **Fix:** A17: add the context.
- **Build (ESS):**
  - **Where:** RB entries (`rej_targets` / item 47) take a risk_mult.
  - **Params:** `rb_ctx_mult=1.0` (applied when not at HTF resistance with bias).
  - **Test:** a counter-bias RB gets 0.5 when set.

### 156. M4-failure-swing-no-new-extreme
- M4 | missing_condition | general
- **Rule (bearish failure swing):** H1 reaches, touches or trades through key resistance K; price drops to swing low L; it retraces to H2 < H1 (no new higher high); trade the break below L or its retest.
  - K's position relative to H1/H2 is irrelevant. Bullish mirror. It is the fallback when the preferred breaker (a run above H1) does not happen.
- **Sources:** cc05_005 ~19:40.
- **Quote:** "it can't make another pass through".
- **Conflicts:** none.
- **Fix:** M4/A15: drop "fails to reach the level".
- **Build (LD):**
  - **Where:** `levels.failure_swing(highs, lows, level, max_above, i)` drops the H2 < K requirement under a switch.
  - **Params:** `fs_def="m4"` ("no_new_extreme").
  - **Test:** an H2 above K but below H1 counts under no_new_extreme.

### 157. A18-traded-through-ok
- A18 | missing_condition | general
- **Rule:** reclaimed-OB candidates on the buy (sell) side of the curve stay valid even when price trades or closes through them before the curve extreme.
  - The A12 MT invalidation does not apply to them. They become entry levels only after the extreme forms.
- **Sources:** cc04_007 ~9:45.
- **Quote:** "it trades through it but we see a climax high".
- **Conflicts:** A12 MT invalidation.
- **Fix:** A18: add the exemption.
- **Build (SM):**
  - **Where:** `levels.reclaimed_obs`. Do not filter candidates by MT closes before ext_i.
  - **Params:** `reclaimed_keep_overrun=False` (check what the current code does first; if it already keeps them, this is a test only).
  - **Test:** a candidate closed through before the high is still returned.

### 158. L8-vacuum-block-levels
- L8 | shortened | index | judgment
- **Rule:** vacuum block = the gap between the last close before an event/session open and the first open after. VB_low/VB_high/VB_MT.
  - Expect price to try to close it. A partial fill stops at the bullish OB just before the gap (deeper: the last up candle before the gap).
- **Sources:** cc04_009 ~4:48/~6:24.
- **Quote:** "treat it just like any other candle".
- **Already covered:** `rule_coverage.md` L8 (`levels.vacuum_block`, near/MT/far, built; `vacuum_blocks`). No new build spec. Only the OB stop levels for a partial fill are extra; they belong to item 93's breakaway state.

### 159. new-divergence-types
- new | missing_rule | general
- **Rule:**
  - **Type 1 (classic):** price higher high, momentum lower high. The retail reversal signal, often trapped: expect a stop run into an OB, then continuation the other way.
  - **Type 2 (hidden):** price higher low, momentum lower low = continuation above the recent high.
  - No OB/OS reading needed. Confirmation only, never a trigger. Mirrors.
- **Sources:** cc04_013 ~2:41/~12:15/~13:52.
- **Quote:** "that's type 2 hidden divergence bullish".
- **Conflicts:** none.
- **Fix:** add a new rule.
- **Build (SM):**
  - **Where:** `levels.stoch_divergence(h,l,c,k=14)` -> tag on Trade (type1/type2); no gating by default.
  - **Params:** `div_tag=False`.
  - **Test:** a fixture yields a type2 tag at a higher low.

### 160. new-buy-program
- new | missing_rule | general | judgment
- **Rule:** buy program (any TF, daily primary) = consecutive up sessions reaching for buy-side above recent highs; a few up days qualify; it can last months. Sell program mirror. ICT pairs it with accumulation evidence.
- **Sources:** cc05_001 ~9:01.
- **Quote:** "a series of successive days sessions that are consecutive".
- **Conflicts:** none.
- **[our interpretation]:** >= 3 consecutive up closes with a higher high.
- **Fix:** add a definition (B20 uses the term).
- **Build (BH):**
  - **Where:** `htf.table` column `program` (+1/-1/0).
  - **Params:** `program_tag=False`, `program_days=3`.
  - **Test:** 3 up days with HHs set program=+1.

### 161. B21-data-range-fv-eq
- B21 | shortened | general | judgment
- **Rule:** for each window (20/40/60 trading days):
  - liquidity = the window high/low;
  - fair value = gaps (FVGs/voids) formed inside the window;
  - equilibrium = 50% of each consolidation inside the window, not of the whole window.
  - **Range ("Z") day:** price hangs around one of these consolidation EQs with no driver. Expect sideways until high-impact news; no expansion trades.
- **Sources:** cc05_003 ~1:18:00.
- **Quote:** "that's where your equilibrium price points are".
- **Conflicts:** none.
- **[our interpretation]:** consolidation detection on daily bars; "no driver" for index = no SMT/no news.
- **Fix:** B21: add gaps and consolidation EQs.
- **Build (LD):**
  - **Where:** `ipda_pools` (built) gains `ipda_fv` (daily gaps per window) and `ipda_consol_eq`; `ipda_eq_day` tests against the consolidation EQs.
  - **Params:** `ipda_fv=False`, `ipda_consol_eq=False`.
  - **Test:** a 60-day fixture with one 6-day box yields its EQ.

### 162. A22-matrix-range-tf
- A22 | missing_condition | general | judgment
- **Rule:** build the matrix on monthly and weekly charts (same hierarchy), with the daily as the lowest TF.
  - Dealing range = the most recent trading range from an old high to an old low on that TF; EQ = midpoint; premium arrays above, discount below, in A22 order.
  - Recompute on a new range (ours).
- **Sources:** cc05_014 ~6:31/~17:49.
- **Quote:** "nothing below a daily chart".
- **Conflicts:** none.
- **[our interpretation]:** the recompute trigger.
- **Fix:** A22: state the range and the TFs.
- **Build (BH):**
  - **Where:** `htf.table` per-TF matrix (`matrix_targets`, coverage A22) on W and M bars.
  - **Params:** `matrix_tfs=("D",)`; test ("M","W","D").
  - **Test:** a weekly EQ column exists and splits arrays.

### 163. A22-breaker-precedence
- A22 | missing_condition | general | judgment
- **Rule:** scan PD arrays outward toward the draw.
  - **No same-side breaker between price and the nearest OB:** expect the void and FVG on the way to fill into that OB.
  - **Same-side breaker in the path:** expect a stop there; arrays beyond stay intact.
  - **Breaker overtaken:** re-enable the void, FVG and OB beyond in order.
- **Sources:** cc05_014 ~28:18/~28:46.
- **Quote:** "without the breaker you would expect the void to be filled".
- **Conflicts:** none.
- **[our interpretation]:** overtake = a body close through the breaker zone; same-side only.
- **Fix:** A22: add the no-breaker and overtake cases.
- **Build (TP):**
  - **Where:** `breaker_first` (coverage A22) in `_targets` gains the overtake re-enable.
  - **Params:** `breaker_overtake=False`.
  - **Test:** a body close through the breaker restores the far rungs.

### 164. A22-rejection-block-fallback
- A22 | missing_condition | general
- **Rule (premium side):** after the mitigation block, breaker, void and FVG, look for the bearish OB.
  - If there is none (a top made of long-wick candles), use the rejection block: level = the highest body of the swing high. Expect price to trade above it into the wicks; the final reference is the old high. Discount mirror.
- **Sources:** cc05_014 ~22:54.
- **Quote:** "you would expect that to be ran out".
- **Conflicts:** none.
- **Fix:** A22: the RB is the no-OB fallback, and its body level gets run.
- **Build (TP):**
  - **Where:** `matrix_targets` in `_targets`. Use the RB body level only when no OB exists in that range; the next rung = the old high.
  - **Params:** `rb_fallback=False`.
  - **Test:** with no OB, the ladder includes the RB body then the high.

### 165. A22-matrix-anchor-market-price
- A22 | wrong | general
- **Rule:** reference price P = current market price (weekly prep: Friday's close); cc05_014's "outward from EQ" is the case P = EQ.
  - **Premium list:** for M/W/D/4h, the unused arrays above P in hierarchy order: bearish mitigation block, breaker, void, FVG, bearish OB, rejection block, old highs/lows above P. Discount mirror.
  - **Path:** price seeks the nearest existing array first; missing types are skipped; exhausted arrays are skipped.
- **Sources:** cc06_003 ~3:45, cc07_004 ~2:25/~8:45.
- **Quote:** "moving from the market price up in the order that's listed".
- **Conflicts:** A22 EQ anchor.
- **Fix:** A22: anchor at the market price.
- **Build (TP):**
  - **Where:** `matrix_targets`.
  - **Params:** `matrix_anchor="eq"` ("price").
  - **Test:** with price above EQ, the premium list starts at the first array above price.

### 166. A22-old-level-polarity
- A22 | missing_condition | general
- **Rule:** an old high/low counts as premium if above price and discount if below, whatever its original type.
  - **Old high broken:** after a close above old high H, a later retrace to H = a bullish discount array (also the nearest short target below).
  - **Old low broken:** after a close below old low L, a rally to L = a bearish premium array.
  - These rank in the outermost class.
- **Sources:** cc05_014 ~23:22, cc06_003 ~3:45, cc06_006 ~21:50, cc07_006 ~13:26, cc07_008 ~23:08.
- **Quote:** "it could be a old low or an old High once broken now turning support".
- **Conflicts:** none.
- **Fix:** A22: polarity by position.
- **Build (TP):**
  - **Where:** `_targets` / matrix. Old highs below price become discount arrays and short targets (the current code treats PDH only as buy-side).
  - **Params:** `level_polarity=False`.
  - **Test:** a short's ladder includes a broken old high below.

### 167. A5-twice-traded-not-fvg
- A5 | missing_rule | general
- **Rule:** A12 anchor addition: when an OB's wick zone has been traded through by another candle ("closed in"), it is not a gap; use the OB open.
  - Only one-sided zones count as gaps. A5's strict wick-based FVG already excludes them.
- **Sources:** cc05_015 ~11:38.
- **Quote:** "this whole little area in here wouldn't be viewed as a gap".
- **Conflicts:** none.
- **Fix:** A12: same as item 90.
- **Build (LD):** the same switch as item 90 (`ob_anchor_rule="gap_presence"`). Counted with item 90, not separately.

### 168. A21-htf-range-anchored-at-arrays
- A21 | missing_rule | general | judgment
- **Rule:** HTF (monthly/weekly) dealing range:
  - **Low:** the reference price of the bullish point-of-origin array (the last down-close candle(s) before the displacement that left an FVG; the OB high or planned entry, body-based).
  - **High:** the nearest monthly premium array / objective (e.g. a bearish breaker or the next swing high).
  - **Levels:** EQ = midpoint, quadrants 25/75.
  - **Use:** for premium/discount and all distance-based management thresholds, on W/D/4h too. Weekly premium arrays inside are intermediate targets. Bearish mirror.
- **Sources:** cc05_015 ~9:05, cc06_008 ~24:56, cc07_001 ~38:06, cc06_004 ~34:43.
- **Quote:** "that's not the monthly range we're trading in".
- **Conflicts:** none.
- **[our interpretation]:** the anchor array choice.
- **Fix:** add to A21.
- **Build (BH):**
  - **Where:** `htf.table` columns `htf_rng_lo` / `htf_rng_hi` from W/M arrays (origin OB to the opposing breaker/high).
  - **Params:** `htf_range_arrays=False`.
  - **Test:** the range low equals the origin OB high, not the wick low.

### 169. A21-swing-no-new-longs-80-90
- A21 | missing_rule | general | judgment
- **Rule:** on the swing dealing range (0/0.2/0.3/0.5/0.8/0.9/1): never initiate longs at >= 0.8; never initiate shorts at <= 0.3. Apply the same range on W, D and 4h.
- **Sources:** cc06_004 ~34:43.
- **Quote:** "I don't like to see any new longs in these levels".
- **Conflicts:** cc05_017 / cc06_003 above-EQ buying (item 170).
- **[our interpretation]:** which range = item 168.
- **Fix:** add to A21.
- **Build (BH):**
  - **Where:** a `_scan` gate on the `htf_rng` position.
  - **Params:** `swing_extreme_block=False` (0.8 / 0.3).
  - **Test:** a long at 0.85 is blocked.

### 170. A21-swing-discount-exception
- A21 | unlisted_contradiction | general | judgment
- **Rule:** switch `swing_ignore_eq`. With a monthly/weekly draw intact, do not block longs above 50% of the HTF range.
  - **Discount condition:** (a) entry below the close of the down-close daily candle, or (b) any bullish array inside [point-of-origin low, intermediate-term high before the retracement].
  - Prefer entries below EQ. Keep the 0.8 cap. Mirror.
- **Sources:** cc05_017 ~10:19, cc06_003 ~17:18.
- **Quote:** "even above the equilibrium price point there was many opportunities".
- **Conflicts:** A21 buy-below-EQ only; cc06_004.
- **[our interpretation]:** combining with the 0.8 cap.
- **Fix:** A21: list the exception.
- **Build (BH):**
  - **Where:** `leg_pd` / `pd_zone` gates.
  - **Params:** `swing_ignore_eq=False`.
  - **Test:** with M/W bullish, a long above the daily EQ at a daily OB passes.

### 171. A21-ob-strength-by-location
- new | missing_rule | general | judgment
- **Rule:** within the swing dealing range:
  - a bullish OB in premium -> only a small bounce, no new HH (skip, or target the near level only);
  - a bullish OB in discount -> expect expansion;
  - bearish OBs in discount are expected to fail.
  - In a bull sequential, up-candle OBs should break and down candles should hold. Mirror.
- **Sources:** cc06_004 ~35:33.
- **Quote:** "bullish order blocks are not going to be as favorable".
- **Conflicts:** none.
- **[our interpretation]:** the "near target only" action.
- **Fix:** add a new rule.
- **Build (TP):**
  - **Where:** `_targets`. For OB entries in the wrong half of the HTF range, cap the ladder at the first rung.
  - **Params:** `ob_location_cap=False`.
  - **Test:** a premium bullish OB trade has a one-rung ladder.

### 172. A12-htf-ob-trade-through-to-mt
- A12 | missing_rule | general | judgment
- **Rule:** for monthly/weekly bearish OBs the reaction zone runs from the OB low through the open up to the MT. A trade through the open is not a failure.
  - It fails only on a body close above the MT on that TF. Expect stop-outs of LTF entries inside a layered M/W zone; take the next setup. HTF levels can be retraded. Mirror.
- **Sources:** cc06_005 ~30:28.
- **Quote:** "we could be trading into the mean threshold".
- **Conflicts:** none.
- **[our interpretation]:** the TF-close test.
- **Fix:** add to A12.
- **Build (BH):**
  - **Where:** `htf._arrays` W/M OB zones extended to the MT; death only on a same-TF close beyond the MT.
  - **Params:** `htf_ob_to_mt=False`.
  - **Test:** a weekly OB stays alive after a daily close through its open.

### 173. new-layered-orders-before-level
- new | missing_rule | general | judgment
- **Rule:** when testing whether price has reached an HTF level (D/W/M array or round number), count an LTF OB/reversal that forms within a small tolerance short of the level as a hit.
  - FX ~10 pips; the index tolerance is to be tested.
- **Sources:** cc06_006 ~10:17.
- **Quote:** "they layer their orders just above or just below these levels".
- **Conflicts:** none.
- **[our interpretation]:** the index tolerance (test 2 / 4 / 6 pts or 0.1 x ADR5).
- **Fix:** add a new rule.
- **Build (BH):**
  - **Where:** `htf.table` react test and `_htf_tag` tolerance.
  - **Params:** `htf_reach_tol_pts=0.0`.
  - **Test:** a reversal 3 pts short counts at 4.

### 174. A17-index-or-rejection-block
- A17 | unlisted_contradiction | index | judgment
- **Rule:**
  - **Bullish OR RB:** among the down-close candles inside the 09:30-10:30 OR, the lowest close. Level = its close; zone down to the OR60 low. On a later-morning return, go long if the bar's low holds above the OR60 low; invalid below.
  - **Bearish (NQ example):** the LAST up-close candle inside the OR (just below a pre-OR bearish OB); level = its close; invalid above the OR60 high.
- **Sources:** cc10_010 ~9:03.
- **Quote:** "The lowest close down close candle".
- **Conflicts:** A17 long-wick swing.
- **[our interpretation]:** after 10:30; the "highest-closing" bearish alternative.
- **Fix:** A17: list the OR variant.
- **Build (SM):**
  - **Where:** a new branch beside the `turtle_soup="or60"` variant in `_scan`, using the OR60 bars.
  - **Params:** `or_rb=False`, `or_rb_from=630` (10:30 in minutes from midnight per existing convention).
  - **Test:** a return to the lowest-close level above the OR low fills a long.

### 175. new-volume-retest-confirmation
- new | missing_rule | needs_unavailable_data
- **Rule:** V0 = the volume of the bar that set the OR60 low (high). When a later bar retests that extreme or the OR RB and V1 < V0 with the extreme held, the retest is weak: allow the long (short).
  - V1 >= V0 = a real break (inference). Needs volume data.
- **Sources:** cc10_010 ~9:50.
- **Quote:** "it should be seen with higher volume".
- **Conflicts:** none.
- **Fix:** add a new rule.
- **Build:** none (CFD/SPY volume is not usable as futures volume; needs futures volume).

### 176. A21-60day-body-range
- A21 | unlisted_contradiction | general | judgment
- **Rule:** premium/discount for daily context: over the last 60 trading days, RangeHigh/RangeLow and EQ60.
  - cc07_004 uses high/low; cc07_005 (OSOK) uses bodies.
  - Premium/discount = price vs EQ60. The A22 list is built from the 20-day window around market price.
  - The current 20-day context conflicts; make it a decision.
- **Sources:** cc07_004 ~7:00, cc07_005 ~4:16.
- **Quote:** "our total 60-day trading range splitting that market in half".
- **Conflicts:** A21 20-day vs 60-day.
- **[our interpretation]:** rolling, ending yesterday.
- **Fix:** list the decision.
- **Build (BH):**
  - **Where:** `pd_day_range` (coverage A21) / `pd_bodies`.
  - **Params:** `pd_days=20` (test 60), `pd_bodies` (listed).
  - **Test:** EQ60 differs from EQ20 on a trending fixture.

### 177. A21-quadrant-grid
- A21 | missing_rule | general
- **Rule:** levels at k/8 of [RangeLow, RangeHigh], k = 0..8.
  - 4/8 = the overall EQ; 2/8 and 6/8 bound the quadrants; the odd k/8 lines are the quadrant EQs. Each quadrant has its own premium/discount.
  - Tag bars with (half, quadrant, eighth). A long in a quadrant's discount is allowed inside the overall premium, with first profit at a 4h/1h premium array (cc07_005).
- **Sources:** cc07_005 ~12:10.
- **Quote:** "we divide it in half then we divide those halves into halves".
- **Conflicts:** none.
- **Fix:** add to A21.
- **Build (BH):**
  - **Where:** `htf.table` columns grid_k from the 60-day range; tags on Trade.
  - **Params:** `pd_grid=False`.
  - **Test:** a price at 30% of the range has quadrant=2 (1-based) and the discount half.

### 178. new-pd-array-at-quadrant-level
- new | missing_rule | general | judgment
- **Rule (OSOK, 4h):** tag a long PD array `grade_confluence` when it forms at or near a graded-range divider/quadrant level in discount.
  - Expect a move toward the opposing premium level/array. Mirror.
- **Sources:** cc07_006 ~6:03.
- **Quote:** "you'll be able to see high probability movement away from that level".
- **Conflicts:** none.
- **[our interpretation]:** the tolerance (10% of grade spacing).
- **Fix:** add a new rule.
- **Build (BH):**
  - **Where:** a Zone tag in `htf._arrays` using the item-177 grid.
  - **Params:** `grade_confluence=False`.
  - **Test:** a 4h OB 1% from a k/8 line is tagged.

### 179. A21-range-position-needs-array
- A21 | missing_condition | general
- **Rule:** a long candidate needs both:
  - (a) price in a discount band;
  - (b) price trading into a bullish PD array in that band.
  - First profit at a 4h/1h premium array. Range position alone = no signal. Mirror.
- **Sources:** cc07_005 ~14:52.
- **Quote:** "by itself it doesn't mean anything".
- **Conflicts:** none.
- **Fix:** A21: add the array-touch condition.
- **Build (BH):**
  - **Where:** used with the item 177/176 gates. When those gates are on, require an `htf_entry_arrays` touch in the same band.
  - **Params:** `pd_need_array=False`.
  - **Test:** a discount entry with no array touch is blocked.

### 180. A21-range-excursion-tolerance
- A21 | missing_condition | general | judgment
- **Rule:** while the market consolidates, keep the 60-day range and its grid valid when price pokes slightly beyond the range extremes and returns inside.
  - The range is broken only when a daily body closes beyond the extreme and the next day does not close back inside. The "poke = high-probability fade" claim is unsourced and dropped.
- **Sources:** cc07_005 ~15:37.
- **Quote:** "make a slightly higher high and return back inside of the range".
- **Conflicts:** none.
- **[our interpretation]:** the break test.
- **Fix:** add to A21.
- **Build (BH):**
  - **Where:** the item-176 range builder.
  - **Params:** `pd_range_break="two_close"`.
  - **Test:** a one-day poke does not reset the range.

### 181. new-monthly-failed-consolidation-break
- new | missing_rule | general
- **Rule:** if price runs above a range's equal highs, returns inside and trades through the range midpoint, expect continuation to the range low.
  - Minimum target = the lowest bodies of the range (the wick low may not be reached). Mirror. Shown on DXY monthly.
- **Sources:** cc12_001 ~45:46.
- **Quote:** "comes back deeper and goes through the midpoint of that".
- **Conflicts:** none.
- **Fix:** add a new rule.
- **Build (BH):**
  - **Where:** `htf.table` bias column `failed_break` on D/W/M consolidations; target = the body low.
  - **Params:** `failed_consol_break=False`.
  - **Test:** a daily fixture flags bearish with the target at the body low.

### 182. A21-nested-ranges
- A21 | missing_rule | general
- **Rule:** if price drops into a discount PD array of the smaller (daily swing) range while staying in the larger range's premium, and does not continue lower, bias = bullish.
  - Targets = the premium arrays above. Confirm with respected bullish OBs. Mirror.
- **Sources:** cc07_007 ~16:59.
- **Quote:** "a willingness to not ... move out of a premium Market".
- **Conflicts:** none.
- **[our interpretation]:** invalidation on a daily close below the array MT.
- **Fix:** add to A21.
- **Build (BH):**
  - **Where:** `htf.table` bias rule using the item-176 (large) and A21 (daily swing) ranges.
  - **Params:** `nested_pd_bias=False`.
  - **Test:** a fixture sets bias +1.

### 183. A21-htf-eq-not-violated
- A21 | missing_condition | general | judgment
- **Rule:** for a bullish HTF dealing range whose refined discount arrays sit above EQ, price may trade down to EQ, but violating it invalidates the long idea for that retracement. Mirror. Single FX example.
- **Sources:** cc12_002 ~26:38.
- **Quote:** "we just don't want to see it violated".
- **Conflicts:** none.
- **[our interpretation]:** violated = a weekly body close below EQ.
- **Fix:** add to A21.
- **Build (BH):**
  - **Where:** `htf.table` bias flip on a weekly close below the `htf_rng` EQ (item 168).
  - **Params:** `htf_eq_invalid=False`.
  - **Test:** a weekly close below EQ sets the bias neutral.

### 184. B5-htf-lookback-9-18-months
- B5 | missing_rule | general | judgment
- **Rule:** for a swing candidate, look back 9-18 monthly candles (may deviate). Choose the range, split it at EQ, and note only the obvious arrays.
  - Identify PD arrays on M, W, D and 4h and transpose them all to the 4h chart. Combine with the 20/40/60-day IPDA ranges.
  - Bullish = longs at M/W/D discount arrays; bearish = shorts at premium arrays.
- **Sources:** cc06_008 ~12:21, cc12_001 ~32:31.
- **Quote:** "you note the 9 to 18mth history of price action".
- **Conflicts:** none.
- **[our interpretation]:** "the most recent significant high and low".
- **Fix:** B5: add the swing mapping.
- **Build (BH):**
  - **Where:** data loading must give >= 18 months of history to `htf.table`; M/W arrays (item 113).
  - **Params:** `htf_history_months=0` (test 18).
  - **Test:** monthly arrays exist from 18 months back.

### 185. A13-daily-breaker-regime
- A13 | missing_rule | general | judgment
- **Rule:** on every TF, locate breakers first; daily breakers carry the most weight.
  - **Regime:** trade in the direction of the most recent daily breaker until the opposite daily breaker forms. ICT calls this a "training wheels" filter.
  - **cc12_004:** the breaker retest is the primary/pyramid entry; do not wait for a deeper OTE.
- **Sources:** cc12_003 ~22:54, cc12_004 ~50:12.
- **Quote:** "trade in between those two price points".
- **Conflicts:** none.
- **[our interpretation]:** optional regime switch, not a ban.
- **Fix:** add to A13/B-section.
- **Build (BH):**
  - **Where:** `htf.table` column `brk_regime` from daily `levels.breakers`; `want` gate.
  - **Params:** `breaker_regime=False`.
  - **Test:** after a daily bearish breaker, longs are blocked until a bullish one forms.

### 186. B5-execution-tf-15m-min
- B5 | unlisted_contradiction | general | judgment
- **Rule [CC]:** after the 4h read, drop to a TF that shows FVGs/OBs/breakers (60m is often muddy). Setups confirm on 15m minimum, refined on 5m; ICT does not like 1m.
  - This conflicts with the 2023 1m execution; list it in section 3. Test it as a switch.
- **Sources:** cc12_004 ~5:00.
- **Quote:** "15 minute minimum the best is to get it down until five minute".
- **Conflicts:** 2023 1m chain (Ep 02, B5).
- **[our interpretation]:** the switch semantics.
- **Fix:** add to section 3 decisions.
- **Build (ESS):**
  - **Where:** `entry_tf` (exists) and the `_scan` FVG source TF.
  - **Params:** `entry_fvg_min_tf=1` (test 5, 15).
  - **Test:** at 15, only 15m FVGs arm entries.

### 187. A22-htf-definition-nested-arrays
- A22 | unlisted_contradiction | index | judgment
- **Rule:** nested array = a 15/60m PD array overlapping a 4h or daily array of the same polarity.
  - **PM reversal:** if the AM move stopped at a nested (HTF) array, expect the PM to fade it. If it stopped at an un-nested 15/60m array, expect continuation.
  - **HTF set per filter:** reversal {4h, D, W+}; consolidation profiles {1h, 4h+}.
- **Sources:** cc10_013 ~8:17/~13:44, cc10_014 ~11:08.
- **Quote:** "nested ideas of Premium array would be our Catalyst".
- **Conflicts:** cc10_013 internal.
- **[our interpretation]:** overlap = any price overlap.
- **Fix:** A22/T13: define the HTF set per filter.
- **Build (SM):**
  - **Where:** `pm_reversal` (M6) gate. Check whether the AM extreme touched a nested array (`htf._arrays` 15/60 vs 240/D).
  - **Params:** `pm_rev_nested=False`.
  - **Test:** the AM high at an un-nested 60m FVG blocks the PM fade.

### 188. new-consolidation-exit-direction
- new | missing_rule | general
- **Rule:** a lower-TF consolidation most often exits in the direction of daily/4h order flow.
  - A move out of the range against that flow is a stop run to fade: expect a return through the EQ to the opposite extreme and just beyond. Use the HTF-side pool as the draw.
- **Sources:** cc09_004 ~5:07.
- **Quote:** "that's going to be the direction of the move outside the consolidation".
- **Conflicts:** none.
- **Fix:** add a new rule.
- **Build (SM):**
  - **Where:** with `delivery_state` CONSOLIDATION (item 125), a break against `want` arms a turtle-style fade (turtle-soup core) targeting the opposite extreme.
  - **Params:** `consol_fade=False`.
  - **Test:** a break below a range with bullish bias arms a long targeting the range high.

### 189. new-price-engine-models
- new | missing_rule | general
- **Rule (bullish HTF IOF):**
  - **OA:** a sweep of a key intraday old low, then a long to a short-term premium array.
  - **RA:** often after a sell-stop raid, a retrace into a discount fair-value array (typically OTE); long there.
  - **Bearish:** OD (buy-stop run, then a short to a discount array) and RD (retrace up into a premium array, short).
  - All are scalps in the London/NY kill zones. Tag `setup_model` in {OA, RA, OD, RD}.
- **Sources:** cc09_006 ~0:54, cc09_007 ~1:27/~2:23.
- **Quote:** "re-accumulate fair value in retracements lower at discount arrays".
- **Conflicts:** none.
- **Fix:** add a new rule (M0 family).
- **Build (SM):**
  - **Where:** a Trade tag at arming in `_scan`. Sweep-triggered = OA/OD; retrace-into-array after a prior sweep = RA/RD.
  - **Params:** none (tag always on).
  - **Test:** a sweep-MSS-FVG trade is tagged OA.

### 190. A12-mt-worked-both-sides
- A12 | missing_condition | general
- **Rule:** track MT crosses for each OB after formation. Once price has traded on both sides of the MT, drop it as a level and keep the open/high/low edges. Single DXY example.
- **Sources:** cc09_008 ~14:37.
- **Quote:** "it's already worked on both sides of that".
- **Conflicts:** none.
- **Fix:** add to A12.
- **Build (ESS):**
  - **Where:** OB zone state (`ob_mt_dead`) in `_scan` / `run_day`; MT stops fall back to the OB low.
  - **Params:** `ob_mt_two_sided=False`.
  - **Test:** after crosses both ways, the MT stop moves to the OB low.

### 191. A5-htf-fvg-last-upclose-anchor
- A5 | missing_condition | general | judgment
- **Rule:** daily bearish FVG: lower edge = the high of the candle after the gap; upper reference = the low of the last up-close candle before the down move (walk back past a down-close c1). Mirror.
  - Single DXY example: an optional zone-extension switch.
- **Sources:** cc09_008 ~12:27.
- **Quote:** "we want to see the last up close".
- **Conflicts:** none.
- **[our interpretation]:** generalising from one example.
- **Fix:** A5 note.
- **Build (BH):**
  - **Where:** `htf._arrays` daily FVG edge.
  - **Params:** `dfvg_upclose_anchor=False`.
  - **Test:** a down-close c1 extends the top to the prior up-close low.

### 192. A12-4h-ob-mt-invalidation-flip
- A12 | missing_condition | general
- **Rule:** with daily IOF bullish, a trade above the MT of the latest 4h bearish OB sets the 4h near-term bias to not-bearish and cancels 4h shorts.
  - Once that whole up candle is traded through, the preceding down-close 4h candles become a potential bullish OB (open to high); look for longs on a return.
- **Sources:** cc09_008 ~26:44.
- **Quote:** "that would nullify any near-term four-hour bearishness".
- **Conflicts:** none.
- **Fix:** add to A12.
- **Build (BH):**
  - **Where:** `htf.table` 4h state column `h4_flip`; adds a 4h bullish OB array.
  - **Params:** `h4_ob_flip=False`.
  - **Test:** a 4h trade above the OB MT clears the short side.

### 193. B6-broken-highs-follow-through
- B6 | missing_condition | general
- **Rule:** daily bullish IOF = (a) down-close candles act as support with higher prices after, AND (b) broken swing highs are followed by higher highs. Bearish mirror.
- **Sources:** cc06_002 ~5:05.
- **Quote:** "are the swing highs breaking and seeing higher highs".
- **Conflicts:** none.
- **[our interpretation]:** a time limit on the follow-through.
- **Fix:** B6: add test (b).
- **Build (BH):**
  - **Where:** `iof` column (coverage B6) gains a follow-through test.
  - **Params:** `iof_follow=False`, `iof_follow_days=5`.
  - **Test:** a broken high with no new HH within 5 days drops the IOF to 0.

### 194. B9-judas-daily-limit-link
- B9 | missing_condition | fx_only | judgment
- **Rule:** with a bearish M/W draw and a daily up-close candle into a daily premium array, sell a limit above that close the next day. The fill often comes on the London Judas high and starts a multi-day move. Mirror. ICT says it applies to any pair or asset.
- **Sources:** cc05_017 ~6:05.
- **Quote:** "it'll open make the high in london and then sell off".
- **Conflicts:** none.
- **Fix:** note under B9/M17.
- **Build:** none (scope fx_only as verified; the daily-limit swing models are parked in M17).

### 195. B11-contraction-details
- B11 | shortened | general
- **Rule:** any TF: an inside bar on bodies (colour irrelevant) or the smallest range of 3/7 = contraction. Expect a large-range bar at t+1 or t+2 in the direction given by bias, especially at an S/R array. Context only.
- **Sources:** cc06_007 ~21:45.
- **Quote:** "we look at the body of the candle not the Wicks".
- **Already covered:** `rule_coverage.md` B11 (`inside_bar_body`, `nr3`/`nr7`, `nr_expansion`). The t+1/t+2 window and the any-TF scope go into that spec. No new build spec.

### 196. new-position-trade-grading-fib
- new | missing_rule | general | judgment
- **Rule (position trade):** fib across the weekly range being traded (the weekly swing extreme where the setup forms -> the opposing W/M objective); 0.5 = EQ.
  - **Trail:** before EQ, beyond the 40-trading-day extreme. Past the halfway point (also "three quarters", ambiguous), tighten to the 20-day extreme, updated daily.
  - Objective = the opposing weekly PD array.
- **Sources:** cc05_018 ~16:20.
- **Quote:** "to grade the scale of this entire range".
- **Conflicts:** 0.5 vs 0.75 switch point.
- **[our interpretation]:** near-edge fill; threshold choice.
- **Fix:** add a new rule (position trades).
- **Build (ME):**
  - **Where:** a new multi-day position engine; none exists (BT is intraday). Spec only: `pos_trail_40_20` in a future `swing.py`.
  - **Params:** `pos_switch_frac=0.5`.
  - **Test:** a daily-bar fixture trails at the 40-day low, then the 20-day low past 50%. Deferred until swing models (M17) are built.

### 197. new-swing-grades
- new | missing_rule | general
- **Rule:** origin O to terminus T:
  - grade 1 = the first retracement entry;
  - grade 2 = EQ;
  - grade 3 = O+0.75(T-O);
  - grade 4 = T (final profit).
  - Entries may be at grade 1, EQ or grade 3. At grade 3 expect no stop run, only a short pullback (smaller OB), still tradable.
- **Sources:** cc07_003 ~17:26.
- **Quote:** "the fourth is Terminus".
- **Conflicts:** none.
- **Fix:** add a new rule.
- **Build (TP):**
  - **Where:** a `levels.swing_grades(o_px, t_px)` helper; a Trade tag `grade` on HTF-range entries (item 168); the `_targets` final rung = T. Deferred to swing work, but the tag is usable intraday.
  - **Params:** `swing_grade_tag=False`.
  - **Test:** an entry at 0.75 is tagged grade 3.

### 198. new-swing-projection-fulcrum
- new | missing_rule | general
- **Rule (consolidation midweek rally, bullish):** fulcrum = the intra-week high made Tue (or Mon) where the retracement starts.
  - Anchor a fib from the fulcrum high down to the discount PD array hit Tue/Wed; project 1.27 and/or 1.68 or a 100% symmetrical swing.
  - Target only where it overlaps a premium PD array on a TF lower than the entry TF. Mirror.
- **Sources:** cc07_003 ~27:33.
- **Quote:** "the highest high at which the market starts to retrace from".
- **Conflicts:** none.
- **Fix:** define the fulcrum in L12.
- **Build (TP):**
  - **Where:** `sd_anchor` gains "fulcrum_week" (coverage L12 lists "fulcrum"); `_targets` projection with an overlap check.
  - **Params:** `sd_anchor="fulcrum_week"` option, `sd_need_array=False`.
  - **Test:** a Wed-entry fixture projects 1.27 from the Tue high to the Wed low.

### 199. M17-swing-trade-definition
- M17 | missing_rule | general
- **Rule:** swing trade = an intermediate-term directional trade of about 2 weeks or more (>= ~10 trading days); long only in bullish, short only in bearish M/W conditions. Excluding shorter setups is ours.
- **Sources:** cc06_001 ~0:50.
- **Quote:** "trade durations of two weeks or longer in time".
- **Conflicts:** none.
- **Fix:** M17: add the definition.
- **Build (BH):**
  - **Where:** a definition used by the future swing engine; for now a Params doc constant `swing_min_days=10` and an M/W side gate helper in `htf.py` (`mw_side()`).
  - **Test:** `mw_side` returns +1 only when M and W are both bullish. Deferred with M17.

### 200. new-intermediate-term-hl-fade
- new | missing_rule | general | judgment
- **Rule:** intermediate-term high/low = an old extreme older than yesterday (from earlier in the week up to ~2 months back).
  - **Fade a raid of it only with context:** a range-bound market, OR the move beyond reaches an HTF array, OR it comes after a long trend (profit taking), confirmed with the matrix.
  - Otherwise expect it to be traded through.
- **Sources:** cc09_005 ~23:14.
- **Quote:** "it's beyond just yesterday".
- **Conflicts:** none.
- **[our interpretation]:** the "long trend" test.
- **Fix:** add a new rule.
- **Build (SM):**
  - **Where:** turtle-soup core gate for pools of kind itl/ith / pw / pm / ipda.
  - **Params:** `ts_itl_context=False`; it requires `ts_need_htf` or a range-bound tag.
  - **Test:** a raid of a 30-day high in a trend day does not arm a fade.

### 201. new-monthly-structure-control
- new | missing_rule | general | judgment
- **Rule (monthly):**
  - higher highs then a lower high and a further lower high -> a long-term high is in control -> shorts;
  - low, higher low, higher low -> long-term low in control -> longs.
  - Confirm with SMT (FX: DXY; indices: SPX/NDX/DJI, our adaptation).
- **Sources:** cc12_001 ~23:53.
- **Quote:** "we've probably made an entering term or long-term High".
- **Conflicts:** none.
- **[our interpretation]:** the index SMT mapping.
- **Fix:** add a new rule.
- **Build (BH):**
  - **Where:** `htf.table` monthly column `m_ctrl` from `levels.swing_tiers` on monthly bars; optional `want` gate.
  - **Params:** `monthly_ctrl=False`.
  - **Test:** a monthly LH, LH sequence sets -1.

### 202. B18-smt-three-point-swing
- B18 | missing_condition | general | judgment
- **Rule:** alternate SMT on 3-point swings.
  - X prints low -> lower low -> higher low while the others print low -> lower low -> lower low = bullish SMT.
  - The window may need to extend past a short-term low that all traded through. Mirror. The index application is an adaptation.
- **Sources:** cc11_004 ~27:39.
- **Quote:** "you can sometimes have to trade through a short-term low".
- **Conflicts:** none.
- **[our interpretation]:** window extension rule.
- **Fix:** B18: add the alternate form.
- **Build (SM):**
  - **Where:** `_smt` helper gains a three-point mode.
  - **Params:** `smt_mode="pair"` ("three_point").
  - **Test:** the fixture with ES LL-LL and NQ LL-HL flags bullish SMT.

### 203. B18-interest-rate-smt
- B18 | missing_rule | bonds_only
- **Rule (bonds-only):** at a seasonal-window swing low, at least one of ZF/ZN/ZB makes a clear higher low while at least one other makes a lower low (an equal low is ambiguous: test both ways).
  - Required before any bond mega-trade long. Scan 2-hour charts covering ~1 month.
- **Sources:** cc11_004 ~12:23.
- **Quote:** "if they diverge and it just takes one".
- **Conflicts:** none.
- **Fix:** B18 bonds note.
- **Build:** none (bonds_only).

### 204. new-mega-trade-definition
- new | missing_rule | stocks
- **Rule:** mega trade = a position entered at a quarterly-shift (earnings-cycle) or seasonal low and held for months.
  - Stocks/calls: 6-9+ months.
  - Bonds: >= $10,000 per ZB contract (about 10 handles) for the annual move; less = "a really good trade".
- **Sources:** cc11_003 ~0:37, cc11_004 ~43:02.
- **Quote:** "six to nine months or more in the stock market".
- **Conflicts:** none.
- **Fix:** add a definition.
- **Build (BH, stocks):**
  - **Where:** a classifier only, for a future stock/position engine. In `htf.py` add `mega_tag(entry_day, exit_day, symbol)` returning "mega" when the hold >= 126 trading days (stocks) or the move >= 10 ZB handles (bonds tag only).
  - **Params:** `mega_min_days=126`.
  - **Test:** a 130-day hold is tagged mega.

### 205. M3-silver-bullet-name-collision
- M3 | missing_rule | stocks
- **Rule:** definition note. In cc11_003 (2017), "silver bullet" = a stock's relative-strength divergence (the stock makes a higher low while the averages make a lower low), screened for leadership and timed with an index SMT at a quarterly/earnings turn. Unrelated to the 2023 SB (M3/T6).
- **Sources:** cc11_003 ~25:16.
- **Quote:** "that's the Silver Bullets uh pattern for for trading stocks".
- **Conflicts:** M3 (2023) vs cc11_003.
- **Fix:** add a terminology note to M3.
- **Build:** documentation only (no stock model exists; `sb_model.py` is unaffected).

### 206. new-ny-close-1500
- new | missing_rule | general
- **Rule:** IPDA true day = 00:00-15:00 NY. "New York close" = the 15:00 true-day close (the close of the last bar ending at 15:00). It is distinct from the 16:00 session close.
- **Sources:** cc08_002 ~9:32.
- **Quote:** "when I say New York I'm referring to epta True day close".
- **Conflicts:** none.
- **Fix:** add the definition; T12 uses "true-day".
- **Build (DWC):**
  - **Where:** `day_context` adds `ny_close_1500` and `true_day_hl` (00:00-15:00) to DayCtx for rules that cite it.
  - **Params:** none (data fields).
  - **Test:** the field equals the 14:59 bar close.

### 207. T13-po3-small-open-wick
- T13 | shortened | general | judgment
- **Rule:** on the day after a daily discount-array reaction (bullish), expect the low only slightly below the open; a low below open - ADR5 is highly unlikely.
  - Expansion up, close slightly off the high. Bearish mirror (high above open + 20 pips + ADR5 highly unlikely).
  - Source uses the 0 GMT open; for indices test the midnight open.
- **Sources:** cc08_008 ~9:13.
- **Quote:** "very little below the opening price".
- **Conflicts:** none.
- **[our interpretation]:** the midnight open for indices.
- **Fix:** T13: add the size bound and the precondition.
- **Build (DWC):**
  - **Where:** a study tag in `day_context`: (open-low)/ADR5 on days after a daily discount reaction (`htf.table` react); optional `want` invalidation in `run_day` when the low < midnight open - ADR5.
  - **Params:** `po3_adr_invalid=False`.
  - **Test:** a fixture breaching open - ADR5 clears the long bias.

### 208. new-judas-size-cbdr
- new | missing_rule | fx_only
- **Rule (FX-only):** London Judas beyond the CBDR edge is usually 1-2 CBDR SDs, generally not beyond 3 (4 on high-impact news or a NY reversal profile).
  - Average about 33 pips, can be ~6. CBDR (14:00-20:00) ideally 20-30 pips, must be < 40; if > 40, flag "no float" and take London only if the Asian range is 20-30 pips.
- **Sources:** cc08_004 ~2:17, cc08_005 ~4:38.
- **Quote:** "they generally don't like to go beyond three".
- **Conflicts:** none.
- **Fix:** an FX note in L13.
- **Build:** none (fx_only).

### 209. L13-session-range-body-and-wick
- L13 | missing_condition | fx_only | judgment
- **Rule (FX-only):** for CBDR and Flout compute body ranges (first choice) and wick ranges and project SD ladders from both. Applying this to the Asian range is extrapolation. A hit on either fills the level (ours).
- **Sources:** cc08_004 ~4:01, cc09_002 ~12:29.
- **Quote:** "you're going to do both".
- **Conflicts:** none.
- **Fix:** an L13 FX note.
- **Build:** none (fx_only).

### 210. L13-flout-definition
- L13 | missing_rule | fx_only | judgment
- **Rule:** Flout = the high/low (wick and body) from 15:00 (cc09_002) or 14:00 (cc12_004) to 00:00 NY. SD = range/2, never the full range; EQ = midpoint.
  - Shorts only above EQ: levels FL - (k-1)*SD. Longs only below EQ: FH + (k-1)*SD.
  - Entries where a Flout SD coincides with a CBDR/Asian SD and a 15-60m array. Extreme Flout levels with a 60/15m array near the London close = near HOD/LOD.
- **Sources:** cc09_002 ~12:27, cc12_004 ~14:04.
- **Quote:** "only half of the range that makes the standard deviation".
- **Conflicts:** 15:00 vs 14:00 start.
- **[our interpretation]:** the start switch.
- **Fix:** an L13 FX note.
- **Build:** none (fx_only).

### 211. L13-gmt-pivot-ladder
- L13 | missing_rule | fx_only
- **Rule (FX-only):** pivot day 0-0 GMT. Standard floor pivots plus midpoints M0-M5 (13 levels).
  - Count 4 sequential levels beyond the entry; take 75-80% off after 4 and leave 25-30%. Not an entry tool. Formulas are not given by ICT.
- **Sources:** cc09_002 ~2:05.
- **Quote:** "these are 0 GMT pivots".
- **Conflicts:** none.
- **Fix:** an L13 FX note.
- **Build:** none (fx_only).

### 212. new-commodity-term-structure
- new | missing_rule | needs_unavailable_data | judgment
- **Rule:** spread = settle(nearby) - settle(next month).
  - Spread > 0 = term_structure_premium (commercial bull); nearby below later months = a carrying-charge market. Larger positive spread = higher odds of a parabolic move.
  - **Signal:** price makes lower lows into a discount array while the spread rises.
  - Keep it separate from pd_zone.
- **Sources:** cc10_004 ~6:09/~9:52/~12:09.
- **Quote:** "do not confuse that with premium and discount PD arrays".
- **Conflicts:** none.
- **Fix:** add a terminology note plus the rule.
- **Build:** none (needs futures-curve data).

### 213. new-oi-roll-not-artifact
- new | missing_rule | needs_unavailable_data
- **Rule:** do not discard OI moves around the quarterly roll as artifacts. Read actual OI against the seasonal multi-year average, which includes the roll dip. Total OI is our choice.
- **Sources:** cc10_005 ~11:19.
- **Quote:** "roll right over into the next month out".
- **Conflicts:** none.
- **Fix:** a B20 note.
- **Build:** none (needs CME OI history; B20.2 `oi_tag` is the future home).

### 214. T4-bond-opening-range
- T4 | missing_rule | bonds_only | judgment
- **Rule (bonds):** bond OR (ZB, 15m) = 08:00-09:00 NY. Edges: bodies first, then wicks, then nearby prior highs/lows to the left (00:00/02:00-08:00).
  - Project the edges as stop-raid references for later in the day and the evening/Asian session. Signals preferred 08:20-08:30 or later. The tick tolerance is ours.
- **Sources:** cc10_006 ~3:36/~10:36.
- **Quote:** "the opening range begins at 8 A.M New York time".
- **Conflicts:** T4 09:30 (index).
- **Fix:** a T4 bonds note.
- **Build:** none (bonds_only).

---

## Counts

- **Items:** 214.
- **New build specs:** 190 distinct. That is 191 `Build (...)` lines minus item 167, which reuses item 90's switch. Items with no new spec: 4 already in `rule_coverage.md` (99, 149, 158, 195) and 2 documentation-only (137, 205).
- **No spec by scope:** fx_only 7 (73, 133, 194, 208-211), bonds_only 2 (203, 214), needs_unavailable_data 8 (66, 69, 70, 71, 108, 175, 212, 213).
- **Specs per package** (by `Build` line):
  - LD 46
  - ESS 39
  - BH 37
  - SM 36
  - TP 16
  - ME 14
  - DWC 3
  - NCT 0
  - SB 0
  - Items that span two packages are counted under the first one listed.
