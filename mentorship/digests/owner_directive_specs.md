# Owner directive build specs: Ep 01-08 caption corrections (#1-#14)

Source: the owner's 2026-10-18 list of 14 rulebook errors in the Ep 01-08 captions (also recorded in `owner_directives.md`). For each item this file gives the correction, the caption evidence, how far the captions support it, the current rulebook and code, the related `rule_coverage.md` ids, the FINAL build spec and the package.

Every spec went through a code review, and all 14 reviews asked for changes. The build specs below are therefore the reviewed versions (`review.revised_spec`). In every item the owner's version is the DEFAULT and the previous behaviour stays available as a switch. Labels used:
- **[our interpretation]**: a judgment call the captions do not settle.
- **[owner]**: binding because the owner said so, even where the captions show less.

Support levels: **yes** = the captions fully back the correction. **partly** = the captions point the same way, but the owner's rule is stronger than what they show.

---

## 1. Last-hour window and the PM session

**Correction.** ICT allows last-hour setups from 15:00 to 15:50. 15:15-15:45 is only the typical sweet spot. Ep 08's 13:30-16:15 PM session overrides Ep 01's.

**Support: yes.**

**Caption evidence**
- Ep01 (001) 00:27:30-00:27:50: the PM session is "three o'clock to four o'clock", a small window, looking for "five handles or more".
- Ep01 01:00:38-01:01:12: the setup forms "between three o'clock and four o'clock"; "if you don't have a setup by 10 minutes before don't do anything"; "generally ... between 315 and 345 ... a little tiny small sweet spot".
- Ep01 01:00:27: "a little bleed over because at 4 15 ... closing bell".
- Ep08 (010) 00:55:05-00:55:12: "the afternoon showing the 1:30 / 4:15 time window" (the caption prints "132 / 415").
- Ep08 00:56:19-00:56:43: operate from 1:30 and use the 1:30 opening price.
- Ep08 01:05:20: "the final hour of trading between 3 pm and 4 15".
- The 15:50 cutoff is Ep01's "10 minutes before", read against the 16:00 hour end. The owner states 15:50 explicitly.

**Rulebook now**

| Where | What it says | Problem |
|---|---|---|
| T9 (l.444-449) | "Bot: PM 13:30-15:50" | — |
| T10 (l.450-454) | last hour 15:00-16:00, sweet spot 15:15-15:45 | — |
| T11 (l.455-458) | flatten at 16:00 | conflicts with the 16:15 PM end |
| M5 (l.652-660) | 15:15-15:45 windows | treats the sweet spot as the window |
| Proposed change 23 (l.1176-1177) | "no entries after 15:45" | contradicts the owner |
| Decision 7 (l.962-967) | pm_last_hour 15:15-15:45 | — |
| Appendix A Ep01 (l.1241-1242) | 15:15-15:45 as the window, plus Ep01's 14:00 start | — |
| Appendix A Ep08 (l.1351) | "Last hour 15:00-16:15" | not marked as the governing source |

**Code now** (`strategy.py`)
- `pm=(810,950)` already allows PM entries until 15:50 (the `_scan` loop at ~l.929 and the pending cut at l.879 both use `pm[1]`).
- `last_hour=(915,945)` is used only for the label at l.1205, so entries at 15:00-15:15 and 15:45-15:50 are tagged "pm".
- `flatten=960` is used at strategy l.858, `sb_model` l.78 and `pre_open` l.99.
- `backtest.complete_sessions`/`days()` (l.80-90) drops every bar at or after 16:00, so the 16:00-16:15 ES bars are never seen.
- `sb_model` l.38 has the bound `t<960`.

**Coverage:** T9, T10, T11 (all SIMPLIFIED); M5/M5.1-M5.3; Ep01.10; Ep01.11 (its build note "pm_setup_window 15:15-15:45" contradicts the owner); Ep01.13; Ep08.6; N10.5; X11b; X11d; build notes l.738 and l.778. Also `owner_directives.md` item 1.

**Package:** news_calendar_times

### Final build spec
Owner's version is the default. Every value is fixed before the bar that uses it. Nothing is derived from bars that have not closed.

1. **`strategy.Params`** (~l.92-94)
   - Keep `pm=(810,950)`. The pending cut at l.879 stays at `p.pm[1]`.
   - `last_hour`: change (915,945) to **(900,950)**, the 15:00-15:50 last-hour entry span.
   - Add `last_hour_sweet=(915,945)` (tag only).
   - Add `last_hour_strict: bool=False`. When True, `_scan` (the l.929 branch) skips a PM setup with `t>=last_hour[0]` unless `last_hour_sweet[0]<=t<last_hour_sweet[1]`.
   - Add `session_close: int=0` (0 = auto). Resolve it once per run in `backtest.run()` and `paper.py`, before any day is processed:
     - 975 for ES/MES futures, identified by `htf.has_overnight(df)` with a non-equity symbol, or by an explicit futures flag;
     - otherwise 960 (SPY/schwab).
     Store the result on a copy of p (`dataclasses.replace`).
   - `flatten`: default 0 means "use the resolved session_close". `eff_flat = p.flatten or p.session_close`, computed once. `flatten=960` restores the old 16:00 exit.
   - **Never** compute eff_flat from the day's last bar. In live runs with partial_last, the last bar is the current bar, so every position would be flattened at once.
   - Use eff_flat at strategy l.858, `sb_model` l.78 and `pre_open` l.99. The rule stays `t + tf >= eff_flat`, so the exit is on the 16:10 bar (5m) or the 16:14 bar (1m).
2. **Labels** (l.1205)
   - "pm_last_hour" if `last_hour[0]<=t<last_hour[1]`; otherwise "pm_sb" if `840<=t<900`; otherwise "pm".
   - Add the Trade field `lh_sweet: bool` from the closed setup bar's t, passed through `Trade(...)` at l.896.
   - Report pm_last_hour and the lh_sweet split in the summary.
   - Do not touch `MACROS (915,945)`. `last_hour` is read only at l.92 and l.1205.
3. **Session data** (`backtest.py`)
   - `days()` l.84: keep bars with `t < max(960, session_close)`. Add a `close=960` argument, set by `backtest.run` and `paper.py`.
   - The completeness test at l.90 is unchanged.
   - `rth()` l.97-98: add the upper bound `t < 960`, so the history frames given to `run_day` (l.133/142/144; paper l.32/34) stay 09:30-16:00. Prior-day close/H/L, NWOG, the ORG fallback (strategy l.246/438/483/492/639/660) and the partner SMT history must stay identical. Add an assertion test.
   - The ORG keeps using `p.org_close` through `closes`.
   - `sb_model` l.38: `<960` becomes `< eff_flat`.
   - strategy l.472 (ppm 810-960): leave as is and add a comment.
   - Confirm that bars with `t>=pm[1]` hit `continue` at l.931-932, so the 16:00-16:15 bars only manage open positions.
4. **Rulebook**
   - T9: "PM session 13:30-16:15 (Ep 08 wins over Ep 01's 14:00-16:00)".
   - T10: "Last hour 15:00-16:15. Entries 15:00-15:50 (15:50 = our reading of Ep01's '10 min before', confirmed by owner). 15:15-15:45 = sweet spot tag lh_sweet. last_hour_strict switch."
   - T11: "Flatten at session close: 16:15 ES/MES, 16:00 SPY; flatten=960 switch. Conflicts with the 2023 'flat before 16:00' videos; owner directive wins."
   - M5 and proposed change 23: drop "no entries after 15:45".
   - Decision 7: pm 13:30-15:50, pm_sb 14:00-15:00, pm_last_hour 15:00-15:50, lh_sweet 15:15-15:45.
   - Appendix A Ep01: add an [owner correction] note.
   - Appendix A Ep08 l.1351: mark it as the governing PM-session source.
5. **Coverage and digests**
   - `rule_coverage.md`: T9, T10, T11, M5/M5.1-5.3, Ep01.10, Ep01.11 (replace the pm_setup_window note), Ep01.13, Ep08.6, N10.5, X11b, X11d, build notes l.738 (remove "no entries after 15:45") and l.778 (last_hour_strict built).
   - Digests: `models.md` l.315 and l.417-418; `times.md` l.362.
   - `owner_directives.md` item 1: mark as built.
6. **Tests**
   - (a) 15:05 setup: taken, pm_last_hour, lh_sweet=False.
   - (b) 15:30 setup: lh_sweet=True.
   - (c) 15:52 setup (1m): not taken. A pending order from 15:45 is cancelled at the 15:50 bar.
   - (d) last_hour_strict rejects 15:05 and takes 15:30.
   - (e) MES 5m: the exit is "eod" on the 16:10 bar. With flatten=960 it is on the 15:55 bar.
   - (f) SPY: session_close resolves to 960 and the exit is on the 15:55 bar.
   - (g) A live day truncated at 14:00 is not flattened.
   - (h) MES `hist` frames have no bars at `t>=960`, and prior-day levels are unchanged.
   - (i) No look-ahead under truncation.
   - Regression run, old vs new defaults, on SPY 5m and MES 1m/5m: trades by label, and the P&L effect of holding 16:00-16:15.

---

## 2. Five handles is the minimum room, not the goal

**Correction.** 5 handles is the minimum room, not the goal.

**Support: partly.**

**Caption evidence**
- Ep01 00:27:47-00:28:34: setups "that's going to offer five handles or more". The target is the buy-side pool at 38.64, not +5.
- Ep01 00:55:20: "where can I find five handles start there".
- Ep07 00:05:56 and 00:17:52-00:18:07: five-handle increments that "accumulate to 15 handles", i.e. 5 is a unit, not a cap.
- Ep08 01:15:16: "give me 10 handles of a range then I'll operate".
- Against: Ep03 00:35:47-00:35:56 calls five handles a "low hanging fruit objective" to grow into, and Ep08 01:16:01 says "your five handles for the day" in chop. So the captions do not reject the goal reading outright. The owner's version is binding.

**Rulebook now:** 5 is written as a goal in L15 (l.562, "aiming to take 5"), M3 (l.628, "take ~5"), X14 (l.890, "5 handles then stop") and Appendix A Ep01 (l.1254) and Ep03 (l.1294). Ep07 (l.1343) uses it as an increment. Build item 7 (l.1109) says `min_draw_pts=10`, while the code uses 5. The digests repeat the goal reading: `times.md` l.88 and `silver_bullet.md` l.277.

**Code now**
- The main engine is already right. `min_draw_pts=5.0` gates the room to the draw (filter tag `x_room_lt_10` at strategy l.1194 in `_scan`), and the targets are pools and arrays.
- `sb_model` (off by default) has a room gate `sb_room_pts=5`, but its target is `t1=min(entry+sb_target_pts(5), draw-exit_before)`, which treats 5 as the goal.
- `pre_open` Ma Deuce uses `sb_room_pts` as room and the CE as the target, which is already right.

**Coverage:**
- L15 FULL; M3.6 FULL; M3.10 MISSING.
- X14a MISSING. Its build note `day_target_pts=5` conflicts with the directive.
- Ep03.24 SIMPLIFIED. Its build note `t1_fixed_pts` (+5) conflicts with the directive.
- Ep01.21, Ep07.10 NA, Ep08.17 (`engage_range_pts`).
- No existing item says "5 = minimum room".

**Package:** targets_partials (1a-d, 1f, 5); silver_bullet (2); management_exits (1e)

### Final build spec
1. **`strategy.py`**
   - a. Keep `min_draw_pts=5.0`. New comment: minimum room, measured to the draw's exit price after pool_beyond/exit_before; 5 = ICT minimum (default), 10 = new-trader switch.
   - b. Rename `_f("x_room_lt_10")` to `_f("x_room_lt_min")` in `_scan` (~l.1194), and update `experienced_rules.md` l.27. No .py report reads the old tag.
   - c. Add `t1_fixed_pts=0.0` (Ep03.24 test switch, default OFF). After lv is filtered and the room gate passes (the gate still uses the draw):
     - f = entry + t1_fixed_pts*es_pt;
     - if t1_fixed_pts>0, f < lv[0]-es_pt and f-entry >= min_rr*risk, then lv=[f]+lv;
     - then t1=lv[0], t2=lv[1] and `levels=lv[:len(ladder_fracs)]`, as now.
   - d. Add `t1_fixed_all=False`. When it is True and t1_fixed_pts>0, lv=[min(f, lv[0])] and t2=None.
   - e. Add `day_target_pts=0.0` (X14a switch, default OFF).
     - In `_after_close(pos,trades,p,done,state)`, accumulate `state["day_pts"] += net P&L / shares / es_pt`, using `tr.pnl(p.cost_per_share)`. Initialise it to 0 in `run_day`.
     - When the total is >= day_target_pts, set done[k]=True for every session. This affects later bars only.
     - `run_sb` trades are neither counted nor blocked.
   - f. Comments: drop "+5 as goal" from the module docstring (l.14), `sb_target_pts` (l.194, "fixed-mode target only"), `sb_mgmt` (l.195) and `sb_min_rr` (l.198, "reward:risk floor on t1").
2. **`sb_model._sb_arm`** (off by default)
   - a. Add `sb_target_mode="draw"` (new default) or "fixed" (today's behaviour).
   - b. Keep the target kinds: `dr=[(v,kind) for v,kind in lv if v>entry]`.
     - ex(v,kind) = v + pool_beyond_pts*es_pt if (exit_mode=="split" and kind=="pool"), else v - exit_before_pts*es_pt.
     - draws = [ex(v,k) for v,k in dr]; draw = draws[0].
   - c. "draw" mode: t1=draws[0]. The room gate is `t1-entry < sb_room_pts*es_pt` → None. t2 = draws[1] if sb_runner and there is one. levels = draws[:len(ladder_fracs)].
   - d. "fixed" mode is byte-identical to the current code: room measured to the raw draw; t1=min(entry+sb_target_pts*es_pt, raw draw-exit_before); t2 = raw draw if sb_runner and draw>t1+es_pt; levels = [t1] + raw draws above, first 2.
   - e. The min_rr check on t1 stays. In draw mode, `sb_mgmt="fixed"` takes everything off at the draw (80% with sb_runner, the rest at draws[1]).
   - f. Docstring l.16: "exit at the draw (nearest untaken liquidity/array, exit_before applied); fixed +sb_target_pts is a switch (sb_target_mode='fixed'); optional runner to the next draw." Comment at l.55: "scale out at the draw levels".
   - g. `sb_room_pts=5.0`, with the comment "minimum room to the draw's exit price; 10 = new-trader switch (046)".
3. **`pre_open.py`:** no logic change. Add the comment "room gate only; target is the CE (owner #2)".
4. **`engage_range_pts`** (Ep08.17) stays a separate switch, default 0.
5. **Docs** (mark each changed line [owner correction 2026-10-18])
   - L15: min room 5 (default) / 10 new (switch); target = draw/PD array.
   - M3: ">= 5 (10 new) ES pts room; exit at the draw; fixed +5 is a switch".
   - X14: "test switch day_target_pts, default off".
   - App. A Ep01 l.1254: "5 handles or more of room (minimum); target = the liquidity pool".
   - Ep03 l.1294: "low-hanging minimum to grow from, not a cap".
   - Ep07: keep as a measuring unit.
   - Build item 7: min_draw_pts=5 default, 10 switch.
   - Digests: `times.md` l.88, `silver_bullet.md` l.277, `experienced_rules.md` l.27.
   - `rule_coverage.md`: L15/M3.6 (room measured to the exit price); Ep03.24 (t1_fixed_pts default off); X14a (day_target_pts default off); M3.10 still MISSING.
6. **Tests** (`tests/test_room_target.py`)
   - (a) exit_before_pts=0: an adjusted draw at +4.75 is rejected with x_room_lt_min; at +5.0 it arms.
   - (b) Draw at +12 with exit_before 0.5: t1 = draw-0.5, no +5 rung.
   - (c) t1_fixed_pts=5: t1=entry+5 and t2 = the first draw. No rung is inserted when lv[0] <= entry+6. t1_fixed_all gives a single level.
   - (d) day_target_pts=5 after a +6 pt trade: no later entries. Default 0 leaves trades unchanged.
   - (e) SB draw mode: t1 = draw-exit_before and the room is checked on t1. "fixed" reproduces the old SB list.
   - (f) Default main-engine trades are identical; only the tag name changes.

---

## 3. Year end takes its side from December's direction

**Correction.** Year end takes its side from December's direction. It is not always bullish.

**Support: partly.** Only Ep 01 covers it, with one example.

**Caption evidence**
- Ep01 00:11:49-00:11:55: last trading day, "not likely to have a big move".
- Ep01 00:12:04-00:12:16: "squaring positions ... what positions would be squaring / ... December it's pretty much been down / ... no Santa Claus rally".
- Ep01 00:31:13-00:31:26: run above 3864 buy-side, a "short covering rally".
- Ep01 00:33:09 and 00:35:28-00:35:45: book profit, square up, the bias is "this pool of liquidity".
- December 2022 was down, shorts were squared, and price rallied. So the only example runs AGAINST December's direction.
- **Open point:** `owner_directives.md` l.23 says "Dec up → bullish, down → bearish", which is the opposite mapping. The owner's message gives no mapping. **The owner must confirm.**

**Rulebook now:**
- Appendix A Ep01 l.1238: "Year end reprices up to buy-side liquidity" (always bullish; this is the error).
- l.1237 and N7 l.356-357: low-vol inside day, nothing on direction.
- `filters.md` l.52: the same always-bullish error.

**Code now:** nothing exists.
- `strategy.day_context(hist, day)` (l.627) handles big_prev, inside_day, three_up/down and tgif only. It is called at l.746, and the run-loop gates are at l.949-951.
- `calendar.py` has HOLIDAYS (up to 2025-12-25) and no last-trading-day helper.

**Coverage:**
- Ep01.9 MISSING (l.423). Plan l.959 `year_end_long` is the old version and must be replaced.
- N7.4 MISSING (l.168; plan l.935).
- Related: Ep01.8, Ep02.7.

**Package:** day_week_context

### Final build spec
- **Calendar** (`mentorship/calendar.py`)
  - `is_trading_day(d)`;
  - `last_n_trading_days(year, n)`, walking back from Dec 31;
  - `last_trading_day_of_year(d)`;
  - add the 2026 NYSE holidays (including 2026-12-25), or document that the list stops at 2025.
- **Params** (next to three_day_rule/tgif, ~l.177)
  - `year_end="december"`. Other values: "long" (old always-bullish), "tag" (no blocking), "off".
  - `year_end_map="squaring"`. Dec down → +1, Dec up → -1, matching Ep01 Dec 2022. The other value, "with", is the mapping written in owner_directives.md:23. **OWNER MUST CONFIRM**; flip the default to "with" if told so.
  - `year_end_days=1`.
  - `year_end_flat_frac=0.25` [our interpretation].
- **`december_dir(hist, day, flat_frac)`**
  - dec = sessions in hist dated December of day.year and before day. hist never contains today.
  - Return 0 if there are fewer than 5 such sessions, or if hist has no session before Dec 1 (December's first session may be truncated: paper.py passes only 21 sessions).
  - o = first open, c = last close, rng = max high - min low.
  - Return 0 if |c-o| < flat_frac*rng, else sign(c-o).
- **`day_context`**
  - New signature `day_context(hist, day, p=None)`. Update the only call (l.746).
  - Put the year-end block BEFORE the `len(hist)<7` early return (l.636). When p.year_end != "off" and day is in the last year_end_days trading days:
    - add the tags "year_end" and "year_end_inside" (Ep01.8, report only);
    - side = +1 for "long", otherwise ±december_dir per year_end_map;
    - add the tag year_end_long or year_end_short;
    - unless the mode is "tag", set `block["year_end"]=(-side,)`.
- **Run loop** (~l.949-951)
  - `if sd.sign in block_side.get("year_end",()): continue`. No reason is logged; ctx.day_tags carries it.
  - Set `ctx.block_side=block_side` after l.746.
- **Ma Deuce:** after the sign is chosen (~l.37-39), return [] if the sign is in `ctx.block_side["year_end"]`.
- **No draw change.** `_scan` already draws to the nearest pool on the allowed side (l.1192).
- **Docs**
  - Rulebook l.1238 becomes: "Year end takes its side from December's direction: positions built in December get squared (Dec 2022 down, no Santa rally → shorts covered → reprice up to buy stops above 3864). Not always bullish. [owner correction #3; mapping = year_end_map, pending owner confirmation]".
  - Add the same to N7 l.356-357 and fix `filters.md` l.52.
  - `owner_directives.md` l.23: append a mapping-conflict note.
  - `rule_coverage.md`: update Ep01.9 / plan l.959 and N7.4 / plan l.935.
- **Tests**
  - last_trading_day_of_year: 2022-12-30 T, 2022-12-29 F, 2023-12-29 T, 2021-12-31 T.
  - Falling December: "squaring" gives long and blocks shorts; "with" gives the reverse. Rising December gives the reverse of each.
  - Flat December: tags only, no side.
  - hist starting Dec 2: no side.
  - "long" gives +1; "tag" gives a tag with no block; "off" gives no tags.
  - Non-year-end days and the three/tgif outputs are unchanged (including p=None).
  - Ma Deuce returns [] for a blocked sign.
  - ES 2022-12-30 with defaults: no shorts.

---

## 4. The post-NFP 30-minute wait is not for all news

**Correction.** The 30-minute wait after NFP does not apply to all news. ICT waits for the news dealing range to form.

**Support: yes.** The exact formation test is [our interpretation].

**Caption evidence**
- Ep04 (006, NFP 2023-01-06) 00:08:13-00:08:23: "there's a way to trade ... after that first 30 minutes or so [of NFP] ... not something I would advise". This is NFP-only and hedged.
- Ep04 00:27:55-00:31:26: "I want to see where the real range is"; "only here ... inside that box ... the dealing range"; then expansion to external range liquidity.
- Ep04 00:12:54: high-impact news can overshoot FVGs.
- Ep02 (002) 00:00:12-00:01:01: waiting for the 09:45 PMI release and the range, with no minute count.
- The blanket 30-minute rule comes from 065B (~4:07), which is outside Ep 01-08.

**Rulebook now:**
- N5 bullet 1 (l.334-335): "Any high/medium-impact release: wait >= 30 min" (the error).
- N1 (l.311-314): "first hour after 08:30".
- Decision 9 (l.979): the 065B 30-min rule.
- Appendix A Ep04 l.1298 and l.1302 are already correct (no fixed minute count; the dealing range as the framework).

**Code now** (`strategy.py`)
- On 10:00 days, `am_start = 600` with no wait. On 08:30 days AM starts at a fixed 09:30.
- `post_news=False` (l.188) is a fixed 30-minute NEWS window.
- `news_hl` is a fixed 08:30-09:00 window (DayCtx l.452-453), used only in the NEWS session; `_scan intact()` hard-codes it as made at 09:00 (l.1044).
- There is no 09:45 set and no release-time function.

**Coverage:**
- N5 and N5.1 are SIMPLIFIED. Build line l.972 `news_wait_min=30 (default on)` contradicts the owner.
- N5.2 (09:45), N6, M9/M9.1.
- Ep04.5 SIMPLIFIED; build l.753 assumes a fixed 09:00 completion.
- N1.
- `owner_directives.md` item 4.

**Package:** news_calendar_times

### Final build spec
After each scheduled release there are no entries until that release's news dealing range has formed, and then the bot trades from it. On jobs days, "the first 30 minutes or so" is only a floor.

1. **Calendar**
   - `NEWS_0945={"pmi_mfg","pmi_svc"}`: pmi_mfg on trading day 1 and pmi_svc on trading day 3 (the same days as the ISM releases). Flash PMI dates are not available.
   - `release_times(day,p)`, sorted: 510 (NEWS_0830), 585 (NEWS_0945), 600 (NEWS_1000), 840 (fomc).
   - Docstring: PCE, GDP, retail sales and JOLTS dates exist for 2026 only. ISM, PMI and sentiment are rule-based.
2. **Params**
   - `news_wait="range"` (default). "fixed" is 065B's wait of news_wait_min after each release. "off" is today's behaviour, bit for bit.
   - `news_wait_min=30`, `nfp_floor_min=30`, `news_range_max_min=90`, `news_range_pivot=0` (= p.pivot_n), `news_range_target=True`, `news_range_pd=False`.
   - Under "off", none of items 3-5 apply.
3. **`DayCtx.news_dr`** `{R:{R,hi,lo,eq,made}}` [our interpretation]
   - kR = the first index with t>=R.
   - Pivots come from `L.pivots(ctx.h,ctx.l,n)`, where `Pivot.known` = pivot index + n.
   - made = max(first swing high known with .i>=kR, first swing low known with .i>=kR, floor_idx). floor_idx = R+nfp_floor_min on jobs days, else kR.
   - hi and lo are taken over kR..made; eq is their midpoint.
   - made=None if no range has formed by R+news_range_max_min.
   - Later breaks do not reset the range.
   - Every reader checks i>=made.
   - Under "fixed", made = the first index with t>=R+news_wait_min.
4. **Gate** (`run_day` ~l.745-760, 925-937)
   - For each session window [a,b) (AM, PM, NEWS, PRE9), the driver is the latest R with a-60<=R<b.
   - If made is None, there are no entries after R and the session is done at R. Entries before R are also blocked on 09:45/10:00 days.
   - Otherwise w0=max(a, t[made]) and i>=made. This replaces `am_start=600`.
   - 08:30 days: AM opens at max(09:30, made). The NEWS window opens at max(540, made).
   - FOMC: PM opens at max(fomc_pm_from (885), made). `blocked()` stays on top.
   - `ctx.news_hl` comes from `news_dr[510]`.
   - `_scan intact()` (l.1042-1044) uses the made index instead of 540.
   - `sb_model.run_sb` skips i<made and skips the window if made is None. Ma Deuce is unaffected.
5. **Using the range**
   - `_sell_side`: a "news_range" pool at lo (longs) / hi (shorts) in AM, NEWS and PM once i>=made.
   - `_targets`: the opposite extreme as "news_dr_ext".
   - news_range_pd filter.
   - Trade fields news_wait_min_actual and news_pd (default None).
6. **Rulebook**
   - N5 bullet 1: "After any scheduled release, wait for the news dealing range (post-release manipulation high/low) to form, then trade from it toward external liquidity; no fixed minute count (Ep02 ~0:12-1:01; Ep04 ~28:16-31:26). '~30 min' is NFP-only (Ep04 ~8:23); 065B blanket rule kept only as news_wait='fixed'."
   - N1 and Decision 9: change to match.
   - `rule_coverage.md`: N5.1 build line, Ep04.5 and N5.2.
   - Mark the two-swing test, the 90-min cap and the NFP floor as [our interpretation].
7. **Tests**
   - (a) 10:00 ISM synthetic day: made = the 10:09 index; no AM or SB fill before it.
   - (b) Jobs day: t[made] >= 09:00.
   - (c) No range by R+90: no trade.
   - (d) "off" matches a fixture saved before the edit; "fixed" puts entries >= R+30.
   - (e) Truncation no-look-ahead test.
   - (f) A PMI+ISM day uses R=600 as the AM driver.
   - Study variants: NEWS_range, NEWS_fixed30, NEWS_off.

---

## 5. Bearish unicorn as well as bullish

**Correction.** The unicorn works bearish as well as bullish.

**Support: partly.**

**Caption evidence**
- Ep05 (007) 00:22:46-00:23:21: the only "unicorn" in Ep 01-08 is bullish, framed "if you're bullish ... that right there is a unicorn", strongest after a 09:30 sell-side run.
- Ep05 00:00:12-00:00:34 defines the bearish breaker (down-close candle, high-low-higher-high) with an imbalance inside it.
- 101 (outside Ep 01-08) 01:24:22-01:24:46 shows an explicit bearish unicorn on ES 60m.

**Rulebook now:** A14 (l.140-142), M4 (l.638-643) and Appendix A l.1315 are worded bullish only. A13 defines both breakers.

**Code now**
- The mirrored `Side` (strategy l.326) already finds bearish unicorns. In `_scan` (l.1099-1116), bz is the highest-close up-close candle in mirrored space, `uni` is the set of fresh FVGs overlapping bz, and the setup carries `unicorn=bool(uni)` (l.1207).
- The reports break results down by unicorn (backtest l.203; study l.69/127).
- There is no side label, no explicit short test and no side switch.

**Coverage:** no item for the direction. Related: A14, M4.2, Ep05.4, D6, A13.1-A13.4, the breaker_zone helper row (l.1025). `owner_directives.md` l.27.

**Package:** setups_models

### Final build spec
Default (#5): the unicorn works both ways. Bullish: a BISI inside a bullish breaker after a sell-side run, bought at the FVG or its CE. Bearish: a SIBI inside a bearish breaker after a buy-side run, sold short at the SIBI or its CE.

1. **Rulebook**
   - A14: "Unicorn = an FVG overlapping the breaker zone, in either direction. Bullish: BISI inside a bullish breaker after a sell-side run. Bearish: SIBI inside a bearish breaker (down-close candle of high-low-higher-high) after a buy-side run. Strongest right after the run at the 09:30 open (007 ~0:12-0:34, ~22:46-23:21; 101 ~84:22-84:46). Both directions: owner directive #5."
   - Apply the same wording to M4 and Appendix A l.1315.
   - Add the coverage row "A14.dir / owner #5: bearish unicorn".
2. **Code** (`strategy.py`)
   - The detection math does not change; it is already look-ahead free.
   - `Params.unicorn_sides="both"` ("long", "short"). A new `__post_init__` raises ValueError on any other value. `dataclasses.replace` also runs it.
   - l.1115: `uni=[g for g in fresh if bz is not None and g.overlaps(bz)] if p.unicorn_sides in ("both","long" if sd.sign>0 else "short") else []`.
   - Setup dict: `unicorn_side=("bull" if sd.sign>0 else "bear") if uni else ""`; bz_top / bz_bottom in real prices (max/min of sd.x of the edges, None when bz is None).
   - Trade fields `unicorn_side=""`, `bz_top=None`, `bz_bottom=None`, all with defaults, so the sb_model and pre_open Trade calls still work. Pass them through at l.896.
3. **Reporting:** add "unicorn_side" to backtest l.203 and study l.69/127.
4. **Tests** (`tests/test_unicorn.py`)
   - Bullish fixture: the H bar is the highest-close up-close candle and the BISI overlaps it. Use Params that neutralise side-dependent context. Expect a long with unicorn=True and unicorn_side="bull".
   - Exact price mirror (K-p, applied to the hist too): a short with unicorn_side="bear", entry and stop = K - the long values, and the mirrored bz. Compare risk in points.
   - Run under both breaker_zone values.
   - unicorn_sides "long"/"short" switch off the other side. An invalid value raises.
   - Add the switch to the existing no-look-ahead test (test_mentorship.py:129).
5. **Interaction:** the later unicorn_open / unicorn_only / unicorn_rules items must be written in mirrored space and respect unicorn_sides. #14 changes bz on both sides.

---

## 6. Mean-threshold respect belongs on the breaker (Ep 02)

**Correction.** In Ep 02, mean-threshold respect belongs on the breaker, not the order block.

**Support: partly.**

**Caption evidence**
- Ep02 (002) 00:03:37-00:03:54: "bearish ICT breaker ... inside this last down close candle ... the bodies ... respecting half of that range from the candle's high and low ... mean threshold". The respect is on the breaker, measured on its full range. The bearish OB comes in later (00:04:14) as confluence only.
- Ep05 00:01:22-00:01:58: MT reaction at "half of the breaker".
- Ep05 00:02:43 and Ep07 00:04:17 / 00:13:35 still use the OB MT as a stop and entry level. ICT's spoken definition remains "MT = half of an order block".

**Rulebook now:**
- A12 (l.125) cites the 002 respect example for the OB.
- A13.3 (l.136) has no Ep02/05 cite.
- D4 (l.935).
- Appendix A Ep02 l.1261-1262 puts the respect on the OB.
- The digests repeat the OB attribution: `pd_arrays.md` l.74 and C1, `levels.md` l.181.

**Code now**
- bz (`_scan` ~l.1099-1115) has no mt, and nothing reads a breaker MT.
- The OB MT is used as a stop (l.1125 `stop_mode="ob_mt"`, ep07_stop, sb_model l.152) and for OB invalidation (`confluence._zones`, inv=ob.mt). htf l.76 uses ob.mt as a reaction level.

**Coverage:**
- A13.3 SIMPLIFIED (build l.882).
- A13 (helper, l.579), A13.4 (l.625).
- Ep05.1 SIMPLIFIED (l.592).
- Ep02.3 is labelled "Bearish OB MT" (a mis-attribution).
- Ep02.4, A12, D4, D6.

**Package:** levels_detectors (primary); entries_stops_sizing (entry floor); management_exits (cancel/exit)

### Final build spec
Move the Ep 02 example and its citation to the breaker, and add breaker-MT respect as a default rule. OB-MT respect STAYS, because 036 ~54:23-54:41 and cc02_004 ~3:14-3:36 support it independently. The code works in Side-normalised prices.

**Rulebook**
1. A12 MT bullet: remove only the "002 ~3:45" cite. It becomes: "MT = 50% of the OB; bodies must not close through it, wicks may (036 ~54:23; cc02_004 ~3:28). Also stop/entry level (009 ~4:17, ~13:35; 007 ~2:43). D4." Add the note "[corrected, owner #6] Ep 02's example is on the breaker, see A13.3".
2. A13.3: "Breaker MT = 50% of the breaker candle's FULL high-low; bodies must not close through it, wicks may (002 ~3:37-3:54; 007 ~1:22-1:58; 018 ~1:22; 070 ~56:01). Owner #6."
3. Appendix A Ep02 l.1261-1262: "[corrected] The MT the bodies respected is the breaker's (last down-close candle, high-to-low, ~3:37-3:54); the bearish OB is confluence (~4:14-4:20); 'MT = half of an order block' stays as the generic definition." Keep l.1263.
4. D4: Ep02 becomes "(breaker MT)". Relabel Ep02.3 as "Breaker MT". Reattribute in `pd_arrays.md` (l.74, C1) and `levels.md` (l.181), keeping the 036 and cc02_004 cites. Log the change in owner_directives.

**`levels.py`**
5. Add the pure helper `breaker_mt(o,h,l,c,k,mode="range")`: range = (h+l)/2, body = (o+c)/2.
   - Add `breaker_candle(o,c,a0,ext_i)`: the up-close candle with the highest close.
   - `_scan` builds `bz=L.Zone(..., mt=breaker_mt(...))` (Zone is frozen, so mt goes in the constructor).
   - `levels.breakers()` gets `mt_mode="range"`.
   - New Param `breaker_mt_mode="range"` ("body" switch; ValueError on other values). It is independent of `breaker_zone` (#14).

**`strategy.py`**
6. New Params `breaker_mt_respect=True`, `breaker_mt_entry_floor=True`, `breaker_mt_exit_after_t1=False`. With the first two off, the trades must be byte-identical to the baseline.
   - (a) `_scan` after bz (~l.1108): if any close in `c[broke+1:i+1]` is below bz.mt, the breaker is lost. Only closes count, and the broke bar is excluded. Then bz=None (so `uni` is empty) and `_f("x_breaker_mt_lost")` is logged. The plain-FVG order can still arm.
   - (b) Entry floor (unicorn pick only, applied before the stop and risk lines at ~l.1124):
     - if g.top <= bz.mt, drop the gap from uni, re-pick, and log `x_unicorn_below_mt`;
     - otherwise entry = max(entry, bz.mt + 0.25*es_pt), capped at g.top;
     - add bz_mt to the order dict and copy it into pos.
   - (c) Pending order (`run_day` section 2):
     - run the fill branch first;
     - if bar i did NOT fill and c[i] < bz_mt, cancel (`breaker_mt_cancel`);
     - if bar i DID fill, the same-bar stop did not trigger, c[i] < bz_mt and t1 is not hit, exit at c[i] with reason "breaker_mt".
   - (d) Position block (next to ce_hold): if i > fill_i and (not t1_done or exit_after_t1) and the close is below bz_mt, exit at the close with reason "breaker_mt".
   - Unchanged: the hard stop, sb_model's OB-MT stop, htf's ob.mt and propulsion_blocks.

**`confluence.py`** (optional, default off)
7. Keep OB inv = ob.mt. Add `conf_breakers=False`, passed to `Confluence(...)` at backtest l.114. When on, add the `breakers()` zones with inv=z.mt. Time it on a full year first (it is O(bars × pivots)).

**Tests**
- Bodies above the MT with a wick below: the order arms and the position is held.
- A close below the MT before the fill cancels the order, but does not block a fill on the same bar.
- A close below the MT after the fill exits "breaker_mt", including on the fill bar.
- Bearish mirror.
- A gap below the MT is dropped; a straddling gap gets entry = MT + 1 tick.
- All switches off gives the baseline.
- ES 2023-01-03 Ep02 replay on front-month data: breaker_mt equals that candle's (h+l)/2.
- Study report of baseline vs new, plus the funnel counts.

---

## 7. In Ep 02 the overhead 15m FVG is resistance, not a target

**Correction.** In Ep 02 the overhead 15m FVG is resistance, not a target.

**Support: partly.** The Ep 02 specifics are clear. The general cap rule is the owner's.

**Caption evidence**
- Ep02 00:02:15-00:02:27: price returns into the 15m FVG and goes lower (resistance).
- Ep02 00:04:45-00:04:51: he adds a short at the 15m FVG (an entry array).
- Ep02 00:05:03-00:05:22: "that's real support and resistance".
- Ep02 00:08:33-00:08:46: the targets are the 38.39 and 38.42.50 sell-side levels.
- Ep02 00:04:55: a 30m FVG below price is reached by a limit fill.
- Ep02 00:08:51-00:09:03: the 30m FVG above is a hold/exit line ("remain heavy").

**Rulebook now:**
- Appendix A Ep02 l.1263, "Targets: higher-TF FVGs (15m, 30m)", is the error.
- L9 (l.522-525), "Bot: FVGs are entries only, never targets", is stale.
- X1, X2, P2 item 12.
- No rule says an opposing HTF FVG caps the trade.

**Code now**
- `htf_targets=("15m","1h","4h","D")` (strategy l.174). The entry builder (~l.1172-1196) adds opposing HTF FVG near edges and CEs as rungs, and pools beyond them stay as targets. An FVG closer than 1R is silently dropped, and nothing caps the trade.
- `confluence._targets_impl` (l.175). `_zones` has no source tag. "dead" = the first close beyond the far edge.

**Coverage:**
- Ep02.5 SIMPLIFIED (build l.690).
- L9 SIMPLIFIED.
- X3f MISSING (resistance_mode).
- L4.
- New id needed: **Ep02.10 "Opposing HTF FVG = resistance cap"**.

**Package:** targets_partials

### Final build spec
Default ON: an unbroken opposing HTF FVG between the entry and the target caps the trade. The exit is just before its near edge, with no rung or draw beyond it, and no trade if the room to it is too small.

1. **`confluence.py`**
   - `_zones`: add a `src` column (FVG 0, OB 1, gap 2).
   - `Confluence.__init__`: opening-gap `add` gets `src=np.full(m.sum(),2.0)`, or the merge drops the column.
   - New `resistance(t, price, side, tfs, src=(0,))` → (level, tf, top, bottom) or None, taking real prices.
     - Mask: kind==-side, known<=now, dead>now, within life, src in src.
     - Long: rows with top>price, level=max(bottom,price), minimum over all rows. Short: the mirror.
2. **Params**
   - `htf_resist_cap=True`
   - `htf_resist_tfs=("15m","30m","1h","4h","D")`
   - `htf_resist_src=("fvg",)` ("ob"/"gap" are switches)
   - `htf_resist_buffer_pts=0.5`
   - `htf_resist_min_room=0.0`
   - `htf_resist_live=False`
   - Adding 30m to htf_targets is a SEPARATE step behind its own switch, `htf_targets_30m=False`.
3. **Entry builder** (~l.1172-1195), after the buffer comprehension and BEFORE the min_rr / `if not lv` checks:
   - now = idx[i]+tf (the bar close); `r=ctx.conf.resistance(now, sd.x(entry), sd.sign, ...)`.
   - capx = sd.x(r.level) - buffer*es_pt.
   - If capx-entry < max(min_rr*risk, min_room*es_pt): `x_htf_resist`, return None.
   - Otherwise keep the (value,kind) pairs <= capx, add (capx,"array") unless a kept value is within 1 pt, re-sort, and rebuild kinds and pools.
   - If ctx.conf is None: log `x_htf_resist_nodata` and proceed.
   - Then the existing min_rr check, `x_no_target_1R`, draw (the nearest pool <= capx, else capx) and min_draw_pts.
   - Trade fields resist_tf, resist_lo, resist_hi, capped, passed through `Trade(...)` (~l.898) and row().
   - htf_resist_live (default off): recompute on each bar close and trim the rungs.
4. **`sb_model.run_sb`:** apply the same cap to draws. If none are left, use [capx]. Return None if room < max(min_rr*risk, sb_room_pts*es_pt).
5. **Ma Deuce:** check the cap at 08:00 between entry and the CE. If there is room >= sb_room_pts, target=capx; otherwise return [].
6. **Ep02 30m "heavy" exit** (separate, default OFF): `runner_htf_exit=""` ("30m" turns it on). Use the same-side 30m FVG containing or just behind the entry. After t1, exit the remainder on the bar whose close is at or after that array's `dead`.
7. **Rulebook**
   - l.1263: "Overhead 15m FVG = resistance: he shorts from it and adds there (~2:15-2:27, ~4:45, ~5:03-5:22). Targets are sell-side liquidity and 38.39 / 38.42.50 (~8:33-8:46). 30m FVG below reached by a limit fill (~4:55-5:01). Runners held while price stays below the 30m FVG [owner #7]."
   - L9 and X1: add the cap and delete "FVGs are entries only".
   - Add coverage row Ep02.10.
8. **Tests**
   - (a) Long 4990, risk 4, pool 5010, bearish 15m FVG at 4998-5002: levels end at 4997.5, capped.
   - (b) FVG at 4992-4996: `x_htf_resist`.
   - (c) An FVG killed before the signal close does not cap. One killed after the signal close still caps.
   - (d) Short mirror.
   - (e) cap=False is byte-identical.
   - (f) A straddling FVG means skip.
   - (g) An OB caps only when "ob" is in the src switch.
   - (h) The D dict with NDOGs keeps src.
9. **A/B** on MES 1m/5m (overnight data): trades, win%, avg R, total R, capped share, and x_htf_resist / x_room_lt_10 / nodata counts. On SPY RTH data the cap is inert because conf is None.

Interactions: #2 (set htf_resist_min_room=5 if wanted); #9 (the locked draw must be on the near side of the cap).

---

## 8. "Tighten or close" before noon means close (Ep 03)

**Correction.** "Tighten or close" before noon means close.

**Support: yes.**

**Caption evidence:** Ep03 (003) never uses the word "tighten".
- 01:17:26-01:17:33: "peel that last one off and be done with it".
- 01:18:21-01:18:30: "should have been me peeling it off".
- 01:18:35-01:18:47: "the time going into noon ... lunch hour ... retracement ... take my stop".
- The exact 12:00 cut-off is our reading.

**Rulebook now:**
- X10 (l.874-877) cites ~1:12:15 (wrong) and says "Bot: AM trades may run to 16:00", which is stale.
- l.1032.
- Appendix A l.1293 calls "tighten" our wording.
- `times.md` l.129 and `execution.md` I3 carry the same cite.

**Code now**
- `am_exit=720` (strategy l.143), with the check at l.854-855, already closes all non-PM units at the close of the bar ending 12:00.
- Gaps: `sb_model.run_sb` (l.77-78) and `pre_open` Ma Deuce (l.99) check only flatten. Both are off by default.

**Coverage:** X10a FULL, Ep03.23 FULL, D16 FULL. The SB and Ma Deuce paths are not covered.

**Package:** management_exits

### Final build spec
1. **`strategy.py`:** keep `am_exit=720` and the check at l.854-855. Comment: "Ep 03 / directive 8: close (not tighten) all remaining AM-family units at the close of the bar ending 12:00".
2. **`am_exit_mode="close"`** (default). "tighten" is a TEST-ONLY switch [our interpretation] and runs once (`pos["am_tightened"]`):
   - be = basis/n (strategy), pos["entry"] (sb_model) or the stored fill (Ma Deuce);
   - new = max(stop, be, l - stop_buffer) in side space;
   - if new >= c, close with reason "am_exit"; otherwise set the stop from the next bar.
3. **`am_exit_extras=True`:** applies am_exit to the sb_model and pre_open trades. False exempts them (A/B only).
4. **`sb_model.run_sb`:** before the flatten check (l.78): `if pos["left"] and session=="AM" and p.am_exit and p.am_exit_extras and t+ctx.tf>=p.am_exit`, close with reason "am_exit" (or tighten). This covers sb_am and sb_london; sb_pm is unaffected.
5. **`pre_open.run_ma_deuce`:** store the fill. Before l.99: `if p.am_exit and p.am_exit_extras and t[i]+ctx.tf>=p.am_exit:` then append the exit with reason "am_exit" and `return [tr]`.
6. **Guard:** with am_exit>0, an AM-family pending order is cancelled on any bar where t+tf>=am_exit. This has no effect under the defaults.
7. **Docs**
   - X10: cite 003 ~1:17:26-1:18:44 and replace the stale bot line with "am_exit=720 closes all AM, PRE/NEWS, SB-AM, London-SB and Ma Deuce units at the close of the bar ending 12:00 (directive 8: close, not tighten)".
   - Appendix A l.1293: "should have peeled the last contract off (closed it) going into noon; lunch retrace took his stop (~1:17:26-1:18:44). Directive 8: close. Exact 12:00 is our wording."
   - Fix `times.md` l.129 and `execution.md` I3.
   - Add the SB / Ma Deuce note to rule_coverage X10a, Ep03.23 and D16.
8. **Tests**
   - (a) A 5m position open at 11:55 exits on that bar with "am_exit" (the 11:59 bar on 1m).
   - (b) am_exit=0 runs to "eod".
   - (c) Tighten mode sets the stop once and holds; below breakeven it closes.
   - (d) sb_am, sb_london and Ma Deuce close at 12:00; with extras=False they do not.
   - (e) PM and sb_pm are unaffected.
   - (f) With the AM window widened to (570,750), there are no fills at or after 12:00.

---

## 9. Mark up and lock the session's draw, one exact target, trade only toward it

**Correction.** Mark up levels and lock the session's draw before it opens, name one exact target, and trade only toward it.

**Support: partly.** The captions back pre-session draw calls and one-sided trading. "Lock" and "one exact target" rest on the owner's word.

**Caption evidence**
- For:
  - Ep01 00:17:08-00:18:24: the game plan and road map are set before the open; price drives to one direction of liquidity.
  - Ep01 00:24:55: 3864 was shared before the open.
  - Ep04 00:24:18-00:25:00: the draw on liquidity comes from the weekly chart.
  - Ep05 00:21:34-00:22:16: "you know the next draw ... I know where it's going to break out".
  - Ep07 00:03:11: "the 40 30 level was the objective I gave you over the weekend".
  - Ep08 00:10:54 and 01:04:20: levels tweeted pre-session, "only one-sided".
- Against:
  - Ep01 00:19:21-00:19:51: "I have to adjust and adapt".
  - Ep03 00:14:45: he doesn't mark up everything.
  - Ep04 00:25:13: "shifted gears intraday".
  - Ep05 00:23:53: several objectives in turn.

**Rulebook now:** B3 (l.201-205) says decide before the session and trade one direction, but the bot scans both sides. L14 (l.546-561) says decide the draw first. L15. Appendix A Ep01 l.1234/1240/1247 and Ep07 l.1334. Nothing about locking, one exact target or exiting at it.

**Code now**
- `run_day` (~l.764-770, 941-958) scans both sides. `want` applies only when htf_bias != "off" (default "off").
- `_scan` (~l.1170-1195) sets draw = the nearest pool >= min_rr at arm time, with the ladder over several levels.
- `sb_model._arm` draws from draws[0]. Ma Deuce targets the CE. Neither uses `want`.
- `htf.table` already builds a pre-09:30 draw_up/draw_dn, but once per day only and unused as targets.

**Coverage:**
- B3, L14a SIMPLIFIED.
- L14, L14d, L14e, B2, M0.1, M3.2, B17.3, N9.2, T8, Ep07.1, Ep03.12.
- Ep01.14 is marked FULL, which is wrong for this directive.
- None locks one exact target per session.

**Package:** bias_htf (also touches targets_partials, silver_bullet, setups_models)

### Final build spec
Default: before each session, mark up the levels and lock ONE draw (side plus exact price). Trade only toward it, exit at it, and end the session once it is delivered.

1. **Params**
   - `draw_lock="session"` ("off" reproduces today exactly)
   - `draw_lock_pick="nearest"` ("ordered" once the B2 columns exist)
   - `draw_lock_neutral="skip"|"both"`
   - `draw_lock_levels="frozen"|"live"`
   - `draw_lock_partials=True`
   - `draw_relock=False` (test switch)
2. **Lock time** (no look-ahead)
   - AM t_lock = am_start; PM = p.pm[0] (13:30); PRE7 = 420; PRE9/NEWS = 540. The SB, last-hour and pm_sb windows inherit their parent's lock.
   - Use only bars with `t+tf <= t_lock`. The lock price is the last such close.
   - `htf.table(cut_min=570)`: the overnight high, low and last use only bars with tmin+bar_minutes <= cut_min. The default must give the current table byte for byte.
   - `backtest` builds one table per t_lock in use and passes `bias_by_cut={t_lock:row}` to `run_day`.
   - `paper.py` passes the same (or `run_day` computes it internally). Test that paper and backtest lock the same.
3. **`mark_levels(ctx, sd_up, bias_row, t_lock, session, spent)`**
   - HTF candidates: draw_up/dn from the cut table.
   - Session candidates, from bars closed by t_lock: PDH/PDL1-3, overnight H/L recomputed before t_lock, prev week/month if on, NWOG/NDOG edges and CE, ORG if known. PM only: AM H/L and lunch H/L.
   - Each candidate keeps its kind (pool or array).
   - Drop levels already traded through (L14d). Levels hit earlier the same day go to `spent` (L14e).
   - "nearest": the smaller distance up or down sets the side. A side with no candidate loses. No candidates or a tie means neutral.
   - Store `ctx.lock[session]={side,target,kind,name,t_lock,marked}`. It is immutable.
   - Neutral "skip" stops only that session.
4. **Side gate** (per session)
   - Run loop ~l.941-948: `continue` if sd.sign != lock.side. Leave the per-day `want` alone; both gates apply if htf_bias is on.
   - sb_model and Ma Deuce gate on the parent lock.
   - Re-entries only toward the same lock.
5. **One target** (`_scan` ~l.1172-1195, `sb_model._arm` l.159-178, the Ma Deuce target)
   - T by kind: pool under "split" → sd.x(target)+pool_beyond; otherwise sd.x(target)-exit_before.
   - Reject with `x_room_lt_10` (keep the name) unless T-entry >= min_draw_pts*es_pt and >= min_rr*risk.
   - lv:
     - frozen = the marked levels between entry+min_rr*risk and T, then T;
     - live = the current levels below T, then T;
     - partials off → [T];
     - always lv[-1]==T.
   - draw=T. All remaining size, adds included, closes at T, and no trail may hold past it.
   - SB: t1=min(entry+sb_target, T) only under the cap switch; runner = T.
   - Ma Deuce: target = whichever of CE and T is nearer; skip if the CE is on the wrong side.
6. **Delivered:** any closed bar reaching the lock target sets done[session], before or after entry. Log `x_draw_delivered`. Ties in with B17.3 / N9.2.
7. **Logging:** Trade fields draw_side, draw_px, draw_name, draw_kind. A `locks` list {day, session, side, px, name, delivered, delivered_t, traded} so the draw call itself can be scored.
8. **Coverage and rulebook**
   - B3, L14, L14a, M0.1 and M3.2 are covered by draw_lock. Ep01.14 goes FULL → SIMPLIFIED until this lands.
   - B3 and L14: "Mark up levels and lock the session's draw before it opens; name ONE exact target and trade only toward it; exit at it; session ends when delivered."
   - Mark as [our interpretation]: the nearest-candidate pick, lock times = session starts, partials before T, and relock as a test switch.
9. **Tests**
   - (a) PDH nearer → +1, and no shorts in AM, SB or Ma Deuce.
   - (b) Mutating bars after t_lock does not change the lock (AM, PM, PRE7; tf 1 and 5). `htf.table(cut_min=570)` equals the old table.
   - (c) The final exit is T under both exit modes, and adds close at T.
   - (d) Less than 5 pts of room → `x_room_lt_10`.
   - (e) Delivered before entry → no trade. Delivered by a trade → no re-arm.
   - (f) A level spent in AM is not the PM lock.
   - (g) "off" is identical to today.
   - (h) A neutral AM still allows PM.
   - (i) The paper lock equals the backtest lock.
   - Backtest on vs off, plus the draw-call hit rate.

---

## 10. Experienced traders stand aside on sloppy days

**Correction.** Experienced traders stand aside on sloppy days. Write "sloppy" as our interpretation.

**Support: partly.** The stand-aside is explicit in the captions. "Sloppy" is never defined.

**Caption evidence**
- Ep08 (010) 01:16:37-01:17:23: "sloppy consolidations ... low probability". New traders keep the charts on to study. "Seasoned students ... turn the charts off and walk away".
- Ep08 00:30:08: "choppy and sloppy until it does certain things". 00:24:22: choppy.
- Ep03 (003) 00:58:43-00:58:53: "sloppy day ... I don't like to engage them".
- Ep03 00:18:23-00:18:49: FOMC + NFP week has a tendency to sloppy delivery. 00:02:58: Thu/Fri of NFP week are choppy.

**Rulebook now:**
- B17.2 (wait), B17.4 (sloppy session named, no action), N7 (August), N8.1 (consolidation = no trade), N8.
- Appendix A Ep03 l.1271 (NFP week no trade). The 00:58:43 line is not recorded.
- Appendix A Ep08 l.1347 presents scalping as the action.
- `experienced_rules.md` row 20 and l.80 say "no change", which contradicts the owner.

**Code now**
- No sloppy or chop concept. The closest pieces:
  - `day_context` big_prev (l.627-666);
  - `neutral_skip=False` (l.176, return at l.747);
  - `nfp_week_block=False` (l.152, logic at l.221-225);
  - `bias_neutral`;
  - `_split` slow_frac (ladder only).
- `run_day` returns at l.747 before `run_sb` and Ma Deuce, so neutral_skip already covers them.

**Coverage:** B17.4 MISSING; Ep08.2 SIMPLIFIED (build l.829 chop_mode); B17 neutral_gate (l.820); N8/N8.1/N8.5 (l.171-176, builds l.915-916 consol_skip); X14b MISSING; Ep03.1 FULL. None makes stand-aside the default, and no Ep03 id covers 00:58:43.

**Package:** day_week_context

### Final build spec
Default (directive 10): stand aside on sloppy days. No new entries and no adds in any entry path while a sloppy reason is active; open positions keep their normal management. Trading these days stays available as a switch. **"Sloppy" detection is [our interpretation] throughout.**

1. **Helpers** (`strategy.py`)
   - `_adr5(days)`: None if fewer than 5 days. Use `_adr5(hist[-5:])` in `_split` and `_adr5(hist[-6:-1])` in day_context. No behaviour change.
   - `sloppy_day(hist, day, p)` → set of day-level reasons:
     - "big_prev": hist[-1] range > sloppy_big_mult (2.0) × `_adr5(hist[-6:-1])`.
     - "nfp_week" / "nfp_week:PM": through `blocked()` with nfp_week_block forced on. It keeps nfp_thu. **OWNER DECISION:** with nfp_thu=True (the default) only Wed PM is blocked (plus Fri when NFP is not on a Friday). Decide whether stand_aside sets nfp_thu=False, and whether to add "fomc_week" (Ep03 00:18:23; not included).
     - "premium_run": off by default.
   - `class Chop` (one per day, built in run_day and passed to run_sb and Ma Deuce):
     - ref = `ctx.opens.get("midnight")` (SPY: the 04:00 stand-in). Inert if ref or adr5 is missing.
     - `update(i)` at bar i's close, from t >= sloppy_chop_from (120). It turns on when the range since ctx.start is < 0.35×adr5 and the closes have changed sign against ref at least 4 times. lo/hi are frozen then.
     - It releases on a close beyond hi/lo ± 0.25×adr5. Once released it never re-triggers that day.
     - Timing: the flag after update(i) gates arming on bar i's close and gates fills and adds from i+1. A pending order is dropped before step 2 of bar i+1. Arming can resume on the release bar's close.
2. **Params**
   - `sloppy_mode="stand_aside"` (default).
   - "scalp": a single exit at min(5×es_pt, T1), no adds, no runner, in all three engines.
   - "off": tag only.
   - `sloppy_tests=("big_prev","chop","nfp_week")`; thresholds 2.0 / 0.35 / 4 / 120 / 0.25 / 5.0.
   - Back-compatibility: neutral_skip=True with mode "off" acts as stand_aside with ("big_prev",). nfp_week_block still works.
   - Comment block citing the captions and [our interpretation].
3. **Gate**
   - `run_day` replaces l.746-747. Day reasons append (day, symbol, "sloppy", reasons) to a NEW optional `skips` list (do not touch the 8-tuple `log`) and return [] before Ma Deuce and run_sb.
   - In the bar loop, `chop.update(i)` runs at the start of step 3. Skip arming in every session (PRE7/PRE9/NEWS included) when chop is active or nfp_week:PM applies in PM. Drop the pending order and block adds.
   - `run_sb` and `run_ma_deuce` get a `chop` param. Ma Deuce uses a precomputed `chop.on_at`.
   - Trade field `sloppy=""`, filled in every mode. Add it to the backtest report column list (l.203).
4. **Docs**
   - Appendix A Ep08 l.1347: "Sloppy consolidations: seasoned traders turn the charts off and walk away; new traders keep charts on to study but do not trade (01:16:37-01:17:23). Bot default = stand aside; 2.5-5 handle scalps only as a switch. 'Sloppy' detection is [our interpretation]."
   - Ep03: add the 00:58:43 and 00:18:39 lines plus a new coverage id.
   - B17.4 and N8 point to sloppy_mode.
   - This one helper closes Ep08.2, N8.1, N8.5 and the B17 neutral_gate.
   - `experienced_rules.md` row 20 / l.80: "stand aside (owner directive 10)".
5. **Tests**
   - (i) Prior-day range at 3× adr5: 0 trades with SB and Ma Deuce on, and one `skips` row. "off" equals the old trades, excluding the `sloppy` column.
   - (ii) Chop morning: no arming after the trigger; a pending order is dropped; arming resumes on the release bar.
   - (iii) NFP week: Thursday under nfp_thu False vs True; Wed PM blocked and Wed AM traded.
   - (iv) Scalp mode: +5, no adds.
   - (v) The neutral_skip alias.
   - (vi) The no-look-ahead truncation test with the defaults.
   - (vii) ES/MES 2019-2025, off vs stand_aside vs scalp, by reason. If chop flags more than ~30% of days, tell the owner.
   - The new default changes the existing baselines and paper/live behaviour. Re-baseline and say so in the commit.

---

## 11. Ep 07 advanced entry at the OB bodies before the break

**Correction.** Ep 07's advanced entry at the order block bodies before the break is the default. Entry after the shift is a switch.

**Support: partly.** The behaviour is shown, but not stated as a general rule.

**Caption evidence**
- For:
  - Ep07 (009) 00:02:10: "the down close that I entered on that's an order block", after the ~09:40 purge.
  - 00:03:49: the "advanced model", expecting expansion.
  - 00:11:06-00:11:22: the bullish OB, "that entire range ... go long another partial or independent entry".
  - 00:12:50-00:13:41: "not a buy there ... fair value gap ... bullish order block ... went long ... midpoint or mean threshold of that down closed candle".
  - 00:15:03-00:16:09: accumulating inside the candle before the break of the 09:30 high.
  - 00:08:11: "entering long on down closed candles".
- Against: the first fill was inside the FVG (00:01:00), and "advanced" refers to expansion.

**Rulebook now:**
- M1 (l.584-597): entry at the FVG after the MSS.
- D10 (~l.984-989) recommends A (after the MSS), the opposite of the owner.
- M4 Advanced (l.644). Appendix A Ep07 (l.1333+).

**Code now**
- `_scan` (l.1027-1215) is sweep → MSS → FVG. It returns None until `sw["broke"]`.
- The OB is used only for the stop (ob_mt; ep07_stop off).
- Adds go only on new FVGs. There is no pre-MSS entry anywhere.

**Coverage:** M1.4 SIMPLIFIED ("No early OB entry"), D10 MISSING (early_entry / turtle_soup), the M1 build `ob_pre_mss_entry`, M4.3 MISSING, Ep07.2 SIMPLIFIED, Ep07.5 MISSING. All are framed as optional.

**Package:** setups_models

### Final build spec
Default (#11): Ep 07's advanced entry at the bullish OB bodies before the break. Entry after the MSS at the FVG is a switch.

1. **Params**
   - `ob_entry="pre_break"`. "post_mss" is exactly the current path; "both" is described in step 3.
   - `ob_entry_px="body_top"` (max open of the series; the body bottom for bearish via side space). Others: "mt" = (max open + min close)/2; "range_top".
   - `ob_arm="leave"` [our interpretation]: armed at the close of a bar i > k_last with c[i] > body top. "touch" arms on the first bar after k_last.
   - `ob_stop="mt"` (body MT - stop_buffer). The fallback to "ext" (`sw["ext"]` - buffer) applies when risk < min_risk_pts or entry <= stop [our interpretation]. This covers every px value.
   - `ob_entry_cancel_on_mss=False`.
   - No HTF or SMT gates and no half risk. The global filters still apply.
2. **`_ob_at_low(sd, sw, i)`**
   - Candidates: down-close bars in [ext_i-3, min(i-1, ext_i+2)], closed bars only.
   - k_last = the nearest to ext_i (ties go to the later bar, as in ep07_stop l.1130-1132). Extend back over consecutive down-close bars to j.
   - Return body_top, body_low, mt, hi and lo.
   - Freeze the result in `sw["ob"]`. Clear `sw["ob"]` and `sw["ob_sent"]` on re-anchor (`sw.update`, l.1057).
3. **`_scan`, the `broke is None` branch** (l.1071-1076)
   - If the mode is pre_break or both, `ob_sent` is not set, the OB exists and it is armed, build the order.
   - **Refactor first:** factor l.1134-1219 into `_finish_order(ctx, sd, i, p, sw, session, entry, stop, risk_mult, **tags)` so every key the fill code reads at l.896-913 is present.
   - Order values: leg_hi = h[ext_i:i+1].max(), entry_kind "ob_pre", unicorn False, fvg_bottom = body_low, fvg_ce = mt, mitigation and propulsion False, plus ob_body_low, ob_lo and ob_pre=True.
   - Skip the arm-time leg_pd.
   - Set `ob_sent=True` whether the filters pass or not. Do not consume `sd.sweep`.
   - Later MSS on the same sweep:
     - pre_break: sweep=None, return None. No FVG entry ever; a re-anchor resets.
     - both: the FVG path runs. If an ob_pre order is pending and cancel_on_mss is False, keep the lower entry in side space (compare in the run loop at l.955-958); otherwise replace it.
4. **Pending** (step 2, l.877-893), for ob_pre:
   - Keep the cut, pending_minutes and E5.
   - Body-violation cancel: if i-1 > the arm bar and c[i-1] < ob_body_low, cancel. Never use c[i].
   - Bypass leg_pd_at=="fill" (l.890-892).
   - Drop the "new low below ext" cancel; it cannot happen before a fill.
5. **Adds**
   - The existing FVG adds are unchanged; the FVG from the later MSS is the first add.
   - New OB re-entry add, `ob_adds=True` [our interpretation of "accumulate more"]: a fresh down-close series with low >= stop and a close above its body top arms an add at its body top. Same fractions, capped by max_total_risk, coordinated with #12 (1.2% / 1.3%).
6. **Scope:** AM, PM, PRE7, PRE9 and NEWS via `_scan`; with entry_tf="5m" the 1m OB is used. `sb_model` and Ma Deuce are unchanged; say so in the docs.
7. **Bearish:** comes free from Side mirroring. Test it.
8. **Docs**
   - M1 Entry: "Default (owner #11; 009 ~2:10, ~11:06, ~13:35, ~15:03): limit at the bodies of the bullish OB at the sweep low before the break of the reference high. FVG after the MSS = switch ob_entry='post_mss'; 'both' takes either."
   - D10: Recommended → B, A as a switch, drop the HTF+SMT gating.
   - Appendix A Ep07: owner note.
   - rule_coverage M1.4, D10 (the early-OB half), Ep07.2 and Ep07.5 → FULL when built.
   - `owner_directives.md` #11; CLI flags --ob-entry, --ob-entry-px, --ob-stop.
9. **Tests**
   - (a) pre_break fills at bar >= arm+1 as ob_pre, with the MT/ext stop, and gives no FVG order after a later MSS.
   - (b) A body-violation close at i-1 cancels; a violation on the fill bar does not.
   - (c) Bearish mirror.
   - (d) "both": expiry followed by an FVG entry; the lower-entry rule.
   - (e) post_mss is identical. Pin the golden tests, study CURRENT and the crosscheck to post_mss, or regenerate them.
   - (f) No re-send: pending["i"] is stable.
   - (g) ES 2023 A/B of pre_break / post_mss / both on front-month data (#13), including the ext-fallback share.

---

## 12. Open risk 1.2% at entry, at most 1.3% with adds (Ep 07)

**Correction.** Open risk is 1.2% at entry and at most 1.3% with adds (Ep 07), not 2%.

**Support: yes.**

**Caption evidence**
- Ep07 (009) 00:05:20-00:05:49: eight contracts, a $100k account, "the risk on this trade is 1.2 percent ... that's the goal I'm reaching for percentage-wise".
- 00:08:22-00:08:27: after the add, "elevated to 1.3 percent ... minuscule".
- 00:19:16-00:19:21: "risking no more than one point three percent".
- No 2% anywhere in Ep 01-08. Ep04 ~2.1% is one example.

**Rulebook now:**
- E8 (l.775-777): 1% default, with the bot at risk_dollars=1000.
- E11 (l.787-788): max_total_risk=2000 (2%).
- Appendix A Ep07 l.1342 (~1-1.3%); Ep04 l.1287 (~2.1%).
- `owner_directives.md` item 12 is recorded but not applied.

**Code now**
- `risk_dollars=1000` (l.97) and `max_total_risk=2000` (l.106).
- First unit: `_scan` l.1200 `_lots(min(risk_mult*risk_dollars/risk, max_notional/|entry|), lot)`. The same at pre_open:70 and sb_model:170.
- Add gate at l.871-875: `basis - stop*n + (g.top-stop)*q <= max_total_risk`. This is correct for shorts because of Side mirroring, but it can go negative.
- Fixed dollars only, no equity.

**Coverage:** E8 SIMPLIFIED (build l.655 says "2% clamp", which is wrong); E11 SIMPLIFIED (l.656); E12/E12a-f.

**Package:** entries_stops_sizing

### Final build spec
Units: 1 unit = $1 per instrument price point. Stops are in instrument price units, and es_pt only converts ES points. SPY lot=1, MES lot=5, ES lot=50.

1. **Params** (l.97/106)
   - `account_equity=100_000.0`, `risk_pct=0.012`, `max_total_risk_pct=0.013`.
   - `risk_basis="fixed"|"equity"` (equity = start-of-day equity from earlier days' closed trades).
   - `risk_dollars` and `max_total_risk` become `float|None=None` overrides. Study preset `legacy_1pct_2pct = dict(risk_dollars=1000.0, max_total_risk=2000.0)`.
   - Helpers `_risk_budget(p,eq)` and `_total_cap(p,eq)`.
2. **Equity plumbing:** `run_day(..., equity=None)` → ctx.equity. `backtest.run` (l.133) passes account_equity + the sum of earlier rows' net when the basis is "equity". `paper.py` passes nothing. `run_ma_deuce` and `run_sb` read ctx.equity.
3. **First unit:** `_lots(min(risk_mult*_risk_budget/risk, _total_cap/risk, max_notional/|entry|), lot)` at `_scan` l.1200, pre_open:70 and sb_model:170 (risk_mult=1 there). risk_mult is only `reentry_half` (l.953-954), so a re-entry risks 0.6%.
4. **Adds** (l.870-875; side space, no sign handling)
   - q = `_lots(tr.shares*adds[k], lot)`.
   - at_risk = max(0, basis - stop*n). The clamp is the only fix.
   - d = g.top - stop; skip if d <= 0.
   - room = cap - at_risk. If d*q > room, q = `_lots(room/d, lot)`.
   - Queue only if q >= lot.
   - The gate at g.top is conservative, since the fill is at min(px, o).
5. **Reporting:** Trade fields entry_risk_pct (shares*(fill-stop)/eq at fill, l.907) and peak_risk_pct (after the add fill and stop updates in each bar: max(0, (basis/n - stop)*left)/eq). Round both to 5 decimals.
6. **Rulebook and coverage**
   - E8: "Default open risk 1.2% of equity at entry (Ep 07 ~5:32 'the goal ... percentage-wise'); risk_pct=0.012, risk_basis fixed|equity; 1% = legacy preset."
   - E11: "Max open risk 1.3% incl. adds (Ep 07 ~8:24, ~19:21); 2% not stated in Ep 01-08 (cc02_004 only; Ep 04 ~2.1% one example); max_total_risk_pct=0.013."
   - rule_coverage E8 (row 317 / build 655): "1.2% entry / 1.3% total cap, start-of-day equity". E11 (320/656) covered.
7. **Tests** (`tests/test_strategy.py`)
   - (a) A 10-pt stop with es_pt=1 at $100k: MES = 120 units (24 contracts), ES = 100 units (2 contracts). SPY with a 1.00 stop: 1200 shares.
   - (b) An add that would reach $1,350 is shrunk or skipped. peak_risk_pct <= 0.013 across a SPY backtest.
   - (c) A mirrored short matches.
   - (d) The legacy preset reproduces the old list except the new columns (list the trades where the old negative at_risk allowed an add, or test with the clamp off).
   - (e) A reentry_half trade risks 0.6%.
   - (f) The equity basis is causal.
- Notes: only 0.1% of headroom is left for adds, so most pyramid adds will be shrunk or skipped. Report both presets. SPY sizes rise about 1.2×; check max_notional. Applying 1.2% / 1.3% to every trade, and measuring open risk against the current stop (0 at or past breakeven), is [our interpretation].

---

## 13. Levels from the actual front-month contract, not the back-adjusted series

**Correction.** Round numbers and levels come from the actual front-month contract prices, not the back-adjusted series.

**Support: partly.** ICT clearly uses the named front-month contract, but he never mentions back-adjustment.

**Caption evidence**
- Ep01 (001) 00:08:08 and 00:29:32-00:29:55: he corrects himself to "esh2023 which is the front month"; the levels (3864) come from that chart.
- Ep03 00:07:00-00:07:17: "esh2023 ... front month ... when that expires we'll be going to June".
- Ep02 00:02:37: "nice round number 3 900", which is only round on the real ESH2023 prices.
- Ep05 00:17:40 and Ep03 01:11:43: exact contract prints.

**Rulebook now:** silent on the price series. L17 (~l.569) rounding is off. N7.5 is a roll tag. Appendix A Ep02 (~l.1260) names the round-number pool. `levels.md` 1i/#21 has round numbers default off. Owner directive 13 is recorded.

**Code now**
- `databento_data.py` downloads ES.v.0 (volume roll). `back_adjust()` shifts the pre-roll bars and does not save `adj`. `_1min_db.csv` has instrument_id and roll; `_5min_db.csv` has instrument_id but no roll.
- `backtest.load(source="databento")` reads the adjusted file, and `_read` keeps only OHLCV.
- Every pre-latest-roll day is offset by the summed roll jumps. P&L is unaffected (the logic is relative), but reported prices are wrong. No round pools exist yet.

**Coverage:** no direct item. Related: L17 MISSING, Ep02.2 SIMPLIFIED (no round pools), N7.5 SIMPLIFIED, B20.2. A new **DATA1** item is needed as a prerequisite for L17, Ep02.2 and N7.5.

**Package:** data

### Final build spec
DATA1 front-month price frame (default ON). The engine keeps running on the back-adjusted series, which gives the same decisions because the logic is relative. Conversion to front-month prices happens only where absolute price matters. Rule tagged [owner]. "Front month = Databento volume roll at 00:00 UTC" is [our interpretation].

1. **`databento_data.py`**
   - `back_adjust()` also writes `df["adj"]` (raw = adjusted - adj).
   - 5-min build: `"adj": g.adj.last()`, `"roll": g.roll.any()`.
   - Rebuild ES, NQ and YM from the cached .dbn.zst. No download, no cost.
2. **`backtest.py`**
   - `_read()` stays OHLCV-only.
   - New `load_meta(symbol, minutes, source)` → [adj, instrument_id, roll] on the same index, with its own cache; None for other sources or old CSVs.
   - `run(..., meta=None)` passes a per-day slice (evening plus the day frame) and off_d = adj at the 00:00 bar. Each calendar-day frame holds one contract, because rolls happen at 19:00/20:00 ET.
3. **Params:** `price_frame="front_month"`; "back_adjusted" (old reports); "raw" (diagnostic). With meta=None, behaviour is identical to today.
4. **Absolute-price features** (with L17 / Ep02.2)
   - A real level R at bar i is compared at R + adj_i, the adj of the latest closed bar (look-ahead free).
   - `round_pools=True`: untaken 00/50 handles as pools and targets (Ep02 "3 900").
   - `round_pool_step_pts=50` (25 alternative). NQ 100/50, YM 500/100.
   - L17 `round_step_pts` (default 0) uses the same mapping.
   - Forced off, with a warning, when the frame is back_adjusted or meta is missing on futures. Off on SPY unless mapped.
   - Bars in evening or pre-open windows that span a roll use their own adj_i.
5. **Reporting:** Trade fields `contract` and `adj`. row() writes real = engine - adj for entry, stop, t1, t2, exits and adds, plus `adj`. P&L is unchanged. A trade held across a roll uses each exit bar's own adj.
6. **N7.5 hook:** roll_day = meta.roll from the prior 18:00 through the day, or an instrument_id change. It is independent of day_type.
7. **Optional, default off:** `roll_kind="calendar"` (ES.c.0, paid; run quote() and get the owner's go-ahead) and `roll_spread="same_bar"` (paid). Caveat [our interpretation]: days before the current contract are its predecessor shifted by the roll jump, which approximates but is not the named contract's own back-month prints.
8. **Docs**
   - Rulebook §2.5 near L17 and Appendix A Ep01/02/03: "[owner] Levels and round numbers are read on the actual front-month contract (e.g. ESH2023), never a back-adjusted continuous series (001 ~29:32-29:55; 003 ~7:00-7:17; 002 ~2:37). Bot: engine runs back-adjusted, absolute levels mapped by per-bar adj, reports in real prices."
   - rule_coverage: a new DATA1 row, listed as a prerequisite in L17, Ep02.2 and N7.5.
9. **Tests**
   - (a) Synthetic 20-pt roll: adj is 20 before and 0 after, and adjusted - adj = raw.
   - (b) With round_pools off, trades and P&L are identical with and without meta.
   - (c) ES 2023-01-03 has a round pool at a real 3900.00.
   - (d) Reported prices lie within that day's ESH2023 raw range in `_1min_dbraw.csv`.
   - (e) Truncation no-look-ahead across an evening roll.
   - (f) Non-databento sources are unchanged.

---

## 14. Breaker zone: full range by default, bodies as a switch

**Correction.** Ep 02, 05 and 07 use the full range for the breaker zone and Ep 01 uses the body. Default to the majority and keep bodies as a switch.

**Support: partly.**

**Caption evidence**
- Ep01 (001) 00:56:19-00:56:32: "it left the high of this body" (body).
- Ep02 (002) 00:03:37-00:03:54: MT = "half of that range from the candle's high and low" (full range).
- Ep05 (007) 00:11:34-00:12:02, 00:15:20 and 00:22:49: the 5m candle's "range ... take your rectangle" (full range).
- Ep07 never says "breaker". Its "entire range" / "entire candle" (00:11:06, 00:15:03) refers to a bullish OB, so counting Ep07 is the owner's reading.
- Tally: body 1, range 2 explicit plus Ep07 by analogy.

**Rulebook now:**
- A13 (l.131-139) defers the extent to D6.
- D6 (l.953-960) recommends the body, and its "bot today" note is stale.
- P2 #13 (l.1137), M4.
- Appendix A Ep01 l.1233 (body); Ep05 l.1312.
- `owner_directives.md`:40 is recorded but the rulebook is unchanged.

**Code now**
- `breaker_zone="body"` (strategy l.145). `_scan` l.1099-1108 picks the up-close candle with the HIGHEST CLOSE between L1 and the sweep extreme. Unknown values silently fall into "range".
- bz is used only for the unicorn preference and flag.
- `levels.breakers()` (l.107-139) is unused: it uses the last up-close candle, full range, with no mode.
- `study.py` CURRENT has "range"; DECISIONS has "D6_breaker_range".

**Coverage:** D6 SIMPLIFIED; A13/A13.2/A13.3 (shared helper planned, l.579); Ep01.6; Ep05.1; M4/A13.4. The default flip is not yet a build item.

**Package:** levels_detectors

### Final build spec
1. **`levels.breaker_zone(o,h,l,c,a0,ext_i,i,kind="bull",mode="range")`**
   - Candidates: up-close candles in [a0, ext_i] (closed bars only). Choose the HIGHEST CLOSE, which is today's rule, not body size.
   - bear: down-close candles, lowest close.
   - range: Zone(kind, h[k], l[k], i=i, src=k, mt=(h+l)/2).
   - body: Zone(kind, max(o,c), min(o,c), mt=(o+c)/2).
   - "leg"/"last" raise NotImplementedError("planned D6"). Any other value raises ValueError. Return None when there is no candidate.
   - The MT follows the mode, so the default MT = 50% of the range (Ep02 ~3:47; ties to #6).
2. **`strategy.py`**
   - `breaker_zone="range"`, with the comment "owner #14: Ep 02/05 (and Ep 07 OB, our interpretation) use the candle's full high-low range; 'body' = Ep 01 switch".
   - Validate once at run start (`__post_init__` or the backtest entry).
   - `_scan`: keep the a0 computation and replace l.1099-1108 with `bz=L.breaker_zone(sd.o,h,l,c,a0,sw["ext_i"],i,"bull",p.breaker_zone)`. Prices are already mirrored for shorts, so always pass "bull".
   - uni, pick and the unicorn flag are unchanged.
3. **`levels.breakers(o,h,l,c,n=2,mode="range")`**
   - Keep the detection.
   - Replace the order_block candle choice with the helper. ext_i = H.i+1+argmin(l[H.i+1:i]) for bull, or argmax of h for bear (bars before i).
   - Emit at the break bar. breakers() and `_scan` then agree.
4. **`study.py`:** CURRENT keeps "range". Replace DECISIONS "D6_breaker_range" with "D6_breaker_body": dict(breaker_zone="body"), and update any notes citing the old key.
5. **Docs**
   - A13: "Zone = full high-low range of the highest-close up-close candle between L1 and the sweep extreme (Ep 02 ~3:37; Ep 05 ~11:34, ~15:20, ~22:49); MT = 50% of that range; body-only is a switch (Ep 01 ~56:19)."
   - D6: Recommended = full range (owner #14); body is the switch; leg and last are planned. Fix the stale note.
   - P2 #13: default range.
   - Appendix A Ep01: "[corrected] break judged on a body close; zone extent default is full range (Ep 02/05/07), body is the switch".
   - Appendix A Ep05: "breaker zone = the 5m candle's range, drawn as a rectangle extended in time (~11:34-12:07)".
   - Ep07 support marked [our interpretation].
   - `rule_coverage.md` D6 and A13 rows; `definitions_audit.md`:200.
6. **Tests**
   - (a) A wick-only FVG overlaps "range" and not "body". The mt values are right. The default is "range".
   - (b) "bogus" raises ValueError; "leg" raises NotImplementedError.
   - (c) The existing test_bullish_breaker still passes (src==4, (10.4, 9.7)) and equals the helper (a0=2, ext_i=7, i=10). Add a bearish case.
   - (d) Golden regression: new defaults equal the old code run with "range"; new "body" equals the old defaults.
- Effect note: the breaker affects trades only through the unicorn preference until the A13.4/M4 breaker_entry and Ep05.1 breaker_levels items are built. Those must call `L.breaker_zone` with `p.breaker_zone` and use zone.mt.

---

## Summary table

| # | package | default change | switch |
|---|---|---|---|
| 1 | news_calendar_times | Last-hour tag covers 15:00-15:50 (sweet spot 15:15-15:45 is tag `lh_sweet` only); futures flatten at the 16:15 session close; RTH history capped at 16:00 | `last_hour_strict=True`; `flatten=960` |
| 2 | targets_partials (+ silver_bullet, management_exits) | 5 handles = minimum room to the draw's exit price; SB targets the draw; filter tag `x_room_lt_min` | `sb_target_mode="fixed"`; `t1_fixed_pts`/`t1_fixed_all`; `day_target_pts`; `min_draw_pts=10` |
| 3 | day_week_context | Last trading day of the year takes its side from December (`year_end="december"`, map "squaring", **pending owner confirmation**) | `year_end="long"\|"tag"\|"off"`; `year_end_map="with"` |
| 4 | news_calendar_times | No entries until the news dealing range has formed; NFP 30-min floor only; range used as pool and target | `news_wait="fixed"\|"off"` |
| 5 | setups_models | Unicorn tagged and reported in both directions (`unicorn_side`) | `unicorn_sides="long"\|"short"` |
| 6 | levels_detectors (+ entries_stops_sizing, management_exits) | Breaker MT (full range) respect: lost-breaker, entry floor, cancel, body-close exit; OB-MT respect kept | `breaker_mt_respect`/`breaker_mt_entry_floor=False`; `breaker_mt_mode="body"`; `conf_breakers` |
| 7 | targets_partials | An unbroken opposing HTF FVG caps the trade (exit before its near edge, no trade if room is short) | `htf_resist_cap=False`; `htf_resist_src`; `htf_resist_live`; `runner_htf_exit="30m"` |
| 8 | management_exits | Close (not tighten) all AM-family units at 12:00, now including SB-AM, London SB and Ma Deuce | `am_exit_mode="tighten"`; `am_exit_extras=False`; `am_exit=0` |
| 9 | bias_htf (+ targets_partials, silver_bullet, setups_models) | Lock one draw per session before it opens; trade only toward it; exit at it; session ends when delivered | `draw_lock="off"`; `draw_lock_neutral`; `draw_lock_levels`; `draw_relock` |
| 10 | day_week_context | Stand aside on sloppy days (big_prev, chop, NFP week) [our interpretation] | `sloppy_mode="scalp"\|"off"`; `sloppy_tests` |
| 11 | setups_models | Limit entry at the OB bodies before the break (`ob_pre`) | `ob_entry="post_mss"\|"both"`; `ob_entry_px`; `ob_stop` |
| 12 | entries_stops_sizing | 1.2% open risk at entry, 1.3% cap with adds | preset `legacy_1pct_2pct`; `risk_basis="equity"` |
| 13 | data | Front-month price frame: absolute levels mapped by per-bar adj; reports in real contract prices; round pools on futures | `price_frame="back_adjusted"\|"raw"`; `roll_kind="calendar"` (paid) |
| 14 | levels_detectors | Breaker zone = full high-low range of the highest-close candle; shared helper | `breaker_zone="body"` |
