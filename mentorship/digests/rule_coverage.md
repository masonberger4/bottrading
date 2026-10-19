# Rule coverage: verified code audit

This is a rule-by-rule audit of `mentorship_rules.md` against the bot code in `mentorship/*.py`. For every rule, one agent gave a verdict and a second agent checked it against the code. Where the checker disagreed, its status is the one used here, and the "revised" column says so.

Statuses:
- **FULL**: the code does what the rule says, either by default or behind a Params switch.
- **SIMPLIFIED**: part of the rule is coded, or a proxy for it.
- **MISSING**: nothing in the code does it, under any name.
- **NA**: not a trading rule, FX-only, or no data exists for it.

New rules go in as Params switches that are off by default. The only exception is ICT's clear experienced-trader rule where nothing contradicts it. "[our interpretation]" marks thresholds we chose because ICT gives none.

## 1. Counts

### By status

| Status | Count | Share |
|---|---|---|
| FULL | 86 | 18% |
| SIMPLIFIED | 248 | 52% |
| MISSING | 121 | 26% |
| NA | 18 | 4% |
| **Total** | **473** | |

The checker changed 23 statuses (section 2, "revised" column). It agreed with the other 450, sometimes after rewriting the build spec.

### By rulebook section

| Section | Total | FULL | SIMPLIFIED | MISSING | NA |
|---|---|---|---|---|---|
| A: PD arrays and structure | 41 | 6 | 27 | 7 | 1 |
| B: Bias | 48 | 4 | 15 | 28 | 1 |
| N: News, calendar, day filters | 44 | 5 | 19 | 20 | 0 |
| T: Time | 14 | 2 | 10 | 1 | 1 |
| L: Liquidity and targets | 24 | 3 | 14 | 7 | 0 |
| M: Models | 75 | 7 | 48 | 17 | 3 |
| E: Entries, stops, sizing | 24 | 4 | 12 | 8 | 0 |
| X: Exits and management | 63 | 14 | 29 | 20 | 0 |
| D: Decisions | 23 | 7 | 15 | 1 | 0 |
| Ep01 | 24 | 7 | 12 | 4 | 1 |
| Ep02 | 9 | 1 | 6 | 2 | 0 |
| Ep03 | 25 | 10 | 10 | 1 | 4 |
| Ep04 | 14 | 4 | 7 | 2 | 1 |
| Ep05 | 11 | 4 | 5 | 0 | 2 |
| Ep06 | 7 | 1 | 4 | 0 | 2 |
| Ep07 | 10 | 2 | 5 | 2 | 1 |
| Ep08 | 17 | 5 | 10 | 1 | 1 |
| **Total** | **473** | **86** | **248** | **121** | **18** |

Bias (B) has the most MISSING rules: 28 of 48. The bot has a daily htf.table and nothing that keeps bias state from one day to the next.

## 2. Full table

`S` = strategy.py, `L` = levels.py, `H` = htf.py, `C` = confluence.py, `SB` = sb_model.py, `PO` = pre_open.py, `BT` = backtest.py. "Missing" is a short version of what the checker confirmed.

| id | rule | status | code | what's missing | revised |
|---|---|---|---|---|---|
| A1 | 3-candle swing; STL/ITL/LTL tiers | SIMPLIFIED | L.pivots (pivot_n=1); S._scan refs[-1] | No ITL/LTL tiers. The MSS reference is always the minor swing, and when there is none it falls back to a highest-high that is not a swing. The rulebook's "pivot_n=2" note is stale. | no |
| A2 | BSL/SSL booked 1 tick through; an imbalance is not liquidity | SIMPLIFIED | S._sell_side, _scan `l<v`, pool_beyond_pts | The sweep has no tick threshold, which matters on CFD prices. Plain old swings count as pools only when pool_swings is on (off by default). The SB draw can be an imbalance. | no |
| A3 | REH/REL; smoother = stronger | SIMPLIFIED | S._eq_levels, L.equal_levels | Equality is tested on wicks only, never bodies. Clusters are not ranked for smoothness or touch count. | no |
| A4 | Bodies mark the level; mohawk wick still counts as respect | SIMPLIFIED | S._scan stops; mt_mode body | Stops and trails have no mohawk tolerance. There is no sweep through the body cluster. | no |
| A5 | FVG definition and sub-rules | SIMPLIFIED | L.fvgs; _scan pick, CE, closed-through | Missing: a c2 direction check, quadrants, VI extension, a skip for gaps above a pool, HTF CE as the draw, an upper-quarter hold, repriced/rebalanced state, and reuse of a gap after it fills. | no |
| A6 | Breakaway, measuring and common gaps | SIMPLIFIED | fvg_pick='first', ce_hold (off) | No breakaway tag. No measuring-gap projection. No protected-range stop. | no |
| A7 | Immediate rebalance | MISSING | (none) | No detector, tag or use. | no |
| A8 | IFVG rules | SIMPLIFIED | L.inversion_fvgs; ifvg_entries (off) | No "holds" confirmation. No depth rule based on prior passes. CE invalidation exists only as the generic ce_hold switch. No bias switch. | no |
| A9 | Volume imbalance | SIMPLIFIED | L.volume_imbalances (never called) | Defined but used nowhere: not as a stop, not with a death rule, not as a porous discount, not as a draw. | no |
| A10 | Liquidity voids and opening gaps | SIMPLIFIED | L.voids via fvg_targets (off); NWOG/NDOG/ORG | Voids are not separate targets. No CC leg-start fill target. | no |
| A11 | Balanced price range | SIMPLIFIED | L.balanced_ranges (used only in a test) | Not used as a target, a barrier, or a midpoint abort. | no |
| A12 | Order block rules | SIMPLIFIED | L.order_block_blend; ob_mt stop | No sensitive range or wick rule. The MT is a wick stop. No quality filters. No intraday opposing-OB targets. No "other half not revisited" rule. | no |
| A13 | Breaker | SIMPLIFIED | S._scan inline bz; L.breakers unused | No check that L2 < L1. No leg zone, no MT invalidation, no breaker entries, no time check. Two breaker definitions disagree. | no |
| A13.1 | Breaker structure L1/H/L2 | SIMPLIFIED | _scan l1/ref/ext | L2 < L1 is not checked. The fallback bars are not swings. The wick and CISD MSS modes do not break H on a body. | no |
| A13.2 | Breaker candle = highest up-close body | FULL | _scan max close, breaker_zone | (none) | no |
| A13.3 | Breaker zone extent; MT not closed through | SIMPLIFIED | breaker_zone body/range | No leg option. No breaker MT exit or cancel. No 018 entry floor. | no |
| A13.4 | Breaker first-touch entry | MISSING | bz used only for the unicorn | The breaker is never an entry. | no |
| A13.5 | Time distortion is not a breaker | MISSING | (none) | No session-block check on H, L2 or the break bar. | no |
| A14 | Unicorn | SIMPLIFIED | uni preference; Trade.unicorn | No unicorn-at-the-open tag or filter. Inherits the A13.1 gap. | no |
| A15 | Mitigation block | SIMPLIFIED | L.mitigation_blocks (tag) | The swing order is wrong: the A low before X is never checked. Used only as a tag, not a target. | no |
| A16 | Propulsion block | SIMPLIFIED | L.propulsion_blocks (tag) | No entry at the block high. No MT-loss exit. | no |
| A17 | Rejection block | MISSING | L.rejection_blocks unused | Not used anywhere. No long-wick test. No 2023 body-edge pool. | no |
| A18 | Reclaimed OB | MISSING | (none) | No sell-side-of-curve OB entry after the low. | no |
| A19 | MSS after a sweep with displacement | SIMPLIFIED | _scan sweep, ref, mss_mode, fvg_wait | No parent-swing reference. Non-swing fallback. No "on side" double MSS. | no |
| A19.1 | MSS core | FULL | _scan | (none) | no |
| A19.2 | Which swing (parent; wait for the lower of equal lows) | SIMPLIFIED | refs[-1] | Only the minor swing. No equal-cluster wait on the MSS reference (the audit's claim that this was met was wrong). | no |
| A19.3 | MSS on wick or close | FULL | mss_mode | (none) | no |
| A19.4 | Two MSS = on side | MISSING | (none) | No count of a second shift. | no |
| A19.5 | Liquidity run first | FULL | _scan needs sd.sweep | (none) | no |
| A20 | Displacement size and speed | SIMPLIFIED | any FVG after the sweep | No 2-3x OB-body test, no follow-through, no rip-through margin. | no |
| A21 | Premium/discount | SIMPLIFIED | leg_pd, use_bias, htf pd (off) | No 20-day range, no OTE band, no body-based multi-day range. | no |
| A21.1 | EQ = 50%, buy below / sell above | FULL | leg_pd=0.5; htf pd | (none) | no |
| A21.2 | Intraday leg; day context = 20-day high/low | SIMPLIFIED | leg_pd; htf pd swings | No 20-day premium/discount. | no |
| A21.3 | OTE 62-79%, thirds, deep | SIMPLIFIED | leg_pd (upper bound only) | No 79% floor, no 70.5% entry, no depth tag. | no |
| A21.4 | Wicks intraday, bodies multi-day | SIMPLIFIED | htf pd on wick pivots | Multi-day ranges use wicks, not bodies. | no |
| A22 | PD-array matrix | SIMPLIFIED | _targets sorted; htf_targets | Breakers, mitigation blocks and rejection blocks are never targets. No breaker precedence. Exhaustion is only partly checked. | no |
| A23 | Wick CE | SIMPLIFIED | L.wick_midpoints; wick_levels | Only the prior RTH day. No continuation/revisit read. Docs and code disagree on the default. | no |
| A24 | Not codeable (implied FVG, Reaper, inducement) | SIMPLIFIED | sweep step | The Reaper is missing (A24.2). | no |
| A24.1 | Implied FVG | NA | (none) | Never defined in the source. | no |
| A24.2 | Reaper | MISSING | (none) | Not built. | no |
| A24.3 | Inducement = sweep step | FULL | _scan sweep | (none) | no |
| B1 | Price runs liquidity or rebalances, else consolidates | SIMPLIFIED | _targets; htf_targets; fvg_targets off | VIs unused. Voids/LTF FVGs off by default. Only the prior day's wick CE. No consolidation state. | no |
| B2 | Draw search order | MISSING | H.table draw = nearest | No inefficiency-first order, no P/D-chosen liquidity, no extent level. | no |
| B3 | Bias toward the next draw; one direction | SIMPLIFIED | htf_bias (off); want filter | Nearest draw, not the largest move. Pre-open look-ahead. SB/Ma Deuce ignore `want`. Judas is only a tag. Now built: see section 4. | no |
| B4 | Bias is a condition, not a trade | FULL | run_day + _scan | (none) | no |
| B5 | Timeframe chain | SIMPLIFIED | topdown, conf_min_top (off) | No weekly gate. No bellwether delivery read. No news-day chain. No daily VI. | no |
| B6 | Institutional order flow on the daily | MISSING | (none) | No IOF score. | no |
| B7 | Daily OB MT close rule | SIMPLIFIED | H react drop; weekly_bias | No OB state or flip. No "high of the week in" rule. | no |
| B8 | Close-based bias flips | MISSING | partial analogues only | No persistent bias state to flip. Now built: see section 4. | no |
| B8a | Flip on a close through the daily OB MT | MISSING | H.table drops the OB | No flip output. Now built: see section 4. | no |
| B8b | Flip on closes through 3 PD arrays | MISSING | pd3_exit (intraday) | No daily version. Now built: see section 4. | no |
| B8c | Weekly close below the last down-close week | MISSING | (none) | No weekly-close rule. Now built: see section 4. | no |
| B8d | Close above Friday's high / wick CE / weekly quadrant | SIMPLIFIED | weekly_bias wick-CE cancel | Only the strong-day wick CE exists. No Friday high, no weekly wick CE or quadrant, no htf_bias flip. Now built: see section 4. | yes (was MISSING) |
| B8e | Thursday trade back through the weekly open | MISSING | (none) | No weekly-open logic. Now built: see section 4. | no |
| B8f | Stop above the breaker cancels SMT -> long | MISSING | reverse_after_loss | No forced direction. Now built: see section 4. | no |
| B9 | What is not a flip | SIMPLIFIED | per-day bias, closes | No neutral-on-target. No retracement persistence. No fallback to the next weekly array. | no |
| B10 | MWD sequential | MISSING | building blocks only | No case logic. | no |
| B11 | Candle-pattern day context | SIMPLIFIED | day_context; three_day_rule | Inside day is a tag only. No inside week, outside day or NR3/NR7. | no |
| B11a | 3-day rule | FULL | three_day_rule | Ma Deuce skips it (minor). | no |
| B11b | Down-close outside day | MISSING | (none) | Not detected. | no |
| B11c | Inside week / NR -> expansion | SIMPLIFIED | inside_day tag | No inside week or NR, no effect. | no |
| B12 | Intraday PO3 vs the midnight/13:30 open | FULL | use_bias | Strict `<` (minor). | no |
| B13 | Weekly open | MISSING | (none) | No weekly-open level. | no |
| B14.1 | NWOG regime | MISSING | NWOG used as targets | No return count, no regime, no convergence. | no |
| B14.2 | Converging NWOGs | MISSING | (none) | No comparison between gaps. | no |
| B14.3 | Bias vs NWOG | MISSING | H react (touch + CE) | No hold-above / reclaim state. | no |
| B15 | ORG direction tell | MISSING | DayCtx.org as targets | No 30-minute attempt test. No gap x bias rule. | no |
| B16 | Sunday gap scenarios | MISSING | skip_monday (exempts NFP/FOMC weeks) | No scenario check. | no |
| B17 | Neutral / no-bias conditions | SIMPLIFIED | htf_bias + bias_neutral; neutral_skip | B17.1 is a proxy. B17.3-5 are absent. | yes (was MISSING) |
| B17.1 | 50/50 framing -> no trade | MISSING | (none) | No both-sides check. | no |
| B17.2 | Stuck or chop -> wait for 09:30 | FULL | AM starts 09:30 | Pre-open switches have no guard. | no |
| B17.3 | HTF draw delivered -> stop for the week | MISSING | (none) | No objective-met state. | no |
| B17.4 | Range market / inside daily BISI / sloppy | MISSING | neutral_skip (N8) | None of the three is detected. Now built: see section 4. | no |
| B17.5 | Indices decoupled; SMT both ways | MISSING | _smt per sweep | No decoupling measure. | no |
| B18.1 | SMT qualifier | SIMPLIFIED | _smt, smt_min | No PD-array requirement. No "obvious" gap. No rel-eq SMT. | no |
| B18.2 | SMT windows | MISSING | (none) | No window filter. No pre-09:30 SMT. | no |
| B18.3 | SMT uses (partials, instrument) | SIMPLIFIED | combine tie-break | No SMT partials. Instrument choice is a tie-break only. No bias input. | no |
| B18 | SMT overall | SIMPLIFIED | _smt | See B18.1-B18.3. | no |
| B19.1 | DXY up = risk-off | SIMPLIFIED | INTERMARKET dxy tag | Tag only, using a 20-day mean, not the range high. | no |
| B19.2 | ES lower low vs DXY higher high | NA | (none) | Needs DXY 1m data. | no |
| B19.3 | Bonds range -> consolidation | SIMPLIFIED | tnx tag | No range detection, no effect. | no |
| B19 | Intermarket overall | SIMPLIFIED | INTERMARKET | Tags only. | no |
| B20.1 | COT commercials | MISSING | (none) | No data. | no |
| B20.2 | Open interest | MISSING | (none) | No data. | no |
| B20.3 | Weekly Williams %R | MISSING | (none) | Not computed. | no |
| B20 | COT/OI/sentiment overall | MISSING | (none) | All three missing. | no |
| B21 | IPDA 20/40/60-day ranges | MISSING | (none) | No pools. History passed in is only 45 days. | no |
| B22 | Quarterly shift | MISSING | (none) | Not computed. | no |
| B23 | Seasonals | MISSING | BT by_month (reporting only) | No map, tag or report. | yes (was SIMPLIFIED) |
| N1 | NFP Friday | SIMPLIFIED | nfp_day=True; entries from 09:30 | Pyramids on NFP. Pre-open switches break the first-hour rule. | no |
| N2 | NFP week beginner block | FULL | nfp_week_block (off) | Also needs nfp_thu=False. | no |
| N3 | FOMC overall | SIMPLIFIED | blocked fomc_pm; am_exit | Day-before, day-after and no-re-entry handling is missing or partial. | no |
| N3.1 | 14:00 release; observe until 14:45 | SIMPLIFIED | fomc_pm_from=885 | No observation: sweeps are not tracked and the 14:00 Judas pool is retired. SB PM is skipped entirely. | no |
| N3.2 | Never hold into the release | SIMPLIFIED | am_exit=720 | Holds only through the default. No recipe or skip variant. | no |
| N3.3 | FOMC-only day AM consolidates | SIMPLIFIED | _split 80/20; PM gate | No FOMC-only distinction. No AM filter. | yes (was MISSING) |
| N3.4 | Day before light / day after AM out | MISSING | _split only | No size cut, no AM block. | no |
| N3.5 | No re-entry on FOMC | SIMPLIFIED | done per session | The PM still trades after an AM loss. reentry_half and SB leak. | no |
| N4 | CPI | SIMPLIFIED | skip_cpi; pre_flat_0830 | No day-before-CPI rule. Ma Deuce and sb_london hold through 08:30. | no |
| N5 | Other releases | SIMPLIFIED | am_start=600 | No 10:00+30 wait, no news room, no 09:45 releases, no two-driver/Fed/auction rules. Calendar has gaps. | no |
| N5.1 | Wait 30 minutes and need 10 handles | SIMPLIFIED | am_start; min_draw_pts | Audit-time note superseded: owner #4 = wait for the news dealing range, no fixed 30 minutes. See section 4. | no |
| N5.2 | 09:45/10:00 releases | SIMPLIFIED | NEWS_1000 | No 09:45 set. Missing 10:00 releases. | no |
| N5.3 | No 08:30 news -> wait for 09:30 | FULL | am=(570,...) | (none) | no |
| N5.4 | Two drivers | SIMPLIFIED | am_start 600 | No stand-aside. Pre-open windows trade ahead of the second release. Detection is weak. | no |
| N5.5 | Fed chair at 10:00 | MISSING | (none) | No calendar. | no |
| N5.6 | Treasury auction AM | MISSING | (none) | No calendar. | no |
| N6 | News Judas profile | SIMPLIFIED | post_news news_range | No first-side tracking. No CE target. No breaker change on NFP/CPI/FOMC. | no |
| N7 | Holidays and calendar | MISSING | roll_week tag | None of the behaviours. | no |
| N7.1 | Holiday eve skip | MISSING | (none) | Not implemented. | no |
| N7.2 | Morning after a holiday | MISSING | (none) | Not implemented. | no |
| N7.3 | Holiday week Thu/Fri | MISSING | (none) | No tag. | no |
| N7.4 | Year end / year start | MISSING | (none) | Not implemented. | no |
| N7.5 | Roll week | SIMPLIFIED | day_type roll_week | Tag is overwritten by other day types. No switch. | no |
| N7.6 | August | MISSING | (none) | Not implemented. | no |
| N8 | Day type overall | SIMPLIFIED | big_prev + neutral_skip | Only the >2x ADR5 skip exists. | no |
| N8.1 | Consolidation = no trade | MISSING | (none) | No detector. | no |
| N8.2 | Trending-day recipe | MISSING | (none) | Not combined. | no |
| N8.3 | Consolidation predictors | MISSING | (none) | Not implemented. | no |
| N8.4 | Big ORG/prior range -> sacrifice the AM | MISSING | neutral_skip (whole day) | No AM-only skip. | yes (was SIMPLIFIED) |
| N8.5 | >2x ADR5 skip / <ADR5 expansion due | SIMPLIFIED | big_prev | No expansion-due logic. Ranges are RTH only. | no |
| N8.6 | Seek & destroy | MISSING | (none) | Not implemented. | no |
| N9 | In-day no-trade conditions | SIMPLIFIED | _scan requirements | Only N9.1, plus a proxy for N9.3. | no |
| N9.1 | No draw/inefficiency/displacement -> no trade | FULL | _scan | (none) | no |
| N9.2 | Draw delivered pre-09:30 | MISSING | (none) | htf.table removes overnight-delivered draws. | no |
| N9.3 | Objective done before lunch | MISSING | no_pm_after_am_win | No objective tracking. | no |
| N9.4 | Narrow overnight / shallow raid | MISSING | (none) | Not implemented. | no |
| N9.5 | Macro with no move -> close the charts | MISSING | MACROS tag | No session end. | no |
| N9.6 | London ~80% of ADR5 | MISSING | (none) | Not implemented. | no |
| N10 | Day of week | SIMPLIFIED | skip_monday; tgif; flatten | Monday rules partial. No Thu/Fri structure. Friday rules mostly missing. | no |
| N10.1 | No Sunday open | FULL | session build | (none) | no |
| N10.2 | Monday | SIMPLIFIED | skip_monday | No PM-only mode, no "obvious" rule, no Tuesday-off-Monday. | no |
| N10.3 | Tue/Wed ideal; Mon-Wed extremes | MISSING | weekday tag | Not implemented. | no |
| N10.4 | Friday rules | SIMPLIFIED | tgif | No Friday 80/20. No weekly objective. Strong-Thursday check missing. | no |
| N10.5 | No weekend or 17:00 holds | FULL | flatten=960 | (none) | no |
| T1 | NY time, time-based charts | FULL | tz_convert NY | (none) | no |
| T2 | Opening prices | SIMPLIFIED | L.opens; use_bias | 08:30 and 09:30 opens unused. No release-day 08:30 body rule. | no |
| T3 | Kill zones | FULL | London pool | (none) | no |
| T4 | Opening range | SIMPLIFIED | or_minutes; OR pools | No or_no_entry. No deep exception. No OR bias. No wide-OR draw. | no |
| T5 | NY AM session | SIMPLIFIED | am, pre windows | No 08:20/08:30-09:00 window. | no |
| T6 | Silver Bullet windows | SIMPLIFIED | SB.run_sb | No 15:00-16:00 or 07:00-08:30 window. | no |
| T7 | Macros | SIMPLIFIED | MACROS tags | Tags only. No 2:00 macro, no gate, no done/MOC rules. | no |
| T8 | Lunch | SIMPLIFIED | am/pm windows; lunch pool | No lunch session. No carried draw. No objective skip. | no |
| T9 | PM session | SIMPLIFIED | pm; tags | No 14:30 skip, no 13:45 restart, no continue-AM filter, no AM-OB entry. | no |
| T10 | Last hour / MOC | SIMPLIFIED | pm end 950; tag | No MOC run. No pool-before-15:50 exit. | no |
| T11 | End of day | SIMPLIFIED | flatten | No late-add cutoff. No fade block. | no |
| T12 | Extreme timing statistics | NA | (none) | Research only. | no |
| T13 | Day templates / PO3 | SIMPLIFIED | use_bias; _judas tag | Judas not required. No expansion hold. No profiles. No NFP seek-and-destroy. | no |
| T14 | Weekly time statistics | MISSING | (none) | No study, no switch. | yes (was NA) |
| L1 | Session pools and priority | SIMPLIFIED | DayCtx.sess; _sell_side | AM range ends 13:30 (rule: 12:00). No previous-AM pool. No priority. ORG is not a pool. | no |
| L2 | Liquidity matrix | SIMPLIFIED | pdh/pdl 1-3 | No PD-array/flow requirement. RTH only. | no |
| L3 | Higher pools | SIMPLIFIED | pw/pm_ switches; or_minutes | No 20/40/60-day pools. RTH only. One OR length at a time. | no |
| L4 | Pool quality | MISSING | draw = nearest pool | No ranking, no equilibrium test, no resistance count. | no |
| L5 | NWOG | SIMPLIFIED | H.opening_gaps | No quarters, no holiday skip, no halfway rule, no run-stop. | no |
| L6 | NDOG | FULL | H.opening_gaps | (none) | no |
| L7 | ORG | SIMPLIFIED | DayCtx.org | No behaviour rules. Capped at 6 days. Close time not per symbol. | no |
| L8 | Vacuum block | MISSING | (none) | No event-anchored gap. | no |
| L9 | FVG targets | SIMPLIFIED | htf_targets; fvg_targets | No FVG-over-OB rule. No remainder. NWOG far edge always added. | no |
| L10 | Wick CE levels | SIMPLIFIED | DayCtx.wick | One day only. No weekly. Target only. | no |
| L11 | Rejection-block target | MISSING | (none) | Exits go past the wick. | no |
| L12 | SD targets | SIMPLIFIED | sd_targets (off) | No -0.5, one anchor, no clusters, no roles, no alignment. | no |
| L13 | Other projections | MISSING | (none) | No breaker/measuring/ORG/extension projections. | no |
| L14 | Choose the draw | SIMPLIFIED | draw = nearest pool | Parts a, c, d, e missing or partial. | no |
| L14a | Draw first, trade toward it | SIMPLIFIED | htf_bias draw (off) | No session draw, no objective-met state, no B2 order. Now built: see section 4. | no |
| L14b | Enter IRL, exit ERL | SIMPLIFIED | FVG entry; pool exits | No OB/void entries. Range not redefined. Arrays used as exits. | yes (was FULL) |
| L14c | Opposing array one TF lower | SIMPLIFIED | react; conf.targets | No TF link. | no |
| L14d | Untraded targets only | SIMPLIFIED | `seen` filter (pools) | Arrays never retired. | no |
| L14e | Conditional draws | MISSING | (none) | No session draw state. | no |
| L14f | Sorted level list | FULL | ladder | (none) | no |
| L14g | SB draw list | SIMPLIFIED | SB._arm -> _targets | No PWH/PWL by default, no OTE, no HTF, no fallback. | no |
| L15 | Room (10-handle framework) | FULL | min_draw_pts=5 | (none) | no |
| L16 | ADR5 targets | MISSING | _split only | Not implemented. | no |
| L17 | Rounding | MISSING | (none) | No switch. Now built: see section 4. | no |
| M0 | Common skeleton | SIMPLIFIED | _scan; htf | Bias proxy. No pool priority. FVG/IFVG entries only. | no |
| M0.1 | Bias = weekly/daily candle draw | SIMPLIFIED | htf_bias | No candle projection. SB/Ma Deuce ignore it. Now built: see section 4. | no |
| M0.2 | Window pools | SIMPLIFIED | _sell_side all armed | No single-window choice. No previous-AM pool. | no |
| M0.3 | Judas raid | FULL | _scan sweep; use_bias | (none) | no |
| M0.4 | MSS with displacement leaves an FVG | SIMPLIFIED | _scan | Displacement is only "an FVG exists". | yes (was FULL) |
| M0.5 | Enter on any PD array | SIMPLIFIED | FVG/IFVG; 5m OB fallback | No OB, breaker, OTE, wick-CE or turtle entries. | no |
| M0.6 | Target the opposite pool | FULL | _targets | (none) | no |
| M1 | AM market maker model | SIMPLIFIED | _scan am_mm | Context, speed check and pre-MSS entry are absent. | no |
| M1.1 | HTF draw and discount array | SIMPLIFIED | require_htf, conf (off) | No HTF-draw requirement. No daily VI. | no |
| M1.2 | Short-term low taken, then MSS | SIMPLIFIED | _scan; pool_swings | The swing_low intact() bug drops valid lows. No displacement test. | yes (was FULL) |
| M1.3 | Speed check | SIMPLIFIED | ep07_body_exit | No rip-through-SIBI timing. | no |
| M1.4 | Entry, unicorn, pre-MSS OB | SIMPLIFIED | _scan | No early OB entry. | no |
| M1.5 | Stop below the OB MT | FULL | ep07_stop | (none) | no |
| M1.6 | MM phases are context | NA | (none) | Context only. | no |
| M2 | 2022 model | SIMPLIFIED | _scan; leg_pd | FVG choice, stop, pyramid and target rules are partial. | no |
| M2.1 | Buy-side incl. NWOG taken | SIMPLIFIED | _sell_side | NWOG is not a sweep pool. | no |
| M2.2 | Sell above 50%, not the breakout candle | FULL | leg_pd | (none) | no |
| M2.3 | FVG choice | SIMPLIFIED | fvg_pick | No VI+OB preference. EQ only rejects. | no |
| M2.4 | New candle, no new low before the fill | SIMPLIFIED | pending | No cancel on a new extreme. | no |
| M2.5 | Stop variants | SIMPLIFIED | stop_mode | Not a pure MT+2pt stop. No candle or CE2 stop. | no |
| M2.6 | Premium pyramid; 25% cutoff; larger pool | SIMPLIFIED | adds; t1_done gate | No P/D check on adds. No 25% cutoff. No pool size rank. | yes (was MISSING) |
| M2.7 | Three drives | MISSING | (none) | No detector. | no |
| M3 | Silver Bullet | SIMPLIFIED | SB | Several sub-rules simplified. | no |
| M3.1 | SB windows | SIMPLIFIED | SB wins | Missing windows. | no |
| M3.2 | SB draw first | SIMPLIFIED | SB._arm draws[0] | Draw not chosen first. Now built: see section 4. | no |
| M3.3 | First FVG in the bias direction | SIMPLIFIED | SB | No bias filter. MSS forced. | no |
| M3.4 | Evolving SB | FULL | SB re-arm | (none) | no |
| M3.5 | Cancel on target; shallow run | SIMPLIFIED | SB cancel | No depth tag. | no |
| M3.6 | SB room | FULL | sb_room_pts | (none) | no |
| M3.7 | SB entry price | FULL | g.top | (none) | no |
| M3.8 | SB stop variants | SIMPLIFIED | SB 090 stop | No 057 or 086 stop. | no |
| M3.9 | Session order, one market | SIMPLIFIED | SB per window | No cascade. combine switches markets. | no |
| M3.10 | Immediate rebalance -> more than 5 handles | MISSING | (none) | Not implemented. Now built: see section 4. | no |
| M3.11 | SB layered exits | SIMPLIFIED | sb_mgmt | No 4/2/4 split. No weekly condition. | no |
| M4 | Breaker and unicorn entries | SIMPLIFIED | uni pref | Classic, advanced, pyramid and CC versions absent. | no |
| M4.1 | Classic breaker entry | MISSING | (none) | No entry. | no |
| M4.2 | Unicorn conditions | SIMPLIFIED | uni; adds | No 09:30 gate, no MT floor. | no |
| M4.3 | Advanced breaker | MISSING | (none) | Not built. | no |
| M4.4 | Turtle soup + breaker pyramid | MISSING | (none) | Not built. | no |
| M4.5 | CC breaker and failure swing | MISSING | MB tag | No entry. | no |
| M5 | PM last hour / MOC | SIMPLIFIED | pm_last_hour tag | No own model. | no |
| M5.1 | Ep01 last-hour version | MISSING | (none) | Not built. | no |
| M5.2 | 2022 model in the window | SIMPLIFIED | params | Sweep not tied to the window. No VI or 1m OB entry. | no |
| M5.3 | Example entry times | NA | pm end 950 | Examples only. | no |
| M6 | PM reversal (2:00 macro) | SIMPLIFIED | _scan PM; ifvg | No bias/objective precondition. No IFVG at the high. No PDH target. | no |
| M7 | PM off lunch; 13:30 Judas | SIMPLIFIED | lunch pool; use_bias | No lunch-target, ORG or premium link. | no |
| M7.1 | Lunch low -> lunch high target | SIMPLIFIED | lunch pool; _targets | The lunch high is always dropped by the `seen` filter. | yes (was FULL) |
| M7.2 | Short mirror into the ORG | SIMPLIFIED | lunch pool | No ORG requirement. | no |
| M7.3 | 13:30 Judas into an array | SIMPLIFIED | use_bias | A pool sweep is required. | no |
| M8 | ORG repricing | SIMPLIFIED | ORG targets | No Judas-away setup. | no |
| M9 | News Judas | SIMPLIFIED | late starts | No first-run detection. | no |
| M9.1 | First run after a release = losing side | SIMPLIFIED | post_news | No direction gate. | no |
| M9.2 | FOMC 14:25 real move | SIMPLIFIED | fomc_pm_from | No 14:00-14:25 range. | no |
| M10 | IFVG entry | SIMPLIFIED | ifvg_entries | No CE+3-4 stop. No 061 trigger. No depth rule. | no |
| M11 | IR / CISD / wick-CE entries | MISSING | mss_cisd (reference only) | Not built. | no |
| M11a | Immediate-rebalance entry | MISSING | (none) | Not built. | no |
| M11b | CISD OB entry | SIMPLIFIED | mss_cisd; leg_pd | OB never the entry. No OB-low hold check. | no |
| M11c | Wick-CE long | MISSING | (none) | Not built. | no |
| M12 | Turtle soup | MISSING | context gates only | No false-break entry. Now built: see section 4. | no |
| M12.1 | 2023 no-MSS version | MISSING | (none) | Not built. Now built: see section 4. | no |
| M12.2 | Short at an old high | SIMPLIFIED | MSS machine | No no-MSS trigger. No breaker adds. | yes (was MISSING) |
| M12.3 | CC limit / 1h OB / OR60 | MISSING | (none) | Not built. Now built: see section 4. | no |
| M12.4 | External turtle soup | MISSING | (none) | Not built. Now built: see section 4. | no |
| M12.5 | Turtle soup context | SIMPLIFIED | conf/topdown gates | No depth or reversal test. Now built: see section 4. | no |
| M13 | OTE | SIMPLIFIED | leg_pd | No band, no 70.5%, strict 50% passes, no leg stop. | no |
| M14 | TGIF | SIMPLIFIED | tgif block | Direction only. | no |
| M14.1 | TGIF context | SIMPLIFIED | day_context | No HTF-array check. RTH week only. | no |
| M14.2 | TGIF 20-30% zone | MISSING | (none) | Not built. | no |
| M14.3 | TGIF timing | MISSING | (none) | Not built. | no |
| M14.4 | TGIF exits | SIMPLIFIED | ladder | No grid. | no |
| M15 | Ma Deuce | SIMPLIFIED | PO.run_ma_deuce | No big-candle check, no 2nd entry, one target, not blocked by blocked(). | no |
| M16 | Index SMT / sick sister | SIMPLIFIED | _smt; combine | Neither model exists. | no |
| M16.1 | CC AM SMT entry | SIMPLIFIED | _smt gate | No stop entry, no 05:00 lows, no exit. | no |
| M16.2 | Sick sister | MISSING | (none) | Not built. | no |
| M17 | Out of scope | NA | (none) | FX/swing/stocks. | no |
| E1 | Resting limit; CC order types | SIMPLIFIED | pending limits | Adds rest as limits. No scalp. No CC stop entries. | no |
| E2 | Edge / CE / IOFED / ladder | SIMPLIFIED | entry edge/ce | No IOFED mode, no ladder. SB hardcodes the edge. | no |
| E3 | Fill needs 1 tick through | SIMPLIFIED | strict `<` | Ma Deuce fills on a touch. Exits fill on a touch. No tick parameter. | no |
| E4 | Buy into down-close candles | SIMPLIFIED | implicit | No candle check. | no |
| E5 | Don't chase / order hygiene | SIMPLIFIED | pending expiry/cancel | No evolving FVG. No waiting for a structural entry. | no |
| E6 | Stop variants | SIMPLIFIED | stop_mode | Only a is full. | no |
| E6a | Stop below the OB MT | FULL | ob_mt; ep07_stop | (none) | no |
| E6b | Stop beyond the FVG-forming candle | SIMPLIFIED | g.bottom | No candle-low or bodies mode. | no |
| E6c | Stop beyond the sweep extreme | MISSING | (none) | Not built. | no |
| E6d | Stop beyond every inefficiency | MISSING | (none) | Not built. | no |
| E6e | Mohawk / EQ swing | MISSING | (none) | Not built. | no |
| E6f | Padding | SIMPLIFIED | stop_buffer 0.01 | Less than a tick. No CE or NFP pad. | no |
| E7 | Never widen a stop | FULL | max() everywhere | (none) | no |
| E8 | Size = risk/stop; 1-2% | SIMPLIFIED | risk_dollars fixed | Audit-time note superseded: owner #12 = 1.2% first unit / 1.3% total. See section 4. | no |
| E9 | Size down/up conditions | MISSING | (none) | No multiplier. | no |
| E10 | Halve after a loss | MISSING | reentry_half | No risk state. | no |
| E11 | Contract caps | SIMPLIFIED | risk caps | No count caps. | no |
| E12 | Adds | SIMPLIFIED | adds | c, e, f missing. | no |
| E12a | Decreasing add sizes | FULL | adds fractions | (none) | no |
| E12b | Where to add | SIMPLIFIED | new FVG tops | No hold test. No other arrays. | no |
| E12c | Add at the FVG low end | MISSING | (none) | Not built. | no |
| E12d | No adds after partials | FULL | t1_done gate | (none) | no |
| E12e | No adds past EQ | MISSING | (none) | Not built. | no |
| E12f | No adds on NFP / decoupled days | MISSING | (none) | Not built. | no |
| X1 | Targets = next opposing liquidity/array | SIMPLIFIED | _targets | Swings and LTF FVGs off. No LTF OBs. min_rr drops inner levels. | no |
| X2 | Exit before arrays, beyond pools | FULL | exit_mode split | (none) | no |
| X3 | Partials | SIMPLIFIED | ladder | Many sub-rules partial. | no |
| X3a | Scale out at each pool | SIMPLIFIED | ladder cap 3 | No run-down. | no |
| X3b | Bulk at first target | PARTIAL | _split | SB ignores _split. JOLTS before 2026 missing. | no |
| X3c | Wick-CE partial | SIMPLIFIED | prior-day wick | Scope limited, can be dropped. | no |
| X3d | -0.5 SD / halfway partials | MISSING | (none) | Not built. | no |
| X3e | Never the exact FVG edge | FULL | exit_before | (none) | no |
| X3f | Full pull vs partials by resistance | MISSING | (none) | Not built. | no |
| X3g | SMT bank 50% | MISSING | (none) | Not built. | no |
| X3h | Capture 80-85% | MISSING | (none) | Not built. | no |
| X4 | Breakeven after partial and expansion | SIMPLIFIED | be_on expansion | No commission pad. SB ignores be_on. | no |
| X5 | Trailing | SIMPLIFIED | ladder_trail fvg | Only the newer-FVG variant. | no |
| X5a | Breakaway / measuring trail | SIMPLIFIED | ladder_trail | No breakaway or measuring mode. | no |
| X5b | Don't trail early | FULL | t1 gate | (none) | no |
| X5c | Day trade keeps its initial stop | MISSING | (none) | Not built. | no |
| X6 | FVG abort | SIMPLIFIED | fvg_abort | Whole-body arm. Any later bar confirms. | no |
| X7 | Three-PD-array rule | SIMPLIFIED | pd3_exit | Partial. | no |
| X7a | Three arrays, exit before the stop | SIMPLIFIED | pd3_exit | FVGs only. List not fixed at entry. | no |
| X7b | Half off on VI+FVG+OB | MISSING | (none) | Not built. | no |
| X7c | Three fails -> stop for the session | SIMPLIFIED | done per session | The SB_AM key and reentry_half leak a third entry. | yes (was FULL) |
| X8 | Other invalidations | SIMPLIFIED | ce_hold; ep07 | c, d, e, g missing. | no |
| X8a | CE close-through | FULL | ce_hold | (none) | no |
| X8b | Leg-candle MT | SIMPLIFIED | ob_mt stop | No close exit. | no |
| X8c | IR EQ exit | MISSING | (none) | Not built. | no |
| X8d | Propulsion MT exit | MISSING | (none) | Not built. | no |
| X8e | Offside test | MISSING | (none) | Not built. | no |
| X8f | Below the swing-low bodies | FULL | ep07_body_exit | (none) | no |
| X8g | Meander exit | MISSING | (none) | Not built. | no |
| X9 | Time stops | SIMPLIFIED | time_stop_min | One generic stop. | no |
| X9a | Deliver in 2-3 candles | SIMPLIFIED | time_stop | Fixed points, full exit. | no |
| X9b | Move within ~10 minutes | FULL | time_stop_min=10 | (none) | no |
| X9c | Far edge, 2 minutes | MISSING | (none) | Not built. | no |
| X9d | Lethargic -> cut half | SIMPLIFIED | time_stop (full exit) | No half cut. | yes (was MISSING) |
| X10 | AM exits | SIMPLIFIED | am_exit | b, c, d missing. SB/Ma Deuce skip am_exit. | no |
| X10a | Last AM unit off before noon | FULL | am_exit=720 | (none) | no |
| X10b | Bulk off 10:00-11:00 | MISSING | (none) | Not built. | no |
| X10c | Hold AM SMT trades to 10:30-11:00 | MISSING | (none) | Not built. | no |
| X10d | AM delivered the range -> skip PM | MISSING | (none) | Not built. | no |
| X11 | PM exits | SIMPLIFIED | pm_done_by; flatten | c missing. | no |
| X11a | Done by 15:00 if the target is hit | FULL | pm_done_by | (none) | no |
| X11b | Hold PM trends to 15:00-16:00 | FULL | flatten | (none) | no |
| X11c | Consolidation PM exits 14:00 | MISSING | (none) | Not built. | no |
| X11d | Flat by 16:00 | FULL | flatten | (none) | no |
| X12 | Objective hit -> stop for the day | SIMPLIFIED | ladder; done | No objective exit. No day stop. | no |
| X13 | After a loss | SIMPLIFIED | reverse_after_loss; reentry_half | Re-entry partial. | no |
| X13a | AM loss, no reversal | SIMPLIFIED | done; lost_side | No in-session experienced reversal. Beginner lock lasts all day. SB_AM leaks. | yes (was FULL) |
| X13b | Half-risk same-direction re-entry | SIMPLIFIED | reentry_half | No direction lock, no intact check, no FOMC exemption. | no |
| X14 | After a win | SIMPLIFIED | no_pm_after_am_win | a, b missing. | no |
| X14a | 5 handles then stop | MISSING | (none) | Audit-time note superseded: owner #2 = 5 handles is the minimum room; `day_target_pts` test switch (off). See section 4. | no |
| X14b | Chop: one win and stop | MISSING | (none) | Not built. | no |
| X14c | AM win -> skip the PM | FULL | no_pm_after_am_win | (none) | no |
| X14d | No re-entry after a winner | SIMPLIFIED | done per session | Per session, not per day. | yes (was FULL) |
| X15 | Frequency | SIMPLIFIED | max_trades_week | d missing. Truncation-order bug. | no |
| X15a | Weekly cap | FULL | max_trades_week | (none) | no |
| X15b | One AM SB a day | FULL | SB per window | (none) | no |
| X15c | ~2 setups a day | FULL | done | (none) | no |
| X15d | Weekly objective -> done | MISSING | (none) | Not built. | no |
| X16 | Journal items | SIMPLIFIED | tags | Partial. | no |
| X16a | Range vs ADR5 | SIMPLIFIED | big_prev tag | Flag only. | yes (was MISSING) |
| X16b | Last 3 days' highs/lows taken | MISSING | (none) | Not built. | no |
| X16c | Weekly H/L weekday and session | MISSING | (none) | Not built. | no |
| X16d | Entry-array timeframe | SIMPLIFIED | entry_kind | No per-trade timeframe. | no |
| D1 | AM from 09:30 vs 10:00; or_no_entry | SIMPLIFIED | am | No or_no_entry. The 10:00 test drops OR sweeps. | no |
| D2 | SB as its own setup | SIMPLIFIED | SB | No fvg_in_window. No first-FVG switch. | no |
| D3 | MSS close vs wick | FULL | mss_mode | (none) | no |
| D4 | MT body vs range | FULL | mt_mode | (none) | no |
| D5 | Exit buffer by type | FULL | exit_mode | (none) | no |
| D6 | Breaker zone body/range/leg | SIMPLIFIED | breaker_zone | No leg or last-candle mode. No tag-only switch. Now built: see section 4. | no |
| D7 | PM window and tags | FULL | pm; tags | (none) | no |
| D8 | News day options | SIMPLIFIED | blocked() | No nfp_day_from, no skip_post_fomc_am, no NFP no-adds. | no |
| D9 | CPI tests | SIMPLIFIED | skip_cpi | No skip_pre_cpi. | no |
| D10 | Early OB / turtle entries | MISSING | (none) | Audit-time note superseded: owner #11 OB-before-the-break default; turtle-soup variants as switches. See section 4. | no |
| D11 | Entry price modes | SIMPLIFIED | entry | No edge_1tick/iofed/ladder. Silent fallback. | no |
| D12 | P/D leg filter, add cutoff, OTE | SIMPLIFIED | leg_pd | No add_cutoff. The OTE test is inverted. | no |
| D13 | First partial size | FULL | ladder fracs | (none) | no |
| D14 | Breakeven / trailing modes | SIMPLIFIED | be_on; ladder_trail | No after_mss or stall BE. Trail-off undocumented. | no |
| D15 | Which index on divergence | SIMPLIFIED | combine | No smt_pick. No consolidation gate. | no |
| D16 | AM 12:00 / PM 15:00 exits | FULL | am_exit; pm_done_by | (none) | no |
| D17 | Pivot size | FULL | pivot_n=1 | (none) | no |
| D18 | Re-entry after a stop-out | SIMPLIFIED | reentry_half | See X13b. | no |
| D19 | Trade frequency | SIMPLIFIED | done; caps | Truncation order. No cap in paper.py. Breakeven counts as a win. | no |
| D20 | Mondays | SIMPLIFIED | skip_monday | No PM-only mode. | no |
| D21 | NWOG/ORG conventions | SIMPLIFIED | H gaps; org | org_days capped at 6. Monday gap mode has no CE. | no |
| D22 | Real midnight open | SIMPLIFIED | L.opens | No bias_open switch. Live SPY uses 04:00. | no |
| D23 | SD anchor | SIMPLIFIED | sd_targets | Anchor is leg_hi. No switch. | no |
| Ep01.0 | NY time | FULL | tz NY | (none) | no |
| Ep01.1 | BSL/SSL | FULL | pools | (none) | no |
| Ep01.2 | FVG/CE | FULL | L.fvgs | (none) | no |
| Ep01.3 | Void | FULL | L.voids | (none) | no |
| Ep01.4 | BPR | MISSING | balanced_ranges unused | Not used. | no |
| Ep01.5 | Breakaway gap | SIMPLIFIED | open-gap check; ce_hold | No classification. | no |
| Ep01.6 | Breaker body close | SIMPLIFIED | inline bz | No lower-low check. Not an entry. | no |
| Ep01.7 | Narrative vs bias | NA | (none) | Concept. | no |
| Ep01.8 | Low-vol inside day | SIMPLIFIED | pdh1/pdl1 | No detection. | no |
| Ep01.9 | Year end reprices up | MISSING | (none) | Audit-time note superseded: owner #3 = December's direction (mapping pending). See section 4. | no |
| Ep01.10 | AM 08:30-11:00, PM 14:00-16:00 | SIMPLIFIED | am/pm | 08:30-09:00 never scanned. | no |
| Ep01.11 | PM 15:15-15:45; nothing by 15:50 -> no trade | SIMPLIFIED | pm; tag | Audit-time note superseded: owner #1 = entries 15:00-15:50, 15:15-15:45 tag only. See section 4. | yes (was FULL) |
| Ep01.12 | AM loss no reverse | FULL | reverse_after_loss | (none) | no |
| Ep01.13 | Last-hour run | SIMPLIFIED | PM slot | No own slot. | no |
| Ep01.14 | Draw on liquidity | FULL | _targets | (none). Now built: see section 4. | no |
| Ep01.15 | Nested FVGs | SIMPLIFIED | require_htf | No all-TF requirement. | no |
| Ep01.16 | Hold above the 4h CE | MISSING | (none) | Not built. | no |
| Ep01.17 | Bodies refuse; started by 15:25 | SIMPLIFIED | require_htf | No timing. No breakaway check. | no |
| Ep01.18 | Entry and adds | SIMPLIFIED | edge; adds | No retest or breaker adds. | no |
| Ep01.19 | Dip into the breakaway gap | SIMPLIFIED | adds | No body stop. | no |
| Ep01.20 | Stop at the FVG candle open | SIMPLIFIED | stop modes | No open stop. No body trail. | no |
| Ep01.21 | Pool target with an intermediate | SIMPLIFIED | ladder; min_draw | No intermediate structure. | yes (was FULL) |
| Ep01.22 | Clean delivery | MISSING | (none) | Not built. | no |
| Ep01.23 | HTF refs on LTF | FULL | hzones; conf | (none) | no |
| Ep02.1 | 09:45 release wait | SIMPLIFIED | NEWS_1000 | No PMI. | no |
| Ep02.2 | AM short model | SIMPLIFIED | mirrored _scan | No round-number pools. No 1m OB/breaker entries. | no |
| Ep02.3 | Bearish OB MT | SIMPLIFIED | mt_mode | Wick-triggered MT stop. | no |
| Ep02.4 | CE/MT | FULL | Zone.mid/mt | (none) | no |
| Ep02.5 | HTF targets / runner | SIMPLIFIED | htf_targets | No 30m. No reclaim exit. | no |
| Ep02.6 | No narrative -> scalp | MISSING | (none) | Not built. | no |
| Ep02.7 | First day of year | MISSING | (ISM 10:00 by accident) | No rule. | no |
| Ep02.8 | Daily VI top-down | SIMPLIFIED | topdown | VIs unused. | no |
| Ep02.9 | Open FVG = breakaway | SIMPLIFIED | ce_hold | No tag. | no |
| Ep03.1 | NFP week | FULL | nfp_week_block | (none) | no |
| Ep03.2 | FOMC release | FULL | fomc_pm_from | (none) | no |
| Ep03.3 | VI daily draw | SIMPLIFIED | detector only | Unused. | no |
| Ep03.4 | BISI/SIBI | FULL | L.fvgs | (none) | no |
| Ep03.5 | Measuring gap | MISSING | (none) | Not built. | no |
| Ep03.6 | IOFED | FULL | edge entry | (none) | no |
| Ep03.7 | Rejection block named | NA | (none) | Not defined. | no |
| Ep03.8 | Reclaimed OB | NA | (none) | Descriptive. | no |
| Ep03.9 | OB anchor high/open | SIMPLIFIED | order_block_blend | No open entry. | no |
| Ep03.10 | First FVG trail | SIMPLIFIED | ladder_trail | Not the first FVG. | no |
| Ep03.11 | Stronger index | SIMPLIFIED | combine | First fill only. | no |
| Ep03.12 | MM buy context | SIMPLIFIED | htf_bias | No draw+pd combination. No pre-existing array. | no |
| Ep03.13 | STL then STH MSS | FULL | _scan | (none) | no |
| Ep03.14 | Entry/stop at the FVG | FULL | _scan | (none) | no |
| Ep03.15 | BE after buy-side | SIMPLIFIED | be_on | Not keyed to a pool. | no |
| Ep03.16 | Pyramid on held FVGs | FULL | adds | (none) | no |
| Ep03.17 | Bull-flag stop run | NA | (none) | Descriptive. | no |
| Ep03.18 | Small after large | NA | (none) | Descriptive. | no |
| Ep03.19 | Scale out one unit at a time | SIMPLIFIED | ladder | Fixed fractions. | no |
| Ep03.20 | Trail after two rounds | SIMPLIFIED | ladder_trail | After one partial. Not a measuring gap. | no |
| Ep03.21 | Never widen | FULL | max() | (none) | no |
| Ep03.22 | Final HTF target | SIMPLIFIED | ladder | Ends at the 3rd level. No VI. | no |
| Ep03.23 | Off before noon | FULL | am_exit | (none) | no |
| Ep03.24 | One setup/week; 5 handles | SIMPLIFIED | caps; min_draw | Audit-time note superseded: owner #2 = minimum, not a target; `t1_fixed_pts` switch (off). See section 4. | yes (was FULL) |
| Ep03.25 | Time-based charts | FULL | bars | (none) | no |
| Ep04.1 | NFP Friday | FULL | nfp_day | (none) | no |
| Ep04.2 | Midnight open | FULL | L.opens | (none) | no |
| Ep04.3 | PO3 bullish | SIMPLIFIED | use_bias | Judas not required. No hold. | no |
| Ep04.4 | PO3 bearish | SIMPLIFIED | mirror | Same as Ep04.3. | no |
| Ep04.5 | News dealing range | SIMPLIFIED | post_news | Not used from 09:30. Not a target. | no |
| Ep04.6 | MSS + OB near midnight | SIMPLIFIED | _scan | No OB entry. No tolerance. | no |
| Ep04.7 | Two MSS | MISSING | (none) | Not built. | no |
| Ep04.8 | IOFED | FULL | edge | (none) | no |
| Ep04.9 | Pyramid sizes | FULL | adds | (none) | no |
| Ep04.10 | Add at the FVG low end | MISSING | (none) | Not built. | no |
| Ep04.11 | Clean REH | SIMPLIFIED | _eq_levels | No smoothness priority. | no |
| Ep04.12 | Target order; bulk first | SIMPLIFIED | _targets | No type order. No VI. | no |
| Ep04.13 | Done by 15:00 | SIMPLIFIED | pm_done_by | No day done. | no |
| Ep04.14 | ES vs MES SMT | NA | (none) | Same underlying. | no |
| Ep05.1 | Breaker/OB MT levels | SIMPLIFIED | bz; ob_mt | Breaker MT unused. | no |
| Ep05.2 | No 08:30 news -> 09:30 | FULL | am | (none) | no |
| Ep05.3 | NWOG target | FULL | H gaps | (none) | no |
| Ep05.4 | Unicorn rules | SIMPLIFIED | uni | Not required. No overlap entry. | no |
| Ep05.5 | Accumulate in the breaker | SIMPLIFIED | limit FVG | No breaker entry. | no |
| Ep05.6 | 08:00 OB move | SIMPLIFIED | pre_0700 | One observation. | no |
| Ep05.7 | Lunch CE reversal | NA | (none) | Observation. | no |
| Ep05.8 | MM sell model | SIMPLIFIED | _scan | No consolidation. No rel-eq. | no |
| Ep05.9 | Weekly bias | FULL | weekly_bias | (none) | no |
| Ep05.10 | One market | FULL | combine | (none) | no |
| Ep05.11 | Stop placement anecdote | NA | (none) | Anecdote. | no |
| Ep06.1 | Kill zones | SIMPLIFIED | London pool | No London entries. | no |
| Ep06.2 | FX day template | NA | (none) | FX. | no |
| Ep06.3 | SIBI retrace to CE | FULL | entry ce; ce_hold | (none) | yes (was SIMPLIFIED) |
| Ep06.4 | SD projection | SIMPLIFIED | sd_targets | Anchor and close-based hits differ. | no |
| Ep06.5 | DXY/EURUSD | NA | dxy tag | FX. | no |
| Ep06.6 | Midnight reference | SIMPLIFIED | use_bias | No confirm, no target. | no |
| Ep06.7 | Prefer rel-eq pools | SIMPLIFIED | _eq_levels | No preference. | no |
| Ep07.1 | Old daily close draw | SIMPLIFIED | ORG q=0 | No weekly draw, no "unrealized" filter. | no |
| Ep07.2 | AM model | SIMPLIFIED | _scan | No VI entry. Edge default. | no |
| Ep07.3 | Ep07 stop/trail | FULL | ep07_stop/trail | (none) | no |
| Ep07.4 | VI holds | MISSING | (none) | Not built. | no |
| Ep07.5 | Down-close adds, up-close exits | MISSING | (none) | Not built. | no |
| Ep07.6 | Speed and distance | SIMPLIFIED | MSS close | No speed test. | no |
| Ep07.7 | Below the swing-low bodies | SIMPLIFIED | ep07_body_exit | The fill bar is never checked. | yes (was FULL) |
| Ep07.8 | Macro 09:50 | SIMPLIFIED | macro tag | Tag only. | no |
| Ep07.9 | Bulk exit; 1% risk | FULL | ladder; risk | (none) | no |
| Ep07.10 | 5-handle thinking | NA | (none) | Expectation. | no |
| Ep08.1 | Daily wick CE / FVG edges | SIMPLIFIED | wick; htf | One RTH day. Early exit. | no |
| Ep08.2 | Neutral / chop | SIMPLIFIED | bias_neutral | No chop mode. | no |
| Ep08.3 | Three opens | SIMPLIFIED | L.opens | 08:30/09:30 unusable. | no |
| Ep08.4 | MSS swing validity | SIMPLIFIED | refs[-1] | Minor swing. | no |
| Ep08.5 | Bearish OB open | SIMPLIFIED | ob_mt | No open entry. | no |
| Ep08.6 | PM 13:30 Judas | FULL | use_bias | (none) | no |
| Ep08.7 | Sell >= 50% | FULL | leg_pd | (none) | no |
| Ep08.8 | Partial before the FVG edge | FULL | exit_before | (none) | no |
| Ep08.9 | Measured move | SIMPLIFIED | sd_targets | Leg anchor. | no |
| Ep08.10 | Liquidity matrix | SIMPLIFIED | pd 1-3 | Window shift. RTH only. | no |
| Ep08.11 | Old level needs PD array + time | FULL | _scan gates | (none) | no |
| Ep08.12 | Size; after a loss | SIMPLIFIED | caps | No after-loss limit. | no |
| Ep08.13 | Done for the week remark | NA | (none) | Remark. | no |
| Ep08.14 | IOFED touch | FULL | edge + E3 fill | (none) | yes (was SIMPLIFIED) |
| Ep08.15 | Turtle soup | MISSING | (none) | Not built. | no |
| Ep08.16 | 5m equal lows MSS | SIMPLIFIED | entry_tf 5m | No 5m reference. | no |
| Ep08.17 | 1-tick stop; 10 handles | SIMPLIFIED | stop_buffer | Not a tick. No range rule. | no |

## 3. Work packages

Each package below lists its SIMPLIFIED and MISSING items, high impact first. Every item gets a short build spec, and new Params switches default off unless a spec says otherwise. Four items the checker moved to package "none" are placed where their code lives: L14b goes to entries_stops_sizing, M0.4 and M1.2 to setups_models, and M7.1 to targets_partials.

### File ownership and integration order

Most packages own a separate region of the code, so they can be built in parallel. Where two packages must change the same function, the integration order below says which merges first.

| Package | Owns | Shares with others |
|---|---|---|
| levels_detectors | `levels.py` (all new detectors); `confluence.py:_zones` new array rows; `htf.py:_arrays`/`opening_gaps`; `strategy.py` DayCtx pool construction, `_sell_side`, `_eq_levels` | `_scan` sweep test (A2 tick threshold), shared with setups_models |
| setups_models | `strategy.py:_scan` sweep/MSS block (~1027-1076) and new setup branches (turtle soup, breaker, IR, OB entries); `backtest.combine` instrument pick | `_scan` gap pick (~1077-1118), shared with entries_stops_sizing |
| entries_stops_sizing | `_scan` entry/stop block (~1118-1137); `run_day` pending-fill block (~877-919) and add-arming block (~863-875); `SB._arm` stop; `PO` fill | Add block shared with management_exits; Params entry/stop fields |
| targets_partials | `strategy.py:_targets`; `_scan` target merge (~1172-1213) | Ladder loop (~793-813), shared with management_exits |
| management_exits | `run_day` position-management loop (~786-860); `_after_close`; done flags | Uses ladder levels and kinds from targets_partials |
| bias_htf | `htf.py:table`; `run_day` `want`/bias (~764-769, ~945-951); `weekly_bias`; `BT.INTERMARKET`; new data loaders (COT/OI) | `_scan` bias gates (~1138-1170), shared with setups_models |
| news_calendar_times | `calendar.py` event sets; `blocked()` news branches; `run_day` session windows (`am_start`, `pre_windows`, ~740-760) | `blocked()` and `calendar.py`, shared with day_week_context |
| day_week_context | `day_context`; `blocked()` day-of-week/holiday branches; `BT.run` weekly state; weekly study scripts | Same as news_calendar_times |
| silver_bullet | `sb_model.py` only | Calls `_targets` and `blocked()` |

Merge order:
1. **levels_detectors.** Most new detectors are used by other packages.
2. **setups_models**, then **entries_stops_sizing**, then **targets_partials**. All three edit `_scan`, top to bottom in that order.
3. **targets_partials ladder changes**, then **management_exits**, then the **entries_stops_sizing add block**. All three edit the run_day management loop.
4. **news_calendar_times**, then **day_week_context**. Both edit `blocked()`, `calendar.py` and the session-window section of `run_day`.
5. **bias_htf**. It edits `htf.table` after levels_detectors adds VI rows to `_arrays`, and the `_scan` bias gates after setups_models.
6. **silver_bullet** goes last because it calls the shared `_targets`/`blocked()`.

Rules for every package:
- **Params:** each package adds its fields in its own commented block at the end of the Params class, so merges do not collide.
- **Shared helpers:**
  - `breaker_zone()` lives in levels_detectors and is used by setups, entries, targets and exits.
  - `adr5()` and `next_trading_day()` live in day_week_context and are used by news and targets.
  - `volume_imbalances` wiring lives in levels_detectors.
- **Build them first** (they are listed with the packages below).

### levels_detectors (36 items)

Owns: `levels.py`, `confluence._zones`, `htf._arrays`/`opening_gaps`, DayCtx pools, `_sell_side`, `_eq_levels`. Includes M1.2 (the `_scan` intact fix) only when the setups_models owner agrees, since that code sits in the sweep block.

High:
- **B21:** Pass at least 61 days of history. Build H/L 20/40/60 as pools `ipda20h` etc., plus `ipda_next` sequencing. Add `ipda_eq_day` (off/tag/skip) for the range-day-at-EQ rule.

Medium:
- **A1:** Add `swing_tiers()` for ITL/LTL, where a tier is known only once its right neighbour is. Add `mss_ref` (stl/itl/ltl) and `mss_ref_fallback`. Fix the stale rulebook note.
- **A2:** Add `sweep_ticks=1.0`, applied in `_scan`, intact, `_smt`, the `seen` filter and the SB swept tag. Test pool_swings=True. Add `sb_draw_pools_only`.
- **A5:** Add `fvg_c2_dir=True`, `Zone.q`, `fvg_quadrants`, `fvg_vi_extend`, `fvg_skip_above_pool`, `htf_ce_draw`, `fvg_q_hold`, a state tag with `fvg_state_filter`, and `fvg_keep_filled`.
- **A13:** Add a shared `breaker_zone(sd,l1_i,ref_i,ext_i,i,mode)` with body/range/leg modes, an L1-run check and an MT. Replace both definitions with it. **[built 2026-10-18, owner directives; see build_log.md]** `levels.breaker_zone(o,h,l,c,a0,ext_i,i,kind,mode,mt_mode)`: range (default, owner #14) / body; leg/last raise NotImplementedError; `_scan` and `levels.breakers()` both use it.
- **B1:** Add `vi_targets`, VI rows in `C._zones` and `H.table`, `wick_days`, and the `no_draw`/`skip_no_draw` consolidation state.
- **L1:** Add `am_range_end`, a `prev_am` pool, `session_priority` (prev_pm > london > prev_am) and `org_pools`.
- **L2:** Add `daily_level_needs_array`, `daily_level_needs_flow`, `pd_hl_session='eth'` and `pool_today_hl`.
- **L5:** Add `gap_quarters`, `nwog_skip_holiday`, `nwog_halfway` and `gap_run_stop`. Count trading days instead of calendar days.
- **L7:** Use an ORG history of max(org_days,5)+1. Set `org_close` per symbol. Add `org_draw`/breakaway, `org_half_draw` and an `org_q_hold` tag.
- **L10:** Add `wick_days`, `wick_weekly`, `wick_both`, `wick_session`, `wick_invalidate` and `wick_partial`. Fix the default mismatch.
- **M2.1:** Add `pool_gaps` (NWOG/NDOG as sweep pools, unique keys) with `gap_pool_edge` far/ce.
- **T2:** Add `release_open` (08:30 body hold) and `release_open_stop` (open/wick_ce). Add `bias_open` for the AM reference.
- **Ep01.5:** Add a breakaway mode (off/tag/hold/next_fvg) using ICT's first-FVG-after-MSS definition.
- **Ep01.6:** Require a lower low for bz. Take the candle from the L1-to-H leg. Add `breaker_entry` (shared with A13.4).
- **Ep02.8:** Add `vi_arrays`: daily/weekly VIs in `H._arrays` as draws, plus targets and an optional `vi_news_draw`.
- **Ep03.3:** Use the same `vi_arrays` switch, with a rebalance death rule and a D_vi draw.
- **Ep05.1:** Add `breaker_levels` (entry clamp at the breaker MT, body-close exit, a fallback stop).
- **Ep06.7:** Add `eq_pref` (off/rank/require) with a `pool_eq` kind.
- **Ep08.10:** Add `matrix_full` (ETH sessions), `matrix_days` (ict with today's H/L), and the labels m3h/m3l.

Low:
- **A3:** Add `eq_bodies` and `eq_rank` (touches, spread). Test eq_tol 0.25/0.5/1.0.
- **A7:** Add `immediate_rebalances()`, `imm_rebalance_disp`, a Trade.imm_rebal tag, and a daily open_to_pdh/pdl tag.
- **A9:** Add a VI min_gap, a body death rule, `vi_stop`, `vi_porous_n` and `vi_htf_draw`.
- **A11:** Window BPR pairs with `bpr_max_gap_bars`. Add `bpr_targets` and `bpr_abort` (body close through the midpoint).
- **A13.1:** Add `breaker_ll` (real pivots, L2 < L1, body close above the real H).
- **A13.5:** Add `breaker_time` (H, L2 and the break in one session block), with an optional L1.
- **A15:** Fix the `mitigation_blocks` swing order (A, X, then a higher low B). Add `mit_targets` and `mit_body_respect`.
- **D6:** Allow breaker_zone leg and last, and raise an error on unknown values. Add `unicorn_pref`.
- **D21:** Pass org_days into DayCtx and widen the history. Add a CE for the monday gap mode. Add `nwog_quarters` and `org_sweep`.
- **L3:** Add `ipda_pools`, `ipda_next`, `or_extra` and `pw_pm_full_session`.
- **L8:** Add `vacuum_block()` at releases (08:30 near/MT/far; 10:00+ near/MT). Do not duplicate NDOG/ORG.
- **M0.2:** Shares the L1 `pool_priority` and prev_am work.
- **Ep01.4:** Add `bpr_rule` with known-time BPRs, the A11 midpoint body-close exit and a T1 cap.
- **Ep02.9:** Use the shared breakaway tag (Ep01.5).
- **Ep08.1:** Add `wick_days` (full session), `wick_react` and `daily_fvg_exact`.
- **M1.2 (reassigned):** In intact(), for swing_low keys use a = pivot index + 1. Optionally add `displacement_mult`. **[built 2026-10-18, owner directives; see build_log.md]** Fixed; `displacement_mult` (default 0 = off).

### entries_stops_sizing (45 items)

Owns: the `_scan` entry/stop block, the pending-fill and add-arming blocks in run_day, the SB stop and the PO fill.

High:
- **E6:** Add stop_mode choices (fvg_c1_low, fvg_bodies, sweep), plus `stop_all_ineff`, `stop_pad_ticks`, `ce_stop_pad_pts`, `mohawk_ticks` and `nfp_stop_wide`. **[built 2026-10-18, entries_stops_sizing; see build_log.md]**
- **E6c:** Add stop_mode='sweep' (sw.ext - buffer), tested with max_risk 25. **[built 2026-10-18, entries_stops_sizing; see build_log.md]**

Medium:
- **A4:** Add `mohawk_ticks` for all structural stops and trails, with a close-based exit beyond the raw level and a mohawk-tolerant fresh test. Add `sweep_body` (unranked, off). **[built 2026-10-18, entries_stops_sizing; see build_log.md]**
- **A12:** Add `ob_zone` (range/sensitive) with the stubby/long wick rule, `mt_close_stop`, `ob_disp_mult`, an ob_cisd tag with a cancel, `ob_targets_1m` and `opp_ob_mt`. **[built 2026-10-18, entries_stops_sizing; see build_log.md]**
- **A13.4:** Add `breaker_entry`. Compute bz before the no-FVG return. Enter at the breaker top with the stop beyond the sweep. Cancel on a body close below the MT. **[built 2026-10-18, entries_stops_sizing; see build_log.md]**
- **M1.4:** ~~Add `early_entry` (pre-MSS OB limit, HTF+SMT gates, half risk).~~ **Owner #11: the OB entry before the break is the DEFAULT (`ob_entry="pre_break"`), no HTF/SMT gates, full risk; `post_mss` / `both` are switches.** **[built 2026-10-18, owner directives; see build_log.md]**
- **M2.4:** Add `no_new_extreme` (freeze leg_hi0 and cancel on a new extreme before the fill). **[built 2026-10-18, entries_stops_sizing; see build_log.md]**
- **E2:** Extend entry to iofed/ladder, with an `iofed_ref` option. Pass it to SB. **[built 2026-10-18, entries_stops_sizing; see build_log.md]**
- **E5:** Add `evolve_fvg` (keep the sweep alive, replace only with a newer untouched FVG) and `wait_structural`. **[built 2026-10-18, entries_stops_sizing; see build_log.md]**
- **E6b:** Add stop_mode fvg_candle and fvg_bodies. **[built 2026-10-18, entries_stops_sizing; see build_log.md]**
- **E6d:** Add `stop_all_ineff` (open FVGs/VIs below the entry, overshoot wick). **[built 2026-10-18, entries_stops_sizing; see build_log.md]**
- **E6f:** Add `stop_pad_ticks` to replace the 0.01 buffer, plus `ce_stop_pad_pts` and `nfp_stop_wide`. **[built 2026-10-18, entries_stops_sizing; see build_log.md]**
- **E9:** Add `size_rules` multipliers (news eve, FOMC week, August, against macro, decoupled, low probability) and test-only size-ups (BPR, HTF 5000). **[built 2026-10-18, entries_stops_sizing; see build_log.md]**
- **E10:** Add `loss_halving` with halving_floor and winback_frac carried across days, plus `no_max_after_loss`. **[built 2026-10-18, entries_stops_sizing; see build_log.md]**
- **E12:** Add `add_points`, `add_fvg_low_end`, `add_cutoff` and `no_adds_nfp`/low probability. Reconcile the adds default with the docs. **[built 2026-10-18, entries_stops_sizing; see build_log.md]**
- **E12e:** Add `add_cut` (EQ of the range or leg 75%) with a cancel once progress passes it. **[built 2026-10-18, entries_stops_sizing; see build_log.md]**
- **D11:** Extend entry to edge_1tick/iofed/ladder, raise on unknown values, and loosen the touch cancel. **[built 2026-10-18, entries_stops_sizing; see build_log.md]**
- **D12:** Add `add_cutoff=0.25` (mirrored for the 022 short) and `leg_pd_min`. Fix the OTE study variant. **[built 2026-10-18, entries_stops_sizing; see build_log.md]**
- **Ep02.2:** Add `round_pools` and `entry_arrays` (ob, breaker). **[built 2026-10-18, entries_stops_sizing; see build_log.md]**
- **Ep02.3:** Add `mt_close_stop` when the MT is the binding stop, with the far-edge hard stop. **[built 2026-10-18, entries_stops_sizing; see build_log.md]**
- **Ep01.20:** Add stop_mode fvg_open and `trail_ref` body. **[built 2026-10-18, entries_stops_sizing; see build_log.md]**
- **Ep07.2:** Add `vi_entries` (VI index offset, not is_ifvg). Add an ep07 preset. **[built 2026-10-18, entries_stops_sizing; see build_log.md]**
- **Ep07.4:** Add `vi_stop` and `vi_hold` (body close below the VI). **[built 2026-10-18, entries_stops_sizing; see build_log.md]**
- **Ep08.5:** Add ob_entries off/fallback/prefer at the anchor open with the MT stop, run before the no-gap return. **[built 2026-10-18, entries_stops_sizing; see build_log.md]**
- **Ep08.17:** Add `stop_tick_pts=0.25` (default on) and `engage_range_pts`. **[built 2026-10-18, entries_stops_sizing; see build_log.md]**
- **L14b (reassigned):** Add `irl_entries` (fvg/ob/void), `erl_range_swings` and `erl_exits_only`. **[built 2026-10-18, entries_stops_sizing; see build_log.md]**

Low:
- **A16:** Add `prop_entry` (top - 1 tick), `prop_mt_exit` and `prop_zone`. **[built 2026-10-18, entries_stops_sizing; see build_log.md]**
- **A21.3:** Add `ote` (62-79% band, 70.5% entry, 79% cancel) and a leg_depth tag. **[built 2026-10-18, entries_stops_sizing; see build_log.md]**
- **M2.5:** Add stop_mode ob_mt_pure (2 pt pad), fvg_candle and ce2. **[built 2026-10-18, entries_stops_sizing; see build_log.md]**
- **E1:** Add `add_order` market-on-retest and `entry_order` stop_cc. **[built 2026-10-18, entries_stops_sizing; see build_log.md]**
- **E3:** Add `tick_pts`/`fill_through` in all paths. Fix Ma Deuce `<=`. Add `exit_fill_through`. **[built 2026-10-18, entries_stops_sizing; see build_log.md]**
- **E4:** Add `retrace_candle` intrabar/closed. **[built 2026-10-18, entries_stops_sizing; see build_log.md]**
- **E8:** ~~Add `risk_pct` with running equity, a 2% clamp and `risk_incl_costs`.~~ **Owner #12: 1.2% open risk at entry (`risk_pct=0.012`), at most 1.3% incl. adds (`max_total_risk_pct=0.013`); no 2% anywhere; `risk_basis="equity"` switch; legacy 1%/2% = study preset.** **[built 2026-10-18, owner directives; see build_log.md]**
- **E11:** Add `max_contracts_initial`/`total` with `units_per_contract`. (The 1.3% total cap of owner #12 is built: adds shrink to fit, open risk clamped at 0.) **[built 2026-10-18, entries_stops_sizing; see build_log.md]**
- **E12b:** Add `add_arrays` (vi/ifvg/ob/breaker) and `add_hold`. **[built 2026-10-18, entries_stops_sizing; see build_log.md]**
- **E12c:** Add `add_low_end` (body closes into the FVG -> add at its bottom, once). **[built 2026-10-18, entries_stops_sizing; see build_log.md]**
- **E12f:** Add `nfp_no_adds=True` and `decoupled_no_adds`. **[built 2026-10-18, entries_stops_sizing; see build_log.md]**
- **Ep01.18:** Add `add_on` retest/breaker. **[built 2026-10-18, entries_stops_sizing; see build_log.md]**
- **Ep01.19:** Add `add_body_stop`. **[built 2026-10-18, entries_stops_sizing; see build_log.md]**
- **Ep03.9:** Add `ob_entry` high/open. **[built 2026-10-18, entries_stops_sizing; see build_log.md]**
- **Ep04.6:** Use entry_arrays ob. Add `mo_tol_pts` (tolerance above the open). **[built 2026-10-18, entries_stops_sizing; see build_log.md]**
- **Ep04.10:** Add `add_fvg_low`. **[built 2026-10-18, entries_stops_sizing; see build_log.md]**
- **Ep05.5:** Add `breaker_entry` fallback at bz.top. **[built 2026-10-18, entries_stops_sizing; see build_log.md]**
- **Ep08.12:** Add `after_loss_mult` and `after_loss_adds`. **[built 2026-10-18, entries_stops_sizing; see build_log.md]**
- **Ep08.17:** Covered under the medium items above.

### targets_partials (36 items)

Owns: `_targets` and the `_scan` target merge. Ladder-loop edits are done in coordination with management_exits.

High:
- **X3:** Umbrella for X3a-h: `ladder_all_pools`, `wick_ce_partial`, `sd_neg05_first`, `halfway_partial`, `smt_bank`, `resistance_mode`, and a capture metric. **[built 2026-10-18, targets_partials; see build_log.md]**

Medium:
- **A6:** Add a breakaway tag, `measuring_gap` (near-edge projection) and `trail_breakaway`. **[built 2026-10-18, targets_partials; see build_log.md]**
- **A22:** Add `matrix_targets` (breakers, mitigation and rejection blocks), `breaker_first` and `skip_exhausted`. **[built 2026-10-18, targets_partials; see build_log.md]**
- **L4:** Add `pool_rank` (touch count + TF), `rel_tfs`, `draw_below_eq`, `lrlr_max` and `pool_runner_pts`. **[PARTIAL 2026-10-18: lrlr_max / rel_tfs / clean_eq_pref act only with draw_lock="off"; gap-note extras not built; see build_log.md]**
- **L9:** Add `fvg_over_ob`, `fvg_remainder` (far-edge test) and `weekly_gap_ce_only`. **[built 2026-10-18, targets_partials; see build_log.md]**
- **L11:** Add `rb_targets` ladder/replace at the body edge. **[built 2026-10-18, targets_partials; see build_log.md]**
- **L12:** Add sd_levels 0.5-4.5, `sd_anchor` (sweep_leg/fulcrum/london/multi), `sd_cluster_ticks`, `sd_roles`, `sd_align` and `sd_no_pool_fallback`. **[built 2026-10-18, targets_partials; see build_log.md]**
- **L14d:** Add `target_hygiene` (retire traded-through arrays, touched HTF arrays). **[built 2026-10-18, targets_partials; see build_log.md]**
- **M8:** Add `org_reprice` (Judas away from the ORG, T1 = near edge). **[built 2026-10-18, targets_partials; see build_log.md]**
- **M14.2:** Add `tgif_zone` (20/22.5/25/30% of the weekly range from Sunday 18:00, cap at 30%, stand down at 40%). **[built 2026-10-18, targets_partials; see build_log.md]**
- **X1:** Add `target_ltf_obs` and `keep_inner_levels`. **[built 2026-10-18, targets_partials; see build_log.md]**
- **X3a:** Add `run_down` and `ladder_max_levels`. Keep level kinds. **[built 2026-10-18, targets_partials; see build_log.md]**
- **X3c:** Add `wick_partials` (multi-TF, longest wick, protected rung). **[built 2026-10-18, targets_partials; see build_log.md]**
- **X3d:** Add `sd_half_partial` (exempt from min_rr) and `halfway_partial`. **[built 2026-10-18, targets_partials; see build_log.md]**
- **Ep02.5:** Add 30m to htf_targets. Add `runner_htf_exit` (test 15m and 30m). **[built 2026-10-18, owner directives; see build_log.md]** `htf_targets_30m`, `runner_htf_exit` (off). Owner #7: the overhead 15m FVG is RESISTANCE (new row Ep02.10, `htf_resist_cap=True`).
- **Ep03.5:** Add `measuring_target` with `measuring_anchor` near/ce. **[built 2026-10-18, targets_partials; see build_log.md]**
- **Ep03.22:** Add `final_htf` (last rung = nearest 4h/D/W array or daily VI). **[built 2026-10-18, targets_partials; see build_log.md]**

Low:
- **A10:** Add `void_targets` and `leg_start_target`. **[built 2026-10-18, targets_partials; see build_log.md]**
- **A17:** Fix the rejection_blocks window and wick test. Add `rej_targets` and `pool_body_edge`. **[built 2026-10-18, targets_partials; see build_log.md]**
- **A23:** Add `wick_days`, `wick_daily_src`, `wick_week`, `wick_tfs` and `wick_read`. Fix the default doc. **[built 2026-10-18, targets_partials; see build_log.md]**
- **L13:** Add `proj_breaker`, `proj_measuring`, `proj_org_k` and `proj_ext`. **[built 2026-10-18, targets_partials; see build_log.md]**
- **L16:** Add `adr_target`/`adr_frac` and `adr_early` (80% off before 10:00). **[built 2026-10-18, targets_partials; see build_log.md]**
- **L17:** Add `round_step_pts` (targets down and entries up toward price; stops not rounded). **[built 2026-10-18, targets_partials; see build_log.md]**
- **M14.4:** Add `tgif_exits` (25/25/50 at 20/22.5/25%). **[built 2026-10-18, targets_partials; see build_log.md]**
- **X3b:** Add JOLTS dates, SB use of _split, and a slow_frac study. **[PARTIAL 2026-10-18: _split and slow_frac built; JOLTS dates before 2026 missing; see build_log.md]**
- **X3f:** Add `resistance_mode` (full pull at the draw). **[built 2026-10-18, targets_partials; see build_log.md]**
- **X3h:** Add `capture_frac`. **[built 2026-10-18, targets_partials; see build_log.md]**
- **D23:** Add `sd_anchor` broken/leg and sd_levels 0.5-4.5. Fix the models.md note. **[built 2026-10-18, targets_partials; see build_log.md]**
- **Ep01.21:** Add `inter_swing_target` (swing intermediate, pool draw). **[built 2026-10-18, targets_partials; see build_log.md]**
- **Ep03.19:** Add mgmt='unit'. **[built 2026-10-18, targets_partials; see build_log.md]**
- **Ep04.11:** Add `clean_eq_pref`. **[built 2026-10-18, targets_partials; see build_log.md]**
- **Ep04.12:** Add `daily_vi_targets`, `ladder_news_day` and `target_order`. **[built 2026-10-18, targets_partials; see build_log.md]**
- **Ep06.4:** Add sd_anchor manip, `sd_close_hit` and `sd_close_window`. **[built 2026-10-18, targets_partials; see build_log.md]**
- **Ep07.1:** Add `close_draw` (unrealized prior closes, the weekly draw as a pool). **[built 2026-10-18, targets_partials; see build_log.md]**
- **Ep08.9:** Add `mm_targets` with `mm_anchor` ref/leg. **[built 2026-10-18, targets_partials; see build_log.md]**
- **M7.1 (reassigned):** Add `pm_off_lunch` (exempt the lunch high from `seen`, make it the draw) and `pm_judas_1330`. **[built 2026-10-18, owner directives; see build_log.md]** Bug fixed at the root (`seen_from_created=True`: a pool is spent only by bars after it formed - the lunch, overnight, London and AM highs were always dropped); `pm_off_lunch`, `pm_judas_1330` switches (off).

### setups_models (75 items)

Owns: the `_scan` sweep/MSS block, new setup branches, and `combine` picking. A shared turtle-soup core covers M12/M12.1-5/D10/Ep08.15/M4.4.

High:
- **A19:** Add mss_ref last/parent, `mss_ref_fallback` and `mss_on_side`.
- **A19.2:** Add mss_ref itl, `mss_eq_wait` and `mss_fallback`.
- **A20:** Add `disp_mult` (OB body), `disp_follow`, `disp_through_pts` and `disp_fvg_after_break`, also in SB.
- **M1:** Add `am_htf_draw`, `am_discount_array`, `rip_through`, `ob_pre_mss_entry` and an explicit nearest-OB stop.
- **M2:** Add fvg_pick m2, `no_breakout_fvg`, stop ce_higher, `add_leg_cut`, `m2_target` and a `three_drives` tag.
- **M12:** Add `turtle_soup` (2023/cc_limit/cc_1h_ob/or60/external) with `ts_max_pts`, `ts_back_bars`, an HTF array and order-flow check. **[shared core built 2026-10-18]** `levels.turtle_soup()` + `turtle_soup="2023"` (`ts_max_pts`, `ts_back_bars`, `ts_need_htf`); the cc_limit/cc_1h_ob/or60/external variants stay with setups_models.
- **M12.1:** 2023 variant: limit at the array top, stop at the array or a gap, no MSS needed.
- **Ep08.4:** Add mss_ref='origin' anchored at ext_i.

Medium:
- **A19.4:** Add `on_side` tag/require (track after arming).
- **M0:** Umbrella: candle_draw bias, pool priority, entry_arrays.
- **M0.5:** Add `entry_arrays` (ob/breaker/ote/wick_ce), merged before the fvg_wait reset.
- **M1.1:** Add `mm_context` and `daily_vi_targets`.
- **M1.3:** Add `speed_check` (SIBI reclaimed within speed_bars) and a fill-bar body_low check.
- **M2.3:** Add fvg_pick='2022' (VI+OB, then first in discount, then deeper of two).
- **M4:** Add `breaker_entries`, `unicorn_mt_floor`, `unicorn_open_only`, leg zone/advanced, `breaker_retest_add` and `failure_swing_entries`.
- **M4.1:** Classic breaker entry (bz before the FVG return, MT cancel, stop beyond L2).
- **M5:** Add `pm_last_hour_model` (sweep in the window, no entries after 15:45, HTF-done skip) and `pm_ep01`.
- **M5.1:** Add `pm_ep01` (nested 1h/4h, refusal, breakaway, 4h CE hold, single exit).
- **M10:** Add `ifvg_entry`, `ifvg_stop_pts`, `ifvg_min_risk_pts`, `ifvg_depth` and `ifvg_061`.
- **M11:** Add `ir_entries`, `cisd_ob_entries` and `wick_ce_entries`.
- **M12.2:** Add the turtle_soup short branch at the spike with `ts_adds_breakers`.
- **M12.3:** Add cc_limit, cc_1h_ob and or60 variants, plus mgmt r_multiple.
- **M12.5:** Add a depth/back gate inside turtle soup, optionally on the MSS model too.
- **M13:** Add `ote` filter/limit, a strict leg_pd, a leg stop and an ote_stack tag.
- **M16:** Add `smt_entry` and `sick_sister`.
- **M16.1:** Add `smt_entry` (05:00 lows, buy stop above the down-close candle, `smt_turtle`, exit at 11:00, ES only).
- **D10:** ~~Add `early_entry`~~ **Owner #11: recommended = B (OB before the MSS) as the default `ob_entry="pre_break"`; A (after the MSS) = `ob_entry="post_mss"`; no HTF+SMT gating.** `turtle_soup` shared core built (2023 variant). **[built 2026-10-18, owner directives; see build_log.md]**
- **Ep01.13:** Add `last_hour_setup` (LH_PM slot, unengaged liquidity, HTF-done skip).
- **Ep01.15:** Add `nest_tfs` with FVG-only confluence.
- **Ep03.11:** Add smt_pick leader/laggard with ext/leg_hi fields.
- **Ep04.3:** Add `require_judas`, `po3_runner` and `judas_window`.
- **Ep04.5:** Add `news_range` (pools from 09:00, opposite-extreme draw). **[built 2026-10-18, owner directives; see build_log.md]** Owner #4: the range completes when it forms (`news_wait="range"`), not at a fixed 09:00; its low/high are pools, the opposite extreme a target.
- **Ep04.7:** Add `mss_count=2` (higher low, second break, both FVGs open).
- **Ep05.4:** Add `unicorn_only`, unicorn_entry overlap, `add_on_vi`, `unicorn_open` and `adds_in_breaker`.
- **Ep05.8:** Add `mmxm_ctx` (consolidation origin, target its low) and `mmxm_breaker`. Reuse ce_hold.
- **Ep07.6:** Add `mss_max_bars`, `mss_disp` and `mss_ref_sibi`.
- **Ep08.15:** Add turtle_soup with `ts_need_htf` and `ts_max_run`.
- **Ep08.16:** Add `mss_ref_tf=5` (5m equal levels or swing as the MSS reference).

Low:
- **A8:** Add IFVG passes and both-way counts, `ifvg_depth`, `ifvg_hold` and `ifvg_after_htf`.
- **A14:** Add a unicorn_open tag and `unicorn_only`.
- **A18:** Add `reclaimed_ob` (sell-side-of-curve OB, reclaimed after the low, retest limit).
- **A24:** Umbrella for the Reaper.
- **A24.2:** Add `reaper` (discount-half FVG of the breaker leg, CE holds, optional `reaper_confirm`).
- **B18:** Umbrella: `smt_window`, `smt_at_pd`, `smt_min_gap` and `smt_pick`.
- **B18.1:** Add `smt_min_gap_pts`, `smt_need_array` and rel-eq partner pivots.
- **B18.2:** Add `smt_windows` with smt_pre for the 05:00-09:30 window.
- **N6:** Add `news_profile` (first-leg extreme), `news_ce_target` and `news_no_unicorn`.
- **T10:** Add `moc_run` (15:40 run to unengaged liquidity, HTF-done gate) and `moc_pool_exit`.
- **T13:** Add `require_judas`, `po3_hold`, profile tags and `nfp_sd`.
- **M2.7:** Add a `three_drives` tag/filter (known pivots, into a level, failing pushes).
- **M4.2:** Add `unicorn_rules` (Judas gate, entry inside bz, MT floor).
- **M4.3:** Add `adv_breaker` (A-B leg, MT 1 tick through, B+1x(B-A)).
- **M4.4:** Add `ts_breaker_pyramid`.
- **M4.5:** Add `cc_swings` (breaker swing/failure swing retest of the breaking point).
- **M5.2:** Add `last_hour_strict`, `last_hour_own_slot` and entry_arrays vi/ob.
- **M6:** Add `pm_reversal` (bias +1, AM high taken, objective met, IFVG at the high).
- **M7:** Add `pm_lunch_target`, `pm_lunch_org` and `pm_judas_filter`.
- **M7.2:** Add `lunch_org`.
- **M7.3:** Add `pm_judas_array`.
- **M11a:** Add `ir_entry` (A7 detector, tight stop, close-beyond-EQ exit).
- **M11b:** Add `cisd_ob_entry` (wick CISD, limit min(EQ, OB top), OB-low cancel).
- **M11c:** Add `wick_ce_entry`.
- **M12.4:** Add the external turtle soup (false low above an unreached HTF array).
- **M15:** Add `md_big_candle`, `md_second`, a ladder of targets, `md_need_news`, ETH dailies and blocked() routing.
- **M16.2:** Add `sick_sister` (fewest reference highs taken, deep discount, untaken targets).
- **Ep01.16:** Add `pm_4h_ce` (body holds above the 4h FVG CE from 15:00).
- **Ep01.17:** Add `lh_start_by=925`.
- **Ep01.22:** Add `clean_leg=-1` and clean_body.
- **Ep04.4:** Add `po3_require_bias`, `po3_inclusive` and require_judas.
- **Ep05.6:** Test variant only.
- **M0.4 (reassigned):** Add `disp_body_mult` and `disp_follow`.

### bias_htf (45 items)

Owns: `htf.table`, run_day bias filters, `weekly_bias`, `INTERMARKET` and new data loaders.

High:
- **B2:** Add draw_ord / draw_ord_lvl / draw_ext_lvl columns (inefficiency first, then P/D liquidity, then extent). Add htf_bias='ordered' and `draw_ext_target`.
- **B3:** Add an ordered/largest-draw mode. Remove the look-ahead with `htf.table cut` per session start. Pass `want` to SB/Ma Deuce. Add `judas_required`. **[built 2026-10-18, owner directives; see build_log.md]** Owner #9 `draw_lock="session"` (default): `htf.table(cut_min)` per lock time, ONE locked draw per session, side gate in all engines, exit at it, session done when delivered. Ordered pick / judas_required still open.
- **B6:** Add an `iof` column (held down-closes, run up-closes, reversed pivot raids) and mode combo2.
- **L14:** Umbrella: `draw_first`, a conf-target hygiene extension, `conditional_draw`.
- **L14a:** Add draw_first='session' (B2 order, side gate, stop once the objective is met). **[built 2026-10-18, owner directives; see build_log.md]** (as owner #9 draw_lock; B2 ordering still open).

Medium:
- **A21:** Add `pd_day_range`, `ote_band`, `pd_zone` and `pd_body_multiday`.
- **A21.2:** Add day_pd='20d' (body range of 20 prior sessions) and a pd20 column.
- **B5:** Add `weekly_gate`, VI rows in C, `news_topdown` and `bellwether_15m`.
- **B7:** Add an `ob_mt` state column (last bull/bear daily OB, flip on a close through the MT) and `how_rule`.
- **B8:** Add a stateful `flip` column with triggers flip_ob_mt, flip_pd3, flip_wk_dc, flip_close_above, flip_thu_wopen and stop_flip. **[shared column built 2026-10-18]** `htf.table` column `flip` (triggers ob_mt and wk_dc; the others raise NotImplementedError until bias_htf adds them); `htf_bias="flip"`.
- **B8a:** Add the `ob_state` flip (same as B7).
- **B8c:** Add `flip_wk_dc` (weekly close beyond the last down/up-close week).
- **B9:** Add `objective_neutral`, persistence and `next_array_on_fail`.
- **B10:** Add `mwd` (M/W/D displacement state, breaker-only cancel, cases A/B/C).
- **B13:** Add weekly_open filter (sun18/mon00/either, Mon-Tue below / Wed+ above, expires at an opposing daily array).
- **B14.1:** Add `nwog_regime` (return count, trending/consolidation, `nwog_converge_pts`).
- **B14.3:** Add `nwog_bias` with hold-until-reclaim.
- **B17:** Add `neutral_gate` tuple (fifty_fifty, premium_chop, draw_delivered, range_market, decoupled).
- **B17.1:** Add `neutral_5050` (both sides armed in the window, or separate react weights).
- **B17.3:** Add objective_met_stop day/week.
- **L14c:** Add `matrix_tf_lower` (react_tf, then the opposing array one TF down as the draw).
- **M0.1:** Add bias_candle W/D (nearest unreached draw from the candle open). Apply `want` in SB/Ma Deuce.
- **D15:** Add smt_pick first/leader/laggard (laggard on consolidation days) and `one_market`.
- **D22:** Add a `bias_open` helper, `bias_open_src`, and live midnight from CFD/ES mapped to SPY.
- **Ep02.6:** Add `no_narrative_scalp` (bias_neutral='scalp', single target, no adds).
- **Ep03.12:** Add htf_bias='draw_pd', daily VI draws and `mmbm_zone`.
- **Ep08.2:** Add chop_mode skip/scalp (overnight range, or stuck inside an HTF array).

Low:
- **A21.4:** Add `pd_bodies` in htf.table and the 20-day range.
- **B8b:** Add `flip_pd3` (3 nearest supporting D/W arrays closed through).
- **B8d:** Add `flip_close_above` (Friday high, last daily wick CE, weekly wick CE/quadrant), with the result set to neutral.
- **B8e:** Add `flip_thu_wopen` (body close across the weekly open on Thursday).
- **B8f:** Add `stop_flip` (breaker_far stored, stop-out flips the day's side, SMT-only option).
- **B14.2:** Add a converging-NWOG check (in the regime function).
- **B17.5:** Add decoupled tag/scalp/skip and `smt_both`.
- **B19:** Umbrella intermarket switches.
- **B19.1:** Add `dxy_gate` (prior close above the 20-day high and rising -> block longs).
- **B19.3:** Add bond_range tag/scalp and bond_dir.
- **B20:** Umbrella.
- **B20.1:** Add a `cot_tag` loader (52-week midpoint, usable from the session after release).
- **B20.2:** Add an `oi_tag` (Databento statistics, roll-summed).
- **B20.3:** Add a `wpr_tag` (weekly %R(14)).
- **B22:** Add qshift_tag/size (60-day turn or consolidation, due window, 252-day trend).
- **L14e:** Add `cond_draw` (failed upper draw -> lower side, spent flag).
- **Ep06.6:** Add `midnight_target`, `midnight_confirm` and `midnight_below_ok`.
- **Ep08.3:** Add bias_open midnight/0830/0930/all with a time guard.

### management_exits (46 items)

**[built 2026-10-18: every item below; see section 6 and `build_log.md` "Package management_exits"]**

Owns: the run_day management loop, `_after_close` and done flags.

High:
- **M2.6:** Add `add_in_pd` and `add_cutoff=0.25` (fixed leg at the fill, block adds past the 25% line) and `pool_size_rank`.

Medium:
- **X3g:** Add `smt_partial` (50% when a sister refuses to break, 80% when the sister breaks against the trade). **[built 2026-10-18: `smt_bank` 50% + `smt_bank_against_frac` 80%]**
- **X5:** Umbrella.
- **X5a:** Add ladder_trail breakaway/measuring and `trail_pad_pts=0.25`.
- **X6:** Rework `fvg_abort` (close-only arm, confirm on the next bar only, clear the arm, 5m candles).
- **X7:** Umbrella.
- **X7a:** Add a pd3 list fixed at the fill (FVG/VI/OB MT/breaker, nearest 3), a warn tag, and `pd3_dynamic`.
- **X7b:** Add `pd3_half` (VI+FVG+OB MT body closes -> 50% off once).
- **X8:** Umbrella.
- **X9:** Umbrella; apply to SB/Ma Deuce.
- **X9a:** Add `time_stop_ref` (pts/leg_high/array_far) and `time_stop_frac`.
- **X9c:** Add far_edge_min=2 with `far_edge_frac` (moved back = CE).
- **X10:** Apply am_exit to SB and Ma Deuce. Add X10b-d. **[built 2026-10-18, owner directives; see build_log.md]** Owner #8: close (not tighten); `am_exit_extras=True` covers SB-AM, London SB and Ma Deuce; `am_exit_mode="tighten"` test switch. X10b-d still open.
- **X11:** Umbrella.
- **X12:** Add `obj_stop` with obj_source draw/htf_ce (exit at the objective, then all done flags for the day).
- **X13:** Umbrella.
- **X13b:** Gated reentry_half (same side, idea intact, not FOMC, restored sweep with fvg after the stop, done_key).
- **D14:** Add be_on after_mss and stall, ladder_trail 'off', and study variants. Fix stale docs.
- **D18:** Add reentry_lock_r/target_r, half of the losing trade's risk, and a lost_side reset at the PM.
- **Ep03.10:** Add `trail_first_fvg` and first_fvg_fail.
- **Ep03.15:** Add be_on='pool' (carry pool levels).
- **Ep03.20:** Add `trail_after=2` and ladder_trail='measuring'.

Low:
- **A13.3:** Add breaker_zone leg (A=L1 to B=H), `breaker_mt_exit` and `breaker_mt_entry`. **[built 2026-10-18, owner directives; see build_log.md]** Owner #6: breaker-MT respect is a DEFAULT (`breaker_mt_respect`, `breaker_mt_entry_floor`; MT = 50% of the full range, `breaker_mt_mode="body"` switch); leg mode still planned.
- **B18.3:** Add `smt_exit`, smt_pick and `smt_bias`.
- **T11:** Add `late_cutoff=945` (no adds, no fades) default on.
- **X4:** Add `be_pad_pts` with a cost pad. Have SB respect be_on.
- **X5c:** Add trade_type 'day' (08:30 open/wick-CE stop, no trail, no BE).
- **X7c:** Add `session_stop_after_fails` (trades/arrays mode, SB keys shared).
- **X8b:** Add `leg_mt_exit` (close below the leg candle MT).
- **X8c:** Add `ir_eq_exit` (wick by default).
- **X8d:** Add `prop_exit`.
- **X8e:** Add `offside_exit` with offside_level open/wick_ce.
- **X8g:** Add `meander_bars` (store fvg_top).
- **X9d:** Add `time_stop_frac=0.5` with fire-once and a min-size close.
- **X10b:** Add `am_bulk_t` and `am_bulk_frac` (only for fills before that time).
- **X10c:** Add `smt_hold_until` and `smt_hold_exit`.
- **X11c:** Add `pm_consol_exit=840` with a consolidation classifier at 13:30, and no entries after it.
- **X13a:** Add `reverse_in_session`, a session-scoped lost_side and `loss_ends_morning`.
- **X14:** Umbrella.
- **X14a:** ~~Add `day_target_pts=5`.~~ **Owner #2: 5 handles is the minimum room, not the goal - `day_target_pts=0` (test switch, default OFF).** **[built 2026-10-18, owner directives; see build_log.md]**
- **X14b:** Add `chop_one_win` (shared _slow helper).
- **X14d:** Add `no_trade_after_win` (day-level, blocks SB/pre-open).
- **Ep04.13:** Add `done_if_target` (final level before 15:00 -> day done).
- **Ep07.5:** Add add_mode downclose and `tp_upclose`.
- **Ep07.7:** Run the body_low check on the fill bar and add a pending guard.

### day_week_context (49 items)

Owns: `day_context`, the day branches of `blocked()`, the weekly state in BT.run, and the study scripts. Build `adr5()` and `next_trading_day()` here first.

Medium:
- **B15:** Add org_tell tag/filter (no 50% attempt by 10:00) and `org_bias_gap`.
- **B16:** Add sunday_scenario tag/filter (futures only).
- **B17.4:** Add daily_range_regime tag/scalp/skip (range days, inside daily BISI, run into premium). **[partial 2026-10-18]** Owner #10 `sloppy_mode` (stand_aside / scalp / off=tag) with big_prev, chop and NFP-week tests [our interpretation]; default "off" (tag only) until the owner answers; the daily-BISI / premium-run tests are still open.
- **N7:** Umbrella for holidays.
- **N8:** Add the adr5 helper and switches for each N8 sub-rule.
- **N8.1:** Add `consol_skip` (range < 0.35 ADR5 and 4+ crosses of the midnight open; expansion resumes trading).
- **N8.2:** Add a trend_recipe tag/only/side (small ranges, react into an array, 08:30 news).
- **N8.4:** Add `big_day_am_skip` (big prior range or ORG -> AM off, PM kept), in run_day.
- **N9:** Umbrella.
- **N10:** Add monday_mode, tue_off_monday, mon_wed_extreme, the thu_reversal tag, friday_first_pool, friday_week_done and strong_thu_no_long.
- **M14:** Add `tgif_model` with sub-switches.
- **M14.1:** Add `tgif_htf_array` (the week's extreme touched a D/W/4h array or NWOG/NDOG, Sunday 18:00 range).
- **X10d:** Add `am_range_skip_pm` (AM range >= k x ADR5 -> done PM and SB_PM).
- **X15:** Sort by entry time before truncating. Add the weekly cap to paper.py.
- **X15d:** Add `week_done_on_draw` (all-hours prior-week H/L or NWOG CE).

Low:
- **B11:** Add inside_week (scalp), outside_day_rule, nr3/nr7/inside_bar_body and nr_expansion.
- **B11b:** Add `outside_day_rule` (block longs until the outside day's high trades).
- **B11c:** Add b11_inside_expansion and b11_inside_week.
- **B23:** Add `seasonal_tag` (month map, htf agreement, fail after day 10, optional samples), reported only.
- **N7.1:** Add `skip_holiday_eve` and EARLY_CLOSE flattening.
- **N7.2:** Add `skip_post_holiday_am=True`, `post_holiday_pm_sync`, week_day_index and the wed_reversal tag.
- **N7.3:** Add a holiday_week tag and `holiday_week_thu_fri`.
- **N7.4:** Add year_end skip/inside and `year_first_am_from`. **[partial 2026-10-18]** `year_end` (default "off" until the owner confirms the December mapping; tags year_end / year_end_inside); `year_first_am_from` still open.
- **N7.5:** Add an independent roll tag, roll_risk and skip_roll_week.
- **N7.6:** Add `august_risk`, `august_from_day` and `skip_august`.
- **N8.3:** Add `consol_day_rules` (predictors, small-OR AM, out by 11:00, PM only if the AM stop pool is intact).
- **N8.5:** Add an expansion_due tag, `expansion_targets` and `adr_basis`.
- **N8.6:** Add `sd_no_hold`, `sd_week_skip` and `sd_context_required`.
- **N9.2:** Add eve_draw columns and `pre_draw_pm` (gate in run_day).
- **N9.3:** Add `objective_done_skip` (draw hit before 12:00 -> PM done) in the bar loop.
- **N9.4:** Add `min_on_range_frac` and `min_raid_pts`.
- **N9.5:** Add `macro_no_move` and `macro_no_move_pm`.
- **N9.6:** Add `london_adr_skip=0.8` (range computed in the context builder).
- **N10.2:** Add monday_mode trade/skip/pm_only/obvious and `tue_off_monday`.
- **N10.3:** Add `pool_mon_wed`, mw_break tags, `thu_fri_break` and a thu_reversal tag.
- **N10.4:** Add `friday_slow_split=True`, `friday_objective` and `no_fri_after_strong_thu`.
- **M14.3:** Add `tgif_timing` (10:00-12:00 and 13:30-15:00) and `tgif_week_sweep`.
- **T14:** Add a `study_week.py` weekly-extreme study, then a `tue_week_extreme` switch if it holds.
- **X16:** Add tags adr5_prev, adr5_today, prev3_taken and entry_array_tf, plus a weekly study.
- **X16a:** Add an adr5 helper and the adr_prev/adr_fill fields, plus a day_ranges CSV.
- **X16b:** Add a taken_3d tag.
- **X16c:** Add `weekly_extremes()` (kill-zone labels).
- **X16d:** Add an entry_tf_tag.
- **D19:** Add a week_left budget across the engine/SB/Ma Deuce, a paper.py cap and `be_counts_as_win`.
- **D20:** Add monday_mode and `monday_small_range`.
- **Ep01.8:** Add `low_vol_inside` (last trading day; optional holiday-adjacent days).
- **Ep01.9:** ~~Add `year_end_long`.~~ **Owner #3: the side comes from December's direction (`year_end="december"`, `year_end_map` squaring/with - OWNER MUST CONFIRM the mapping); the old always-long is `year_end="long"`. Built as switches, default OFF pending the owner's answer.**
- **Ep02.7:** Add `first_day_wait` set later than 10:00, or first_day_skip_am.
- **Ep03.24:** Add `t1_fixed_pts` (+5 first rung) and t1_fixed_all. **Owner #2: test switches only, default OFF (5 handles = minimum room, not the goal).** **[built 2026-10-18, owner directives; see build_log.md]**

### news_calendar_times (31 items)

Owns: `calendar.py` events, the news branches of `blocked()`, and the run_day session windows. Merge before day_week_context.

Medium:
- **N1:** Add `nfp_no_adds=True` and `nfp_first_hour=True` (skip PRE9; Ma Deuce off on jobs days). Add an nfp tag.
- **N3:** Add `fomc_flat_before`, `fomc_eve_risk`, `fomc_after_am_block`, `fomc_only_am` and `fomc_no_reentry`.
- **N3.1:** Add `fomc_observe` (scan during 14:00-14:45, defer the order, Judas side), `fomc_pm_block_from`, and an SB check at max(a, fomc_pm_from).
- **N5:** Add the 2019-2025 calendar (PCE/GDP/retail/JOLTS/CB), NEWS_0945 and `release_times()`.
- **N5.1:** ~~Add `news_wait_min=30` (default on) in all models~~ **Owner #4: the 30-minute wait is NFP-only (`nfp_floor_min=30`); after every release wait for the news dealing range (`news_wait="range"`, default); the fixed wait is `news_wait="fixed"` with `news_wait_min=30` (065B), a switch.** `news_room_pts` still open. **[built 2026-10-18, owner directives; see build_log.md]**
- **N5.2:** Add the NEWS_0945 set and `news_0945` start at 09:45. **[built 2026-10-18, owner directives; see build_log.md]** `calendar.NEWS_0945` (PMI on ISM days), `release_times()`; the 09:45 release drives the AM range wait.
- **T4:** Add `or_no_entry` (fills from 10:00, expiry anchored at 10:00), `or_deep` (09:37-09:46), `or_bias` and `or_wide`.
- **T5:** Add `pre_0820` (a PRE8 window with a 500 snapshot, skipped on 08:30 days).
- **T8:** Add a `lunch` session (710-810, no look-ahead AM H/L), `pm_carry_draw` and `draw_done_skip`.
- **M9:** Add `news_judas` (first post-release run blocks that direction).
- **M9.1:** Add news_judas with pre-release reference pools and no entries before the first run.
- **D1:** Add `or_no_entry`, `or_no_entry_news1000` and `or_deep_pd`.
- **D8:** Add `nfp_day_from`, `skip_post_fomc_am`, `nfp_no_adds` and `fomc_no_reentry`.
- **Ep01.10:** Add `am_from_0830` (a 510 snapshot, no double scan).

Low:
- **N3.2:** Add `fomc_flat=840` (default on) and fomc_am open/recipe/skip.
- **N3.3:** Add a fomc_only tag and fomc_only_am consolidation/skip.
- **N3.4:** Add `pre_fomc_risk` (compounded with re-entry) and `skip_post_fomc_am`. Fix _split's holiday handling.
- **N3.5:** Add `fomc_no_reentry=True` (all done keys, skip reentry_half).
- **N4:** Add pre_cpi skip/small. Generalize the 08:29 flat to Ma Deuce and sb_london.
- **N5.4:** Add `skip_two_drivers` and the minimal no-trading-ahead-of-the-second-release rule. Add tags.
- **N5.5:** Add a FED_CHAIR calendar and `fed_chair_skip_am=True`.
- **N5.6:** Add an AUCTIONS list and `skip_auction_am`.
- **T7:** Add a 13:39 macro, multi-tag support, `macro_gate`, `macro_done_skip` and `moc_htf_done`.
- **T9:** Add `pm_skip_after=870`, `pm_bad_am_start`, `pm_continue_am` and `pm_ob_entry`.
- **M9.2:** Add `fomc_judas` (a 14:00-14:25 range, fomc_pm_from 865) and `fomc_stage2_cont`.
- **D9:** Add skip_pre_cpi skip/small with next_trading_day.
- **Ep01.11:** ~~Add `pm_setup_window` (detect 15:15-15:45, fills until 15:50).~~ **Owner #1: entries 15:00-15:50 (`last_hour=(900,950)`), 15:15-15:45 = sweet-spot tag `lh_sweet`; `last_hour_strict` switch; PM session 13:30-16:15 (futures flatten 16:15).** **[built 2026-10-18, owner directives; see build_log.md]**
- **Ep02.1:** Add the 'pmi' event set and `wait_0945=True`.
- **Ep06.1:** Add `london_kz` (a LON window, futures only), `london_kz_start` and `ny_kz_futures`.
- **Ep07.8:** Add macro_only 0950/all (start-or-arm test).

### silver_bullet (12 items)

Owns: `sb_model.py` only. Merge last.

Medium:
- **M3:** Umbrella: `sb_mss_required`, sb_fvg_pick, `sb_one_per_day`, sb_entry, sb_room_mode, sb_rebalance_ext, sb_mgmt layered057, sb_stop.
- **M3.2:** Add `sb_draw_first` (the 054 list with an HTF fallback). Apply `want` to run_sb.
- **D2:** Add `sb_fvg_in_window`, `sb_fvg_from` and `sb_evolve`. Honour mss_mode, mt_mode and entry consistently.

Low:
- **T6:** Add `sb_last_hour` (900-950) and `sb_0700` (with an 08:29 flat).
- **L14g:** Merge conf/fvg targets in _arm. Add `sb_pw_pools=True`, `sb_ote_draw` and `sb_htf_fallback`.
- **M3.1:** Add sb_extra pm2/early.
- **M3.3:** Pass `want`, use_bias and weekly_bias into SB. Add `sb_need_mss`.
- **M3.5:** Add a sweep_depth tag, `sb_need_sweep` and sb_sweep_max_pts.
- **M3.8:** Add sb_stop 090/fvg2/entry_candle.
- **M3.9:** Add `sb_one_market` and `sb_cascade`. Fix combine's session key.
- **M3.10:** Add `sb_rebalance_ext` (A7 rebalance in the 10-11 window -> extended target).
- **M3.11:** Add sb_mgmt gap424 and `sb_runner_if_weekly`.

### Shared pieces to build first (cross-package)

| Helper | Owner | Used by | Status |
|---|---|---|---|
| `breaker_zone()` (A13) | levels_detectors | setups (M4.x, A14), entries (A13.4, Ep05.5), targets (A22, L13), exits (A13.3) | **built** (`levels.breaker_zone`, `breaker_mt`) |
| VI wiring (`vi_arrays`, VI rows in C/H) | levels_detectors | targets (Ep03.22, Ep04.12), bias (B5, Ep03.12), entries (Ep07.2/4, E12b) | **built** (`vi_arrays`: confluence src 3 rows, htf "vi" arrays/draws) |
| `adr5()`, `next_trading_day()` | day_week_context | news (N3.4, D9), targets (L16), exits (X10d, X11c, X14b) | **built** (`strategy.adr5`, `calendar.next_trading_day`; `_split` now skips holidays) |
| Turtle-soup core (M12) | setups_models | M4.4, M12.x, D10, Ep08.15 | **built** (`levels.turtle_soup`; variants `turtle_soup` = 2023 / cc_limit / cc_1h_ob / or60 / external; M12.5 `ts_gate_mss`) |
| Level kinds carried into `pos` | targets_partials | exits (Ep03.15 be_on pool, X3a run-down) | **built** (`pos["level_kinds"]`) |
| Stateful bias column (`flip`) | bias_htf | B8a-f, B9, B13, B17.3 | **built** (`htf.table` column `flip`; daily triggers ob_mt / flip_pd3 / wk_dc / flip_close_above / flip_thu_wopen via `flip_triggers`; B8f = engine switch `stop_flip`). Was partial until the 2026-10-18 review pass |


## 4. Owner-directive build (2026-10-18)

The 14 owner corrections (`owner_directive_specs.md`), the verified bugs M1.2 / M7.1 and the shared
helpers were built on branch `mentorship`; `build_log.md` lists every item with its switches and
defaults. Status changes against section 2 (all behind Params switches; owner versions are the
defaults except #3 year end and #10 sloppy days, which wait for the owner's answer):

| Id | New status | Note |
|---|---|---|
| T9, T10, T11, Ep01.10, Ep01.11, Ep08.6, M5.2 | FULL | owner #1: last hour 15:00-15:50, sweet-spot tag, 16:15 futures close |
| L15, M3.6, X14a, Ep03.24 | FULL | owner #2: 5 = minimum room; `t1_fixed_pts`, `day_target_pts` switches (off) |
| Ep01.9, N7.4 | SIMPLIFIED | owner #3 built as a switch, default off (mapping pending) |
| N5, N5.1, N5.2, Ep04.5, Ep02.1 | FULL | owner #4: news dealing range wait (formation test [our interpretation]) |
| A14, M4.2 (direction) | FULL | owner #5: unicorn both ways, `unicorn_side` tag, `unicorn_sides` switch |
| A13.3, Ep02.3, Ep05.1 (MT) | FULL | owner #6: breaker-MT respect / entry floor / cancel / exit |
| Ep02.10 (new), L9, X3f | FULL | owner #7: opposing HTF FVG caps the trade |
| X10, X10a, Ep03.23, D16 | FULL | owner #8: close at 12:00, now SB-AM, London SB and Ma Deuce too |
| B3, L14a, M0.1, M3.2, Ep01.14 | FULL | owner #9: lock one draw per session (nearest pick [our interpretation]). Review pass: was effectively SIMPLIFIED (frozen rungs always empty; lunch / AM highs never a PM lock) - both fixed and tested; OWNER QUESTION on #7 x #9 (cap replaces the draw in most trades, `lock_capped`) |
| B17.4, N8.1, Ep08.2 | SIMPLIFIED | owner #10 built as a switch, default tag-only (pending) |
| M1.4, D10, Ep07.2, Ep07.5 | FULL | owner #11: OB-bodies entry before the break is the default. D10's turtle half: variants built in the review pass (M12 rows) |
| A14, A13.3, D6 under the default entry | NOTE | #5 / #6 / #14 act only on the FVG path (`ob_entry="post_mss"` or `"both"`); with the default `pre_break` no trade uses the breaker / unicorn (owner question in owner_directives.md) |
| E8, E11 | FULL | owner #12: 1.2% / 1.3% |
| DATA1 (new), Ep02.2 (round pools), N7.5 (hook) | FULL / SIMPLIFIED | owner #13: front-month frame, round pools on futures |
| D6, A13, A13.2 | FULL | owner #14: full-range breaker default, shared helper; review pass: `breaker_zone` "leg" (070) and "last" (cc05_014) built |
| M1.2 | FULL | intact() fix + `displacement_mult` |
| M7.1 | FULL | `seen_from_created` fix + `pm_off_lunch`, `pm_judas_1330` |
| M12, M12.1, M12.3, M12.4, M12.5 | FULL | review pass: `turtle_soup` 2023 (limit at the PD array top, stop at the array / a gap - M12.1 wording), cc_limit, cc_1h_ob (1R / BE 2R / 5R), or60, external; `ts_gate_mss` (bar mechanics [our interpretation]; all off) |
| M12.2 | SIMPLIFIED | short at an old high: no turtle-specific breaker adds (unchanged) |
| B8, B8a-B8f | FULL | review pass: all five daily flip triggers in the `flip` column + `stop_flip` (B8f) |
| B17.4 | SIMPLIFIED | owner #10 still tag-only by default; premium_run / inside_bisi / fomc_week tests built (opt-in) |
| L17 | FULL | review pass: `round_step_pts` on the shared front-month mapping (off) |
| M3.10 | FULL | review pass: `sb_rebalance_ext` (A7 immediate rebalance in the SB window -> extended draw; off) |
| DATA1 roll_kind="calendar" / roll_spread | MISSING | needs paid ES.c.0 data - owner go-ahead |
| B21, L3 | FULL | levels_detectors: `ipda_pools`, `ipda_next`, `ipda_eq_day` (61-session history), `or_extra`, `pw_pm_full_session` (all off) |
| A1 | FULL | `levels.swing_tiers`, `mss_ref` / `mss_ref_fallback` (default stl / lower = old); rulebook pivot_n note fixed |
| A2 | FULL | `sweep_ticks=1.0` (spec default: 1 tick through to book a level, in the sweep, intact, SMT, seen filter and SB tag), `sb_draw_pools_only` |
| A5 | FULL | `fvg_c2_dir=True` (spec default) + quadrants, VI extension, skip-above-pool, HTF CE draw, upper-quarter hold, state tag / filter, keep-filled (off) |
| B1 | FULL | `vi_targets`, `wick_days`, `no_draw` / `skip_no_draw` (off) |
| L1, M0.2 | FULL | `am_range_end`, `prev_am_pool`, `session_priority`, `org_pools` (off) |
| L2, Ep08.10 | FULL | `daily_level_needs_array` / `_flow`, `pd_hl_session="eth"` / `matrix_full`, `pool_today_hl`, `matrix_days="ict"` (m3h / m3l) (off) |
| L5, D21, M2.1 | FULL | `gap_quarters`, `nwog_quarters`, `nwog_skip_holiday`, `nwog_halfway`, `gap_run_stop`, `nwog_trading_days` (fix, on), `monday_ce`, `org_sweep`, `pool_gaps` / `gap_pool_edge` |
| L7 | FULL | ORG history max(org_days,5)+1, `org_close` per symbol (0 = auto), `org_draw`, `org_half_draw`, `org_q_hold` |
| L10, A23 (levels part), Ep08.1 | FULL | `wick_days`, `wick_weekly`, `wick_both`, `wick_session`, `wick_invalidate`, `wick_partial`, `wick_react`, `daily_fvg_exact`; default doc mismatch fixed (wick_levels ON) |
| T2 | FULL | `release_open`, `release_open_stop`, `bias_open` |
| Ep01.5, Ep02.9 | FULL | `breakaway` tag / hold / next_fvg (first FVG after the MSS) |
| Ep01.6, A13.1, A13.4 (shared), A13.5, Ep05.1 | FULL | `breaker_ll`, `breaker_cand_to`, `breaker_entry` (fallback / prefer), `breaker_time`, `breaker_levels` |
| Ep02.8, Ep03.3, A9 | FULL | `vi_news_draw`, `vi_body_death`, `vi_min_gap_pts`, `vi_stop`, `vi_porous_n`, `vi_htf_draw` |
| Ep06.7, A3 | FULL | `eq_pref` (kind pool_eq), `eq_bodies`, `eq_rank` |
| A7 | FULL | `levels.immediate_rebalances`, `imm_rebalance_disp`, Trade.imm_rebal, open_to_pdh / pdl tag |
| A11, Ep01.4 | FULL | `bpr_max_gap_bars`, `bpr_targets`, `bpr_abort`, `bpr_rule` |
| A15 | FULL | swing order fixed (legacy switch in levels), `mit_targets`, `mit_body_respect` |
| D6 | FULL | `unicorn_pref` added (leg / last / errors built earlier) |
| L8 | FULL | `levels.vacuum_block`, `vacuum_blocks` |

### setups_models package (2026-10-18)

Built on branch `mentorship` (`mentorship/setups.py` + hooks; `build_log.md` "Package setups_models"
lists every item with its switches). All new switches are off; with all of them off the engine's
trades are identical to the commit before. FVG-path switches act with `ob_entry="post_mss"` / `"both"`.

| Id | New status | Note |
|---|---|---|
| A19, A19.2, A19.4, A20, M0.4, Ep07.6, Ep08.4, Ep08.16, Ep04.7, Ep01.22 | FULL | MSS reference parent / origin / SIBI / higher-tf, eq wait, on-side tag / require, displacement tests (also in the SB), speed, clean leg |
| M0, M0.5, M1, M1.1, M1.3, M2, M2.3, M2.7, M13 | FULL | candle draw, entry arrays, MM context, speed check, 2022 pick / stops / add cut / target, three drives, OTE |
| M4, M4.1, M4.2, M4.4, M4.5, A14, A18, A24.2, Ep05.4, Ep05.8 | FULL | classic breaker, unicorn rules / only / open / overlap, adds (VI, in breaker, retest), turtle-breaker pyramid, CC breaker / failure swing, reclaimed OB, Reaper, MMXM |
| M4.3, M5.1, A24, T13 | SIMPLIFIED | advanced breaker without the pre-break A-B entry; Ep 01 last hour with the generic adds / trail; implied FVG / inducement not codeable; profiles = expected profile from D / 4h |
| M5, M5.2, M6, M7, M7.2, M7.3, T10, Ep01.13, Ep01.16, Ep01.17 | FULL | own last-hour slot, 2022 model in 15:15-15:45, PM reversal, lunch target / ORG, 13:30 Judas into an array, MOC run / pool exit, 4h CE hold, started by 15:25 |
| M10, A8, M11, M11a, M11b, M11c | FULL | IFVG entry / stop / depth / hold / 061 / after HTF; IR, CISD OB and wick-CE entries |
| M12, M12.2, Ep08.15 | FULL | turtle soup order flow, breaker adds, max run |
| M16, M16.1, M16.2, Ep03.11, B18, B18.1, B18.2 | FULL | SMT stop / turtle entry (ES only, 05:00 low, 11:00 exit), sick sister, leader / laggard pick, SMT gap / array / rel-eq twin / windows |
| N6, Ep04.3, Ep04.4, Ep01.15, M15 | FULL | news profile / CE / no unicorn; Judas required, runner, bias, inclusive; nested FVGs; Ma Deuce big candle / 2nd entry / ladder / news / ETH / blocked |
| Ep05.6 | SIMPLIFIED | study variant only (one observation) |

### setups_models review pass (2026-10-18)

Review fixes and the items the first build left partial (`build_log.md` "setups_models review
fixes" has the switches, the per-variant ES trade counts and the items still unverified on real
data).

| Id | New status | Note |
|---|---|---|
| M4.3 | FULL | `adv_breaker_pre`: with the bias on side, the first close back above A after the run below it enters at market (stop beyond L2, target B + 1x(B-A)) [our interpretation of the trigger] |
| M5.1 | FULL | `pm_ep01_adds`: the Ep 01 sequence (add in the FVG at its CE, in the breakaway gap with the stop moved below its bodies, on a breaker) and the trail under each new FVG's bodies; owner #1 window 15:00-15:50; nested 1h/4h pairs; fires on the Ep 01 day (ES 2022-12-30, long ~15:20) |
| A24 / A24.1 | FULL | `implied_fvg`: wick-CE to wick-CE across a displacement candle whose outer wicks overlap (035 ~29:46, named once) [our interpretation]; inducement = the sweep step (A24.3) |
| T13 | FULL | `cc_profile` ("tag" / "gate"): the six CC index profiles classified at 13:30 from the AM leg, an opposing 4h / D array at the AM extreme, no news after 10:00 + a small AM range, NFP = seek and destroy [our interpretation of the classification]; consolidation profiles out by 14:00 |
| Ep05.8 | FULL | `mmxm_rel_eq` (the sweep must be of relative equal lows / highs); the CE exit now reuses the ce_hold rule |
| A19, A19.2, A20, M0.4, M1.3, Ep07.6, Ep08.4, Ep08.16, Ep01.22 | FULL | under the owner #11 default (OB order before the break) the MSS gates act through `ob_pre_gate` ("cancel" default / "hold"); Ep08.4 "origin" anchored at the sweep extreme (`leg_origin`), the first rule kept as "origin_max" |
| Ep05.6 | SIMPLIFIED | study variant only, by spec |


## 5. targets_partials build (2026-10-18)

Owner #7 REVISED is the default: an opposing HTF FVG between price and the draw is a SPEED BUMP (a protected
partial at its near edge, the rest stays for the draw; `htf_resist_mode="bump"`). The first build (the cap) and the
timeframe split stay as `htf_resist_mode="cap"` / `"split"`. Status changes against section 2 (all behind Params
switches, default off unless the owner directive makes it the default):

| Id | New status | Note |
|---|---|---|
| Ep02.10, L9, Ep02.5 | FULL | owner #7 revised: speed bump default (a small protected partial `htf_bump_frac`, `htf_bump_max=1`, `htf_bump_below_min`); `htf_resist_mode`, `htf_resist_cap_tfs` |
| X3, X3a, X3c, X3d, X3h, Ep03.19, Ep04.12 | FULL | rung planner: `run_down`, `ladder_all_pools`, `ladder_max_levels`, `wick_partials`, `sd_half_partial`, `halfway_partial`, `capture_frac`, `mgmt="unit"`, `target_order`, `ladder_news_day`; `Trade.capture`, `Trade.rungs` |
| X3f | FULL | `resistance_mode` (low_full yields to any speed bump / wick / SD partial) |
| X3g | FULL (review fix 2026-10-18) | `smt_bank` (50%, the sister refuses a new high) and `smt_bank_against_frac` (0.8: the sister breaks against the trade) |
| A6, Ep03.5, L13, Ep08.9 | FULL | `measuring_gap`, `measuring_target` / `measuring_anchor`, `trail_breakaway`, `proj_*`, `mm_targets` |
| L12, D23, Ep06.4 | PARTIAL (the "time" alignment of `sd_align` not coded: no rule gives a clock) | `sd_anchor` leg / broken / downleg / fulcrum / london / multi, `sd_cluster_ticks`, `sd_roles`, `sd_align`, `sd_no_pool_fallback`, `sd_close_hit` |
| A22, L9, L14d, A10, A17, L11, A23, X1, Ep01.21, Ep03.22, M8, L16 | FULL | array / pool target sources and filters |
| M14.2, M14.4 | FULL | `tgif_zone`, `tgif_exits` |
| L4 | PARTIAL | `pool_rank`, `draw_below_eq` act under the lock; `lrlr_max`, `rel_tfs`, `clean_eq_pref` only with `draw_lock="off"`; NOT built: hrlr_time_k, clear_path, hrlr_news_only, resist_def, session_pool_first, eq_beyond_imb |
| Ep04.11, Ep07.1 | FULL (clean_eq only without the #9 lock) | `pool_rank`, `rel_tfs`, `draw_below_eq`, `lrlr_max`, `clean_eq_pref`, `pool_runner_pts`, `close_draw` |
| X3b | PARTIAL | SB uses `_split` (`sb_split`) and a slow_frac study; MISSING: JOLTS release dates before 2026 (no verifiable source, none invented) |


## 6. management_exits build (2026-10-18)

Mid-trade management, session / day stops and the add rules (`mentorship/manage.py` + hooks; `build_log.md` "Package management_exits" lists every
item with its switches and notes). All new switches are off except T11 `late_cutoff=945` (spec: default on) and the bug-fix switches
`add_leg_at_fill` / `ep07_body_fixes` (act only when the rule they fix is on). With `late_cutoff=0` the trades of the commit before are identical.
Status changes against section 2:

| Id | New status | Note |
|---|---|---|
| M2.6 | FULL (add_cutoff itself stays 0: two readings of the "25% line") | `add_in_pd`, `add_leg_at_fill`, `pool_size_rank` (+ `add_cutoff`, `add_cutoff_read`, `add_cut_ref`) |
| X4 | FULL | `be_pad_pts`, `be_cost_pad`; the Silver Bullet follows `be_on` |
| X5, X5a, Ep03.10, Ep03.15, Ep03.20, D14 | FULL | `ladder_trail` fvg / hit / prior / measuring / breakaway / off, `trail_after`, `trail_first_fvg`, `first_fvg_fail`, `trail_pad_pts`, `be_on` after_mss / stall / pool / off |
| X5c | FULL | `trade_type="day"`, `day_stop` (08:30 open / wick CE; futures only) |
| X6 | FULL | `fvg_abort_mode="rule"` (5m close arms, only the next 5m candle confirms, the arm is cleared), `fvg_abort_tf`, `fvg_abort_body`; "legacy" = first build |
| X7, X7a, X7b, X7c | FULL | `pd3_exit` + `pd3_n` / `pd3_list` / `pd3_dynamic` (fixed list at the fill, `pd3_warn` tag), `pd3_half`, `session_stop_after_fails` (+ `session_fail_mode`; SB / Ma Deuce share it) |
| X8, X8b, X8c, X8d, X8e, X8g | FULL | `leg_mt_exit`, `ir_eq_exit`, `prop_exit`, `offside_exit` (X8e is [our interpretation]), `meander_bars` |
| X9, X9a, X9c, X9d | FULL | `time_stop_ref` / `time_stop_bars` / `time_stop_frac` (also SB and Ma Deuce), `far_edge_min` / `far_edge_frac` |
| X10, X10b, X10c | FULL | `am_bulk_t` / `am_bulk_frac`, `smt_hold_until` / `smt_hold_exit` (X10d = day_week_context) |
| X11, X11c | FULL | `pm_consol_exit` (13:30 cc_profile classifier, no entries after it) |
| X12 | FULL | `obj_stop`, `obj_source` (draw / htf_ce), day stop for every setup |
| X13, X13a, X13b, D18 | FULL | `reverse_in_session`, `lost_side_session`, `loss_ends_morning`, `reentry_gate`, `reentry_fomc_ok`, `reentry_risk`, `reentry_lock_r`, `reentry_target_r` |
| X14, X14b, X14d, Ep04.13 | FULL | `chop_one_win`, `no_trade_after_win`, `done_if_target` |
| Ep07.5, Ep07.7, T11 | FULL | `add_mode="downclose"`, `tp_upclose`; `ep07_body_fixes`; `late_cutoff` |
| B18.3 | PARTIAL | `smt_bias` (the previous-day high / low SMT in the overnight range, [our interpretation]), `smt_exit_against`; the partials are X3g, the instrument pick is `smt_pick`; `smt_exit` stays the M16.1 time exit |
| A13.3 | FULL | built earlier (owner #6: `breaker_zone="leg"`, `breaker_mt_*`) |
