# 2026 SMC 029: The 07:00-09:00 rule, Thu/Fri review, NQ (recorded Sat ~Aug 2026)
Full read (5.5k words; last ~30% is a market-replay vs live demo). Clean caption. Frames laptop-only.
## Summary
States the 07:00-09:00 "pre-market session" rule explicitly with Thursday (trending 7-9 -> choppy AM) and Friday (consolidating 7-9 -> trending AM) examples, plus session-to-session alternation, level persistence, and the first-hour dealing range.
## Rules in ICT's wording
- **7-9 rule**: "look at the range between 7:00 in the morning and 9:00 in the morning Eastern time to determine how the AM session is going to trade after 9:30." "If we're trending in 7:00 to 9:00, [the AM] session's going to be a block. Up and down, up and down." "Consolidation between 7:00 and 9:00 ... tells us ... after ... 9:00 a.m. closes. We're going to get trending environments."
- "When there is a report due at 8:30, you go up to 8:30, not 9:00" (window = 07:00-08:30).
- Trending 7-9 = "a significant dealing range": grade it (high to low); a SIBI at the 0.875 octant in the premium of that range was the salient one; "it has to be anchored to a key level. Period." Equilibrium in a contrasting color; at/above = premium, at/below = discount.
- **Session alternation**: "If the previous session is in consolidation, the next session's going to move. The next session after that expected to be in consolidation, but be prepared in the event that it is trending in the 24-hour cycle." Order Asia, London, New York; NY subdivides into pre-market (7-9), AM session, first hour's dealing range, 2-hour lunch, PM session, market on close / last hour.
- Levels persist: "my levels don't have an expiration date ... go back the last three sessions. You're going to have all the information you'll ever need. You don't even need to have a daily chart."
- NDOG = 17:00 settle to 18:00 restart; extend it to the right continuously ("not one and done"); Asia used the NDOG CE as discount array; midnight opening price as a reference.
- Bearish signal: bodies fail to reach the CE of a prior-session gap; "relative equal highs with the bodies" = run on relative equal highs even if wicks went further. Close below the next gap validates it as an IFVG; its validity: "sitting right there on the upper quadrant at 0.25" of the 7-9 range.
- Retrace premium sensitivity = midpoint to low of the range (bearish leg); hit an octant +1 tick.
- First hour's dealing range 09:30-10:30: draw it, find equilibrium; after the low, price retraced up into the NDOG and the stops above the 09:30 high. Friday afternoon "consolidate rest of the day" = "nothing burger profile".
- "The algorithm is going to refer back to time first. Time is more important than the actual price."
## Our interpretation / switches (all off)
- [off] am_session_regime_from_0700_0900 (trend -> range day mode; consolidation -> trend day mode) [new; core rule of this series, see 025, 027, 028]
- [off] premarket_window_ends_0830_on_0830_news_days
- [off] session_alternation_consolidation_then_expansion (Asia/London/NY) [conflict check: 2023 rulebook session bias logic]
- [off] levels_expire_after_3_sessions (keep last 3 sessions' gaps/ranges)
- [off] ndog_ce_as_asia_array; extend NDOG
- [off] bodies_equal_highs_counts_as_liquidity_run
- [off] first_hour_dealing_range_0930_1030 equilibrium as retrace target
