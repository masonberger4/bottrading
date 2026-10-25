# Rulebook gaps: day selection, news and calendar

Topic `day_selection_news_calendar`. Each item below is a verified gap between ICT's captions and `mentorship_rules.md`. Where the checker gave a corrected rule, the corrected rule is the one written here. "[our interpretation]" marks thresholds or readings that ICT does not state.

Conventions:
- Times are New York. Params times are minutes from midnight (510 = 08:30, 570 = 09:30, 600 = 10:00, 660 = 11:00, 720 = 12:00, 810 = 13:30, 840 = 14:00, 865 = 14:25, 885 = 14:45, 900 = 15:00).
- New Params switches default off, following rule_coverage.md. Each work package adds its fields in its own commented block at the end of `Params`.
- Work packages are the names in `rule_coverage.md` section 3.
- "Already in rule_coverage" means the item's switch is already specified there. In those cases the build spec below covers only the new part. Specs name test functions; put new tests in `tests/test_day_selection.py` unless a package's own test file fits better.
- Scope `fx_only`, `bonds_only` or `needs_unavailable_data` gets the rulebook fix only, with no build spec.

Summary: 92 items, 75 new build specs. Items without a build spec:
- 4 fx_only
- 4 bonds_only
- 5 that need data we do not have
- 4 text-only or already listed: N3-fomc-students-never; N4-day-before-cpi-tradeable, already in rule_coverage as D9/N4 `skip_pre_cpi` skip/small with the same content; DS2-n8-cc09003-miscite; new-lethargic-3m-market, which is swing market selection and does not apply to an ES/NQ-only bot.

---

## N: NFP

### 1. N2-nfp-week-imprecise-targets
- **rule_id / kind:** N2 / missing_condition. Scope: index. judgment = true.
- **Rule:** NFP week (Mon-Fri) and FOMC days: expect sloppy delivery. HTF targets (e.g. a daily VI) may be missed or not touched at all. Take most of the position at nearer liquidity and do not rely on the runner reaching the HTF array. [our interpretation] The test values nfp_week_partial = 0.8 and "limit just before the array edge" are ours, not ICT's.
- **Sources:** 003_ojy5ApHhEu4 ~00:18:39 (also ~2:00-4:30: on FOMC day price "never even touched" the daily VI).
- **Quote:** "targets won't really get filled perfectly or maybe not even get touched at all"
- **Conflicts:** none.
- **Rulebook fix:** In N2, add: "NFP week (Mon-Fri) and FOMC days deliver sloppily. HTF targets may be missed. Bank most at the first liquidity and do not count on the runner (003 ~18:39)." Cross-reference E9/X ladder.
- **BUILD SPEC (targets_partials):**
  - Where: `strategy._split`. When `nfp_week_split` is on and the day is in an NFP week (`JOBS` date in Mon-Fri of `day`) or is an FOMC day, return `(p.nfp_week_partial, 1 - p.nfp_week_partial)`.
  - Same condition in `_targets`: shift HTF-array rungs (kinds from `htf_targets` / `vi_targets`) inside the array by `nfp_week_inside_pts`.
  - Params:
    - `nfp_week_split: bool = False`
    - `nfp_week_partial: float = 0.8`
    - `nfp_week_inside_pts: float = 1.0` [our interpretation]
  - Tag trades `nfp_week`.
  - Test: `test_nfp_week_split`. Use a day in the week of 2023-03-10 (NFP Mar 10) and expect fracs (0.8, 0.2). Use 2023-02-01 FOMC and expect the same. Use a normal week and expect the default ladder.

### 2. N1-nfp-30min-wait
- **rule_id / kind:** N1 / wrong. Scope: index. judgment = true.
- **Rule:** N1 currently says "first hour". Replace that with the first ~30 minutes after 08:30 (006 ~8:18; 065B ~4:12). 006 frames trading after that window as possible but not advised. 065B frames it as allowed for traders with experience. The bot default stays blocked. D8 test switch nfp_day_from = 09:00, with 09:30 and 10:00 as variants. Drop the "~10 ES pts to a pool" filter, which these sources do not give.
- **Sources:** 006_VKkn8uckkW0 ~00:08:18; 065_rx15_eN9sxI ~04:12:01.
- **Quotes:**
  - "there's a way to trade the market after that first 30 minutes or so"
  - "you can trade after non-front payroll about 30 minutes after"
- **Conflicts:** 006 calls it "not something I would advise anybody". 065B presents it as permitted. N1 says "first hour" while N5 says ~30 min, so the rulebook contradicts itself.
- **[our interpretation]** The 09:00 default for the test switch.
- **Rulebook fix:**
  - N1: change "Nobody trades the first hour after 08:30" to "the first ~30 minutes after 08:30 (006 ~8:18; 065B ~4:12); after that, experienced only".
  - D8: change nfp_day_from from 10:00 to 09:00, with variants 09:30 and 10:00.
- **BUILD SPEC (news_calendar_times):**
  - Code today: `Params.nfp_day=True` trades from 09:30, and `nfp_floor_min=30` already floors the news wait on jobs days.
  - Add `nfp_day_from: int = 0`. 0 = off, which keeps current behaviour. 540 / 570 / 600 are the test values.
  - Where: `blocked()`. If `"jobs" in tags` and `p.nfp_day_from` and `t < p.nfp_day_from`, return `"nfp_before_from"`.
  - Where: `run_day` session windows. When `nfp_day_from` is set on a jobs day, set `am_start = max(am_start, p.nfp_day_from)`.
  - The bot default for a new trader is `nfp_day=False`. Leave the default as is (owner decision) and only add the switch.
  - Test: `test_nfp_day_from`. On 2023-07-07, `blocked(d,"AM",p,t=535)` returns "nfp_before_from" and `t=540` returns None.

### 3. N1-nfp-no-htf-hold
- **rule_id / kind:** N1 / missing_condition. Scope: index. judgment = true.
- **Rule:** If NFP-day trading is enabled, targets are limited to intraday liquidity: relative equal highs/lows and old daily highs/lows. Examples from 006: 3876.25, 3885, 3896.25. Hold no runner for the HTF draw (the daily VI or weekly target), not even on demo. [our interpretation] The "flat by 11:00-12:00" clause is ours, not ICT's.
- **Sources:** 006_VKkn8uckkW0 ~00:03:31.
- **Quote:** "I'm not gonna hold something to that level even for a demo trade"
- **Conflicts:** Appendix A Ep 04 lists the daily VI as the third target.
- **Rulebook fix:**
  - N1: add "NFP day: intraday-liquidity targets only. No runner to the daily VI / HTF draw (006 ~3:31)."
  - Appendix A Ep 04: add the note "on NFP the daily VI is not held for".
- **BUILD SPEC (targets_partials):**
  - Where: `_targets` and the `_scan` target merge. On jobs days with `nfp_no_htf_targets`, drop target levels whose kind is an HTF array: `htf_targets` FVG/OB/gap rungs, `daily_vi_targets`, `vi_htf_draw`, weekly `pw` pools. Keep session pools, PDH/PDL and old daily H/L.
  - Params: `nfp_no_htf_targets: bool = False`.
  - Optional: `nfp_flat_by: int = 0`, with 720 as the test value [our interpretation]. It feeds `am_exit` on jobs days.
  - Test: `test_nfp_no_htf_targets`. A synthetic jobs-day ctx with a daily VI above the PDH gives a ladder that ends at the PDH.

### 4. N1-nfp-both-sides-macro
- **rule_id / kind:** N1 / shortened. Scope: index. judgment = true.
- **Rule (N6 addition):** The NFP-day profile has three outcomes:
  - run one side, then the other, then the real move;
  - the mirror of that;
  - a choppy mess, which means no trade.

  After 08:30, wait until both the post-release high-side and low-side pools have been run. Then use a macro window (09:50-10:10, the 10:00-11:00 SB, or 10:50-11:10) for the run opposite the first false run. If no move toward the draw comes in the macros, take no trade (N9). Cite 073 alongside 071 for Jul 7 2023 in N1/D8. Test switch: nfp_day_from = 09:50 plus a both-sides-taken requirement.
- **Sources:** 073_fXVJnBVizYY ~00:13:15, ~00:26:38.
- **Quotes:**
  - "I'm actually doing that same thing and with my live Trading"
  - "or just be a choppy you know mess"
- **Conflicts:** N1 says no live trading on NFP Friday, but 073 shows live AM trades. The day is already an exception through 071.
- **[our interpretation]** The macro gating as a hard rule.
- **Rulebook fix:**
  - N6: add the third outcome (choppy mess = no trade) and the both-sides-then-macro sequence.
  - N1/D8: cite 073 next to 071 for 2023-07-07.
- **BUILD SPEC (news_calendar_times):**
  - Where: `_news_ranges` / `_news_gate`. On jobs days with `nfp_both_sides`, record the post-08:30 news-range high and low. Allow entries only after both have been traded through by 1 tick, and only for the side opposite the first one taken.
  - With `nfp_macro_only`, entries must also fall in `MACROS` windows (590-610, 600-660, 650-670).
  - If neither condition is met by 670, no entries for the AM.
  - Params:
    - `nfp_both_sides: bool = False`
    - `nfp_macro_only: bool = False`
    - Use together with `nfp_day_from=590` from item 2.
  - Test: `test_nfp_both_sides`. Synthetic bars where the high is taken first, then the low: a long is allowed after both, and nothing before the second side.

### 5. N1-nfp-release-4h-fvg
- **rule_id / kind:** N1 / unlisted_contradiction. Scope: index. judgment = false.
- **Rule:** This is a demonstration for experienced traders only. The bot default stays N1 blocked.
  - Setup: NFP Friday with bullish 4h bias. Before 08:30, mark the nearest 4h bullish FVG in the discount of the current swing range.
  - Entry: if the release drives price into it, buy inside it at or just after the release. A small overshoot into an adjacent balanced price range is acceptable.
  - Stop: wide, below the HTF bodies.
  - Management: take a first partial (about half) at the first liquidity. Optionally add one small contract at the CE limit, with no real pyramiding. Then go to breakeven plus commissions.
  - Bearish is the mirror. Test as nfp_release_fvg = True.
- **Sources:** 105_A97shZGPE2I ~00:05:54.
- **Quote:** "the market drops back down into that area overshoots it a little bit but that's fine"
- **Conflicts:** Contradicts N1 ("nobody trades the first hour") and Ep 04 ("ignore the immediate reaction").
- **Rulebook fix:** In N1/D8 option B, add the 105 release-FVG model as a separate experienced exception, apart from `nfp_day_from`.
- **BUILD SPEC (setups_models):**
  - Add a setup branch `_nfp_release_fvg(ctx, sd, i, p, ...)` in `strategy.py`, beside `_turtle` / `_cc_limit`. It runs only on jobs days, and only for the side given by `htf.table` 4h/daily bias.
  - At 510 it reads the 4h bullish FVGs from `htf._arrays` and picks the nearest one below price whose CE is under the swing-range EQ.
  - Order: a limit at the FVG's upper edge, valid from bar 510 to 515 [our interpretation], filled through the existing pending-fill block.
  - Stop: below the 4h FVG's lower candle body. Use `breaker_zone`-style body logic, or the FVG low minus `stop_buffer`.
  - Ladder: 50% at the first pool, rest to the draw. One add at the CE through `_arm_add`, capped at 1 unit.
  - Params:
    - `nfp_release_fvg: bool = False`
    - `nfp_release_fvg_min: int = 5` (minutes after 08:30 during which a fill is accepted)
  - Must bypass `nfp_floor_min` and `news_wait` for this setup only.
  - Test: `test_nfp_release_fvg`. A synthetic 4h FVG below the open plus a 08:30 drop into it fills; the same drop at 08:40 does not.

### 6. N6-nfp-first-move-fake-if-liquidity
- **rule_id / kind:** N6 / missing_condition. Scope: index. judgment = false.
- **Rule:** The first post-release move is the fake only if it runs a defined pool: an old high/low or relative equal highs/lows.
  - If the first move takes no pool on its side, the counter move that follows is the Judas. Example: a drop into an HTF PD array, such as a 4h FVG in discount, aligned with HTF bias.
  - Enter in the bias direction at that array and target the untaken pools the first move left.
  - [our interpretation] Pool-penetration tolerance (e.g. 1 tick) is our parameter.
- **Sources:** 105_A97shZGPE2I ~00:07:58 (also ~2:00-2:30).
- **Quote:** "I don't see this initial rally as the fake move"
- **Conflicts:** none.
- **Rulebook fix:** In N6, change "first side taken is usually false" to "the first post-release move is false only if it ran a defined pool. Otherwise the following counter move into an HTF array is the Judas (105 ~7:58)."
- **BUILD SPEC (setups_models):**
  - Where: the `news_profile` logic, Params `news_profile` (first-leg extreme). Add the mode `"pool_test"`.
  - Logic:
    1. After R (the release minute), find move1 = the first leg until a 1m swing reverses.
    2. If move1 traded through a marked pool (`mark_levels` / `_sell_side` pools, tolerance `sweep_ticks`), block move1's direction as today.
    3. Otherwise, block the counter move's direction until price reaches an HTF array (`htf._arrays` 4h/1h) in bias direction. Then allow bias-direction entries, with targets set to the pools left untaken on move1's side.
  - Params: `news_profile: str` gains the value `"pool_test"`. Default stays `"off"`.
  - Test: `test_news_profile_pool_test`. Case A: a rally that takes no high, then a drop to a 4h FVG; longs are allowed and shorts blocked. Case B: a rally that takes the PDH; shorts are allowed, as in today's mode.

---

## N4/N5: pre-open, releases, CPI

### 7. N5-soft-bias-pre-open
- **rule_id / kind:** N5 / unlisted_contradiction. Scope: index. judgment = true.
- **Rule:** On a day with no 08:30 (or other pre-open) high- or medium-impact release, the default for a new trader and for the bot is no entries in the early pre-market.
  - Switch `soft_bias_pre_open_from` = 09:00 vs 09:30: allow setups that form in the last ~30 min before the open (sweep, MSS, FVG/OB/breaker entry toward the pre-set draw), as well as setups after 09:30.
  - Switch `pre_open_bnb` (experienced only; the 007 example was a Twitter call): from 08:00 to 09:00, after a sweep of a pre-market REL into an HTF discount array (top of a daily VI or a 60m BISI), buy at a 1m bullish OB that holds. Stop below the OB's MT. Target the nearest short-term high (expect 10-12 handles). Flat by 09:30.
  - Drop the "09:05-09:30" fill timing; it is not in the captions.
- **Sources:** 007_bGtQOXrrK9c ~00:11:21 (and 14:35-15:17); 019_ZrZJmwrMxFY ~00:07:57.
- **Quote:** "so you kind of like have to wait until we get closer to that 9 30"
- **Conflicts:** 007 ~11:21 says to wait for 09:30, but the same video has a pre-09:30 long. 019 says "closer to" 09:30.
- **[our interpretation]** The 09:00 start, the 08:00-09:00 window and the flat-by-09:30 rule.
- **Rulebook fix:**
  - N5: change "no 08:30 news -> wait for 09:30" to "wait until closer to 09:30. Setups in the last ~30 min of the pre-open are allowed (019 ~7:57, ~10:40)."
  - Move the 007 bread-and-butter pre-open long from the appendix into N5 as an experienced exception.
- **BUILD SPEC (news_calendar_times):**
  - Code today: `pre_0900` (09:00-09:29 on any day) exists.
  - Add `pre_0900_no_news: bool = False`. It gates `pre_0900` to days where `release_times(d)` has no 510 entry.
  - `pre_open_bnb` is a setup variant, so it belongs to setups_models, using the existing `ob_entry` branch. Window: the 480-540 pre-window in `pre_windows`.
    - Requires a sweep of a pre-market REL (`_eq_levels` built from 00:00) into an HTF discount array (`daily_vi_targets` source or a 60m BISI from `htf._arrays`).
    - Target: the nearest 1m swing high.
    - Flatten at 569.
  - Params: `pre_open_bnb: bool = False`.
  - Test: `test_pre_0900_no_news`. On 2023-01-30 (no 08:30 release) a 09:10 entry is allowed. On a CPI day it is blocked.

### 8. N4-eve-of-high-impact
- **rule_id / kind:** N4 / shortened. Scope: index. judgment = true.
- **Rule:** If a high-impact release (CPI, NFP, FOMC) is scheduled for the next trading day:
  - Tag the session `high_resistance=True`, plus `pre_fomc` / `pre_cpi` in the journal.
  - Take only A+ setups.
  - Target one "bread and butter" run of about 5 ES handles, or the session objective (HTF FVG CE), whichever comes first. Partial at the first pool, no runners.
  - Set targets slightly inside levels, because 029 shows price stopping one tick short of the target.
  - Keep the initial stop with no trailing. Expect a quick move, then chop.
  - Stop for the day after the objective or one win.
  - Size: test risk_mult 0.5 vs 1.0. 042 itself says only "lower expectations".
  - [our interpretation] The no-trailing rule, the absence of 2-3 candle time stops, and the 5-handle cap as a hard rule.
- **Sources:** 029_dwJcsi3ddFg ~00:52:11; 042_hQ379EuyNKQ ~00:39:05 (also ~3:30-5:00, ~53:00).
- **Quote:** "so you have to be a lot more Nimble on days like this and also by lowering your expectations"
- **Conflicts:** 029 and E9 imply reduced risk. 042 does not state a size cut.
- **Rulebook fix:**
  - N4: add a general "eve of CPI/NFP/FOMC = high-resistance day" bullet (029 ~52:11; 042 ~3:30-5:00, ~39:05).
  - E9: re-source the size-down to 029/094 instead of 042.
- **BUILD SPEC (targets_partials + news_calendar_times):**
  - Code today: `_split` already detects `events(next_trading_day(day)) & {"cpi","jobs","fomc"}` and uses `ladder_fracs_slow`.
  - Add `eve_mode: str = "off"`, with values `"off"` / `"tag"` / `"bnb"`.
  - `"bnb"`, applied in the `_scan` target merge:
    - Cap the targets at min(entry ± `eve_target_pts`, first pool) minus `exit_before_pts`.
    - Single exit, `ladder_trail="off"` for that trade.
    - The `day_target_pts`-style stop for the day after one win.
  - `eve_risk_mult: float = 1.0`, with 0.5 as the test value, applied as `risk_mult` in `_scan`.
  - Params: `eve_target_pts: float = 5.0`.
  - Tag trades `pre_cpi` / `pre_nfp` / `pre_fomc`.
  - Test: `test_eve_bnb`. On the day before 2023-02-14 CPI, the ladder holds a single rung of at most +5 pts.

### 9. N4-pre-cpi-monday-gap
- **rule_id / kind:** new / missing_rule. Scope: index. judgment = true.
- **Rule:** On the Monday before a Tuesday CPI, measure NWOG = |Sunday 18:00 open - Friday close|.
  - Small NWOG: tag Monday "quiet pre-CPI". Small targets only, or skip.
  - Large NWOG: expect Monday to reprice into the gap range, toward Friday's close or the gap CE. Allow the normal model with the gap as the draw. Gap down: look for longs into the gap, or shorts after the rally into it, per bias. Gap up is the mirror.
  - [our interpretation] Threshold: NWOG > 0.5 x ADR5.
- **Sources:** 028_wWvFUW-jY4w ~00:34:21.
- **Quote:** "if we see a gap lower that's big that creates a really good trading opportunity for Monday"
- **Conflicts:** none.
- **Rulebook fix:** Add to N4: "Pre-CPI Monday: a small NWOG means a quiet day; a large NWOG means a Monday reprice into the gap is a good trade (028 ~34:21)."
- **BUILD SPEC (day_week_context):**
  - Where: `day_context`. If `day.weekday()==0` and `"cpi" in events(next_trading_day(day))`, compute the NWOG from `htf.opening_gaps` (the newest NWOG) and `adr5(hist)`.
  - Tag `pre_cpi_mon_small` or `pre_cpi_mon_gap`.
  - With `pre_cpi_mon="gap"`, `block["pre_cpi_mon"]` removes the side away from the gap. The gap CE / Friday close is already a target via `gap_mode`.
  - With `pre_cpi_mon="skip_small"`, skip `pre_cpi_mon_small` days.
  - Params:
    - `pre_cpi_mon: str = "off"`, with values `"tag"` / `"gap"` / `"skip_small"`
    - `pre_cpi_gap_adr: float = 0.5`
  - Test: `test_pre_cpi_monday_gap`. Synthetic Friday close 4000, Sunday open 3980, ADR5 30: tag gap; longs only.

### 10. N4-cpi-day-new-traders
- **rule_id / kind:** N4 / missing_condition. Scope: index. judgment = true.
- **Rule:** If today has an 08:30 CPI release:
  - Never hold or open a position through the release.
  - No entries 08:30-09:30.
  - New traders preferably skip the day, and at minimum never trade before the number (030 ~7:13).
  - After 09:30, first watch how the opening range is used (030 ~42:21). Then trade only toward remaining liquidity (028 ~3:40).
  - Test skip_cpi=True vs entries from 10:00 [our interpretation].
- **Sources:** 030_ZdnGlropfmU ~00:07:13 (also ~42:21).
- **Quote:** "really for those that are new not to trade this day at least not trade before the CPI number"
- **Conflicts:** D9 recommends allowing CPI days with entries from 09:30.
- **Rulebook fix:**
  - N4: add the new-trader framing and the 08:30-09:30 wait, then opening-range observation.
  - D9: cite 030 ~7:13 / ~42:21 and add the cpi_from=10:00 variant.
- **BUILD SPEC (news_calendar_times):**
  - Code today: `skip_cpi` exists. `pre_flat_0830` already flattens pre-open models.
  - Add `cpi_from: int = 0`, with 600 as the test value. It acts in `blocked()`: `"cpi" in tags and t < p.cpi_from` returns `"cpi_before_from"`.
  - In `run_day`, set `am_start = max(am_start, cpi_from)`.
  - Also set `pre_0900`/`post_news` off on CPI days when `cpi_from` is set.
  - Test: `test_cpi_from`. On 2023-02-14, t=590 is blocked and t=600 is not.

### 11. N5-hold-through-0830
- **rule_id / kind:** N5 / unlisted_contradiction. Scope: index. judgment = true.
- **Rule:** The default (bot / new trader) is to close pre-09:30 intraday positions before any 08:30 high/medium release, banking the profit if about 5+ handles were available. No new entries 08:25-08:30, and stops are not relied on through the release.
  - Switch `hold_through_0830` (experienced), default False: a position opened 07:00-08:29 in the bias direction may be held through 08:30. This includes a Ma Deuce short entered 08:00-08:29 on the retrace into the inverted FVG. The exit is a resting limit at the target pool, so the spike fills it.
  - Never open on the 08:30 bar itself.
  - NFP Friday (N1) and CPI under N4 strict mode are excluded.
  - [our interpretation] The 08:29 close time and the 08:25 cutoff.
- **Sources:** 032_SSWN6YSVyFY ~00:06:56; 040_JlbQ-Z88NsI ~00:01:03; 091_1PkTGkOjoGo ~00:22:26.
- **Quote:** "I have no fear of getting in a trade and using the 8 30 hour to roll right into my targets"
- **Conflicts:** 040 goes flat before claims, though 040 is a drawdown demo. 032 and 091 hold through 08:30 releases. N4 bars positions into CPI.
- **Rulebook fix:** In N5, add "positions open before an 08:30 release: default bank and go flat (040); experienced may hold with resting target limits (032 ~6:56; 091 ~22:26 / M15)". List it as a conflict.
- **BUILD SPEC (management_exits):**
  - Code today: `pre_flat_0830=True` flattens the `pre_0700` model. Per the N4 note, the flat should be generalized to Ma Deuce and `sb_london`.
  - Generalize the 08:29 flat in the `run_day` management loop: any open position with entry < 510 on a day where `510 in release_times(d)` is closed at bar 509, unless `hold_through_0830`.
  - Add `no_entry_0825: bool = True`: pending orders with fill time 505-510 are cancelled on 08:30-release days. Default on, because this is the existing intent of `pre_flat_0830`.
  - Params: `hold_through_0830: bool = False`. Jobs and CPI days stay excluded even when it is True.
  - Data gap: jobless claims (every Thursday 08:30, or Wednesday when Thursday is a holiday) are not in `calendar.py`. Add rule-based `claims_events(d)` to `release_times` (news_calendar_times).
  - Test: `test_flat_before_0830`. A Ma Deuce position open at 08:15 on a PPI day is closed at 08:29. With `hold_through_0830=True` it stays open.

### 12. N5-entry-at-release
- **rule_id / kind:** N5 / unlisted_contradiction. Scope: index. judgment = true.
- **Rule:** Two experienced switches, both default off. N5 `news_wait` and N6 stay the default.
  - (a) `post_news_continuation` (040, drawdown drill): after an 08:30 release, once the run-out has printed in the direction of the daily bias, go long or short on the first 1m OB retrace in that direction. Target by swing projection. Adds at the OB, within max_contracts.
  - (b) `release_ob_entry` (049): on a 10:00 high-impact day with a known daily draw, if price at 10:00 is inside a 5m OB in the bias direction, enter at 10:00 inside the OB, executing on 1m. The first target is the nearest short-term low or high (a scalp). Continue only if an SMT or sick-sister read supports it.
  - List both under D8/D9 option B.
- **Sources:** 040_JlbQ-Z88NsI ~00:01:28; 049_St9FJHRVdq8 ~00:02:27.
- **Quote:** "News at 10 o'clock high impact and I use this order block here ... I went short okay at 10 o'clock"
- **Conflicts:** N5 (wait for the news dealing range, or 30 min per 065B) and N6 (first side false) vs 040/049.
- **Rulebook fix:** Add both to D8/D9 option B as experienced exceptions. In 040, note that it is a drill.
- **BUILD SPEC (setups_models):**
  - (a) `post_news_continuation: bool = False`.
    - After R=510, the run-out is the first post-release leg of at least `post_news_run_pts` (default 5.0 [our interpretation]) in the `htf.table` daily bias direction.
    - Arm `_ob_pre`-style entries on the first opposing 1m candle's body in the bias direction. Bypass `news_wait` for this setup only.
    - Targets come from `sd_targets` (L12 projection of the run-out leg).
    - `ob_adds` follows the existing setting.
  - (b) `release_ob_entry: bool = False`.
    - On days with 600 in `release_times`: at bar 600, if the close is inside a 5m OB (`zones_tf(..., 5)` OB kind) aligned with bias, place a market entry at bar 600's open, with stop beyond the OB's far edge.
    - Target 1 is the nearest 1m swing, with `sb_mgmt="fixed"` semantics.
  - Test: `test_release_ob_entry`. Synthetic bars: 5m bearish OB containing 10:00 plus bearish bias gives a short fill at 600.

### 13. N5-two-driver-session
- **rule_id / kind:** N5 / shortened. Scope: index. judgment = false.
- **Rule:** Two high-impact releases in the same session (e.g. 08:30 + 10:00) make a two_driver day. An 08:30 + 14:00 pair does not count.
  - Release 1 tends to continue the London/prior-day move.
  - Release 2 delivers the real run: either a reversal against the day's move, or a squeeze further into trailing stops (especially on Fridays).
  - No entries ahead of release 2. The N5 wait applies after it.
  - A possible first reversal target is ~50% of the day's range so far (day-range EQ). This comes from a single "devil's advocate" scenario in 100 ~29:00, so keep it as a tagged hypothesis.
- **Sources:** 100_GJeEU2oIh24 ~01:10:53, ~00:29:00.
- **Quote:** "there's two of them in the same session the morning session"
- **Conflicts:** cc08_006 ~7:04 treats two or more releases in a session as a reason to avoid it (item 65).
- **Rulebook fix:** In N5, state the same-session condition and the 08:30+14:00 exclusion. Add the two-stage mechanism and the hypothesis tag.
- **BUILD SPEC (news_calendar_times):**
  - Code: N5.4 `skip_two_drivers` is already in rule_coverage. The delta is the precise definition plus a wait mode.
  - Definition: `two_driver = 510 in rt and 600 in rt`, with `rt = release_times(d)`. FOMC 840 is excluded from the count.
  - `two_driver_mode: str = "off"`, with values `"tag"` / `"wait2"` / `"skip"`.
    - `"wait2"`: in `_news_gate`, the news range is built from the second release (600), and no entries are allowed in 510..range-made(600).
  - Tag trades `two_driver` and record the day-range EQ at 600 as `eq_two_driver` for a later study. It is not a target.
  - Test: `test_two_driver_wait2`. On 2023-09-29 (PCE 08:30 + 10:00 sentiment), entries at 09:40 are blocked.

### 14. N5-multi-release-count
- **rule_id / kind:** N5 / shortened. Scope: general. judgment = false.
- **Rule:** Count high- AND medium-impact releases in the session window.
  - Two or more: problematic. Avoid the session or use minimum risk; ICT says "not all the time".
  - Exactly one: ideal. Expect one manipulation stage around it, then the expansion.
  - None: a "wild card". It can be a clean technical day or a shock day; tag `no_news_wildcard`.
  - Fix the N5 citation to cc08_006 ~7:00-7:50.
- **Sources:** cc08_006_stK2gNqhLaM ~00:07:04.
- **Quote:** "if we see multiple events due out on the economic calendar for that particular pair it could be problematic"
- **Conflicts:** 100 trades a two-release session with a two-stage read (item 13).
- **Rulebook fix:** N5: medium impact counts the same as high, plus the "exactly one = one manipulation leg" and "none = wildcard" notes. Fix the citation time.
- **BUILD SPEC (news_calendar_times):**
  - Where: `day_context` tags, using `release_times(d)` restricted to 510-660 (NY AM).
  - Tag `rel0_wildcard` / `rel1` / `rel2plus`.
  - Params:
    - `multi_release: str = "off"`, with values `"tag"` / `"skip"` / `"half"`. `"half"` sets risk_mult 0.5 on `rel2plus`.
  - Test: `test_release_count_tags`. An ISM day with 08:30 PPI gives `rel2plus`; a plain Tuesday gives `rel0_wildcard`.

### 15. N5-fed-speaker-day
- **rule_id / kind:** N5 / missing_rule. Scope: needs_unavailable_data. judgment = true.
- **Rule:** Extend the N5 Fed-chair bullet to any Fed official speaking or testifying, treated like a rate announcement:
  - no bias before the event;
  - tag the day as consolidation / no trade until after the event;
  - apply on every scheduled testimony day;
  - new-trader default 13:30-16:00 (already in N5).
  - Experienced variant: resume after a short filter (~10-15 min) once the event ends (027, 037).
  - Drop the unverified claim about skipping 09:30-10:00 setups.
- **Sources:** 027_STEGBblm4dI ~00:25:43; 037_wu0sQarBRrI ~00:30:13; 038_4H74nXabvL0 ~00:48:31; 067_vuBRMFhFZAY ~00:34:33.
- **Quote:** "whenever you have the Fed you know talking speaking testifying it's equivalent to a rate announcement"
- **Conflicts:** The post-event buffer differs: 5-15 min (N5), "a couple minutes maybe 15" (037), and wait until lunch is over (067).
- **Rulebook fix:** Broaden the N5 bullet from "Fed chair testimony at 10:00" to "any Fed official speaking or testifying", with the multi-day and experienced-variant notes.
- **Build:** None. A Fed-speaker calendar is unavailable. When one exists, extend the planned N5.5 `FED_CHAIR` set into `FED_SPEAK` (news_calendar_times).

### 16. N5-pre-fed-testimony-week-map
- **rule_id / kind:** N5 / missing_rule. Scope: needs_unavailable_data. judgment = false.
- **Rule:** Pre-week: map all high- and medium-impact releases and Fed speakers for Mon-Fri. Tag the days before a Fed-chair testimony (or another major event) as slow / small range. They are still tradeable, but be nimble, take only the nearest draw, and expect a small PM range. Tie this to N8's consolidation-day predictor. The specific settings (80/20, AM done by 11:00, "after a prior-day range expansion") are our interpretation.
- **Sources:** 036_n37ozsUreR0 ~01:04:22, ~01:15:13.
- **Quote:** "look at the entire weekly calendar where are the big heavy stones"
- **Conflicts:** none.
- **Rulebook fix:** Add a weekend calendar-mapping step to N5/N8, plus a "day(s) before Fed-chair testimony = slow" bullet.
- **Build:** None, because a Fed-speaker calendar is needed. Partial coverage today: `_split` already uses 80/20 when a CPI/NFP/FOMC event is next.

### 17. N4-day-before-cpi-tradeable
- **rule_id / kind:** N4 / wrong. Scope: index. judgment = false.
- **Rule:**
  - CPI day: no position from the open until the 08:30 release (028 ~3:55; 030 ~7:22).
  - Day before CPI: tradeable with low expectations. Small bread-and-butter targets only (~5 handles), no runners, size down per E9 (028 ~30:39; 029 ~5:22).
  - Exception: the pre-CPI Monday gap rule (item 9).
- **Sources:** 028_wWvFUW-jY4w ~00:30:39.
- **Quote:** "can you trade on Monday I believe you [can] but I don't want you to think massive big range"
- **Conflicts:** none.
- **Rulebook fix:** In N4, delete "no trade ahead of it" for the day before CPI. Keep "small bread-and-butter only".
- **Build:** None. This is already in rule_coverage with the same content: N4 "pre_cpi skip/small" and D9 "skip_pre_cpi skip/small with next_trading_day". The only change is a default note: once built, `skip_pre_cpi` should default to "small", not "skip", when tested. Item 8's `eve_mode="bnb"` covers the same mechanics.

### 18. N6-both-pools-news
- **rule_id / kind:** N6 / missing_condition. Scope: index. judgment = false.
- **Rule:** Before 08:30 on CPI/NFP/FOMC-type days, record the nearest smooth REH (BSL), REL (SSL) and the nearest unfilled FVG.
  - Expect both pools to be taken after the release, often with the FVG touched first (overshoot allowed), possibly within the first 1m candle.
  - This is observation only; no trade during the move (N4/N5).
  - Then apply N6: the first pool taken is usually false, and a retrace to the CE between the pools follows.
  - Context tag: on non-news days the same sequence plays out more slowly, with the AM going to the FVG and first pool and the PM to the opposite pool (064 ~1:07:20).
- **Sources:** 064__YTK5uXBe4o ~00:30:16.
- **Quote:** "Both sides of the marketplace are always in contention for high impact news drivers"
- **Conflicts:** none.
- **Rulebook fix:** In N6, add the pre-release marking, the FVG-first step and the compression note.
- **BUILD SPEC (news_calendar_times):**
  - Study/tag only. Where: `_news_ranges`. At R-1, snapshot `pre_bsl` and `pre_ssl` (nearest `_eq_levels` above and below, falling back to the nearest swing) and the nearest open 1m/5m FVG.
  - After R, record the order in which they are taken and the minute of each. Write these to `Trade` meta and a `news_sequence.csv` from `study.py`.
  - Params: `news_seq_study: bool = False`.
  - Test: `test_news_sequence`. Synthetic 08:30 bar with high > pre_bsl and low < pre_ssl gives the sequence ("both", same bar).

### 19. N6-news-runs-trailed-stops
- **rule_id / kind:** N6 / missing_rule. Scope: general. judgment = true.
- **Rule:** On a high-impact (sometimes medium-impact) news day in an established trend, expect the release move to run first against the trend, into the trend-holders' trailed stops or the relative-equal pool beneath them, and then usually resume the trend (065 ~4:11:02).
  - Hold no position into the release (N4/N5).
  - After the sweep, continuation in the trend direction is the expected case. Decide reversal vs resumption only from how price delivers after the release.
  - Bot reading: wait for the news dealing range, then trade in the trend direction if price reclaims after the sweep. A downtrend is the mirror.
- **Sources:** 065_rx15_eN9sxI ~04:11:02.
- **Quote:** "my mindset is always it's going to run against that either to reverse on them or to offset any trailed stop losses"
- **Conflicts:** none.
- **Rulebook fix:** In N6, add the trend-context version of "first side false".
- **BUILD SPEC (news_calendar_times):**
  - Where: `_news_gate`. With `news_trend_side=True`, on a release day where `htf.table` daily bias ≠ 0 (trend = bias), after the news range completes, allow only the bias side, and only if the range's counter-trend extreme swept a pool below/above.
  - Params: `news_trend_side: bool = False`.
  - Test: `test_news_trend_side`. Bullish bias, the release dips under the REL, the news range forms: longs allowed, shorts blocked.

### 20. DS2-killzone-news-manipulation-time
- **rule_id / kind:** N5 / missing_rule. Scope: general. judgment = true.
- **Rule:** Before the session, list high- and medium-impact releases and keep those inside the London (02:00-05:00) or NY (07:00-10:00) kill zone.
  - Expect the manipulation extreme against the bias (the low if bullish, the high if bearish) at or around the release time.
  - Arm the entry for completion of that leg. This is compatible with N5's dealing-range wait.
  - The no-release "soft" case is already in N5/N8. Choosing the instrument by release is [fx-only] pair selection.
  - [our interpretation] Index mapping: an 08:30 release gives a manipulation window of 08:30-09:30.
- **Sources:** cc09_008_cqf8nH54bb8 ~00:01:46.
- **Quote:** "look for payers in the London session or the New York session to have a medium or high impact news event"
- **Conflicts:** none, if entry is armed on completion of the release-time leg.
- **Rulebook fix:** In N5, add "the kill-zone release time = expected manipulation (Judas) time".
- **BUILD SPEC (news_calendar_times):**
  - Tag/study: for each release in `release_times(d)` within 420-600, record whether the day's low (bullish bias) or high (bearish bias) formed within R..R+60.
  - Output `kz_release_extreme` on Trade meta and in study.
  - Params: `kz_release_tag: bool = False`.
  - Test: `test_kz_release_tag`. Day low at 08:41 on a CPI day with bullish bias gives the tag True.

### 21. T13-judas-news-driver
- **rule_id / kind:** T13 / missing_condition. Scope: general. judgment = true.
- **Rule:** The manipulation (Judas) leg is usually triggered by a news driver released at the time of the move or just before it (cc01_002, stated as "always"). Tag the Judas window to the nearest release. Window size is our interpretation.
- **Sources:** cc01_002_XwYYWBttWro ~00:15:16.
- **Quote:** "that's always going to come by way of some news event some news driver"
- **Conflicts:** cc08_006 says no-news sessions are wildcards that can still be clean. N5: no 08:30 news = soft bias.
- **Rulebook fix:** In T13, add the news-driver link and list the conflict.
- **BUILD SPEC (setups_models):**
  - Where: `_judas(ctx, sd, sw, session, window)`. Add a field `judas_news` = True when a release R exists with R-30 <= sweep time <= R+30 [our interpretation].
  - With `require_judas_news=True` (in the `require_judas` path), only news-backed Judas sweeps count.
  - Params: `require_judas_news: bool = False`.
  - Test: `test_judas_news`. A sweep at 08:35 on a CPI day sets the flag; a sweep at 10:20 on a no-news day does not.

---

## N3: FOMC

### 22. N3-fomc-students-never
- **rule_id / kind:** N3 / missing_condition. Scope: index. judgment = false.
- **Rule:**
  - The student/new-trader default is no FOMC trading at all after 14:00. The bot already does this through the FOMC PM block.
  - Trading after 14:45 (last hour preferred) is ICT's own experienced-only practice, and he calls it below 50/50.
  - Correct D8 B so that 021 supports 14:45, not 14:25.
- **Sources:** 021_DVxC7UAHzwk ~00:05:41 (also ~27:13).
- **Quote:** "I teach my students don't touch it at all"
- **Conflicts:** N3's "after 14:45 the normal routine applies" vs 021's "students don't touch it".
- **Rulebook fix:**
  - N3: lead with the student default (no trading after 14:00). Then add "experienced: from 14:45, last hour preferred, below 50/50 (021 ~5:41, ~27:13)".
  - D8 B: change 14:25 to 14:45 for 021.
- **Build:** None. Text-only; the bot already blocks via `blocked()` "fomc_pm" with `fomc_pm_from=885`.

### 23. N3-fomc-two-stage
- **rule_id / kind:** N3 / missing_rule. Scope: index. judgment = true.
- **Rule:** FOMC research tag. Experienced only; entries from 14:45 per N3.
  - Mark the 14:00-14:25 first-leg extreme, the pool it took (S), the FVG it leaves, and the opposite primed pool B (a smooth REH/REL or old high/low).
  - 14:25-14:45: in one live 021 scenario, price ran one more time toward S into the nearest 1m FVG, then made an MSS. Label this as a single-scenario observation.
  - Form A (most common): price reverses through the first leg's origin and expands to B and beyond.
  - Form B: price retraces into the first-leg FVG, rejects, and continues the first leg.
  - Use it as a label and a statistic.
  - NFP: ICT says it works "the same way" (same two forms after 08:30). Drop "muted".
- **Sources:** 021_DVxC7UAHzwk ~00:39:02; 065_rx15_eN9sxI ~05:34:01.
- **Quote:** "Maximum Carnage that's what I'm looking at all the time when it's fomc"
- **Conflicts:** none.
- **Rulebook fix:** In N3/M9, add the two stage-2 forms (A common, B less common), the leadership read and the NFP equivalence.
- **BUILD SPEC (news_calendar_times):**
  - Code: M9.2 `fomc_judas` / `fomc_stage2_cont` are already in rule_coverage. The delta is the A/B label and the S/B pool record.
  - Where: an FOMC-day study block in `run_day`, active when `fomc_stage_study`. Record `leg1_ext` (840-865), `leg1_pool`, `leg1_fvg` and `opp_pool`.
  - At 900, classify:
    - A = price closed beyond the 840 open, opposite to leg1;
    - B = touched `leg1_fvg` then made a new leg1 extreme;
    - else "none".
  - Write the label to day meta / study CSV. Reuse the same code on jobs days with R=510.
  - Params: `fomc_stage_study: bool = False`.
  - Test: `test_fomc_stage_label`. Synthetic 14:00 drop, then a 14:30 rally above the 14:00 open, gives "A".

### 24. N3-skip-am-before-pm-event
- **rule_id / kind:** N3 / unlisted_contradiction. Scope: index. judgment = true.
- **Rule:** Switch `skip_am_before_pm_event`: on days with a scheduled 14:00 FOMC event, no AM entries. Source 067 frames it as context: price has done nothing in the AM, so wait for lunch and the 13:30 PM run. PM entries still follow N3 (nothing 14:00-14:45). Test against the current AM-open default (cc10_009).
- **Sources:** 067_vuBRMFhFZAY ~00:43:45.
- **Quote:** "there's a afternoon event that's expected like fomc ... you avoid the morning session"
- **Conflicts:** N3 bot note ("AM open") and cc10_009 (AM tradeable with the trending-day recipe) vs 067.
- **Rulebook fix:** In N3, list 067 ~43:45 as a conflict with cc10_009. Add the switch to D8.
- **BUILD SPEC (news_calendar_times):**
  - Code: `fomc_only_am` consolidation/skip (N3.3) is already listed. This switch is the general one, keyed on any FOMC day.
  - Where: `blocked()`. `if p.skip_am_before_fomc and "fomc" in tags and session in ("AM","PRE") : return "fomc_am"`.
  - Params: `skip_am_before_fomc: bool = False`.
  - Test: `test_skip_am_before_fomc`. On 2023-03-22 the AM is blocked and the PM is unchanged.

### 25. N3-fomc-minutes
- **rule_id / kind:** N3 / unlisted_contradiction. Scope: index. judgment = true.
- **Rule:** Separate FOMC rate-decision days (14:00 statement plus 14:30 press conference; N3 applies) from FOMC-minutes days (14:00 minutes only).
  - On minutes days, a test switch `allow_fomc_minutes_pm` permits PM setups (PM SB 14:00-15:00, Model 2022) in the bias direction, with the minutes as the expected catalyst.
  - The evidence is a single after-the-fact review in which ICT did not trade it. Keep the N3 block as the default and test the switch.
  - cc10_008 avoids any 14:00 rate driver.
- **Sources:** 082_JpdNsPE0kWQ ~00:04:18.
- **Quote:** "at that two o'clock fomc minutes expecting that to be a wonderful sell-off"
- **Conflicts:** N3 blanket FOMC-PM block vs 082. cc10_008 ~11:18 avoids the PM on any 14:00 rate driver.
- **Rulebook fix:** In N3, define "FOMC day" = decision day, and add an "FOMC minutes" bullet with the 082 review and the cc10_008 conflict.
- **BUILD SPEC (news_calendar_times):**
  - Calendar: add `FOMC_MINUTES` to `calendar.py`. Rule-based: decision date + 21 calendar days, on a Wednesday; verify against the Fed site when filling in dates. Tag the events "fomc_minutes". Today "fomc" covers decisions only, so minutes days are currently treated as normal days.
  - `blocked()`: `fomc_minutes_mode: str = "allow"`, with values `"allow"` (current behaviour) / `"block"` (cc10_008: treat like "fomc" for the PM) / `"pm_only"` (082: no AM, PM SB allowed).
  - `sb_model.py`: honour the same block through `blocked()`.
  - Test: `test_fomc_minutes_tag`. 2023-08-16 has "fomc_minutes". With "block", the PM is blocked at 850.

### 26. N3-fomc-move-ends-1500
- **rule_id / kind:** N3 / missing_rule. Scope: general. judgment = true.
- **Rule:** On an FOMC statement or minutes day, treat 14:00-15:00 as the event window. After 15:00 the bulk of the FOMC move is assumed done, so take no new entries that expect the FOMC expansion to continue. The source is FX (true-day close at 15:00 because bonds close), so applying it to index futures is our interpretation, as is reopening entries after 15:00.
- **Sources:** cc08_002__2nUKLAD9ig ~00:09:56.
- **Quote:** "the bulk of the move has ended by 3 P.M"
- **Conflicts:** 021 prefers the last hour (15:00-16:00) for experienced FOMC trading.
- **Rulebook fix:** In N3, add "FOMC move is usually done by 15:00 (cc08_002 ~9:56, FX source)" and list the 021 conflict.
- **BUILD SPEC (news_calendar_times):**
  - Where: `blocked()` / PM window. On FOMC days with `fomc_end=900`, block entries at t ≥ 900 whose side equals the direction of the 840-900 move (`|close900 - open840| ≥ fomc_end_min_pts`, default 5 [our interpretation]).
  - The last-hour model (`last_hour`) on FOMC days then only takes the counter side.
  - Params:
    - `fomc_end: int = 0` (test value 900)
    - `fomc_end_min_pts: float = 5.0`
  - Test: `test_fomc_end`. FOMC day rallies 14:00-15:00 by 20 pts: a 15:10 long is blocked and a short is allowed.

### 27. N3-fomc-week-mon-wed
- **rule_id / kind:** N3 / wrong. Scope: index. judgment = true.
- **Rule:** FOMC week (Wed 14:00 statement):
  - From Monday until Wed 14:00: reduced size (ICT: "keep it real light"; he did trade live on Monday, lightly), no max leverage or pyramiding.
  - Optional filter: ES and NQ move in concert.
  - Wed 14:00 keeps the N3 block.
  - Fix N3's citation: 094 is the Monday of FOMC week, not the day before; 042 is the day before.
  - Switch `pre_fomc_week_light`.
- **Sources:** 094_2AC4IKTj2ug ~00:01:48 (also ~7:09).
- **Quote:** "I'll just be mindful that the market will likely be a little fickle"
- **Conflicts:** 042 (day before FOMC) lowers expectations without a size cut.
- **Rulebook fix:** In N3, change "Day before FOMC: slow, trade light (042; 094)" to "FOMC week Mon-Wed 14:00: light size, no max leverage (094 ~1:48, ~7:09); day before: slow (042 ~3:50)".
- **BUILD SPEC (news_calendar_times):**
  - Code: N3.4 `pre_fomc_risk` is already listed (day before). The delta is the Mon-Wed span and no adds.
  - Where: `_scan` risk_mult. If `pre_fomc_week_light` and an FOMC date F lies in this Mon-Fri week with `day < F` (or `day == F` and t < 840), apply `risk_mult *= p.pre_fomc_week_mult` and `no_adds=True`.
  - Optional `pre_fomc_week_smt=True`: require `_smt` same-direction agreement (ES and NQ both swept the same side) at the setup.
  - Params:
    - `pre_fomc_week_light: bool = False`
    - `pre_fomc_week_mult: float = 0.5`
    - `pre_fomc_week_smt: bool = False`
  - Test: `test_pre_fomc_week_light`. Mon 2023-09-18 trade has risk_mult 0.5 and no adds.

### 28. N3-post-fomc-thu-fri
- **rule_id / kind:** N3 / unlisted_contradiction. Scope: index. judgment = true.
- **Rule:**
  - 095 (said on the actual day after) says sit still in the Thursday AM after FOMC. 094 (a Monday forecast) expects clean, symmetric Thu/Fri.
  - Default: keep `skip_post_fomc_am` as a test switch.
  - Middle option: allow the Thursday AM only if ES and NQ make same-direction swings in 09:30-10:00. Thursday PM and Friday at normal risk.
  - Note that 095's sit-still was said while viewing FX pairs.
- **Sources:** 094_2AC4IKTj2ug ~00:07:09.
- **Quote:** "expect cleaner price action and symmetry to return back on Thursday and Friday"
- **Conflicts:** 095 (~51:27) sits still on the Thursday AM vs 094.
- **Rulebook fix:** In N3 "Day after", add the 094 counterpoint and the symmetry-gated middle option. List the conflict in D8.
- **BUILD SPEC (news_calendar_times):**
  - Code: `skip_post_fomc_am` (D8/N3.4) is already listed.
  - Add the mode `post_fomc_am: str = "open"`, with values `"open"` / `"skip"` / `"symmetry"`.
  - `"symmetry"`: on `prev_trading_day(day)` being FOMC, block AM entries until both ES and NQ (via `pctx` / `psides`) have taken the same-side 09:30-10:00 swing extreme, with no opposite SMT. Reuse the `_smt` machinery: symmetry = `_smt(...)` returns no divergence and both broke.
  - Test: `test_post_fomc_symmetry`. On Thu 2023-09-21, ES breaks the 09:45 high and NQ does not: blocked. Both break: allowed.

### 29. N3-fomc-whipsaw-skip-london
- **rule_id / kind:** N3 / missing_rule. Scope: general. judgment = true.
- **Rule:** On an FOMC day, flag `fomc_whipsaw` if:
  - 14:00-16:00 (or 14:00-20:00) made moves both above and below the 14:00 price, each ≥ 0.5 x ADR5 [our interpretation]; or
  - the day's range is > 2x ADR5.

  Next day: no London (02:00-05:00) entries. A switch also skips the next NY AM, consistent with N3's "day after: sit still". A one-directional reaction does not fire the filter.
- **Sources:** cc08_006_stK2gNqhLaM ~00:04:37.
- **Quote:** "so just avoid trading London open after fomc events that create whipsaw"
- **Conflicts:** none.
- **Rulebook fix:** Add an N3 bullet: "FOMC whipsaw (both directions after 14:00) means skip the next London open (cc08_006 ~4:37)".
- **BUILD SPEC (news_calendar_times):**
  - Where: `day_context` on `day` where `prev_trading_day(day)` is FOMC. Compute from `hist[-1]` bars 840-960: up = max - px840, dn = px840 - min, and `adr5(hist[-6:-1])`.
  - Tag `fomc_whipsaw` if min(up, dn) ≥ `fomc_whip_frac` x ADR5.
  - `fomc_whipsaw_skip: str = "off"`, with values `"london"` (blocks `sb_london` and any 120-300 window) / `"am"` (also blocks the AM).
  - Params: `fomc_whip_frac: float = 0.5`.
  - Test: `test_fomc_whipsaw_tag`. Synthetic FOMC day +15/-15 with ADR5 20 sets the tag; +30/-2 does not.

### 30. DS2-fomc-only-week-prescan
- **rule_id / kind:** N3 / missing_condition. Scope: general. judgment = false.
- **Rule:** Weekly pre-scan [cc10_008 ~2:23-3:19, bond lesson; the generalization to indices is our reading].
  - If the FOMC day (14:00) also has high-impact USD releases in the NY AM, tag the whole day `high_volatility` (not consolidation). AM trading follows the normal/trending-day rules, and the PM stays blocked per N3.
  - If FOMC is the only high-impact event that day, tag the preceding day(s) and the FOMC-day AM as consolidation. This is already in N3 and N8; just add the explicit tag.
- **Sources:** cc10_008_RgpxhuVp5Xg ~00:02:56.
- **Quote:** "fomc was the only high impact news event then generally we would see a consolidation day leading up to this"
- **Conflicts:** N3 (042 ~3:50; 094 ~1:48), which is consistent.
- **Rulebook fix:** In N3, add the counter-case "FOMC + AM high-impact news = high-volatility day".
- **BUILD SPEC (news_calendar_times):**
  - Code: N3.3 fomc_only tag / `fomc_only_am` are already listed. The delta is the `fomc_hv` tag.
  - Where: `day_context`. If "fomc" in events(day) and `510 in release_times(day)` or `600 in release_times(day)`, tag `fomc_hv`. Otherwise tag `fomc_only`, and the previous trading day gets `pre_fomc_only`.
  - With `fomc_only_am="skip"`, `fomc_hv` days are exempt from the AM skip.
  - Test: `test_fomc_hv_tag`. An FOMC day with 08:30 PPI gives `fomc_hv`.

### 31. DS2-afternoon-fomc-pm-runner
- **rule_id / kind:** N3 / missing_rule. Scope: bonds_only. judgment = false.
- **Rule:** On days with a 14:00 FOMC (or another afternoon release), expect the AM (08:00-12:00) to consolidate and the trend to start in the PM. The PM move may continue into the next session(s) as a runner. The bot is flat by 16:00 (T11), so it only tags the next-session continuation (`pm_runner_next_day`) for study.
- **Sources:** cc10_007_JpV-J31mxhg ~00:05:42.
- **Quote:** "go into a trending environment in the PM session that carries over in what we call a runner"
- **Conflicts:** none.
- **Rulebook fix:** In N3, add the bond note "a trending day can start in the PM alone and carry into the next session [bonds]".
- **Build:** None (bonds_only).

---

## N1/N2: NFP week

### 32. N2-nfp-date-from-calendar
- **rule_id / kind:** N2 / missing_condition. Scope: general. judgment = false.
- **Rule:**
  - nfp_date = the BLS Employment Situation release date, read from a calendar file. Never infer it as the first Friday (example: March 2023 released on Mar 10).
  - NFP week = the Mon-Fri week that contains nfp_date.
  - The N1/N2 blocks key off that date: nfp_date itself, the day before it, and Wednesday after 11:00 in that week.
- **Sources:** 038_4H74nXabvL0 ~00:08:03.
- **Quote:** "typically but not always typically the first Friday of every month"
- **Conflicts:** none.
- **Rulebook fix:** In N2, add "NFP date from the BLS calendar, never the first Friday (038 ~8:03)."
- **BUILD SPEC (news_calendar_times):**
  - Code: already satisfied. `blocked()` uses `JOBS` dates from `calendar.py` (BLS list).
  - Remaining work, a guard only: `test_nfp_week_from_calendar` asserts `blocked(date(2023,3,9),"AM",Params(nfp_week_block=True,nfp_thu=False)) == "nfp_week_thu_fri"` and `blocked(date(2023,3,2),...) is None`.
  - Also handle off-Friday releases (2025-07-03 Thu, 2025-11-20, 2025-12-16): "day before" = `prev_trading_day(nfp_date)`, not weekday 3.
    - Fix: in `blocked()`, replace `d.weekday() >= 3` with `d >= prev_trading_day(jd[0])`.
    - Replace the `nfp_thu` check `d.weekday()==3` with `d == prev_trading_day(jd[0])`.
  - No new Params.

### 33. N2-nfp-wed-after-11
- **rule_id / kind:** N2 / unlisted_contradiction. Scope: index. judgment = true.
- **Rule:** Keep the bot's Wednesday 11:00 cutoff in NFP week (new-trader rule, 101 ~25:12). Add to D8 option B:
  - 101 (~1:28:45-1:29:30), NFP-week Wed Oct 4 2023, live NQ long.
  - Entry in a 5m inefficiency plus order block. Target 14864.00 (2 ticks under the old high).
  - He was stopped once, re-entered in the same direction (X13), and the target was hit near 12:00 ET.
  - Timing comes from price data, not the captions: the re-entry and exit were at or after 11:00.
  - Test nfp_wed_cutoff = 11:00 | 12:00.
- **Sources:** 101_VElIka5sk0E ~01:29:18 (the item's 00:29:18 is wrong).
- **Quote:** "it came back on my stop and then I went right back in again and it ran right to my objective"
- **Conflicts:** N2's 11:00 Wednesday cutoff vs ICT's own trade after 11:00.
- **Rulebook fix:** In D8 option B, add 101 with the corrected timestamp. In N2, keep the cutoff.
- **BUILD SPEC (news_calendar_times):**
  - Where: `blocked()`. Today "nfp_week_wed_pm" fires for session "PM" only, so AM entries after 11:00 are not blocked when `am` ends later.
  - Add `nfp_wed_cutoff: int = 660`. The rule becomes: `if jd and week_block and d.weekday()==2 and (session=="PM" or t >= p.nfp_wed_cutoff)`. Test value 720.
  - Test: `test_nfp_wed_cutoff`. With nfp_week_block, Wed 2023-10-04 t=665 is blocked at 660 and allowed at 720.

### 34. D20-landmine-week-monday
- **rule_id / kind:** D20 / shortened. Scope: index. judgment = true.
- **Rule:** If the week holds two or more high-impact releases (CPI, FOMC, NFP, etc.) on Tue-Fri, Monday is a trading day, exempt from skip_monday. This extends D20's NFP/FOMC exemption (064 ~10:18; there, CPI Tue + FOMC Wed). Ahead of each release, N4/N5 still apply. Do not add a skip-rest-of-week clause from this source.
- **Sources:** 064__YTK5uXBe4o ~00:10:18.
- **Quote:** "This week is littered with landmines ... you want to try to get yourself up on Monday"
- **Conflicts:** N10: new students do not trade Monday.
- **Rulebook fix:** Broaden the D20 exemption from "NFP or FOMC week" to "a week with two or more high-impact releases Tue-Fri" (064 ~10:18).
- **BUILD SPEC (day_week_context):**
  - Where: `blocked()` skip_monday branch. Add the exemption `landmine = sum(bool(events(x) & {"cpi","jobs","fomc","pce","ppi"}) for x in week[1:]) >= p.landmine_min`.
  - Params: `landmine_min: int = 0` (0 = off, test value 2).
  - Test: `test_landmine_monday`. With skip_monday and landmine_min=2, Mon 2023-06-12 (CPI Tue + FOMC Wed) is not blocked.

---

## N7: holidays, seasons, calendar

### 35. N7-post-holiday-am-symmetry
- **rule_id / kind:** N7 / unlisted_contradiction. Scope: index. judgment = true.
- **Rule:**
  - Trigger: the prior session was a holiday, an abbreviated session, or a large-range day.
  - Block AM entries until ES and NQ show symmetry: both make the same-direction short-term swing break, with no divergence. After that, allow normal setups in the remaining AM (090 ~2:07:38).
  - Without symmetry, keep N7's "PM or next day".
  - Leave out the cc09_008 part, which N7 already has. Do not cite 009 as a post-holiday trade unless its date is checked against the calendar.
- **Sources:** 090_bhYcXBI3z9U ~02:07:38.
- **Quote:** "you have to sit on your hands and wait until the market starts showing signs of symmetry"
- **Conflicts:** N7 (090 ~8:00) reads as "no AM trade after a holiday".
- **[our interpretation]** The swing-break definition of symmetry.
- **Rulebook fix:** In N7 "Morning after a holiday", add "AM tradable once ES/NQ symmetry returns (090 ~2:07:38); also applies after abbreviated sessions and large-range days".
- **BUILD SPEC (day_week_context):**
  - Code: N7.2 `skip_post_holiday_am` / `post_holiday_pm_sync` are already listed. The delta is the same-AM symmetry release and the wider trigger.
  - Trigger: `prev_trading_day(day)` follows a holiday (`not is_trading_day(prev_trading_day(day)+1 day)`, i.e. a gap of more than one weekday), OR the prior day is an early close (EARLY_CLOSE set, to be built under N7.1), OR the `big_prev` tag.
  - `post_holiday_am: str = "off"`, with values `"skip"` / `"symmetry"`. The `"symmetry"` gate in `_scan` reuses the item-28 helper `_symmetry_ok(ctx, pctx, i)`.
  - Test: `test_post_holiday_symmetry`. On Tue 2023-01-17, before both indices break the 09:30-09:45 high, entries are blocked; after both break, they are allowed.

### 36. N7-holiday-week
- **rule_id / kind:** N7 / unlisted_contradiction. Scope: index. judgment = true.
- **Rule:**
  - If a US holiday falls early in NFP week (072: Tuesday July 4), expect light volume early in the week and cleaner delivery Thursday (from 00:00 NY) and Friday. This replaces N2's "done by Wed 11:00" for that week: test `nfp_week_thu_fri` off for Thursday, with NFP Friday still under N1/D8.
  - Other holiday weeks (045, Easter week): expect wonky delivery mixed with sudden large moves. Tag "holiday_week" and test reduced size with no pyramiding against normal handling.
- **Sources:** 045_DNi9S3_NA44 ~00:44:04; 072_AKg_r0DIa3k ~00:04:19.
- **Quote:** "because there was a holiday ... cleaner price action on ... Thursday and Friday"
- **Conflicts:** 045 (wonky) vs 072 (cleaner Thu/Fri). N2 is overridden in 072.
- **Rulebook fix:** In N7, replace "Holiday weeks deliver cleaner Thu/Fri" with the NFP-week-with-early-holiday condition, and add the 045 contrast.
- **BUILD SPEC (day_week_context):**
  - Code: N7.3 (holiday_week tag + `holiday_week_thu_fri`) is already listed, with the same tag. The delta is the NFP-week override and the wonky-size test.
  - In `blocked()`: when `nfp_week_block` is on and the week's Mon-Wed contains a holiday (`not is_trading_day(x)` for a weekday x), skip the "nfp_week_thu_fri" return for Thursday.
  - Params:
    - `holiday_nfp_override: bool = False`
    - `holiday_week_mult: float = 1.0` (test value 0.5, with `no_adds` on `holiday_week` days, applied in `_scan`)
  - Test: `test_holiday_nfp_override`. Week of 2023-07-03 (Jul 4 Tue, NFP Fri Jul 7): Thursday Jul 6 is not blocked when the override is on.

### 37. N7-august
- **rule_id / kind:** N7 / shortened. Scope: general. judgment = true.
- **Rule:**
  - Aug 1-31: default skip_august (no new entries).
  - Experienced-profile variant: minimum size, no pyramiding or max leverage, full exit at the first pool (no trailing or runners), only with an obvious draw and a clean shift.
  - New-trader profile: no live trades and no funded challenges in August. Per 084/087, no funded challenges in any summer month (Jun-Aug); wait for the fall.
  - Test switch summer_off (Jun-Aug).
  - Drop "especially the last two weeks".
- **Sources:** 079__NWG_eJRBpU ~00:10:14; 081_0xYpeVRi_qs ~00:22:03; 084_VdGihxSuSRk ~00:28:06; 087_z4GVg3aPnAk ~00:01:56.
- **Quote:** "I want you to think about abstaining not participating in this keep your powder dry"
- **Conflicts:** N7's "especially the last two weeks" vs whole-month in 079/081.
- **Rulebook fix:** In N7, change the August bullet to the whole month, add the experienced variant and the summer funded-challenge note, and delete "especially the last two weeks".
- **BUILD SPEC (day_week_context):**
  - Code: N7.6 `august_risk` / `august_from_day` / `skip_august` are already listed. Change their spec: `august_from_day` should default to 1, not mid-month.
  - Add `august_mode: str = "off"`, with values `"skip"` / `"light"`.
    - `"light"`: risk_mult 0.5, `no_adds`, single exit at T1 (`t1_fixed_all`-style flag), `ladder_trail` off.
  - Add `summer_off: bool = False` (blocks months 6-8 in `blocked()`).
  - Test: `test_august_mode`. 2023-08-01 is blocked with "skip". With "light", the ladder is a single rung.

### 38. B23-seasonal-quality
- **rule_id / kind:** B23 / missing_rule. Scope: general. judgment = true.
- **Rule:** Tag each date with a seasonal quality.
  - "prime" = Sep/Oct 1 to about Dec 10-14 (especially Oct 1-Nov 15), plus Feb 1-May 31.
  - "poor" = August, and about Dec 10 to year end.
  - "off_season" = everything else.
  - Use the tag as a size/participation filter, not as direction. March is reduced while B23 flags it low probability (test both). Report stats by tag.
  - cc10_015 also calls May-Oct less directional, so May overlaps; flag the overlap.
  - The Dec wind-down starts around the second week of December (102).
- **Sources:** 079__NWG_eJRBpU ~00:24:47; 100_GJeEU2oIh24 ~00:29:55; 102_uzPM1CuSSx8 ~00:10:24; cc10_015_rlTl8QKpqCU ~00:04:43.
- **Quote:** "you primarily want to focus on being a Trader from October to the end of the year and from February to May"
- **Conflicts:** B23 lists March low probability vs spring prime (079, cc10_015). The autumn start differs: Sep (079) vs Oct (cc10_015).
- **Rulebook fix:** Add a B23 "delivery quality calendar" paragraph with prime/poor windows and the conflicts.
- **BUILD SPEC (day_week_context):**
  - Code: B23 `seasonal_tag` (direction map) is already listed. This adds a separate quality tag.
  - Where: `day_context` tags `season_prime` / `season_poor` / `season_off`, plus `season_may_overlap` on May dates. Windows: prime = (Sep 1 or Oct 1 per `season_autumn_start`) to Dec 10, plus Feb 1-May 31; poor = Aug and Dec 11-31.
  - Params:
    - `season_quality: str = "off"`, with values `"tag"` / `"size"`. `"size"` sets risk_mult 1.0 / 0.5 / 0.75 [our interpretation].
    - `season_autumn_start: int = 9`
  - `backtest` report: add a by-tag breakdown.
  - Test: `test_season_tags`. 2023-10-16 gives prime, 2023-12-20 gives poor, 2023-07-10 gives off.

### 39. B23-daily-seasonal-review
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** Before each session, check the date against a precomputed per-instrument list of seasonal months (the current month and the coming month). Tag `in_seasonal_window` (direction) and `window_next_month`. Use the tag as HTF context for B23 only, never as a trigger. ICT gives month-level granularity, so finer windows are our interpretation.
- **Sources:** cc05_012_O2Sio7opKxo ~00:13:05.
- **Quote:** "always start your trading day every single day with reviewing a macro perspective like this"
- **Conflicts:** none.
- **Rulebook fix:** In B23, add the daily review routine and the precomputed month list.
- **BUILD SPEC (day_week_context):**
  - Merge into B23 `seasonal_tag`. Add a module constant `SEASONAL_MONTHS = {"ES": {m: dir}}` in `calendar.py`, filled from the B23 map.
  - `day_context` adds tags `season_dir_{+1|-1}` and `season_next_{+1|-1}`.
  - No new switch beyond `seasonal_tag`. Report only.
  - Test: `test_seasonal_month_tag`.

### 40. N7-election
- **rule_id / kind:** N7 / missing_rule. Scope: general. judgment = true.
- **Rule:** Optional filter `skip_election`: in US presidential election years, no new trades from the start of November through about two weeks (the election week and the week after). [our interpretation] Narrow variant: election day plus the following trading day. It can be generalized to major scheduled political events with an uncertain outcome.
- **Sources:** cc04_002_npL3ZXJ5zOU ~00:26:40; cc04_003_PIYh0CxoY9c ~00:32:20.
- **Quote:** "I was on the sidelines the entire first two weeks of November"
- **Conflicts:** none.
- **Rulebook fix:** In N7, add an election bullet marked as ICT's personal practice, not a stated rule.
- **BUILD SPEC (day_week_context):**
  - Where: `blocked()`. Add `ELECTIONS = {date(2020,11,3), date(2024,11,5)}` in `calendar.py`.
  - `skip_election: str = "off"`, with values `"two_weeks"` (Nov 1 to election+9 calendar days) / `"narrow"` (election day and next_trading_day). Returns "election".
  - Test: `test_skip_election`. 2024-11-06 is blocked under both modes; 2024-11-12 is blocked only under two_weeks.

### 41. DS2-holiday-eve-friday-before-tue-holiday
- **rule_id / kind:** N7 / missing_condition. Scope: general. judgment = false.
- **Rule:** skip_holiday_eve skips:
  - (a) the trading day immediately before a US market holiday;
  - (b) the Friday before a week whose Monday or Tuesday is a widely followed US holiday (e.g. July 4 on a Tuesday, with the Monday in between an early-close session) (cc10_019 ~15:20, ~23:45).
  - Optional confirmation [our interpretation]: early-session consolidation with no clear draw.
  - Note that the weekly objective was already met that day too (B17).
- **Sources:** cc10_019_gs3KMgz84yc ~00:23:45.
- **Quote:** "ahead of a weekend ahead of a holiday even though the holidays not Monday not Friday today it's next Tuesday"
- **Conflicts:** none.
- **Rulebook fix:** In N7 "Day before a long weekend/holiday", add case (b) and the Jun 30 2017 example.
- **BUILD SPEC (day_week_context):**
  - Code: N7.1 `skip_holiday_eve` is already listed.
  - Delta: a helper `holiday_eve(d)` that returns True if `not is_trading_day(next weekday)` (case a), or if d is a Friday and the next Monday or Tuesday is a holiday in `DT.HOLIDAYS` (case b).
  - `skip_holiday_eve: str = "off"`, with values `"a"` / `"ab"`.
  - Test: `test_holiday_eve_b`. 2023-06-30 (Fri, Jul 4 Tue) is True for "ab" and False for "a".

---

## N8/B17: day type (chop, consolidation, seek and destroy, ranges)

### 42. N9-objective-before-lunch
- **rule_id / kind:** N9 / wrong. Scope: index. judgment = true.
- **Rule:**
  - If the move toward the daily objective is mostly delivered (the "lion's portion") before the planned entry, take no continuation entry toward it.
  - Once the objective is reached (before or at lunch), PM retracement/reversal setups (the 2:00 macro, M6) targeting the lunch-hour lows (bullish day) or highs (bearish day) are allowed.
  - [our interpretation] The "more than about half" threshold.
- **Sources:** 015_QKvjPltjsqU ~00:16:22 (also 28:39-30:50, 36:29).
- **Quote:** "it had already delivered the lion's portion of the move."
- **Conflicts:** none.
- **Rulebook fix:** In N9, replace "Daily objective done before lunch: skip the rest of the day (015 ~16:22)" with the corrected rule.
- **BUILD SPEC (day_week_context):**
  - Code: N9.3 `objective_done_skip` is already listed. Change its spec: it must block only continuation toward the objective, not the PM.
  - Where: the `run_day` bar loop, using the locked draw (`draw_lock`) as the objective.
    - `objective_frac_gate: float = 0.0` (test value 0.5): if `(price_now - session_open_side) / (draw - session_open_side) > frac` at arm time, cancel continuation entries toward the draw.
    - `objective_done_pm: str = "off"`, with values `"reversal_only"`: after the draw trades before 720, PM entries are allowed only in the counter direction, targeting the lunch low/high (`pm_lunch_target` already exists).
  - Test: `test_objective_done_pm`. Draw hit at 11:20: a PM long is blocked and a PM short to the lunch low is allowed.

### 43. N8-intraday-seek-destroy
- **rule_id / kind:** N8 / missing_rule. Scope: index. judgment = true.
- **Rule:** Flag the session "manipulated / seek_and_destroy" if, early on or by mid-session, price takes a short-term high's buy stops and a short-term low's sell stops in turn, inside a narrow range with no displacement. Then:
  - (a) no 1m entries inside the range;
  - (b) no entry until an MSS leaves an FVG that a later retrace holds (015);
  - (c) any trade exits fully at the first target: no runner, no trailing to a second target (024);
  - (d) after price reaches the pre-marked HTF level, no trade on the reversal off it (024).
  - If no confirmed MSS forms, expect chop all day.
  - [our interpretation] The numeric timing (09:30-10:00) and the narrow-range test.
- **Sources:** 015_QKvjPltjsqU ~00:21:31; 024_gH1e-TVrK6k ~00:19:27.
- **Quote:** "That is a highly manipulated market environment."
- **Conflicts:** none.
- **Rulebook fix:** In N8, add an intraday seek-and-destroy definition and handling (a-d) next to the weekly regime.
- **BUILD SPEC (day_week_context):**
  - Code: the owner #10 chop detector (`sloppy_chop_*`, class at ~2047) already exists.
  - Add `sd_intraday: str = "off"`, with values `"tag"` / `"rules"`.
  - Detector: from 570 to `sd_intraday_until` (default 630), count alternating takes of 1m swing highs and lows (pivot_n) with the session range < `sd_intraday_frac` x ADR5 (default 0.35) and no bar with body ≥ `displacement_mult` x average. Two or more alternations set the flag.
  - `"rules"`, applied in `_scan`:
    - require an FVG hold (`fvg_q_hold`-style: a retrace into the FVG closes without a body through);
    - `t1_fixed_all`-style single exit;
    - cancel entries after the locked HTF level trades (`draw_lock` delivered).
  - Test: `test_sd_intraday_flag`. A synthetic ping-pong 09:30-10:00 sets the flag; a trend day does not.

### 44. N8-seek-destroy-week
- **rule_id / kind:** N8 / wrong. Scope: general. judgment = true.
- **Rule:** Classify the week as Seek & Destroy when:
  - Mon-Wed/Thu consolidates and runs both the running weekly high and low by a small amount; [our interpretation] with no daily close beyond them; AND
  - FOMC or NFP is pending this week, or the month is July or August.

  Then take no trades through the expansion, Friday's included. Watch for Thursday high/medium-impact news (FOMC/employment) to raid one side, then a run beyond all intra-week extremes to a daily or weekly PD array. Only after that array is hit, look for a reversal, which needs a new setup. Scope: CC, general.
- **Sources:** cc07_002_wFjeUzJys7w ~00:07:57; cc07_003_hbE8S5FSdtQ ~00:33:45.
- **Quote:** "it's probably better for you to sit on your hands and just don't trade it"
- **Conflicts:** cc07_002 calls the Friday leg an expansion; cc07_003 expects a reversal after the array. N8 says only "then reversal".
- **Rulebook fix:** In N8, replace "both sides run, then reversal; don't hold trades" with the Mon-Thu shallow-runs definition, the Thursday news raid, the run to a D/W array, and "do not trade it".
- **BUILD SPEC (day_week_context):**
  - Code: N8.6 `sd_week_skip` / `sd_context_required` are already listed. Precise detector delta:
    - In `BT.run` weekly state, track the running weekly H/L. On Wed and Thu, set `sd_week` if both the running H and L were exceeded by ≤ `sd_shallow_frac` x ADR5 (default 0.25 [our interpretation]) with no daily close beyond the prior running extreme, and (week has jobs/fomc, or month in {7,8}).
    - `sd_week_skip=True` blocks the rest of the week via `blocked()` returning "sd_week".
    - `sd_after_array: bool = False`: re-enable after the week's extreme touches a D/W array from `htf._arrays`.
  - Test: `test_sd_week_flag`.

### 45. B17-chop-revert-middle
- **rule_id / kind:** B17 / missing_rule. Scope: index. judgment = true.
- **Rule:** On a day classified as chop (daily sideways for several days, or the DXY regime test says chop):
  - compute the baseline = the midpoint of the range since 08:30 (ICT used the bottom of an old 5m FVG near it);
  - after any run to a pool or FVG, expect a return to the baseline;
  - take profit at the first target, with no runners and no extensions;
  - price above the baseline means the buy-side pool is next, below means the sell-side. This is a lean, not an entry signal.
  - [our interpretation] No runners / first target only.
- **Sources:** 031_8YSVu51hUWQ ~00:19:39.
- **Quote:** "once it goes there it's right back to the middle of the range"
- **Conflicts:** none.
- **Rulebook fix:** In B17, change "range market = scalping market" to add "runs revert to the post-08:30 baseline; above it = buy-side lean (031 ~19:39)".
- **BUILD SPEC (bias_htf):**
  - Code: the B17 `neutral_gate` "range_market" and owner #10 `sloppy_mode="scalp"` exist.
  - Delta: on days tagged range (B17.4 / `sloppy` chop), compute `baseline = (max(h[510:i]) + min(l[510:i]))/2`.
    - `chop_lean: bool = False`: allow only the side toward the pool on the far side of the baseline from price (above the baseline gives longs).
    - `chop_target_baseline: bool = False`: add the baseline as a target rung for counter-moves.
  - Test: `test_chop_lean`.

### 46. B17-range-day-sit-out-am
- **rule_id / kind:** B17 / missing_condition. Scope: index. judgment = true.
- **Rule:** Day type range_bound: the ES daily is inside a multi-day range with no definitive draw, and DXY is not through its key level (031 ~9:20; 032 ~28:53).
  - Expect a lethargic, two-sided 09:30 session.
  - Imbalances formed after the 08:30 move are liquidity-seeking, not setups (032 ~28:00).
  - Pushing the button in it is gambling (031 ~25:16).
  - Bot / new trader: no AM entries; carry the draw into the PM 13:30-16:00 (031 ~35:13).
  - Experienced: small surgical intraday scalps only.
  - [FX-sourced addition, 103 ~18:40 EURUSD] A non-symmetrical market that marks time with small back-and-forth swings is one new students should not risk in.
  - Numeric thresholds are our interpretation.
- **Sources:** 031_8YSVu51hUWQ ~00:35:13; 032_SSWN6YSVyFY ~00:28:53; 103_IU673ZUGuxI ~00:18:40.
- **Quote:** "I'm willing to let go of the first move of the day when it's like this"
- **Conflicts:** B17's "range = scalping market" vs 031/103 (sit out, PM).
- **Rulebook fix:** In B17, add the AM sit-out and PM carry, and list the conflict.
- **BUILD SPEC (bias_htf):**
  - Code: B17.4 `daily_range_regime` tag/scalp/skip is listed. The delta is the AM-only mode.
  - `range_day_mode: str = "off"`, with values `"pm_only"` / `"scalp"`. `"pm_only"` blocks AM/PRE sessions on range-tagged days and keeps the locked draw for the PM (`pm_carry_draw`, T8).
  - Range tag [our interpretation]: the last N=5 daily closes are inside the high-low of the day 6 back, and `htf.table` draw = 0.
  - Test: `test_range_day_pm_only`.

### 47. N8-large-org-day
- **rule_id / kind:** N8 / shortened. Scope: index. judgment = true.
- **Rule:** Flag the day if ORG = |09:30 open - prior RTH close| is large, OR the prior day's range was very large (e.g. a 13:30-16:00 expansion in either direction). On a flagged day:
  - no entries from 09:30 to about 10:15;
  - expect alternating sweeps of the post-open high and low;
  - expect the directional run to begin around 10:45-11:15;
  - preferred window 13:30-16:00.
  - [our interpretation] Proxies: ORG > 0.5x ADR5, or prior-day range > 1.5x ADR5.
- **Sources:** 033_KXx07qzW5u0 ~00:13:51.
- **Quote:** "the morning session can be tricky it can be choppy ... take out buy side take out sell side"
- **Conflicts:** none.
- **Rulebook fix:** In N8, add the two-sided sweep pattern, the ~11:00 run start, and the PM-explosion example.
- **BUILD SPEC (day_week_context):**
  - Code: N8.4 `big_day_am_skip` (AM off, PM kept) is already listed with the same content.
  - Delta only: `big_day_am_resume: int = 0` (test value 645). When set, AM entries are allowed from this minute instead of skipping the whole AM.
  - Proxies: `big_day_org_frac=0.5` and `big_day_prev_mult=1.5`.
  - Test: `test_big_day_am_resume`.

### 48. N8-consolidation-tradeable
- **rule_id / kind:** N8 / unlisted_contradiction. Scope: general. judgment = true.
- **Rule:** Switch `consolidation_mode`, with values "skip" | "range_trade" | "fade_with_htf" | "scalp". Default "skip", as today.
  - "range_trade" (053; cc01_005; cc04_012): on forecast consolidation days or in a multi-leg daily range, only range models:
    - sick sister on the laggard index;
    - turtle soups after a run of an old 4h/daily high or low;
    - OTE sells in premium (62-79% of a clean swing) or buys in discount.

    Target the opposite open FVG or equal highs/lows inside the range. No runners or breakout trades (B14).
  - "fade_with_htf" (cc09_004): trade only on the side of the daily/4H order-flow bias, entering on runs of the range's short-term lows (bullish) or highs (bearish). No HTF bias = no trade.
  - "scalp" (cc10_008, bonds; scale the targets for indices): AM only if the opening range is small; single small target; no runner; done by 11:00. PM only if the AM has not run a stop pool.
  - List the conflict in N8: bullet 1 against 053, cc01_005, cc04_012 and cc09_004.
- **Sources:** 053_VSSwM6rDIg0 ~00:01:13; cc01_005_YuefjnUKQdM ~00:11:01; cc04_012_FgacYSN9QEo ~00:07:57; cc09_004_g7jchu4g31c ~00:20:24; cc10_008_RgpxhuVp5Xg ~00:09:01.
- **Quote:** "that doesn't mean it can't be traded or you can't find setups in it it just means you have to be much more Nimble"
- **Conflicts:** N8 bullet 1 (cc01_001; cc09_003) vs 053, cc01_005, cc04_012, cc09_004 and cc10_008.
- **[our interpretation]** The mode split and the index scaling of the bond tick targets.
- **Rulebook fix:** In N8 bullet 1, change "Consolidation = no trade" to "Consolidation: default no trade; range models, an HTF-bias fade or scalps are alternatives", and list the conflicts.
- **BUILD SPEC (day_week_context):**
  - Code: N8.1 `consol_skip` exists via owner #10 `sloppy_mode`, with stand_aside/scalp. N8.3 `consol_day_rules` is listed.
  - Add `consolidation_mode: str = "skip"`, mapped onto existing machinery:
    - `"skip"` = `sloppy_mode="stand_aside"`.
    - `"scalp"` = `sloppy_mode="scalp"`, plus `am_exit=660` on those days.
    - `"range_trade"` enables only `sick_sister`, `turtle_soup`, `ote` setups on consol days, and drops targets beyond the consolidation range high/low.
    - `"fade_with_htf"` requires `htf.table` bias ≠ 0 and enables `turtle_soup` with that side only.
  - Test: `test_consolidation_mode_routes`. A consol-tagged day with "fade_with_htf" and bias +1 gives only long turtle-soup orders.

### 49. N8-consolidation-builds-orders
- **rule_id / kind:** N8 / missing_condition. Scope: general. judgment = true.
- **Rule:** While in a consolidation, no entries in skip mode. Mark the range high and low as buy-side and sell-side pools (L1).
  - The next leg will be an impulsive expansion out of the range, never a retracement or reversal straight out of the consolidation (cc01_002 ~17:28-18:30).
  - After the expansion, expect either a retracement to the order block it left (then continuation) or a reversal.
  - Take the direction from the HTF premise. A false run of the opposite extreme is the manipulation.
  - Trade only after the expansion has printed.
- **Sources:** cc01_002_XwYYWBttWro ~00:17:28.
- **Quote:** "the market makers will allow orders to build up above and below the range"
- **Conflicts:** none.
- **Rulebook fix:** In N8, add "the consolidation range edges = the pools for the coming expansion".
- **BUILD SPEC (levels_detectors):**
  - Where: DayCtx pool construction. When the chop detector (owner #10 class) releases, add the chop range high/low as named pools `consol_h` / `consol_l` (eligible as sweep pools and targets).
  - Params: `consol_pools: bool = False`.
  - Test: `test_consol_pools`. After the chop releases upward, `consol_l` is in the sell-side pools.

### 50. N8-expansion-day-conditions
- **rule_id / kind:** N8 / missing_condition. Scope: general. judgment = true.
- **Rule:** Flag expansion_due only when all of these hold:
  - the prior day's range < ADR5 (several sub-ADR5 days strengthen it);
  - a daily bias exists;
  - none of the cc08_006 avoidance filters fired;
  - the session profile (lesson 5: manipulation, then expansion) is unfolding in the bias direction.

  The expected day range is then ~1.5-2x ADR5. [our interpretation] Measuring targets from the manipulation extreme. Sub-ADR5 days alone are common in quiet periods and do not predict expansion.
- **Sources:** cc08_006_stK2gNqhLaM ~00:24:37.
- **Quote:** "it has yet to trade above the average daily range on a five-day basis the previous day and you're bullish"
- **Conflicts:** none.
- **Rulebook fix:** In N8, make "prior day under ADR5: expansion due" conditional on the four items.
- **BUILD SPEC (day_week_context):**
  - Code: N8.5 `expansion_due` tag / `expansion_targets` / `adr_basis` is listed. The delta is the conditions.
  - The tag fires only if `hist[-1]` range < `adr5(hist[-6:-1])`, `htf.table` bias ≠ 0, no `sloppy_day` reason, no `big_prev`, no `three_*`, and (at arm time) the day's manipulation leg (the `_judas` flag) is opposite the bias.
  - `expansion_targets` then adds a rung at the manipulation extreme ± 1.5 x ADR5.
  - Test: `test_expansion_due_conditions`.

### 51. N8-middle-of-range
- **rule_id / kind:** N8 / missing_rule. Scope: general. judgment = true.
- **Rule:** When the daily chart is in a consolidation (range-bound within the last 60 trading days), divide the range into premium/discount quadrants.
  - Avoid short-term trades in the middle of the range unless the directional bias and the liquidity draw (where the buy and sell stops are) are clearly defined.
  - Prefer shorts from the upper premium quadrant and longs from the lower discount quadrant, using PD arrays not yet traded to.
  - [our interpretation] The middle band definition (e.g. 3/8-5/8 of the high-low range).
- **Sources:** cc07_005_y0lVKWLsZeM ~00:23:47.
- **Quote:** "if you're trading in the middle of the range like this and you're not strong in your directional bias ... you're going to get chopped up a lot"
- **Conflicts:** none.
- **Rulebook fix:** In N8 (or B21), add the middle-of-range filter and cite cc07_005.
- **BUILD SPEC (bias_htf):**
  - Code: B21 `ipda_eq_day` / `ipda_eq_frac` exist (the range-day-at-EQ rule).
  - Add `ipda_mid_skip: bool = False`. Using the 60-day IPDA high/low (`ipda_pools`), if the prior close is in [lo + 0.375R, lo + 0.625R] and (`htf.table` bias == 0 or the locked draw is None), skip the day. Otherwise allow longs only in the lower quadrant and shorts only in the upper quadrant (`ipda_quadrant_side`).
  - Test: `test_ipda_mid_skip`.

### 52. new-skip-high-resistance
- **rule_id / kind:** new / missing_rule. Scope: index. judgment = true.
- **Rule:** Experienced-preference switch skip_high_resistance (default off; tag first).
  - High resistance = slow delivery: price heads toward the target but retraces a lot, consolidates and goes sideways instead of running quickly from one pool or PD array to the next (036 ~40:30, ~1:20:40-1:22:00).
  - Proxy: many overlapping swings or opposing FVGs between entry and target, or little displacement in the first 20-30 min of the session.
  - ICT opts out of these conditions. New students study them and do not trade them. They can still be traded profitably.
  - If traded, use the 80/20 ladder (D13, 036) and small targets.
  - The pre-testimony and pre-news context is already handled by N5.
- **Sources:** 036_n37ozsUreR0 ~00:39:59.
- **Quote:** "those conditions I opt out of I don't want to participate in those things"
- **Conflicts:** none.
- **Rulebook fix:** In L4/B17, add a day-level "high-resistance opt-out (experienced preference)" with the delivery-speed definition.
- **BUILD SPEC (targets_partials):**
  - Code: L4 `pool_rank` / resistance count is listed.
  - Add `skip_high_resistance: str = "off"`, with values `"tag"` / `"skip"`.
  - Proxy computed at arm time in the `_scan` target merge: count opposing open FVGs (`opposing()`) plus 1m swing pivots between entry and the locked draw. If ≥ `hr_max_obstacles` (default 3 [our interpretation]), tag `high_res`.
  - `"skip"` cancels the order. `"tag"` forces `ladder_fracs_slow`.
  - Test: `test_high_resistance_tag`.

### 53. DS2-contraction-precedes-expansion
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = false.
- **Rule:**
  - If day D is tagged consolidation_day (calendar predictors per N8, or realized range < ADR5), tag the next high/medium-impact news day within D+1..D+2 as expansion_candidate (cc10_008 ~17:40). Prefer the news day; ICT identifies it from the calendar.
  - Small or contracting ranges by themselves are not a reason to scalp. Trade small ranges only when expansion or volatility is expected (news, kill zone) (cc09_007 ~22:04-22:37).
  - [our interpretation] Draw selection and full-target management on expansion days follow the normal draw rules.
- **Sources:** cc10_008_RgpxhuVp5Xg ~00:17:40; cc09_007_-oMtfDvc18Y ~00:22:37.
- **Quote:** "we should immediately note the next trading day or the day not long after it will produce a large range day"
- **Conflicts:** none.
- **Rulebook fix:** In N8/B11, add "consolidation day, then the next news day = expansion candidate" and the "no scalping small ranges without expected volatility" caveat. Line ~1305 should be reconciled.
- **BUILD SPEC (day_week_context):**
  - Where: `day_context`. If `hist[-1]` (or `hist[-2]`) range < ADR5 or was tagged consol, and `release_times(day)` has an entry in 510-600, tag `expansion_candidate`.
  - With `expansion_mode="full"`: no `ladder_fracs_slow` on that day, and `po3_runner` allowed.
  - Params: `expansion_mode: str = "off"`, with values `"tag"` / `"full"`.
  - Test: `test_expansion_candidate`.

### 54. DS2-trending-day-direction
- **rule_id / kind:** N8 / missing_condition. Scope: general. judgment = true.
- **Rule:** Trending-day long [cc10_009 ~1:17-2:46, ~4:15]:
  - (1) the previous daily range is small compared with the last few days [our threshold: smallest of the prior 3-5], OR ranges have contracted over a series of days;
  - (2) those small-range days have recently traded down into a daily discount PD array;
  - (3) the daily PD-array matrix and institutional order flow point higher (premium array / buy-side as the draw);
  - (4) high/medium-impact USD news at 08:30.

  Expect a large-range expansion from discount toward premium. Shorts mirror this. Restricting to one direction that day is our interpretation.
- **Sources:** cc10_009_S0ouOvtjV2I ~00:04:15.
- **Quote:** "we know that PDA rate Matrix and institutional order flow is suggesting a directional bias"
- **Conflicts:** none.
- **Rulebook fix:** In N8's trending-day recipe, add the direction rule, the matrix/IOF alignment and the comparison basis.
- **BUILD SPEC (day_week_context):**
  - Code: N8.2 `trend_recipe` tag/only/side is listed. The delta is the direction rule:
    - side = +1 if any of `hist[-3:]` lows touched a daily discount array (`htf._arrays` "D" bullish FVG/OB below the 60-day EQ) and `htf.table` draw = +1;
    - mirror for -1;
    - "small" = `hist[-1]` range is the min of `hist[-5:]`, or ranges are monotonically decreasing over 3 days.
  - `trend_recipe="side"` blocks the other side.
  - Test: `test_trend_recipe_side`.

---

## N9/N10: in-day conditions and day of week

### 55. N10-friday-preopen-delivered
- **rule_id / kind:** N10 / missing_condition. Scope: general. judgment = true.
- **Rule:** On Friday, if all of these hold:
  - (a) most of the expected move was delivered before 09:30;
  - (b) the index has reached its intraday/HTF objective or is right at it;
  - (c) an SMT failure prints there (DXY fails to confirm the index extreme);
  - (d) the time is approaching NY lunch;

  then take no new continuation entries and no PM trade toward a further objective. Expect consolidation or a retrace against the move into the close (035 ~39:24).
- **Sources:** 035_kFIOp8Tprdc ~00:39:24.
- **Quote:** "more likely for the market to enter a consolidation or retrace"
- **Conflicts:** N9 (022): a draw delivered pre-09:30 sends you to the PM.
- **[our interpretation]** "Most of the move" and the lunch timing as thresholds.
- **Rulebook fix:** In N10 Friday, add this rule and list it as a conflict with N9.2 (022).
- **BUILD SPEC (day_week_context):**
  - Code: N9.2 `pre_draw_pm` is listed.
  - Add `fri_delivered_stop: bool = False`. On Fridays, if the locked draw was delivered before 570 (`eve_draw` columns from N9.2), and an SMT at that extreme exists (`_smt` with `smt_entry_syms`; DXY data permitting, otherwise NQ/YM), block continuation-side entries after 660 and all PM entries toward a new draw. Counter-side PM entries are left to `pm_reversal`.
  - Test: `test_fri_delivered_stop`.

### 56. N10-friday-pool-choice
- **rule_id / kind:** N10 / missing_condition. Scope: general. judgment = true.
- **Rule:** On Friday, when price has already run a nearby sell-side pool and sits under unrun buy-side (session or overnight high), favour a long toward the buy-side and do not use the remaining REL below as the draw.
  - If Mon-Thu trended in one direction, expect a choppy Friday: allow a trade only to the nearest pools in the trend direction (equal highs or a short-term high), with no target beyond the week's extreme. Afterwards, expect a run on the opposite side (sell-side under REL).
  - No runners and no new-extreme targets.
  - Overlap with M14 TGIF: after a trending week, M14 expects a 20-30% retrace, while cc04_011 expects a choppy run of the nearby buy stops and then the sell stops under REL, with no new weekly extreme. cc04_011 is FX (DXY). Treat as discretionary context and tag it.
- **Sources:** 096_tjnir-o4rsQ ~00:06:54; cc04_011_Gnw54f9v6SA ~00:18:05.
- **Quote:** "because it's Friday it's likely to see it run up against buy stops"
- **Conflicts:** overlaps M14 TGIF.
- **Rulebook fix:** In N10 Friday, add the pool-choice note and cross-reference M14.
- **BUILD SPEC (day_week_context):**
  - Code: N10 `friday_first_pool` is listed.
  - Spec: on Fridays with `friday_first_pool=True`, `draw_lock_pick` is overridden. If the session's sell-side pool (overnight low / REL nearest) has already been taken before the lock, lock the nearest unrun buy-side pool (mirror for bearish), and cap targets at the week's high/low.
  - If `tgif_*` is tagged, use a single exit (no runner).
  - Test: `test_friday_first_pool`.

### 57. N10-monday-weekly-extreme
- **rule_id / kind:** N10 / unlisted_contradiction. Scope: general. judgment = true.
- **Rule:** Bearish week (bullish is the mirror):
  - The weekly-high candidates are Mon, Tue, Wed in order. Start by assuming Monday is the high and sell only a small piece above it, keeping leeway for a Tue/Wed higher high.
  - Mondays are normally small range.
  - Exception: if Monday (or the Sunday-open-to-Frankfurt range checked at 00:00 NY, an FX context) is a large-range move into a daily premium (discount) PD array, anticipate Monday as the weekly high (low) and watch Monday London.
  - Thresholds for "large" (e.g. a fraction of ADR5) are our interpretation.
  - Record as a conflict with N10/D20 "skip Monday".
- **Sources:** cc07_008_LBlK6JB0QS0 ~00:29:09; cc08_001_-cXnnHjy9s0 ~00:20:18, ~00:33:18.
- **Quote:** "if Monday is a big range day and we trade up into a premium relative to the Daily then we can really anticipate that being the high of the week"
- **Conflicts:** N10 / cc12_003 "let Monday go" vs cc07_008 / cc08_001.
- **Rulebook fix:** In N10 Monday, add the large-range-Monday exception and list the conflict in D20.
- **BUILD SPEC (day_week_context):**
  - Code: D20 `monday_small_range` and N10 `monday_mode` are listed.
  - Add `monday_mode="big_into_array"`. Trade Monday only if the 00:00-09:30 range ≥ `mon_big_frac` x ADR5 (default 0.5 [our interpretation]) and the overnight extreme touched a daily PD array (`htf._arrays` "D") in the direction against the weekly bias. Only the weekly-bias side is allowed, at `risk_mult` 0.5.
  - Tag Monday's extreme as `wk_ext_candidate` for the T14 study.
  - Test: `test_monday_big_into_array`.

### 58. N10-thursday-caps-week
- **rule_id / kind:** N10 / shortened. Scope: general. judgment = true.
- **Rule:** The weekly range is usually completed (capped) by Thursday's NY session. A Thursday London trade in the weekly direction may fizzle, and the week may reverse in Thursday NY or the London close (10:00-12:00). Practical handling [our interpretation]: bank Thursday London positions by early NY, and treat a Thursday NY new weekly extreme into a daily PD array as a candidate weekly high/low.
- **Sources:** cc08_001_-cXnnHjy9s0 ~00:21:59.
- **Quote:** "usually the weekly range is again capped by Thursday's New York session"
- **Conflicts:** none.
- **Rulebook fix:** In N10 Thursday, add "the weekly range is usually capped by Thursday NY (cc08_001 ~21:59)".
- **BUILD SPEC (management_exits):**
  - Where: the `run_day` management loop. On Thursdays with `thu_cap=True`, positions entered before 570 (sb_london / pre models) are closed at 600 [our interpretation]. In `_scan`, a new weekly extreme made on Thursday 570-720 that touches a daily array blocks further weekly-direction entries that day.
  - Tag `thu_week_ext`.
  - Test: `test_thu_cap`.

### 59. N10-weekly-template
- **rule_id / kind:** N10 / missing_rule. Scope: general. judgment = false.
- **Rule:** Bullish week (HTF bullish, plus optional seasonal/COT/intermarket support; point of origin and weekly/monthly premium target defined in advance):
  - (1) an impulse up Sun/Mon-Wed;
  - (2) a retracement within Mon-Wed;
  - (3) during it, price trades into a monthly/weekly/daily/4h/1h discount PD array, which is where to buy;
  - (4) hold for the expansion to the premium array.

  Bearish is the mirror. [our interpretation] No Mon-Wed retracement into a discount array means skip the week. The execution timeframe and kill-zone timing are not given here.
- **Sources:** cc07_001_mQA8jCem9d0 ~00:27:49.
- **Quote:** "we're looking for a market that rallies higher than retraces and this is going to occur Monday through Wednesday"
- **Conflicts:** none.
- **Rulebook fix:** In N10, add the weekly template paragraph. It is out of scope per M17 except as a statistic.
- **BUILD SPEC (day_week_context):**
  - Study only, in a new `study_week.py`, the T14 study listed in rule_coverage. Per week:
    - impulse = the Mon-Wed max excursion in the weekly-bias direction;
    - retrace_into_array = whether a Mon-Wed low touched a 1h-or-higher discount array (`htf._arrays`);
    - expansion = whether Thu/Fri exceeded the Mon-Wed high.
  - Report hit rates. No engine switch until the study holds.
  - Test: `test_study_week_template_fields`.

### 60. N10-mon-wed-range-break
- **rule_id / kind:** N10 / shortened. Scope: general. judgment = false.
- **Rule:** Mon-Wed range = the high/low from Monday's open (optionally Sunday's open) through Wednesday.
  - With bullish HTF bias, an intra-week (Thu/Fri) break above the Mon-Wed high confirms the buy program: expect aggressive expansion to the predefined weekly/monthly premium array.
  - Bearish: a break below the Mon-Wed low. Only the bias-side break counts.
  - If the target is not reached that week, keep the same bias for the next week.
  - [our interpretation] Hold or add with the bias; no counter-bias trades.
- **Sources:** cc07_001_mQA8jCem9d0 ~00:44:15.
- **Quote:** "if that is broken on an intra-week basis that is confirmation that you are an aggressive sell-off"
- **Conflicts:** none.
- **Rulebook fix:** In N10, add the bias-side condition, the Monday-open anchor and the carry-over to the next week.
- **BUILD SPEC (day_week_context):**
  - Code: N10.3 `pool_mon_wed`, mw_break tags and `thu_fri_break` are listed. The delta: `thu_fri_break` counts only when the break side equals `htf.table` weekly bias. Add `mw_carry: bool = False`, which keeps the weekly bias into the next week when the week's target (locked weekly draw) is not reached by Friday's close.
  - Test: `test_mw_break_bias_side`.

### 61. T14-tuesday-weekly-extreme
- **rule_id / kind:** T14 / missing_rule. Scope: general. judgment = true.
- **Rule:** Bullish (weekly bias bullish):
  - Mark the nearest HTF discount array: an old M/W/D low to run, a broken old M/W/D high retested as support, or an M/W/D/4h bullish OB.
  - If Monday fails to reach it, expect Tuesday London open and/or NY to drive into it and form the week's low. NY may undercut the Tuesday London low and still make the week's low.
  - Target a premium PD array on a lower timeframe than the entry array, overlapping a 1.27/1.68 extension or a 100% symmetrical swing. The week's high is expected by Thursday NY (may carry into Friday).
  - Bearish mirror: Tuesday rises into an HTF premium array to form the week's high.
  - [our interpretation] Session clock times, stop placement, no counter-trades.
  - Tag weekly_profile tue_low/tue_high.
- **Sources:** cc07_002_wFjeUzJys7w ~00:01:10, ~00:01:52, ~00:02:33; cc07_003_hbE8S5FSdtQ ~00:02:58.
- **Quote:** "then drops into a higher time frame discount array on Tuesday to form the low of the week"
- **Conflicts:** none.
- **Rulebook fix:** In T14, add the profile conditions. Out of scope per M17 except as statistics.
- **BUILD SPEC (day_week_context):**
  - In the `study_week.py` T14 study:
    - tue_low = the week's low printed Tue AND Monday's low > the nearest HTF discount array AND the Tuesday low touched it;
    - record whether NY undercut London (Tue 120-300 vs 570-720);
    - record whether the week's high printed by Thu 720.
  - Then `tue_week_extreme` (already listed): on Tuesdays with bullish weekly bias and the array untouched by Monday, enable longs only, with the stop beyond the array.
  - Test: `test_study_week_tue_low`.

### 62. T14-wednesday-weekly-extreme
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** Bullish: weekly bias bullish; neither Monday's nor Tuesday's low reaches the nearest HTF discount array (Mon and Tue may both close down, or Monday makes a short-term low and Tuesday trades up).
  - Expect Wednesday London and/or NY to drive into the array (old M/W/D low sell stops, a broken-high retest, an M/W/D bullish OB) and form the week's low. Wednesday NY may undercut the Wednesday London low once; the week's low is the lower of the two.
  - After the sell stops are taken, go long. Target the lower-TF premium array overlapping 1.27/1.68 of the Tue-Wed swing, reached Thursday or preferably Friday.
  - Bearish mirror: Wednesday runs a short-term or old high (buy stops) into an HTF premium array, with the projection anchored from the Tuesday low to the Wednesday high.
  - Tag "wed_low"/"wed_high".
- **Sources:** cc07_002_wFjeUzJys7w ~00:03:01, ~00:03:57; cc07_003_hbE8S5FSdtQ ~00:14:58.
- **Quote:** "then drops into the higher time frame discount array on Wednesday to form the low of the week"
- **Conflicts:** none.
- **[our interpretation]** The min(London, NY) rule.
- **Rulebook fix:** Add a T14 Wednesday profile paragraph (stats only per M17).
- **BUILD SPEC (day_week_context):**
  - Extend the `study_week.py` profile classifier with `wed_low` / `wed_high` (Mon and Tue lows above the nearest HTF discount array; the Wed low touches it and is the week's low).
  - Optional switch `wed_week_extreme: bool = False`, mirroring `tue_week_extreme`.
  - Test: `test_study_week_wed_low`.

### 63. new-consolidation-thursday-reversal
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** Bullish: weekly bias bullish; Mon-Wed is a consolidation ([our interpretation] range ≤ ~1.5x ADR5 and no daily close beyond the prior week's range); the HTF discount array below is not yet reached.
  - Thursday: an 08:30 employment release or a 14:00 FOMC/rate release drives price below the Mon-Wed low (a turtle-soup false break) into the array, then it reverses. The Thursday low = the week's low.
  - Target the buy stops above the intra-week high, Thursday into Friday.
  - Experienced-only entry: after the knee-jerk, a very small limit buy below the Mon/Tue low.
  - The bot default keeps N3 (no entries 14:00-14:45) and N2.
  - Bearish is the mirror. Tag "thu_reversal"/"thu_reversal_bear".
- **Sources:** cc07_002_wFjeUzJys7w ~00:04:51, ~00:05:41; cc07_003_hbE8S5FSdtQ ~00:24:47.
- **Quote:** "consolidation Monday through Wednesday then price runs the entry week low and rejects it forming a market reversal"
- **Conflicts:** cc07_003's small FOMC knee-jerk entry vs N3. Thursday employment-release trading vs N2.
- **Rulebook fix:** Add a T14/N10 Thursday-reversal profile and list the conflicts.
- **BUILD SPEC (day_week_context):**
  - Code: N10.3 thu_reversal tag is listed. Precise tag:
    - Thursday;
    - the Mon-Wed range is ≤ 1.5x ADR5;
    - Thursday trades below the Mon-Wed low by ≥ 1 tick, then closes above it, with a release (510 or 840) on Thursday.
  - Optional `thu_reversal_trade: bool = False`: a `turtle_soup` long variant with the Mon-Wed low as the pool, valid only after the N3/N5 waits.
  - Test: `test_thu_reversal_tag`.

### 64. new-consolidation-midweek-rally
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = false.
- **Rule:** Bullish: weekly bias bullish; the last swing rallied from an HTF discount array and the HTF premium target is not yet reached; price paused with no bearish reversal price action [concrete test = our interpretation].
  - Monday rallies. The Mon or Tue short-term high is the fulcrum.
  - Tue-Wed retrace into a discount FVG / liquidity void / bullish OB.
  - A high/medium-impact release is expected Wednesday in London or NY. ICT states it as a precursor; treating its absence as invalidating the template is our interpretation.
  - Buy the discount array. Target an M/W/D premium array overlapping 1.27/1.68 of the fulcrum-to-entry swing, using a lower timeframe than the entry array (or a measured swing projection).
  - Price runs the intra-week high and expands into Friday.
  - Bearish mirror (midweek decline; can occur Tuesday).
  - Out of scope per M17 except as a tag or statistic: "midweek_rally"/"midweek_decline".
- **Sources:** cc07_002_wFjeUzJys7w ~00:06:40, ~00:07:20; cc07_003_hbE8S5FSdtQ ~00:26:43.
- **Quote:** "you're expecting on Wednesday a high or medium impact news event either in London or in New York session"
- **Conflicts:** none.
- **Rulebook fix:** Add to T14 as a stats-only profile.
- **BUILD SPEC (day_week_context):**
  - Add to the `study_week.py` classifier: `midweek_rally` = Monday up close, Tue-Wed low inside a bullish FVG/OB (`htf._arrays` 1h+), a Wednesday release in `release_times`, the week closing above the Mon/Tue high.
  - Report frequency and the Thu/Fri expansion rate. No engine switch.
  - Test: `test_study_week_midweek_rally`.

### 65. new-wednesday-weekly-reversal
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** Bullish: weekly bias bullish; the market is at a long-term or intermediate-term low; Mon-Tue consolidate.
  - Wednesday drives lower into an HTF discount array to run sell stops (the Mon-Tue lows [our reading]), then reverses strongly.
  - The Wednesday low is expected to be the weekly low. Target opposing liquidity into Friday.
  - Bearish mirror at a long-term/intermediate-term high: a Wednesday buy-stop raid into an HTF premium array, then a strong reversal.
  - Out of scope per M17 except as a tag or statistic: "wed_weekly_reversal".
- **Sources:** cc07_002_wFjeUzJys7w ~00:09:09, ~00:09:43.
- **Quote:** "consolidating Monday through Tuesday and drives lower into a higher time frame discount array to induce sell stops than strongly reverses"
- **Conflicts:** none.
- **Rulebook fix:** Add to T14 (stats only).
- **BUILD SPEC (day_week_context):**
  - Add to the `study_week.py` classifier: `wed_weekly_reversal` =
    - Mon-Tue range ≤ ADR5 [our interpretation];
    - Wed trades below the Mon-Tue low into an HTF discount array;
    - Wed closes in the top third of its range;
    - Wed low = the week's low.
  - Stats only.
  - Test: `test_study_week_wed_reversal`.

### 66. DS2-monday-ideal-day
- **rule_id / kind:** N10 / unlisted_contradiction. Scope: general. judgment = false.
- **Rule:**
  - The primary day-trade days are Mon, Tue and Wed, in the HTF/daily institutional-order-flow direction (cc08_007 ~7:17, ~21:02; cc09_007 ~22:37; cc09_008 ~55:20; cc12_004 ~6:30).
  - Add these to D20 option B and list the conflict with cc12_003 ~15:40 "let Monday go", 065B ~4:12 and 101 ~30:53.
  - Thu/Fri: use the late-week templates only when the Mon-Wed move fails (cc12_004).
  - Test `days=Mon-Wed` vs `skip_monday`.
- **Sources:** cc08_007_5Z_3NbclMSY ~00:07:17, ~00:21:02; cc09_007_-oMtfDvc18Y ~00:22:37; cc09_008_cqf8nH54bb8 ~00:55:20; cc12_004_Oec_0NM_OeY ~00:06:30.
- **Quote:** "the ideal days of the week buying are Monday Tuesday and Wednesday"
- **Conflicts:** cc12_003 ~15:40, 065B ~4:12 and 101 ~30:53 vs the four CC lessons.
- **Rulebook fix:** In N10, add the CC Mon/Tue/Wed sources. In D20 option B, add the four citations and the conflict.
- **BUILD SPEC (day_week_context):**
  - Add `days_mode: str = "all"`, with values `"mon_wed"` (block Thu/Fri unless `late_week_fallback` from item 67 fires) / `"tue_wed"`.
  - Where: `blocked()`, returning "days_mode".
  - Test: `test_days_mode_mon_wed`. A Thursday is blocked and a Monday is allowed.

### 67. DS2-mon-wed-fallback-thu-fri
- **rule_id / kind:** N10 / missing_rule. Scope: general. judgment = true.
- **Rule:** With HTF bias set before the week (Sunday open checked for a gap), expect the bias-direction move Mon-Wed. If it does not materialize (or the bias was wrong), switch to the late-week (Thu/Fri) templates and weekly profiles, chosen with that week's economic calendar. [our interpretation] The Wednesday-close cutoff. Conflicts with N2's "nothing by Wed 11:00 = week done" in NFP weeks.
- **Sources:** cc12_004_Oec_0NM_OeY ~00:06:30.
- **Quote:** "then I'm going to be focusing on Thursday and Friday templates"
- **Conflicts:** N2 (NFP week done if nothing by Wed 11:00).
- **Rulebook fix:** In N10, add the fallback and list the N2 conflict.
- **BUILD SPEC (day_week_context):**
  - In `BT.run` weekly state: `mw_delivered` = by Wed close, the week moved ≥ 1x ADR5 [our interpretation] in the weekly-bias direction from the Monday open.
  - `late_week_fallback: bool = False`: with `days_mode="mon_wed"`, Thu/Fri are unblocked only if `mw_delivered` is False, and are tagged `late_week`.
  - Test: `test_late_week_fallback`.

### 68. DS2-weekly-template-sequence
- **rule_id / kind:** T14 / missing_rule. Scope: general. judgment = true.
- **Rule:** Bullish week (daily IOF bullish), with the discount array for the weekly low (the buy level) defined in advance:
  - Mon: long only if a Monday-low setup is evident.
  - Tue: if the Monday low is not in, look for the Tuesday low of the week. Tuesday may "dilly-dally". If Tuesday rallies before reaching the buy level, do not chase; keep the limit order.
  - Wed: if Wednesday trades lower into the buy level (a lower low than Tuesday), that is the expected weekly low, so enter there. If Tuesday already closed up, Wednesday is a buy day.
  - Expansion runs from the second half of Tuesday through Wednesday into the first half of Thursday. Longs are allowed until Thursday's NY open. The weekly high is expected by about Thursday noon. After that, no new longs.
  - Friday is a retracement: no longs if Thursday closed higher.

  Bearish week: the weekly high forms Tuesday; shorts Tue-Wed; the weekly low forms at or around Thursday's NY open; Monday and Friday are consolidation (weekly PO3 open/close). That Mon/Fri consolidation applies to the bearish template only; the bullish template allows a Monday low. ICT calls these default assumptions, not certainties. Tag/stats only, per M17.
- **Sources:** cc09_008_cqf8nH54bb8 ~00:41:53; cc12_003_3B7Reg2Yiqs ~00:14:19, ~00:08:45.
- **Quote:** "I internalized the Tuesday creating the high of the week and Thursdays New York open creating the low of the week"
- **Conflicts:** none (the Monday "conflict" was a misreading; see the corrected rule).
- **[our interpretation]** Clock times for "Thursday NY open" (08:30-11:00).
- **Rulebook fix:** In T14, add the bullish and bearish templates and the Wednesday-low variant (stats only).
- **BUILD SPEC (day_week_context):**
  - Add to the `study_week.py` classifier: the weekday/session of the weekly high and low vs the weekly bias (session buckets London 120-300, NY 510-660, PM 810-960). Report the bearish "Tue high + Thu NY low" and bullish "Mon/Tue/Wed low, high by Thu 720" rates.
  - Engine switch `no_long_after_thu_noon: bool = False`: with weekly bias +1, block new weekly-direction entries after Thu 720 and on Friday if Thursday closed up. This overlaps the listed N10.4 `no_fri_after_strong_thu`; implement both as one switch.
  - Test: `test_no_long_after_thu_noon`.

### 69. DS2-tue-to-thu-horizon
- **rule_id / kind:** N10 / shortened. Scope: general. judgment = true.
- **Rule:** Swing within the week: skip the Monday entry.
  - Tuesday: take an OTE retrace referenced to Monday's low. If Tuesday does not fill, take Wednesday off Tuesday's low.
  - The aim is the Tuesday-to-Thursday leg, held into Thursday's NY open. He does not try to catch the weekly low itself.
  - [our interpretation] OTE = 62-79% of the Monday-low-to-swing-high leg, stop below Monday's low, Thursday NY open = 08:30-11:00.
  - Bearish is the mirror. This complements N10's Tue/Wed-ideal bullet; there is no contradiction.
- **Sources:** cc12_003_3B7Reg2Yiqs ~00:15:56.
- **Quote:** "if I can get Tuesday's action into Thursday's New York open then I got it"
- **Conflicts:** none.
- **Rulebook fix:** In N10's "let Monday go" bullet, add the OTE entry type and the Thursday NY open horizon.
- **BUILD SPEC (day_week_context):**
  - Code: N10.2 `tue_off_monday` is listed. The intraday bot cannot hold across days (T11 flat by the close), so the horizon becomes a study field.
  - Engine part: `tue_off_monday` uses the existing `ote` setup with the leg anchored at Monday's low (from `hist[-1]` when today is Tuesday) and the stop below Monday's low.
  - Study part: measure the Tue-entry-to-Thu-11:00 excursion in `study_week.py`.
  - Test: `test_tue_off_monday_anchor`.

### 70. DS2-weekend-first-driver
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** [CC, discretionary; test as a statistic only] At the weekend, list the week's high/medium-impact releases by day and session (London/NY).
  - Hypothesis: when the calendar is quiet until the first major driver, the weekly extreme against the bias tends to form at that driver's session (e.g. a Tuesday NY-open reversal that starts the weekly range), and the days before it are slow.
  - Re-evaluate daily. ICT stresses this is not systematic (~60% confidence after Monday).
- **Sources:** cc12_003_3B7Reg2Yiqs ~00:18:01.
- **Quote:** "there's going to be a slow start to the week because the economic calendar is rather quiet until around Tuesday New York open"
- **Conflicts:** none.
- **Rulebook fix:** In B16/T14, add a weekend calendar step and the first-driver hypothesis (stats only).
- **BUILD SPEC (day_week_context):**
  - In `study_week.py`: first_driver = the earliest day/minute in the week with `release_times` non-empty.
  - Record whether the week's against-bias extreme formed within that day's session (R..R+120), and the range of the days before it vs ADR5.
  - Stats only.
  - Test: `test_study_week_first_driver`.

### 71. DS2-ny-continuation-adr-pending
- **rule_id / kind:** N9 / missing_condition. Scope: general. judgment = false.
- **Rule:** [CC, FX-derived; test as an index filter] NY continuation long, with entries 07:00-10:00 NY only, requires:
  - HTF bias bullish;
  - London (00:00-05:00) posted the day low with displacement ("sponsorship");
  - no 4h/daily premium array touched intraday;
  - today's range so far < ADR5.

  Entry: buy a run below a 5m short-term low into a discount array (turtle soup / FVG / OB). Targets: the ADR5 high (LOD + ADR5 [our interpretation]) and the next 60m/4h premium array. If ADR5 is reached before 10:00, take 80% and leave a runner (L16). If ADR5 is already met or an HTF premium array was hit, no NY continuation. Bearish is the mirror.
- **Sources:** cc09_003_km0haQkTalc ~00:12:11; cc09_006_OVfn-gDk2dE ~00:18:28.
- **Quote:** "we expect to see New York open to continue higher unless a higher time frame premium array has been hit intraday and or ADR is reached"
- **Conflicts:** cc08_001 ~13:41 skips NY at ~80% of ADR5; these sources use 100%. cc09_007 ~18:32 says the range extends when ADR fills before the open and news is due (item 72).
- **Rulebook fix:** In N9, add the ADR-pending/HTF-array continuation conditions with the [CC, FX-derived] tag.
- **BUILD SPEC (day_week_context):**
  - Code: N9.6 `london_adr_skip=0.8` and L16 `adr_target` are listed.
  - Add `ny_cont_gate: bool = False`. In `_scan`, for entries in the bias direction before 600:
    - require the day's extreme against the bias to have printed in 0-300;
    - require no touch of an `htf._arrays` 4h/D array on the bias side since 0;
    - require (day H - day L) < `adr5(hist)`.
  - Add the target rung LOD + ADR5 (mirror HOD - ADR5) through `adr_target`.
  - Test: `test_ny_cont_gate`.

### 72. DS2-adr-filled-news-extends
- **rule_id / kind:** N9 / unlisted_contradiction. Scope: general. judgment = false.
- **Rule:** [CC, FX source] If the day range is ≥ ADR5 at or before the NY open AND a high-impact release is scheduled after 09:30 (10:00, 11:00 or afternoon): expect ADR5 to be exceeded (not necessarily doubled), so the N9 80% skip does not apply. With no later news, the N9 skip stands. Record this as an unresolved conflict with N9 (cc08_001 ~13:41) and cc09_006 ~18:28, and test it.
- **Sources:** cc09_007_-oMtfDvc18Y ~00:18:32.
- **Quote:** "the average daily range will likely be exceeded especially if high impact news is due out after equities open"
- **Conflicts:** N9 / cc08_001 ~13:41 and cc09_006 ~18:28 vs cc09_007 ~18:32.
- **Rulebook fix:** In N9, add the exception and list the conflict.
- **BUILD SPEC (day_week_context):**
  - Where: the N9.6 `london_adr_skip` check in the context builder.
  - Add `adr_news_exempt: bool = False`. If any of `release_times(day)` ≥ 600 (10:00 data or FOMC 840), the London-ADR skip does not fire. Tag `adr_filled_news`.
  - Test: `test_adr_news_exempt`. London covers 0.9 x ADR5 on an ISM 10:00 day: not skipped when exempt.

### 73. new-london-low-violated
- **rule_id / kind:** new / missing_rule. Scope: index. judgment = true.
- **Rule:** After London has delivered its move into the discount array (bullish lean), record the London-session low.
  - If NY trades below it, block all entries that day.
  - While it holds and 15m bodies stay above the London-reached discount level (wicks allowed), allow only longs, and only after the 09:30-10:00 opening range shows what it leaves.
  - Mirror for bearish.
  - Single source and partly discretionary (ICT said he was not committing to a trade); tag it and test as a switch.
- **Sources:** 092_9MLRE-n6St8 ~02:29:00.
- **Quote:** "if it does I'm not interested in trading at all not long or short"
- **Conflicts:** none.
- **Rulebook fix:** Add a new N9 bullet: "bullish lean after London delivered: NY below the London low = no trades (092 ~2:29)".
- **BUILD SPEC (day_week_context):**
  - Where: `run_day` bar loop. With `london_low_guard=True` and `htf.table` bias ≠ 0, set `lon_ext` = the London (120-300) low (bullish) or high (bearish).
  - Any bar from 570 trading through `lon_ext` by 1 tick sets `done` for all sessions that day, reason "london_violated".
  - Also require entries ≥ 600 when the guard is on.
  - Test: `test_london_low_guard`.

### 74. DS2-buy-day-checklist
- **rule_id / kind:** B22 / missing_condition. Scope: general. judgment = true.
- **Rule:** Long day trades are high probability only when all of these hold:
  - (a) the current or new quarter is expected to be bullish;
  - (b) the daily chart has already reacted up from a discount PD array (any array in the PD-array matrix);
  - (c) there is a clear, unobstructed path to an opposing premium array above;
  - (d) a bullish seasonal period is a plus but not required.

  Shorts mirror this: quarter expected bearish, the daily already reacted down from a premium array, a clear path down to a discount array.
- **Sources:** cc08_007_5Z_3NbclMSY ~00:06:40.
- **Quote:** "when the current quarter or new quarter is expected to be bullish after the daily chart has reacted positively on a discount PD array"
- **Conflicts:** none.
- **[our interpretation]** How "quarter bias" and "clear path" are computed.
- **Rulebook fix:** In B22 (or B10), add the four-item checklist as entry preconditions (CC; London lesson, HTF items only).
- **BUILD SPEC (bias_htf):**
  - Add `htf_checklist: bool = False`, using `htf.table`.
    - (a) Quarter bias = sign of (price - quarter open), or the B22 quarterly shift if built.
    - (b) The `react` column = +1 within the last 3 sessions.
    - (c) Clear path = the `htf_resist_cap` count of opposing D/4h arrays between price and the draw = 0.
  - Entries against any item are blocked in `_scan` bias gates.
  - Test: `test_htf_checklist`.

### 75. new-perspective-cadence
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** Set the BigPicture and Intermediate perspectives on the weekend, before the week opens. They usually hold all week but may be revised midweek (Tue/Wed) if price changes gears; there is no stated limit on revisions. Re-evaluate the ShortTerm perspective every trading day before the session.
- **Sources:** cc02_006_bftKgceXqYo ~00:48:38.
- **Quote:** "the big picture perspective you usually have that at the beginning of the week"
- **Conflicts:** none.
- **Rulebook fix:** In the B section, add a cadence note.
- **BUILD SPEC (bias_htf):**
  - Add `bias_cadence: str = "daily"`, with values `"weekly"` / `"weekly_midweek"`.
    - `"weekly"`: freeze the weekly-timeframe columns of `htf.table` (`weekly_bias`, W/M draws) at the Monday open.
    - `"weekly_midweek"`: allow one refresh at the Wednesday open if the daily `flip` column changed.
  - The daily columns are recomputed daily as now.
  - Test: `test_bias_cadence_freeze`.

### 76. L4-hrlr-news-exception
- **rule_id / kind:** L4 / missing_condition. Scope: general. judgment = true.
- **Rule:** A high-resistance-run target (an old high/low behind many overlapping swings) is generally defended and is the least probable target. Only a sharp market-driver release such as NFP or FOMC (or a comparable shock) is expected to run through it. On other days, prefer the low-resistance target or the nearest intermediate pool [the cap and the post-release timing are our interpretation].
- **Sources:** cc01_007_22XkhpJR5eA ~00:08:34.
- **Quote:** "it's going to take a very sharp economic market release ... like non-farm payroll or fomc"
- **Conflicts:** none.
- **Rulebook fix:** In L4, add the NFP/FOMC exception.
- **BUILD SPEC (targets_partials):**
  - Code: L4 `pool_rank` / `lrlr_max` are listed.
  - Delta: `hrlr_news_only: bool = False`. With it, a draw classified high-resistance (`pool_rank` resistance count ≥ `lrlr_max`) is eligible as the locked draw only on days whose events include "jobs" or "fomc", and only after the release (t > R). Otherwise the draw falls back to the nearest intermediate swing pool.
  - Test: `test_hrlr_news_only`.

### 77. N8-london-filters-gate-london
- **rule_id / kind:** N8 / wrong. Scope: general. judgment = true.
- **Rule:** The cc08_006 filters gate the London session (02:00-05:00). The lesson's stated action is "sleep in, trade New York".
  - Exceptions: the prior-day > 2x ADR5 filter is phrased as "don't trade the day after", and the 3-consecutive-closes filter as "at least London", so those two may be tested as whole-day switches.
  - NFP and holiday-eve skips stay whole-day because other sources support that.
  - FOMC whipsaw, multiple releases and a wide/erratic/trending CBDR or Asian range affect London only and should not block NY.
- **Sources:** cc08_006_stK2gNqhLaM ~00:13:20.
- **Quote:** "when the market is conditioned for London slop ... sleep in trade New York"
- **Conflicts:** none.
- **Rulebook fix:** In N8 / B11, add "cc08_006 filters gate London; action = trade NY". Mark which ones are day-level.
- **BUILD SPEC (day_week_context):**
  - Code: `neutral_skip` (big_prev whole day) and `three_day_rule` exist.
  - Add `london_filters: bool = False`. It blocks only London-session windows (`sb_london`, 120-300 windows) on `fomc_whipsaw` (item 29), `rel2plus` in 120-300, or a CBDR/Asian range > threshold (FX-only data, so not computed for the index bot).
  - Keep `neutral_skip` / `three_day_rule` as whole-day switches, unchanged.
  - Test: `test_london_filters_scope`. A `fomc_whipsaw` day blocks `sb_london` and not the AM.

---

## Out of scope for the bot (rulebook fix only)

### 78. L13-cbdr-size-bias
- **rule_id / kind:** L13 / missing_condition. Scope: fx_only. judgment = false.
- **Rule:** [fx-only] Use CBDR (14:00-20:00 NY) projections only if the CBDR is < 40 pips (bodies preferred, wicks also checked).
  - 20-30 is ideal: about one third of a ~100-pip ADR; smaller ranges such as 13-19 also work.
  - Above 30 tends to be unfruitful.
  - At ≥ 40 the model gives no day trade (scalp or stand aside).
  - A directional bias must be defined (e.g. price coming off a premium into a discount daily PD array for a buy day).
  - Index adaptation: ideal ≤ ADR/3, max ~0.4 x ADR [our interpretation].
- **Sources:** cc08_003_nI1AMOC1pro ~00:11:54; cc08_004_JKzEhfwV1dY ~00:24:57.
- **Quote:** "we want to have 40 Pips or less ideally 20 to 30 Pips"
- **Conflicts:** none.
- **Rulebook fix:** Add the size and bias filter to the L13/M17 fx-only CBDR note.
- **Build:** None (fx_only).

### 79. L13-sd4-news
- **rule_id / kind:** L13 / missing_condition. Scope: fx_only. judgment = false.
- **Rule:** [fx-only] CBDR SD expectations:
  - On sell days the HOD usually forms within 3 SD of the CBDR, ideally no more than 2 SD, often 1 SD. Buy days mirror this with the LOD.
  - A 4-SD extreme is expected only with a very high-impact news release in that day's London session, or when the day forms a NY session reversal profile.
- **Sources:** cc08_003_nI1AMOC1pro ~00:03:56.
- **Quote:** "four standard deviations above for a high today is going to be on the heels of a very high impact news event"
- **Conflicts:** none.
- **Rulebook fix:** Add to the L13 fx-only note.
- **Build:** None (fx_only).

### 80. T14-osok-london-low-tue-thu
- **rule_id / kind:** T14 / shortened. Scope: fx_only. judgment = true.
- **Rule:** [fx-only] Bullish weekly bias (OSOK):
  - On Tue, Wed and Thu (preferred; Monday possible), expect the day's low in the London session (01:00/02:00-05:00 NY).
  - Favour days where the CBDR passes the size filter (< 40 pips, 20-30 ideal) and the London low falls 1-2 SD below the CBDR.
  - A bearish week is the mirror (London HOD).
  - Test as a statistic first.
- **Sources:** cc08_003_nI1AMOC1pro ~00:08:18.
- **Quote:** "we're going to be looking primarily for low of the day in London each day Tuesday Wednesday and Thursday"
- **Conflicts:** none.
- **Rulebook fix:** In T14, add "OSOK: London LOD Tue-Thu with the CBDR filter [fx-only]".
- **Build:** None (fx_only).

### 81. M17-london-normal-protraction
- **rule_id / kind:** M17 / missing_rule. Scope: fx_only. judgment = false.
- **Rule:** London normal-protraction profile (FX only):
  - CBDR (14:00-20:00) < 40 pips AND an Asian range (20:00-00:00) of 20-30 pips. The cc08_007 strict version asks for ≤ 20 pips by the Frankfurt open, 01:00 NY.
  - If the CBDR is > 40, the profile is still possible only if Asia consolidates in 20-30 pips. If neither holds, use the delayed profile or skip London.
  - Third requirement: price must move against the bias from 00:00 into 02:00 (a rally for a sell day, a drop for a buy day).
  - The Judas move is 1-2 SD of the CBDR. The HOD (sell) or LOD (buy) forms 02:00-04:00.
  - Lesson 6 avoid thresholds differ: CBDR > 50, Asian > 40.
- **Sources:** cc08_005_eU8WcUftUtY ~00:01:28, ~00:01:57, ~00:05:39; cc08_007_5Z_3NbclMSY ~00:07:24.
- **Quote:** "the Central Bank dealers range is going to be less than 40 Pips"
- **Conflicts:** cc08_005 (20-30) vs cc08_007 (≤ 20 by Frankfurt). Lesson 6 thresholds (CBDR > 50 / Asian > 40).
- **Rulebook fix:** Record the thresholds in the M17 fx-only entry.
- **Build:** None (fx_only).

### 82. DS2-bonds-rate-reports
- **rule_id / kind:** N5 / missing_condition. Scope: bonds_only. judgment = true.
- **Rule:** [bonds-only] {needs: ZB/ZN intraday} Do not hold or open bond positions ahead of FOMC, any central-bank rate decision or interest-rate-based report, or NFP. Do not trade around the release (illiquid gaps). Whether to skip the rest of the day is unspecified; skipping it by default is our interpretation.
- **Sources:** cc10_006_CGbSpa_9Z9Y ~00:13:12.
- **Quote:** "the easiest way to avoid that is simply stay out of that particular asset class ahead of those news events"
- **Conflicts:** none.
- **Rulebook fix:** Add an N5 bonds bullet.
- **Build:** None (bonds_only).

### 83. DS2-bond-trending-day
- **rule_id / kind:** T13 / missing_rule. Scope: bonds_only. judgment = false.
- **Rule:** Bond (ZB) trending day, bullish [bonds only, cc10_007 ~5:12]:
  - The 08:00-08:20 NY opening prints the day's low, and price trades one-sidedly higher through the AM and PM until ~15:00.
  - The AM and PM legs together form the full daily range.
  - Bearish is the mirror.
  - [our operationalization] Label day_type='trend' when the low (high) sits in 08:00-08:20 and both sessions extend in the same direction. Using it to hold runners through the PM is our interpretation.
- **Sources:** cc10_007_JpV-J31mxhg ~00:05:12.
- **Quote:** "the opening around 8 A.M 8 20 a.m New York time creates the low of the day"
- **Conflicts:** none.
- **Rulebook fix:** In T13, add a bonds note.
- **Build:** None (bonds_only).

### 84. DS2-consolidation-day-split-sessions
- **rule_id / kind:** T13 / missing_rule. Scope: bonds_only. judgment = true.
- **Rule:** [bonds lesson, cc10_007 ~6:10] A realized consolidation day is either:
  - (a) a day where the AM and PM sessions move in opposite directions; or
  - (b) a day where one session makes a swing and the other is quiet or consolidates.

  [our threshold] "Quiet" = session range < ~30% of the swing session's range. Management (scalps only, no cross-session runners) is our interpretation, consistent with N8.
- **Sources:** cc10_007_JpV-J31mxhg ~00:06:10.
- **Quote:** "consolidation days can see opposing directions in the AM and PM sessions"
- **Conflicts:** none.
- **Rulebook fix:** In T13/N8, add the realized-consolidation definition (bond source).
- **Build:** None (bonds_only). If wanted later, it is a post-hoc label for `study.py`.

### 85. DS2-auction-day-before
- **rule_id / kind:** N8 / missing_condition. Scope: needs_unavailable_data. judgment = false.
- **Rule:** [bond lesson cc10_008 ~7:37; needs a Treasury auction calendar] Tag auction_day-1 as a consolidation_day candidate. On auction day the AM is consolidation: no AM entries (N5). Treating the auction-day PM under the consolidation-day rules is our reading.
- **Sources:** cc10_008_RgpxhuVp5Xg ~00:07:37.
- **Quote:** "the day before the bond auction could be a consolidation day"
- **Conflicts:** none.
- **Rulebook fix:** In the N8 consolidation predictors, add "day before a bond auction".
- **Build:** None, because there is no auction calendar. When one exists, extend the listed N5.6 `AUCTIONS` / `skip_auction_am` with an `auction_eve` tag.

### 86. DS2-delivery-month-premium-scan
- **rule_id / kind:** new / missing_rule. Scope: needs_unavailable_data. judgment = false.
- **Rule:** Every 10-15 trading days, for each commodity, compare the nearby contract with the next month out (and the months after).
  - Premium = nearby > next month out. It is stronger when the later months are progressively cheaper.
  - Carrying-charge market = later months progressively higher, so a parabolic move is less likely.
  - Flag markets with a premium developing as commercial-bull-market (long-side) candidates.
- **Sources:** cc10_004_WsolkBzpDOQ ~00:01:09.
- **Quote:** "once every two to three weeks you want to be looking for markets that are developing a premium"
- **Conflicts:** none.
- **Rulebook fix:** Add to M17 / B20 as commodity-only market selection.
- **Build:** None (commodity curve data unavailable).

### 87. DS2-avoid-thin-markets
- **rule_id / kind:** new / missing_rule. Scope: needs_unavailable_data. judgment = false.
- **Rule:** Commodity universe:
  - Exclude thin contracts that can lock limit: oats, rice, canola, palladium, platinum.
  - Grains followed: soybeans, CBOT wheat, CBOT corn.
  - Metals: gold, silver, high-grade copper.
- **Sources:** cc11_001_u5S6Zt1ZIpA ~00:05:14.
- **Quote:** "it's a rather thin Market you can get hurt in that if it starts to do limit moves"
- **Conflicts:** none.
- **Rulebook fix:** Add to M17 as a commodity universe note.
- **Build:** None (no commodity data; the bot trades ES/NQ/SPY).

---

## Text-only / not applicable to the bot

### 88. DS2-n8-cc09003-miscite
- **rule_id / kind:** N8 / wrong. Scope: general. judgment = true.
- **Rule:**
  - N8: drop cc09_003 from the "Consolidation = no trade" citation and keep cc01_001.
  - Add: "Profile the session first (consolidation, reversal, expansion) and use the model that fits the profile (cc09_003 ~1:58) [CC]."
  - The Asian range-fade scalp inside an expected consolidation (20:00-00:00, fade the first run of a short-term high/low, fixed 20-pip target/stop) is [fx-only] and not part of the index rules.
- **Sources:** cc09_003_km0haQkTalc ~00:08:30.
- **Quote:** "we're anticipating consolidation so there's nothing to fear"
- **Conflicts:** N8 bullet 1 (cc01_001) vs cc09_003 trading an expected Asian consolidation.
- **Rulebook fix:** As in the rule above.
- **Build:** None. Citation fix only; the index-side "match model to profile" is covered by item 48 `consolidation_mode`.

### 89. new-lethargic-3m-market
- **rule_id / kind:** new / missing_rule. Scope: general. judgment = true.
- **Rule:** Swing-trading market selection only: skip markets with little to no movement over the last ~3 months (about 63 trading days), and prefer markets whose monthly/weekly profile is trending, away from consolidation. ICT gives no threshold. [our interpretation] Compare the 63-day range with the median of prior quarters.
- **Sources:** cc06_001_0juYnbKays0 ~00:02:36.
- **Quote:** "avoid lackluster or lethargic markets to have little to no movement over the last three months"
- **Conflicts:** none.
- **Rulebook fix:** Add to M17 as swing market selection.
- **Build:** None. Swing market selection does not apply to an ES/NQ/SPY intraday bot. If ever needed, it is a one-line tag in `study.py` (63-day range vs the median of the prior 4 quarters).

---

## Items 90-92 (index/general, build specs)

### 90. DS2-two-session-close-templates
- **rule_id / kind:** T13 / missing_rule. Scope: index. judgment = false.
- **Rule:** Two-session UP close. Conditions: daily/4h IOF bullish, mid-swing, no 4h/daily/weekly premium array reached yet.
  - AM returns to a discount array, then rallies.
  - Lunch consolidates with shallow retracements. On strong-catalyst days it may trend straight through lunch.
  - PM runs the lunch-hour low (sell stops) or drops into a fair-value discount array, then rallies into the close.
  - Rough measured move: PM leg ~= AM leg.
  - Bot: AM longs off the discount array, PM longs after a lunch-low sweep or a discount-FVG tap, no shorts [our mapping].
  - DOWN close is the mirror.
  - Valid only until price trades into an opposing 4h/daily/weekly PD array (cc10_013 ~5:10). After that, switch to the AM-move/PM-reversal or consolidation profiles.
- **Sources:** cc10_013_P5pyzmgZA1s ~00:01:33, ~00:03:26, ~00:05:10.
- **Quote:** "that down close is high probability until we get to a four hour or a daily or weekly discount array"
- **Conflicts:** none.
- **Rulebook fix:** In T13, write out the sequence, the PM alternatives, the validity condition and the strong-catalyst caveat.
- **BUILD SPEC (setups_models):**
  - Code: T13 profile tags (`profile_tags`) and `pm_lunch_target` exist.
  - Add `profile_two_session: bool = False`. If `htf.table` bias ≠ 0, no D/4h/W opposing array was touched since the swing origin, and the AM delivered in the bias direction, then PM entries are allowed only in the bias direction, triggered by a lunch-low sweep (`_sell_side` lunch pool, which already exists via `extra_pools`) or a tap of a discount FVG (lower half of the day range). Shorts are blocked in the PM.
  - Tag `two_session_up` / `two_session_down`.
  - Test: `test_profile_two_session`.

### 91. DS2-am-move-pm-reversal-templates
- **rule_id / kind:** T13 / missing_rule. Scope: index. judgment = false.
- **Rule:** AM rally, PM reversal. Conditions: daily/4h IOF bullish, but a 4h/daily premium array lies just above.
  - AM returns to discount, then rallies into the HTF premium array.
  - Lunch consolidates.
  - PM runs the lunch-hour high (a lower high vs the AM high is a failure swing) OR the AM high, then reverses down into the close.
  - Exception: if the AM rallied off a 4h/daily/weekly discount array, the PM may instead retrace to it and resume higher. Expect the reversal to carry through only when that AM array was lower-timeframe (60m/15m) (cc10_013 ~7:46-8:58).
  - AM decline / PM reversal is the mirror (cc10_013 ~9:04-11:03).
  - Bot trigger after the sweep = MSS [our mapping].
- **Sources:** cc10_013_P5pyzmgZA1s ~00:06:36, ~00:09:36.
- **Quote:** "the PM Trend runs the lunch hour lows then reverses into the close or it runs the intraday lows then reverses into the close"
- **Conflicts:** M6 (015) requires the intraday high to be taken; cc10_013 also accepts a lunch-high sweep (failure swing).
- **Rulebook fix:** In T13, add both reversal templates and the HTF-array exception. In M6, add the lunch-high failure-swing variant and list the conflict.
- **BUILD SPEC (setups_models):**
  - Code: M6 `pm_reversal` exists and requires the AM high to be taken.
  - Add `pm_reversal_pool: str = "am_high"`, with values `"lunch_or_am"` (accept a sweep of the lunch high, 720-810, even below the AM high).
  - Add `pm_reversal_ltf_only: bool = False`: allow the reversal only if the AM's origin array was ≤ 60m. Check `htf._arrays` TF at the AM low via `entry_tf_tag` / `conf_top`. A 4h+ origin blocks the PM reversal.
  - Test: `test_pm_reversal_lunch_high`.

### 92. DS2-consolidation-profiles
- **rule_id / kind:** T13 / missing_rule. Scope: index. judgment = true.
- **Rule:** Preconditions: daily/4h premium-discount location unclear (neutral IOF) AND no high- or medium-impact release in the 10:00 hour or later. Do not use with a strong directional bias.
  - Consolidation AM rally / PM decline:
    - AM: return to a discount array then rally, OR after the first hour / opening range, expand up from its equilibrium to run London buy stops or the intraday highs.
    - Lunch: consolidates with shallow retracements.
    - PM path choice: if the AM high reached a higher-timeframe (1h/4h or higher) premium array, the PM only runs the lunch high, then reaches for the day's sell stops. If the AM did not reach an HTF premium array, the PM runs the intraday high, then reaches for the intraday or London sell stops.
    - The PM may also just consolidate into the close.
  - Consolidation AM decline / PM rally is the mirror. The AM runs London sell stops or returns to a premium array. If the AM low reached an HTF discount array, the PM runs only the lunch low; otherwise the PM runs the intraday low. Then it targets the day's / intraday / London buy stops.
- **Sources:** cc10_013_P5pyzmgZA1s ~00:11:35, ~00:12:00, ~00:14:43.
- **Quote:** "especially if there's no real high impact or medium impact news expected during the uh the 10 o'clock hour or later in the day"
- **Conflicts:** none.
- **[our interpretation]** The neutral-IOF test (`htf.table` bias == 0).
- **Rulebook fix:** In T13, write out the preconditions, AM variants and the PM path-choice rule.
- **BUILD SPEC (setups_models):**
  - Add `profile_consol_pm: bool = False`.
  - Conditions: `htf.table` bias == 0 and no `release_times(day)` entry ≥ 600.
  - After 810: if the AM extreme touched a 1h+ array (`htf._arrays`), the PM sweep pool = the lunch high (low). Otherwise it is the AM high (low).
  - After the sweep plus MSS, allow the counter side with targets at the day / London opposite pools (`extra_pools` London).
  - Tag `consol_am_rally` / `consol_am_decline`.
  - Test: `test_profile_consol_pm_path`.
