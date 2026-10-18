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
3. Year end takes its side from December's direction (December up -> bullish repricing, down ->
   bearish), not always bullish. **[built as switches, default OFF - OWNER ANSWER NEEDED]** The
   only caption example (Ep 01, Dec 2022 down -> shorts squared -> rally) runs AGAINST
   December's direction, the opposite of the mapping written here. `year_end_map="squaring"`
   (Dec down -> long, Ep 01) vs `"with"` (this line). Confirm which, then `year_end="december"`.
4. The post-NFP 30-minute wait is not a rule for all news. After a release ICT waits for the news
   dealing range to form, then trades from it (no fixed minute count).
5. Bearish unicorn as well as bullish (check both directions are detected and tagged).
6. Mean-threshold respect belongs on the BREAKER, not the order block (Ep 02).
7. In Ep 02 the overhead 15m FVG is RESISTANCE, not a target: an unbroken opposing HTF FVG caps the
   trade (exit before it / no target beyond it).
8. "Tighten or close" before noon means CLOSE (Ep 03).
9. Mark up levels and LOCK the session's draw before it opens; name ONE exact target and trade only
   toward it.
10. Experienced traders stand aside on sloppy days. "Sloppy" is written as [our interpretation].
    **[built as a switch `sloppy_mode="stand_aside"`, default tag-only - OWNER ANSWER NEEDED on the
    sloppy tests (big prior day, chop, NFP week; keep Thursday of NFP week?)]**
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
