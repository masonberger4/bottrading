# Owner directives (Mase) - binding for the build

These override the rulebook where they differ. Source: the owner's own check of the Ep 01-08
captions (2026-10-18) plus earlier owner decisions in this project.

## Standing decisions
- The bot follows ICT's EXPERIENCED-trader version wherever he distinguishes (news days, reversals,
  room, NWOG lifetime, ...).
- Every ICT rule is built in full detail, not simplified. Judgment calls get the closest exact rule,
  marked "[our interpretation]".
- New behaviour goes in as a Params switch; contested choices keep the alternative as a switch.
- Silver Bullet off by default until a version holds up in testing.
- Management default: 50/25/25 scale-out (80/20 on slow / news-ahead days), breakeven only after the
  first partial and expansion, trail under FVGs formed since each partial; stop-to-the-array trail as
  a switch. CE body-close exit off by default (Ep 04 holds and adds).
- No 08:30 entries; pre-09:30 setups are test-only switches.

## Ep 01-08 caption corrections (2026-10-18)
1. Last-hour window: entries allowed 15:00-15:50; 15:15-15:45 is only the typical sweet spot (tag).
   Ep 08's PM session 13:30-16:15 wins over Ep 01's.
2. 5 handles is the MINIMUM room, not the goal. Targets are the draw / PD arrays, not a fixed +5
   (applies to the Silver Bullet's fixed +5 target too; keep +5 as a switch).
3. Year end takes its side from December's direction, AGAINST it (positions squared: December down ->
   bullish repricing, December up -> bearish), not always bullish. **[OWNER ANSWER 2026-10-18: (a) - the year-end move goes AGAINST December's direction because positions get squared, as in Ep 01. Default year_end="december", year_end_map="squaring".]** The
   only caption example (Ep 01, Dec 2022 down -> shorts squared -> rally) runs AGAINST
   December's direction, the opposite of the mapping written here. `year_end_map="squaring"`
   (Dec down -> long, Ep 01) vs `"with"` (this line). Confirm which, then `year_end="december"`.
4. The post-NFP 30-minute wait is not a rule for all news. After a release ICT waits for the news
   dealing range to form, then trades from it (no fixed minute count).
5. Bearish unicorn as well as bullish (check both directions are detected and tagged).
6. Mean-threshold respect belongs on the BREAKER, not the order block (Ep 02).
7. [REVISED 2026-10-18 - narrower than first built] In Ep 02 the 15m FVG sat above price on a SHORT:
   it was the entry zone and the resistance price respected on the retrace; the rulebook wrongly
   listed it as a target. So: an FVG BEHIND the trade (one price has already traded through) is
   resistance/support and an ADD zone, never a target. An opposing FVG BETWEEN price and the draw
   is ICT's "speed bump": DEFAULT = take a partial at it and keep the rest for the draw (b). The
   cap (exit before it, no target beyond - the first build of #7) and the timeframe split (cap on
   1h+, speed bump on 15m and lower) stay as switches.
8. "Tighten or close" before noon means CLOSE (Ep 03).
9. Mark up levels and LOCK the session's draw before it opens; name ONE exact target and trade only
   toward it.
10. Experienced traders stand aside on sloppy days. "Sloppy" is written as [our interpretation].
    **[OWNER ANSWER 2026-10-18: stand aside only on days that meet the sloppy definition
    (sloppy_mode="stand_aside", tests big_prev + chop). NFP-week Thursday and FOMC week stay tradable
    under the experienced rules; the calendar block ("nfp_week" test / nfp_week_block) stays a switch.]**
11. Ep 07's advanced entry at the order-block bodies BEFORE the break is the DEFAULT; entry after the
    structure shift becomes a switch.
12. Risk: 1.2% open risk at entry, at most 1.3% including adds (Ep 07) - not 2%.
13. Round numbers and levels come from the actual front-month contract prices, not the
    back-adjusted series.
14. Breaker zone: Ep 02, 05 and 07 use the FULL RANGE, Ep 01 the body. Default full range; body as
    a switch.

## Build status (2026-10-18)
Items 1, 2, 4-9 and 11-14 are built as the defaults (previous behaviour kept as switches); items 3
and 10 are built as switches that stay off until the owner answers. Details, switches and notes per
item: `build_log.md`. Effect note: with every owner default on, ES 5m produces far fewer trades
than before - mostly the #7 resistance cap (an opposing 15m-D FVG within 1R of the entry, or
price inside one) and the #9 session lock (one side, session over once the draw is delivered).

Update (entries_stops_sizing): the revised #7 add zone is built as the default - `add_arrays=("htf_fvg",)`:
an HTF FVG behind the trade that price already traded through (the position was filled at or under its
top) takes one add at its top (before the first partial, within the 1.3% cap); it is never a target.
`add_arrays=()` switches it off. The 1.3% total cap binds the add: with 1.2% open risk at entry only ~0.1% is free before the first partial, so it arms a small add (or waits until a stop move frees risk - the one shot is spent only when an add is armed); `htf_add_extra_risk_pct` lets it use extra risk above the cap (study variant `Ep02.2_add_htf_fvg_extra_risk`). Also new DEFAULTS from the build specs: the one-tick stop pad
(`stop_tick_pts=0.25`, Ep 08) and no adds on NFP days (`nfp_no_adds=True`, E12f).

## Open questions for the owner (review pass, 2026-10-18)
Built as switches; the defaults stay as they are until the owner answers.
1. **#5 / #6 / #14 are inactive under the default entry.** The bearish-unicorn tag (#5), the
   breaker-MT respect / floor / cancel / exit (#6) and the full-range breaker zone (#14) act only on
   the FVG entry path. With the default `ob_entry="pre_break"` (#11) the sweep is dropped at the
   MSS, so no default trade ever uses them (ES 5m 2023-01..2024-06: every default trade is
   `ob_pre`, none a unicorn). Choose: (a) make `ob_entry="both"` the default (OB order first, FVG /
   unicorn order after the MSS, lower entry kept), or (b) also apply breaker-MT respect to OB-pre
   entries, or (c) keep as is. Study variants: `A13.3_ob_both_breaker_mt`,
   `A13.3_ob_both_breaker_mt_off`, `A13.3_post_mss_breaker_mt_off`.
2. **#7 x #9: the HTF cap replaces the locked draw in most trades.** When an unbroken opposing HTF
   FVG lies before the locked draw, the trade exits at the cap (`lock_capped` tag, reported by
   `backtest.report`). Choose: (a) keep that, or (b) `draw_lock_near_cap=True`: the lock only
   picks draws on the near side of the nearest opposing HTF FVG, so the "one exact target" is
   always the draw. Numbers in `build_log.md` (review pass).
3. **Own lock times for London SB (02:00) and Ma Deuce (08:00)** [our interpretation]: each locks
   its own draw at its leg start with the htf table cut there. Confirm, or tie them to the AM lock.
4. **Round pools are anchored at the session** (`round_pool_from="session"`): on 2023-01-03 ES
   traded 3906.75 overnight, yet Ep 02's buy side at the open was "3 900" (spec test c), so a round
   handle counts as untaken if the session so far has not traded it. "midnight" is the switch.
5. **#10 extra sloppy tests** (opt-in): `premium_run` (044 ~1:14:47), `inside_bisi` (091 ~6:12),
   `fomc_week` (Ep 03 00:18:23, FOMC + NFP in the same week). Which belong in the default set?
   (The nfp_thu question above still stands.)
6. **Paid data:** `roll_kind="calendar"` / `roll_spread` need Databento ES.c.0 (paid). Not built
   without a go-ahead (and a `quote()` first).

7. **setups_models FVG-path switches under #11 (review pass, extends question 1).** About 40 of the
   setups_models switches (2022 FVG pick, unicorn rules, IFVG entries, OTE, entry arrays, Reaper,
   on-side "require", breaker entries, N6 no-unicorn ...) act only on the FVG entry after the MSS.
   Under the default `ob_entry="pre_break"` they never trade; the study runs them with
   `SM_POST` (`ob_entry="post_mss"`, no #9 lock, no #7 cap - post_mss with the lock and cap gave 0
   trades on ES 5m 2023H2). The MSS-validity gates (displacement, speed, equal-low wait, clean leg,
   the MSS reference variants) now also act on the default OB order through `ob_pre_gate`:
   "cancel" (default; a failed break cancels the still-pending OB order - rare, because the OB
   order usually fills before the break) or "hold" (the OB order fills only after the gated MSS -
   no longer "before the break", so it contradicts #11). Choose: (a) keep "cancel" (the gates
   rarely matter for the default entry), (b) "hold" as the default when a gate is on, or (c) answer
   question 1 with `ob_entry="both"`, which also brings the FVG-path switches back.
8. **Own last-hour lock (review pass).** The own LH slot (`last_hour_own_slot`) now locks its own
   draw at 15:00 like the MD / SB own locks (question 3); `lh_no_lock` keeps the first build (no
   lock once the PM draw was delivered). On the Ep 01 day (ES 2022-12-30) the 15:00 lock picks the
   AM low below (nearest), while ICT's draw was the buy side above - so the Ep 01 last-hour long is
   blocked by the default lock. Confirm the 15:00 lock, or tie the LH slot to the PM lock.
