# results.md — every backtest and audit result

Append new results at the top of "Latest" with date, commit, runner, $ at $1k risk, halves (2019-22 / 2023-26), trade count. Report $ not avg R.

## Latest (from the old MEMORY.md index)
- Live status: see the index NOW line (INDEX.md). Results below are append-only. Backtests run on commit 229c1a5 (study.main_decisions, MENTORSHIP_SRC=databento); full list 2,543 variants x 8 yrs (~1,000 h at 3 min/job) is too big, hence the screening plan in decisions.md. Threads: threads.md.
- Not built yet: fx_nonconf_exit (needs EURUSD/GBPUSD), dxy_smt no_press, udx_shape, weekly-OB-open ladder level.
- ES 5m 2019-22 only ~169 trades, all variants lose ~-$5.6k.
- Silver Bullet paper bot stopped 2026-11-01 morning; Mase told how to restart (sign out/in).
- Cloud baseline 2026-10-31 (pre-owner-answer build): ES 5m 413 trades -$141k, 1m 1,082 trades -$363k at $1k risk.
- POST-BUILD 5m ES baseline on 3fb9cd1: 413 trades, -$140k, 24% wins.
- Swing version: DONE, no consistent edge; PR #1 CLOSED unmerged 2026-11-01 (branch kept). Only lead: OSOK ES without premium/discount limit.
- Cloud backtesting: PR #2 merged. Shards the version list across laptop and cloud on one mentorship commit; results to backtest-results branch; cloud thread merges summary into shared folder. Backtest on BOTH laptop and cloud (Mase 2026-10-29). Code: private repo https://github.com/masonberger4/bottrading.

# Detailed memory files moved here verbatim (one section each)

## mentorship-backtest-results — Latest trustworthy Mentorship bot backtest numbers (futures data, corrected ICT definitions), 1-minute and combined 5m+1m modes
(source: mentorship-backtest-results.md, modified 2026-10-18T02:01:07.097Z)

Setup for all rows: Databento ES signals, SPY P&L at $1k risk per trade, Jan 2019 to Oct 16 2026, corrected definitions (10-17 audit) plus the six added concepts. Earlier numbers on old definitions or HistData are superseded. 5m results: /mnt/project-files/mentorship/results_5min_futures.md (see [[mentorship-bot]]).

First 1m results (reported to Mase 2026-10-18 ~01:50 UTC):
- Today's bot (pre-week rules): 1,108 trades, -$44.9k, lost all 8 years.
- Recommended defaults: 363 trades, -$4.8k (2019-22 -$0.5k; 2023-26 -$4.4k).
- 5m FVG/OB zone entered after the 1m shift (Ep 03/08): 157 trades, -$4.2k (2019-22 -$12.3k; 2023-26 +$8.1k on 79 trades; 5 of 8 years profitable).
- 1m FVG nested in a 5m FVG/OB (Ep 01): 126 trades, -$2.5k (-$2.6k; +$0.1k).
Combined 5m+1m loses less than 1m alone; nothing is profitable in both halves yet.

Re-plan 2026-10-18 ~02:15 UTC: all 8 new pieces committed (39/39 tests). HTF targets now ON in defaults (RC choice; off kept as a comparison), SMT stays a label. Old 1m run stopped at 109/352 (outdated defaults). Now: 5m run of new defaults + new pieces (~2-3h), then top-25 variants on 1m (~12-15h). RC misread Mase's "1 and 2 but not 3" and dropped the extra SB trade from the queue; Mase was given a correction line to restore it, add week/month H-L and short-term swing liquidity, research pre-9:30 entries, and test 4/5/12-week NWOG lookbacks.

Silver Bullet full-run results and diagnosis: [[mentorship-silver-bullet-results]]. Main AM/PM model, experienced defaults, SB off (1m 2019-26): 323 trades +$4.6k (+$5.6k/-$1.1k), PM 14-15 +$10.2k on 88, AM -$4.6k; only positive full-period result so far.

2026-10-18 ~03:00 UTC: CE exit OFF by default (switch ce_hold, per Ep 04); new off-by-default switches ep07_stop, ep07_body_exit, ep07_trail, htf_far_edge. Comparison restarted on these defaults (SB on, experienced rules): 1m core first (defaults, SB off/only/10-handle/runner, beginner rules, original bot, 5m+1m entries), then ~65 variants on 5m, then key ones on 1m.

Pre-09:30 test switches (2026-10-18 ~03:20 UTC, off by default): pre_0700 (07:00-08:30, flat before 08:30 on release days), pre_0900 (09:00-09:29), post_news (08:30 days, wait 30 min, sweep of 08:30-09:00 range), ma_deuce (091; stop is RC inference). Building them found and fixed a look-ahead: overnight H/L and same-day ORG used bars up to 09:30 for pre-open trades (09:30+ setups unaffected). First look: 0-1 trades per switch Q1 2024; Ma Deuce 18 trades 2022-24 -$17.9k.

Still pending: the rest of the 352-run 1m comparison; tests of the 8 new pieces (SMT, HTF targets, SB setup, top-down, day/week templates, 3-PD-array exit + SD partials, Judas tag, DXY/yield labels) vs defaults on 5m then 1m; the walk-forward pick on 2019-22 checked on 2023-26; results by day type ([[day-type-aware-strategies]]).

**Why:** later sessions need the current baseline without re-running.
**How to apply:** compare new results against these rows; report in $ and by both halves.

## mentorship-silver-bullet-results — How ICT's Silver Bullet, built as its own setup in the Mentorship bot, did on 1-minute ES 2019-2026, why it loses, and which filters are proposed next
(source: mentorship-silver-bullet-results.md)

ICT Silver Bullet (built 02:40 UTC as own setup, on by default). FULL 1m 2019-26 (04:30 UTC, 49/72 core runs): SB alone 2,020 trades, 46% win, -$37.6k (2019-22 -$30.7k, 2023-26 -$6.9k; AM -$34.7k, PM -$3.0k); 10-handle room 1,511 trades -$7.6k (+$0.7k/-$8.3k); runner -$36.6k. The Q1 2024 +$20.8k was a lucky quarter. Main AM/PM model, experienced defaults, SB off: 323 trades +$4.6k (+$5.6k/-$1.1k), PM 14-15 +$10.2k on 88, AM -$4.6k. Defaults with SB -$33.0k; original bot -$83.3k. SB diagnosis (04:40 UTC): not the stop. Symmetric 5/5 stop-target = exactly 50% win (no directional info); tighter stops worse, 15-pt stop barely +0.3 pt; gross -$7k, costs -$30k; daily-bias agreement, prior sweep (worse) and weekday = noise. Gap vs ICT: he picks one direction per day from narrative before 10:00; skips spotty/out-of-sync days; uses 15-30s charts; examples hand-picked. Proposed switches: one direction/day toward nearest untaken daily/weekly draw, displacement >=1.5x avg 1m range, ES/NQ/YM agreement, 10-pt room; SB off by default. Mase given one line to send. Pre-09:30 switches were committed before the suite finished (7 trade-ordering failures, fixed, suite rerunning).

**Why:** Mase believes the Silver Bullet works because ICT shows it working; later sessions need the evidence that the coded version is a coin flip and why.
**How to apply:** don't re-test stop placement as the fix; test direction/day-selection filters. Related: [[mentorship-backtest-results]], [[mentorship-ict-research-findings]], [[silver-bullet-bot]].

## swing-version — Swing version of the ICT bot - spec, models built, results, PARKED status (2026-10-20), PR #1
(source: swing-version.md, modified 2026-10-20T07:26:14.591Z)

Started 2026-10-18 in the "Swing version" thread. Spec: /mnt/project-files/swing/spec.md. Results: /mnt/project-files/swing/results_osok_v1.md.
Code: package `swing/` on branch claude/swing-version-hek2c9, PR #1 into mentorship (https://github.com/masonberger4/bottrading/pull/1). Imports mentorship.levels/calendar, never edits them. Built: Month 7 OSOK (default), Month 6 swing (`--model swing`), stop_tf switch. Month 5 position model NOT coded.
Findings: no consistent edge on ES/NQ/YM in any variant, including ICT-style stops. Only NQ Month 6 positive in both halves (+7.8k).
Open ICT conflicts, defaults picked: position stop tightens 40->20 day at 75% (alt 50%); no longs above 0.5 of range (alt 0.8).
**Status: PARKED (Mase 2026-10-20). Mase 2026-10-21 06:17 UTC: "Retest this once the engine is fully built" - re-run ES/NQ/YM OSOK + Month 6 after the mentorship build (stages 9-10, sb-build merge) is on GitHub; ask the coordinator or check mentorship commits. PR #1 review skipped for now.

## mentorship-rule-coverage — Result of the full audit of every Mentorship bot rule against the code (how many are full, simplified, missing), bugs found, and the build package order
(source: mentorship-rule-coverage.md)

FULL AUDIT DONE (laptop workflow, ~05:45 UTC 2026-10-18; digests/rule_coverage.md, committed): 473 sub-rules: 86 FULL, 248 SIMPLIFIED, 121 MISSING, 18 N/A. Weakest: HTF bias (B) 28/48 missing; all FOMC sub-rules incomplete. Verifier overturned 23 verdicts; bugs M1.2 (untouched-swing-low check starts at wrong bar, drops valid short-term lows as sweep pools) and M7.1 (lunch high never a target) to fix first. Packages (simplified+missing): setups 75, day/week 49, management/exits 46, HTF bias 45, entries/stops/sizing 45, detectors 36, targets/partials 36, news/calendar 31, SB 12. Merge order: detectors, setups, entries, targets, exits, news, day/week, bias, SB. 217-caption gaps get added before the build.

Cloud cross-check DONE (2026-10-18, /mnt/project-files/mentorship/full_detail_check_ep01-08.md, from Ep 01-08 captions vs bot as of 04:29 UTC): 280 merged rules, 9 full, 116 simplified, 120 missing, 15 conflicts, 15 unknown, 5 not possible. Mase given a 14-item line of rulebook errors (list in laptop digests/owner_directives.md). Mase SENT it (10:44 UTC). Laptop saved all 14 word-for-word with standing decisions in digests/owner_directives.md (owner directives beat the rulebook); a third workflow writes owner_directive_specs.md (Mase's version default, old behavior a switch). 217-caption check: 252 gap items in final verification. Build order: 14 directives + bugs M1.2/M7.1 first, then the packages. BUILD STARTED (~11:20 UTC): 10 stages in merge order, each build/adversarial review/fix/full tests (~25 min)/commit, logged in digests/build_log.md; 217-caption gaps in a follow-up pass. Open questions to Mase (laptop put both in as OFF switches): #3 year end = (a) AGAINST December's direction (Ep01 ~12:04: December down, shorts squared, price up; my original wording was ambiguous); #10 sloppy stand-aside only on days meeting the price-based definition, NFP-week Thu/FOMC week stay tradable per experienced rules (Ep03 caution is for students; Ep08 seasoned students walk away). Mase ANSWERED (16:22 UTC): #3 = (a) against December; #10 = stand aside only on days meeting the sloppy definition, NFP-week Thu/FOMC week tradable, calendar block a switch. Applied (~16:40): year-end default ON (Dec down = bullish into year end); sloppy (our interpretation) = yesterday range >2x 5-day avg, or morning range <0.35x 5-day avg with 4+ crossings of the midnight open. Stage 1 done+reviewed; stage 2 detectors (36) committed, in review. Stage 1 built (~12:00 UTC): directives 1,2,4-9,11-14 now defaults; #3/#10 OFF switches pending Mase. Far fewer trades, mostly from #7 (overhead HTF FVG caps target) and #9 (one locked draw per session). 217-caption check: >1,400 candidate gaps, hit 1,000-agent cap, resumed with 10 items per verifier; output digests/rulebook_gaps/.

217-caption check DONE (~19:00 UTC): 1,313 confirmed gaps (651 missing, 313 missing a condition, 169 shortened, 135 unlisted contradictions, 45 wrong) -> 1,081 build specs (digests/rulebook_gaps.md), built in a second pass after the 10 stages. Laptop misread directive #7 as "opposing HTF FVG in the path caps the trade" (cut trades); intended: Ep02 FVG BEHIND the trade (above price on a short, already traded through) = resistance/add zone, never a target. Mase SENT it (19:06): speed bump (partial at it, rest to the draw) is default for FVGs in the path; cap and 1h+-only cap are switches; FVG behind the trade = resistance/add zone, never a target. Bugs: NFP assumed Friday (2025-07-03 Thu); jobless claims and FOMC minutes missing from calendar; fixed in news stage.

**Why:** Mase asked (2026-10-18) why the bot does "simple versions" of ICT; this is the baseline for the full-detail build.
**How to apply:** report build progress against these counts; the 217-caption check adds gaps before the build. Related: [[mentorship-missing-concepts]], [[mentorship-standing-rules]], [[mentorship-scaling-rules]].

## coverage-audit-2026-10-31 — Result of the 2026-10-31 full ICT concept coverage audit (engine vs notes): rule level complete; gaps are calendars and parked data items
(source: coverage-audit-2026-10-31.md, modified 2026-10-31T01:21:09.792Z)

Full audit done 2026-10-31 on ed54858 (Opus thread "Find ICT concepts missing from engine"). File: /mnt/project-files/mentorship/coverage_gaps_2026-10-31.md.

- Rule level is complete: all 100 rule_coverage MISSING rules are built; 1,077 of 1,081 caption-gap specs have switches in code.
- Real gaps were in the 99 caption-gap items parked as "needs data / bonds / stocks" (COT, OI and macro dates came from here).
- BIGGEST GAP: calendar.py news dates cover 2019-2025 (+2026 via claude_hf); 2016-2018 has no NFP/CPI/PPI/FOMC/holidays, so news rules are silent on the new 2016-18 data. macro_risk_dates.csv (NFP/CPI/FOMC 2016-26) is not loaded by anything; the `macro_risk_dates` Param reads a different (week,direction) format.
- Also missing: PCE/GDP/retail/JOLTS 2016-25, Fed speakers, full auction list (all free data); symmetrical-market gate (9 cites, 2023); DXY 1h/daily rules; NDOG lifetime/size; COT extremes/blend/divergence.
- Paid-data cluster: intraday DXY 1m (11 items, most-cited 2023 gap); bond 1m; seconds bars.

- 01:11 UTC Mase approved gaps 1-3 + free DX 1m cost check. Done in cloud (01:45): 593 rows (PCE, GDP adv/2nd/3rd, retail, JOLTS 2016-2027; PPI 2016-18) added to macro_risk_dates.csv, each checked against ALFRED vintages (alfred.stlouisfed.org works with plain curl; BLS pages via WebFetch only). Build spec for the laptop: /mnt/project-files/mentorship/coverage_build_2026-10-31.md. Found: claude_hf.daytypes 2026 PCE dates after April are wrong. Fed speakers/auctions left out (coordinator scope).

**Why:** Mase worried concepts were still missing after the COT/OI/calendar finds.
**How to apply:** don't re-run a full audit; start from this file. Related: [[mentorship-rule-coverage]].

## silver-bullet-bot — Where the Silver Bullet Python bot + thinkScript live, how paper trading works, and what's still unverified (as of 2026-10-10)
(source: silver-bullet-bot.md, modified 2026-10-10T20:14:01.563Z)

Code lives in /mnt/project-files/silver-bullet/ (zip at /mnt/project-files/silver-bullet.zip). It's also on Mase's laptop as a local git repo at C:\Users\mason\bottrading: commit 8c40aa8 on 2026-10-11, with .venv set up and 9 tests passing, but no remote and no thinkScript file there yet. There's no GitHub repo. Built 2026-10-10 in the "Highly profitable stock trades" thread.

- The Python package `silver_bullet`: one bar-by-bar Strategy shared by the backtest and paper trading, PaperBroker (pessimistic fills), and SchwabBroker (SPY/QQQ bracket orders, dry-run by default, live needs `--live` plus SB_ALLOW_LIVE=1). There are 9 pytest rule tests.
- `thinkscript/SilverBullet_Strategy.ts` is for /MES charts in paperMoney. It was never compiled in TOS, so syntax errors are possible.
- Schwab API can't trade or chart futures and can't reach paperMoney, so "paper trading" = live Schwab SPY bars with locally simulated fills. Earlier project chat found the same and pointed at IBKR (ib_insync) for automated futures; see [[overview]].
- The cloud container blocks market-data hosts (Yahoo, Schwab, Databento), so real data has to be fetched on the laptop session (yfinance works there). A pure synthetic random walk gave PF ~0.9-1.0, so there's no lookahead.
- First real backtest (2026-10-14, yfinance MES=F, files in bottrading): 5-min over 59 days gave 19 trades, 63% win, +$116, PF 1.57. 1-min over 27 days gave 56 trades, 45% win, -$113, PF 0.84. London was positive in both runs and PM negative in both. Breakeven win rate is about 53%. The verdict needs 1+ year of paid 1-min data.
- Schwab app is created; the keys are set with setx on the laptop, and OAuth worked on 2026-10-15 (schwab_token.json is in bottrading and needs a re-login every 7 days). SPY 1-min backtest over 45 days (AM+PM, 100 shares): 52 trades, 42% win, -$95, PF 0.92. Longs -$304, shorts +$210. No edge shown in any test so far. Paper mode started 2026-10-15; warm-up bugs (skipped bars, warm-up using up a window) fixed in laptop commit 9cb9c41. Mase chose to keep SPY min_stop at 0.10 (ICT gives no minimum stop; stop = beyond displacement swing + 2 ticks).

**Why:** later threads shouldn't rebuild this or claim real backtest results exist.
**How to apply:** extend this package; real backtests need Mase's Schwab key run locally or a CSV of /MES 1-min bars.

2026-10-16: auto-start at Windows logon via Task Scheduler "Silver Bullet paper bot" -> bottrading\run_paper.ps1 (hidden, restarts bot if it exits; commit b9feba1). Network-failure retry fix 62f5dbc. Log: paper_log.txt. Weekly Schwab re-login: stop task, run `backtest --schwab --days 2`, log in, start task. First forward paper trade 2026-10-15 PM long +$50.

## imported/legacy-memory (original claude.ai project summary, Silver Bullet futures plan, pre-2026-10-10)

**Purpose & context**

Mase is building an automated futures trading algorithm based on the ICT "Silver Bullet" strategy. The project follows a deliberate three-phase pipeline: historical backtesting → paper trading → live trading, with one contract traded at a time. The goal is a fully automated system capable of executing trades without manual intervention.

Key platform constraints shaped the architecture: thinkorswim's native thinkScript cannot execute live trades automatically, and the Schwab Trader API does not support futures order entry or historical futures data. These blockers ruled out the initially considered stack and redirected the project toward Interactive Brokers (via `ib_insync`) for paper and live trading execution.

**Current state**

Two working artifacts have been produced:

- **thinkScript strategy file** — for thinkorswim chart-based visual backtesting and validation
- **`silver_bullet_backtester.py`** — a broker-agnostic Python backtester that accepts any OHLCV DataFrame and applies the full strategy logic with realistic futures economics (contract point values, per-side commissions, adverse slippage in ticks, pessimistic fill assumptions), per-trade logs, and summary statistics broken down by session window. Confirmed running via synthetic smoke test.

The Silver Bullet strategy mechanics encoded in both artifacts:
- Three fixed 60-minute New York time windows: London (3–4am), AM (10–11am), PM (2–3pm)
- Fair Value Gap (FVG) detection via three-candle pattern
- Market Structure Shift (MSS) for directional bias
- Entry on first price tap into the gap within an active window
- Fixed-point stop/take-profit exits; force-flat at 4pm ET

**On the horizon**

Open decisions and next steps at conversation end:
- Which specific futures contract to trade (ES, MES, NQ, etc.)
- Whether to next build an IBKR data-fetcher and paper trading runner, or first refine backtest mechanics (e.g., swing-based stops, per-session max hold time)

**Key learnings & principles**

- Platform compatibility must be validated early — both the thinkorswim/Schwab and futures API blockers were discovered before code was committed to an incompatible stack
- The hybrid approach (thinkScript for visual validation + Python for automation) is useful for the backtesting phase even though only the Python/IBKR path reaches true automation
- Realistic futures economics (commissions, slippage, fill assumptions) should be baked into backtesting from the start to avoid overfitting to clean data

**Tools & resources**

- **Execution & paper trading**: Interactive Brokers via `ib_insync`
- **Historical data**: Databento, IQFeed, or Norgate Data (candidates; not yet selected)
- **Visual validation**: thinkorswim (thinkScript strategy file)
- **Strategy reference**: ICT Silver Bullet YouTube video

## Phase 1 screen (2021, all variants): results (append rankings here; both threads use this heading)
Laptop: 9 of 1,332 jobs at 21:38 UTC 2026-11-01 (bias-cache build). Cloud: ~55 jobs per 10 min at 21:26. Add: variant, trades, $ at $1k risk, movers vs default.

## Cards screen 2026-11-09 (Mase asked to record, 2026-11-10)
Engine f5dbfe0 (mentorship 16aea32 + PR #59), ES 5m Databento, $1k risk. Both runs read the complete parquet (2016-01-03 to 2026-10-16, 760,505 five-minute bars).
- Defaults baseline 2019-26: 168 trades, +$810 total; 2019-22 -$5,901, 2023-26 +$6,711. By year (trades/$): 2019 13/+459, 2020 21/-3442, 2021 17/+101, 2022 28/-3019, 2023 32/+847, 2024 15/-1656, 2025 22/+6354, 2026 20/+1166. Venom fired 2x in 8 years.
- 2021 card screen: 72 single-switch variants, 43 identical to defaults. Best PREMARKET-ENTRY A +$1,120 vs defaults, STOP-MGMT B +$697; worst LUNCH-TRADE A -$824. All noise-sized at ~17 trades/yr.
- Full suite 5315 pass, 3 skipped; 2 stale tests fixed in PR #59. Handoff: mentorship/handoff_cards5_2026-11-09.md on branch claude/project-thread-kekmm5.
- Data note: laptop data\mentorship\ES_1min_dbraw.csv is truncated to its first week; the parquet copy is complete.
## Moved from the MEMORY.md index 2026-11-13 (Mase approved trimming the index, 2026-11-13 00:52 UTC; entries verbatim as they stood in the index on 2026-11-12)
- ENGINE BUILD DONE (2026-11-09): all cards + CONTRACT B + Venom built; full suite 5315 pass. PRs #59 and #62 (stale-test fixes + handoff mentorship/handoff_cards5_2026-11-09.md) merged per Mase 11-11.
- CARDS SCREEN RESULT (2026-11-09, engine f5dbfe0, ES 5m databento, $1k risk, OLD late-roll data; in results.md via PR #60): defaults 2019-26 = 168 trades +$810; 2019-22 -$5,901, 2023-26 +$6,711 (2025 +$6,354). Venom fired 2x in 8 yrs. 2021 screen: 72 single-switch variants, 43 identical to defaults; all differences noise at ~17 trades/yr. Temp .worktrees\bis and .worktrees\oldcards can be removed.
- LOW TRADE COUNT (2026-11-11, PR #66 merged per Mase 11-12, also carries the data-switch scripts that missed #65; not yet in results.md; old thread "Find why the bot rarely trades" done): on FIXED-ROLL data, ES 5m 2019-26, $1k risk: defaults 166 trades -$490. Cause: "done for the week" rule (SG-m2024-41) blocks 1,378 of 2,147 sessions; it stops the week once last week's high, last week's low, or the new-week opening gap middle is reached (one hit on Monday in 383 of 406 weeks; median gap 4.75 pts). ICT's version (038, 101) is one called weekly target in the week's direction; which level counts was never defined, so the engine's reading is stricter. Rule off: 899 trades -$2,106 (2024 -$12,844); lunch +$5.8k, last hour +$3.1k, PM Silver Bullet -$8.8k, AM setups -$5.2k; only 132 of 1,524 open AM sessions get an AM trade.
- WEEKLY RULE SCREEN (2026-11-12, Mase "continue with the backtesting with this change"; laptop thread "Backtest the nearest-level weekly rule" cmsg_01FAHERC1Lsrg2bYtrKuRHmPVHNmnaqimKJCPondSfNkZG; PR #67 OPEN awaiting Mase, results only, no defaults changed; runs/weekly_rule_2026-11-12/README.md; not yet in results.md, needs Mase OK). ES 5m fixed-roll $1k, trades / total (2019-22 / 2023-26): defaults 166 -$490 (-5.9k/+5.4k); nearest of last week's high/low 383 -$372 (+2.0k/-2.4k); high or low only, no gap mid (week_done_levels=('pwh','pwl')) 338 +$4,441 (+2,099/+2,342), the only reading positive in both halves; off 899 -$2,106 (+4.9k/-7.0k). PM Silver Bullet and AM setups (order-block-before-break limit, midpoint stop ~2.3 pt) lose in both halves; four wider-stop switches same or worse, so the problem is entry selection. With both setups dropped (runner-side in funnel_x.py, not an engine switch; also drops 11 release_ob trades labelled AM): high/low only 276 trades +$7,441 (+3,838/+3,603, DD -11.0k, up 5 of 8 yrs); rule off 664 +$10,213 (+8,965/+1,248, lunch -$10.2k in 2024, DD -16.5k). WAITING ON MASE: merge #67 and pick which weekly-rule reading (and whether AM/PM SB off) becomes default.
