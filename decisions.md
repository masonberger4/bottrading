# decisions.md — owner answers and standing rules (who decided, when)

## ACTIVE RULES DIGEST (read this first; grep the rest; this is the single home for these rules)
1. One laptop writer at a time; call remote_control_status before touching the laptop; if another writer is active, stop and ask the coordinator.
2. Laptop folder C:\Users\mason\bottrading only; NEVER C:\Users\mason\X; leave ict_fetch PIDs and the Silver Bullet paper bot alone; one pytest run at a time, launched detached.
3. Long work (>30 min): check in and commit+push at least every 30 min; while laptop work runs, verify it is moving every 15 min and update Mase every 30.
4. No workflows/helper agents unless Mase asks (except build-stage review); short replies.
5. Models: threads Sonnet 5.5 at medium effort; rule-decision threads and audits Opus; coordinator Opus 5.5.
6. Free downloads pre-approved; paid purchases need Mase's OK in the thread that buys.
7. "Exactly what ICT says", full detail, experienced-trader version default, 2023 beats older videos; where ICT uses judgment label it "our interpretation".
8. Every owner answer is a backtestable switch; defaults first, alternatives as switches.
9. Report $ at $1k risk, by half and day type; choose on 2019-22, check on 2023-26.
10. Silver Bullet is settled (no edge, off by default): don't re-propose.
11. Don't re-offer: cloud video processing, cloud stage tests, a parallel laptop task.
12. Mase-only actions (agents hand him the exact steps up front, don't try first): merge PRs, copy files to the laptop, run taskkill, edit GitHub rulesets/branch protection, one-time pushes from the laptop. Cloud sessions can push only to their designated branch (other pushes and GitHub API writes return 403).
13. Only Mase and the coordinator write the project-memory index; threads don't call update_memory.

Append new decisions at the bottom of the first section as `- (Mase, YYYY-MM-DD HH:MM UTC) decision`. Every owner-answer decision is a backtestable switch.

## Facts carried from the old MEMORY.md index
- Q92 DECIDED (Mase 05:14 UTC 2026-11-01): non-narrative OB default, Q92 a switch. Every owner-answer decision is a backtestable switch.
- SCREENING PLAN (Mase 21:08 UTC 2026-11-01): screen every variant on ONE year (2021), entry/stop/trade-count variants first; meaningful movers expand to 2019-22, winners checked on 2023-26; little-effect variants parked for later. UPDATE (Mase 21:08-21:11 UTC 2026-11-01): also drop variants that are exact copies of defaults; movers expand in stages to 2019-22; winners checked on 2023-26; then combine winners one at a time; full combos later. Laptop holds current+defaults on all years as baseline.
- LONG-WORK RULE (Mase 20:59 UTC 2026-11-01, in project instructions): see ACTIVE RULES DIGEST item 3.
- DXY decisions D1-D4 FINAL (Mase 05:47 UTC 2026-10-31): scalp, hard block, staged, no purchase; other modes stay switches. See dxy-intraday-spec below.
- Silver Bullet SETTLED: no edge as coded. OFF by default. Don't re-propose.
- Guiding rules (Mase): "exactly what ICT says", full detail, never simplified; where ICT uses judgment, write the closest exact rule labelled "our interpretation". Experienced-trader version default, beginner a switch. 2023 beats older videos. Test defaults first, then alternatives as switches.
- Owner directives (2026-10-18): risk 1.2% at entry/1.3% with adds; Ep 07 advanced OB-body entry default; last hour 15:00-15:50; PM session 13:30-16:15; 5 handles minimum room; breaker full range; front-month prices. Year-end move goes AGAINST December's direction; stand aside only on sloppy days (calendar block a switch). FVG behind the trade is resistance and an add zone, never a target; opposing FVG between price and draw is a speed bump by default.
- Experienced defaults: NFP Friday traded from 9:30; NFP-week Wed PM-Fri unblocked; FOMC PM entries from 14:45; reversing after a loss allowed; 5 points minimum room; week gaps kept 60 days; Mondays traded.
- Definitions: daily bias from HTF draws on liquidity, FVGs, OBs and daily/weekly opening gaps. Week gap = Fri 4:59pm close to Sun 6pm open, kept 60 trading days. Day gaps Mon-Thu 5pm-6pm. Opening range gap = prior close (ES 4:15pm) to 9:30 open. Opening range 9:30-10:00, no trades inside it. Closed candles only; structure shift needs a close; CE exit off by default. 3-candle swings; one OB definition. ES/NQ/YM SMT is a qualifier only. 1m main chart with 5m zones. Conviction score is a label, not a filter.
- Pre-9:30 entries: test-only switches, off by default; weak so far.
- Scaling: adds 6/3/1 ladder (add_ladder 631); trail under the newest gap after each partial; breakeven once a later candle closes past first target; 80/20 split on slow days or with news ahead, else 50/25/25.
- GAP PASS FINISHED 2026-10-29. Owner answers: trendline switches stay off; balanced FVG = OWN timeframe; breaker candle = extreme close, full-range zone. News-day test: only N5b beat base, +$540 on 21 trades. COT default: Legacy Commercial net vs 12-month midpoint; TFF variants are switches.
- Usage (Mase, 2026-10-18): Ultracode only for the second-agent review of each build stage; no workflows/helper agents unless Mase asks; short replies. Model (Mase, 05:07 UTC 2026-10-31): threads use Sonnet 5.5 at medium effort; rule-decision threads and audits use Opus. Coordinator stays Opus 5.5. Mase declined a parallel laptop task to use idle cores; don't re-offer. Mase wants threads moved to fresh ones when context grows.
- Cloud work in parallel (Mase chose "Backtests + swing"). Building stages in the cloud declined. Stage tests "Laptop only"; don't re-offer cloud test runs.
- Transcripts: 217 videos. Mase declined cloud processing of videos; don't re-offer.
- Results/validation (Mase): report $ at $1k risk and by day type; choose on 2019-22, check on 2023-26.
- DOWNLOADS (Mase, 00:45 UTC 2026-10-31): any FREE download is pre-approved. Paid purchases need Mase's OK in the thread that buys.
- Mentorship bot builds ICT's mentorship rules. Live orders would be SPY shares via Schwab. Schwab account HAS margin (can short SPY). All strategies trade long and short.

# Detailed memory files moved here verbatim (one section each)

## mentorship-standing-rules — Mase's standing rules for choosing between ICT's versions when building the Mentorship bot (experienced-trader version, 2023 over older videos)
(source: mentorship-standing-rules.md, modified 2026-10-18T02:09:02.323Z)

- **Experienced-trader version is the default** (Mase, 2026-10-18 02:08 UTC): "Whenever ICT says 'for experienced traders' that is how we are treating the bot." Where ICT gives a beginner version and an experienced version of a rule, the bot defaults to the experienced one; the beginner version can be kept as a comparison switch. First application: NWOG lookback, where video 051 allows ~60 days for experienced traders vs "keep at least the last 4, preferably 5" in 039, so the default moves to ~60 days (about 12 week gaps) with 4 and 5 tested as comparisons.
  Defaults switched (2026-10-18 ~02:35 UTC, laptop digests/experienced_rules.md): NFP Friday traded from 09:30 (101, 105, 071); NFP-week Wed PM-Fri unblocked (101); FOMC PM entries from 14:45 (021); reversing after a loss allowed (001); min room to target 5 handles not 10 (046); NWOG 60 trading days (051). Already experienced: CPI days, Mondays, trades per day/week. Kept as tests only (experienced permission inferred, not ICT's words): half-size re-entry after loss, lunch window, turtle soup without MSS; also ICT's 5% risk near HTF levels (102). Beginner versions kept as switches.
- **Full detail, never simplified** (Mase, 2026-10-18 04:37 UTC): "The bot needs to be as complex and detailed as the totality of all the videos." Build every ICT rule in its full form (scaling in/out, trailing, setup selection, etc.), not a minimal testable version; where ICT uses judgment, write the closest exact rule and label it "our interpretation". Mase was given a line asking the laptop to audit all ~190 rulebook rules vs the code (full / simplified / missing) and build the rest in full as switches, plus SB off by default. Mase SENT it to the laptop at 04:38 UTC. The cloud thread is cross-checking Ep 01-08 captions vs the bot (workflow; output to /mnt/project-files/mentorship/full_detail_check_ep01-08.md) to compare with the laptop audit when it arrives. Laptop (04:52 UTC): SB OFF by default; auditing ~190 rules + Ep 01-08 appendix (FULL/SIMPLIFIED/MISSING/n.a.), then building in parallel packages, each a switch with a look-ahead test; BACKTESTS PAUSED until the full build is in; ladder scale-in/out built, tests running, not committed. Mase also sent (04:56 UTC): re-check the rulebook against the captions of all 217 videos (on the laptop) for rules shortened, missing a condition, or missed, and add them to the audit and build. Mase (04:53): SB-with-new-scaling test can wait until after the build. Mase (04:57): "We should be using Ultracode for all this." Laptop now runs the 217-caption check as a workflow (agent per video, merge, adversarial verify, build specs) and will build as a second workflow (agent per package, own worktree, tests). The audit covers all ~190 rules from all 217 videos plus the Ep 01-08 appendix. Ultracode on the laptop: "/effort ultracode" typed in the thread runs in the CLOUD session only (laptop can't take it); prefix laptop lines with "ultracode:" instead. Usage limits hit mid-run fail RC agents. Laptop (05:15 UTC) runs the code audit as a workflow too: 17 rule groups, agent each, per-rule skeptical re-check, output digests/rule_coverage.md with build packages by code area.
- **2023 over older videos:** where the 2016-17 Core Content conflicts with the 2023 mentorship, the bot uses the 2023 version (from MEMORY.md, 2026-10-17).
- Results are reported in $ at $1k risk, split 2019-22 vs 2023-26, and by day type ([[day-type-aware-strategies]]).

**Why:** Mase treats the bot as an experienced trader, not a beginner.
**How to apply:** when a rule conflict or option comes up in the notes, check whether ICT labels one version as for experienced traders and pick it without asking. Related: [[mentorship-bot]], [[mentorship-missing-concepts]].

## mentorship-owner-questions-pass — Outcome of the Opus check of the caption-gap owner questions (2026-10-29) - which defaults the captions say should change, and what is still open for Mase
(source: mentorship-owner-questions-pass.md, modified 2026-10-29T09:35:53.422Z)

Doc: /mnt/project-files/mentorship/owner_questions_settled.md (Opus redo, 2026-10-29; replaces a Haiku version with wrong answers on Q2/Q90/Q94/Q142). Q numbers = order of the "Owner questions" blocks in build_log.md (298 numbered, ~250 distinct).

MASE APPROVED ALL (15:18 UTC 2026-10-29); build list /mnt/project-files/mentorship/owner_answers_build_2026-10-29.md, for the laptop after data wiring. Defaults to change: bk_depth any_open; cisd_ob_px open (+discount); ob_need_narrative True (big trade-count effect, study first); add_ladder 631 (ICT's "standard 10 lot model", 060 ~1:03:10 - the old "adds 1/2,1/3,1/6" was the 6/3/2/1 build, not a directive); htf_gap_final far_edge; tgif_exits "066"; hold_through_0830 True; objective_done_pm reversal_only; tgif_window off; pd3_result neutral; org_with_bias True; ifvg_stop split HTF ce / LTF far; htf_monthly_series raw; htf_bias_pools True.
Q1 breaker / Q6 balance_tf: MASE AGREED (15:16 UTC 2026-10-29): keep extreme_close (zone = full range, 032 ~41:26) and balance_tf "own" (061 ~40:20), reversing his earlier "any timeframe". Both are current code defaults: no build. The repo handoff_2026-10-29.md still says "any timeframe" - outdated.
D-decisions approved as recommended: keep ob_mt stop + three_pd study; release_ob_entry (N5b) default on, N1/N5a off; counter trade after delivered draw = study only; 5m added to speed-bump TFs.
Flag: commit f8e921b has unreviewed bias_htf#2/7 edits.

**Why:** later threads building or backtesting the final engine need to know which defaults are pending.
**How to apply:** don't rebuild these answers; check the doc and whether Mase has replied. Related: [[mentorship-standing-rules]], [[model-choice-for-decisions]].

## day-type-aware-strategies — Mase wants trading strategies to change by day type (CPI, FOMC, quarter/year ends, options/futures expiry), not one rule set every day
(source: day-type-aware-strategies.md, modified 2026-10-15T18:52:30.375Z)

Mase said on 2026-10-15 (in the Claude HF thread): "The same strategy can't be used every single day." Strategies must account for market-moving days: CPI, Fed rate decisions, beginning/end of quarter or year, and expiring options or futures contracts.

Claude HF now tags each day (FOMC, CPI, jobs report, monthly opex, quad witching, quarter/month end and start, futures roll week, plain weekday) from official 2026 BLS and Fed schedules, and its self-improvement loop picks playbook A, B, or sit out per day type.

**Why:** Mase's view of how markets behave; a single-rule-set bot misses it.
**How to apply:** any new or revised strategy should be day-type aware, and results should be reported per day type, noting how few event days the data holds. See [[claude-hf-bot]].

## model-choice-for-decisions — Mase wants Opus (not Haiku) for work that settles rule decisions or owner questions needing critical thinking
(source: model-choice-for-decisions.md, modified 2026-10-29T09:22:46.887Z)

Mase (09:22 UTC 2026-10-29), after a Haiku pass on the caption-gap owner questions: "redo this work with opus. we need more critical thinking for these decisions."

**Why:** the Haiku pass sorted questions shallowly and cited the rulebook without reading the captions it referenced.
**How to apply:** threads default to Sonnet 5.5 at medium effort (updated 2026-11-01 per Mase 05:07 UTC 2026-10-31; was written as Haiku 5.5), but any thread that settles rule conflicts, owner questions or default choices for the Mentorship bot should run on Opus and check the cited captions directly, not just rulebook summaries. Related: [[mentorship-standing-rules]].

## mentorship-usage-preferences — How much multi-agent/Ultracode work Mase wants on the Mentorship bot, and the plan to split the long thread into fresh threads
(source: mentorship-usage-preferences.md, modified 2026-10-18T21:39:52.213Z)

Mase (2026-10-18 16:25 UTC) found usage in the Mentorship bot thread too high and chose "Both" on the coordinator's card: Ultracode / multi-agent workflows ONLY for the second-agent review of each build stage; everything else at normal effort; backtest restart and swing version get fresh threads after the full-detail build. Current build stage finishes first. Laptop line given to Mase: keep stage reviews, no other workflows, finish the 217-transcript gap verification at ~50 items per agent. Handoff note for the new threads: /mnt/project-files/mentorship/handoff.md.

Backup (Mase, 16:32 UTC): every session must see the files with the laptop off. Coordinator thread "Copy mentorship notes to cloud" copies notes/captions/rulebook/digests to /mnt/project-files/mentorship/laptop/. Mase tapped Yes to a private GitHub repo for the code (suggested name bottrading); Mase given a laptop line (16:35): after the current stage commits, push all branches, .gitignore data/, runs/, .env, keys, Schwab tokens, stop if any are already committed; Mase SENT it (16:36) with the repo https://github.com/masonberger4/bottrading. Laptop (16:45): repo private+empty, logged in as masonberger4; history scan of branches claude-hf, master, mentorship clean (no data, tokens, keys); .gitignore extended and committed; PUSHED (~17:00 UTC): master, claude-hf, mentorship (e58eed1, through stage 2) to the private repo. Later build commits stay local until pushed; Mase SENT (17:14): auto-push mentorship to GitHub after each build stage commits, after the secrets check.

Mase (16:36, project chat): "Please optimize this project for usage." Thread now: short replies, inline lookups, no helper agents except build-stage reviews. The effort switch tool needs Mase to name a level; asked him (17:15), suggested medium.

Mase (19:01, project chat): "Also optimize for model use, not just effort." Cloud threads default to Sonnet 5.5; this thread switched to Sonnet 5.5 (19:02). Mase SENT the laptop line (19:07): helper agents incl. stage reviews on Sonnet; the laptop session itself switches only via /model on the laptop.

Mase SENT (19:06) the laptop line to run the full suite on the exact pushed commit and fix the 7 cloud-only test failures (115/122 pass on Linux) without changing trading behavior.

Cloud tests on e58eed1 (cloud_test_failures.md): 149 tests, 10 failed (the "7 of 122" was a miscount). RESOLVED by the laptop (21:35, commits 162decb, b5f5bce, 7da5dc1, test-only, golden run 23 trades +$4,693.52 unchanged): Zone NaN equality (Python 3.13 vs laptop 3.11), stale year-end/sloppy tests, both data tests stale from Mase's year-end and sloppy answers (presets set year_end/sloppy_mode off), schwab test skips. Stage 3 pushed fe4b2e5; stages 4-10 run on Sonnet, every stage runs ALL test files on Windows and Linux. Stage 4 changes the golden window 23 to 24 trades; the laptop must keep the old behaviour reachable via the preset or document it.

**Why:** each workflow agent draws on Mase's plan; the 217-transcript check alone hit the 1,000-agent cap.
**How to apply:** don't launch workflows or fan-out agents for Mentorship work beyond build-stage reviews unless Mase asks again; prefer one agent or inline work. Don't prefix laptop lines with "ultracode:". Related: [[mentorship-standing-rules]], [[mentorship-rule-coverage]].

## mentorship-scaling-rules — What ICT teaches on scaling in and out of Mentorship bot trades (partials, breakeven, trailing, adds) and how the bot now does it
(source: mentorship-scaling-rules.md)

Scaling (Mase asked 2026-10-18 04:32 UTC, wants the bot to do exactly what ICT says): rules.md/captions say scale out by "running down equity" (bulk e.g. 10 of 12 at first target, then one unit per next pool, trail under the latest gap that holds, accept stops on the last units; clean runs held whole, choppy runs get partials at each level), scale in on pullbacks into a holding gap using open profit (~6 contracts building to 10-16), no pyramiding after partials; SMT partials bank ~half. Bot: one partial + breakeven; early trail-under-each-FVG (-$4.1k 5m) and pyramiding tests hurt. Mase given a line to build both as switches on main model and SB. BUILT (04:45 UTC) as the NEW DEFAULT management: out 50/25/25 along the target list, BE after first partial, stop to each paid array after a 1-handle close beyond it (Mase's own suggestion), adds 0.5/0.33/0.17 of first size at each new FVG after fill (ICT 6/3/2/1, Ep 04), none after first partial, total risk cap 2% (laptop's guard); switches: old T1/T2, 80/20, stop one level behind, ICT trail under newer FVGs, no adds; SB tested with the ladder too. Laptop notes: ICT 50/25/25 normal days, 80/20 slow/news-ahead days (036); BE only after first partial AND expansion (X4); trail under newer FVGs after each partial, never the FVG right after the shift (003, 062); trailing too soon = main error (029, 085). Mase SENT (04:49 UTC): ICT's trail under the newest FVG since each partial (never the post-shift FVG) is DEFAULT, Mase's stop-to-the-array is a switch; BE only after first partial AND expansion (X4); 50/25/25 normal days, 80/20 slow/news-ahead days ('slow day' = our interpretation). BUILT (05:00 UTC, tests running): trail X5 under newest FVG since each partial (switch ladder_trail="hit" = Mase's version); BE after first partial AND a later close beyond T1 (our interpretation of expansion); 80/20 if news later that day after fill or CPI/NFP/FOMC next day, or slow day = midnight-to-fill range < half the 5-day avg RTH range (our interpretation), else 50/25/25. Quick Jan-Jun 2024 1m main model, 21 trades: defaults +$9.6k, Mase trail +$9.9k, fixed 50/25/25 +$11.4k (too few). SB-with-ladder switch sb_mgmt="ladder" parked for later.

**Why:** Mase wants the bot to manage trades exactly as ICT does (2026-10-18); later sessions shouldn't redo the search.
**How to apply:** ICT's own version is the default, Mase's stop-to-the-array idea a switch, unless Mase says otherwise. Related: [[mentorship-ict-research-findings]], [[mentorship-standing-rules]], [[mentorship-backtest-results]].

## dxy-intraday-spec — Build spec for the 16 DXY rules (11 intraday, sym gate, 4 daily/hourly) written 2026-10-31; data caveats; decisions D1-D4 final (2026-10-31 05:47 UTC)
(source: dxy-intraday-spec.md, modified 2026-10-31T05:21:03.280Z)

Spec: /mnt/project-files/mentorship/dxy_intraday_spec_2026-10-31.md (Opus thread "Write specs for ICT's intraday DXY rules", 2026-10-31). Docs only; the laptop build thread builds it after the owner-answer build. Base ed54858.

- Covers coverage_gaps section C intraday DXY items, B17.5 sym gate (`sym_gate`), and the daily/hourly items (DXY turtle-soup raid, daily MT regime, DXY weekly objective via `week_done_levels`, ES+DXY end-day via `obj_stop`). All new switch names checked as unused.
- Highs/lows: default `dxy_bars="udx_shape"` (spot close + HistData UDX in-minute shape; 1m change corr 0.95). Free FX-pair rebuild ("bound") recommended: real H/L, EURUSD/GBPUSD for the 045 exit, stale column, maybe 2016-18.
- Data holes: spot file stale on 2023-03-07 10:00-10:55 (ICT's 037 unicorn example; UDX has no bars then either) plus 16 flagged hours listed in the spec. No 1m DXY for 2016-18 or 2026, so these switches are judged on 2019-25 (check set 2023-25).
- Decisions FINAL (Mase 05:47 UTC 2026-10-31, "final for now but they can be toggled for back testing"): D1 sym_gate scalp; D2 dxy_states hard block; D3 staged bank-then-close (fx_nonconf any time); D4 no DX 1m purchase now. All other modes stay switches.
- Found: rulebook-gap "093 says asymmetric still tradable" conflict is not in the 093 caption.

**Why:** most-cited unbuilt 2023 material. **How to apply:** build from this file; don't re-read the cites. Related: [[coverage-audit-2026-10-31]], [[databento-extra-data]].

## mentorship-missing-concepts — Which ICT concepts the Mentorship bot still lacks, the build order proposed to Mase, and what his "start" / "start all" reply means
(source: mentorship-missing-concepts.md, modified 2026-10-18T01:19:38.848Z)

Full list: /mnt/project-files/mentorship/missing_concepts.md (Mentorship bot thread, 2026-10-18), built from the RC's code review plus a second independent check of the notes.

Proposed build, each as a switch tested vs the defaults, tests to run after the 1m comparison:
1. Three-index SMT (ES/NQ/YM) as a filter and for partials. Today the bot only labels whether NQ confirmed ES's sweep; YM is downloaded but unused.
2. Higher-timeframe FVGs/OBs (15m to daily) as targets.
3. Silver Bullet as its own setup, plus macro windows 10:50-11:10, 13:10-13:40, 15:15-15:45.
4. Top-down filter needing daily/4h/1h/15m to agree (15m is ICT's "bellwether").
Cheap extras from the second check: previous week's/month's high-low as liquidity and targets; ordinary short-term swing highs/lows as liquidity (may explain part of the low trade count); AM entries from 8:30.

Mase replied "Start all" (2026-10-18 01:21 UTC). The RC read it as its own 8-piece list and is building in order, each tested and committed before the next: (1) 3-index SMT count/filter/leader-vs-sick-sister, (2) HTF targets, (3) SB own setup + macro labels, (4) top-down daily/4h/1h/15m filter, (5) day/week templates (neutral-day gate, inside day/week, weekly profiles, TGIF), (6) three-PD-array exit + SD partials, (7) Judas/P3 tag, (8) DXY and 10y labels. Ma Deuce research-only (needs a discretionary pre-market read); FX tools out. The RC receives only Mase's own typed messages (send_message to it is refused), so the three cheap extras need Mase to send: "Also add last week's and last month's high and low as liquidity, ordinary short-term swing highs and lows as liquidity, and morning entries from 8:30." Asked 01:23 UTC.

Mase decided 2026-10-18 02:03 UTC: ADD last week/month high-low and ordinary short-term swings as liquidity (switches); DO NOT add 8:30 entries; research whether pre-9:30 entries are a one-off or their own setup (cloud notes lean one-off: Ep 01-08 say wait for 9:30 or the news release; decisions.md #1 early-2023 entries 9:37-9:50, 10:00+ from video 44; the 9:21 entry in #18 is the only earlier one found). The RC misread "1 and 2 but not 3" as its build list (SMT, HTF targets, drop SB setup) and proposed HTF targets ON by default; Mase was given a correction line to send at 02:06 UTC.

DONE 2026-10-18 ~02:45 UTC: switches pool_prev_week, pool_prev_month, pool_swings (untaken 3-candle swings from yesterday and today), each a sweep level and target, off by default, queued after the current comparison. No 8:30 entries; RC researching every pre-09:30 entry type (London, 03-04 SB, 07:00-08:30, 08:30 news, Ma Deuce, NDOG Asian scalps) for Mase to decide.

Full rule-by-rule audit and build packages: [[mentorship-rule-coverage]].

Research findings on week gaps, Silver Bullet, bodies/wicks and CE: [[mentorship-ict-research-findings]].

Unverified, check on the laptop before claiming: whether equal highs/lows come from 5m swings, whether monthly opening gaps were built, whether the 10-17 Ep 07 proposals (stop under sweep candle's body midpoint, exit below the swing low's lowest body) were ever built. STH/ITH/LTH swing hierarchy isn't found in the notes yet.

**Why:** Mase asked what's still missing (2026-10-18) after noticing the bot doesn't use all timeframes at once.
**How to apply:** when Mase replies, build the chosen set; don't re-propose items already listed. Related: [[mentorship-bot]], [[day-type-aware-strategies]].

## mentorship-ict-research-findings — What ICT's videos say on week-gap lifetime, the Silver Bullet setup, bodies vs wicks and consequent encroachment, and how the Mentorship bot now handles each
(source: mentorship-ict-research-findings.md)

Week-gap lookback (Mase asked 2026-10-18 02:06 UTC; he recalls ICT keeps only the last 20 trading days of NWOGs): the 10-17 check of videos 039/051 found "keep at least the last 4-5" (~20-25 trading days), 051 allows ~60 days for experienced traders, fills do not end an NWOG; bot keeps last 5. RC is searching all notes. Offered Mase: send "test 4, 5 and 12 weeks" to queue switches.

RC research 2026-10-18 ~02:25 UTC (laptop digests gap_lifetime.md, silver_bullet.md): NWOG max 60 market days (051, 065), "20 days" (015) = sensitivity ranking for ALL PD arrays (20 then 40 then 60), not a cutoff; plan NWOG 60 days, last 5 primary, never retired by fill, test 4/5/20/60; NDOG through Friday; ORG 5 days. Silver Bullet = real daily setup (36 videos, 43 examples): 10-11 and 14-15 windows, no sweep required, first FVG, limit at near edge cancelled if target trades first, ~+5 handles, since 2023-05-23 only the entry must be in the window; bot version differs ~10 ways; RC asked whether to build it as its own setup. Bodies/wicks: bot acts on closed candles; wicks = sweeps, fills, stops; bodies = MSS, FVG validity, OB mean threshold, bias flips; missing: 1-2 tick wick past a level still counts as respect. CE added: exit if a body closes past the entry FVG CE before T1 (default ON), prior-day wick CEs as targets (ON). Mase was given one line to send (02:27 UTC): build full SB as own setup, add week/month H-L and short-term swing liquidity switches, no 8:30 entries, research pre-9:30 entries.

Pre-09:30 entries (laptop digests/pre_open_entries.md, 2026-10-18 ~03:00 UTC): 7 own fills in 6 videos (018 09:21, 032, 040, 050, 096 07:47 paper, 105 NFP demo), all but 096 on 08:30 news days; stated rule: no 08:30 news, wait for 09:30; 07:00-08:30 optional (022, 032, 099); wait 30 min after high-impact news (065), often broken; not labeled experienced-only. SPY can't trade it realistically. Recommended leaving out, but Mase chose (03:07 UTC) to add 07:00-08:30 window, post-08:30-news model, 09:00-09:29 entries and Ma Deuce as TEST-ONLY switches (futures-only realism; SPY can't trade pre-open well). Original offer was an optional line to add 07:00-08:30, post-news, 09:00-09:29, Ma Deuce as test-only switches. Bodies/wicks/CE second check (/mnt/project-files/mentorship/bodies_wicks_ce_check.md): CE exit may be too broad (Ep 04 holds/adds on a close into the gap; CE hold is for breakaway gaps); MSS wick is the later/majority view (5 of 7) but close kept on backtest; Ep 07 stop anchor, invalidation and trail not built; HTF targets stop at midpoint. Mase given a line to turn CE exit default off and add these.

Scaling in/out rules and the built version: [[mentorship-scaling-rules]].

**Why:** Mase asked each question in the Mentorship bot thread on 2026-10-18; later sessions shouldn't redo the video search.
**How to apply:** use these as the settled reading of ICT unless Mase says otherwise; full write-ups are on the laptop in bottrading/mentorship/digests/. Related: [[mentorship-missing-concepts]], [[mentorship-standing-rules]].

## mentorship-bot — Mentorship bot (formerly "2023 Mentorship"; ICT mentorship video rules) - where code/rules live, backtest results, transcript plan
(source: mentorship-bot.md, modified 2026-10-15T19:51:19.295Z)

Mase's third bot, "Mentorship" (renamed from "2023 Mentorship" on 2026-10-17 because more videos beyond the 2023 playlist will feed it), built from ICT 2023 mentorship video transcripts Mase pastes into its thread. Shared rules file /mnt/project-files/mentorship/rules.md covers Ep 01-08 only; the full rulebook is on the laptop.

Code lives in C:\Users\mason\bottrading (local only, not pushed), SPY with QQQ for SMT, backtest/paper only. Reuses silver_bullet Schwab code and claude_hf event calendar. 

Decision (Mase, 2026-10-16): signals come from futures/index data (ES-style, ICT's market), orders are SPY shares ($0 commission, Schwab can't trade futures). Free 2019+ data = HistData SPX/NDX CFD 1-min.

Final AM test 2026-10-16 (commit 4668ae0): 1m -$32k, 5m +$16.8k patchy; no reliable edge.

Parked idea (Mase, 2026-10-16): build a swing version (1h/4h/daily, multi-day holds, weekly high/low targets) only AFTER all transcripts are uploaded; check whether ICT covers swing trades first.

Transcripts (2026-10-17): captions + key frames per video on the laptop; videos deleted after notes.

More playlists (Mase, 2026-10-17): queued after the first, same treatment. Full ordered list: /mnt/project-files/mentorship/playlists.md (append new ones there). Runs on laptop only, 4 workers (max for its 4 cores); Mase declined cloud processing (2026-10-17).

Laptop names (since 2026-10-17): package mentorship/, branch `mentorship`, bottrading/mentorship_rules.md, runs/mentorship/.

Rulebook done 2026-10-17: ~190 rules from all 217 videos in laptop mentorship_rules.md. 23 conflicts with defaults in /mnt/project-files/mentorship/decisions.md, sent to Mase along with the swing-version timing question; Mase (2026-10-17 15:52): test defaults first, then each alternative as a switch. Swing version starts after this re-test (my default, unopposed). Daily-bias test (old bot, 5m, 2019-26): no bias 172 trades +0.14R; reaction-bias 53 trades +0.51R but top 5 trades carry it (±0.37R); bias calls direction ~50%; 1m all lose. Kept as a label, not a filter. Defaults test (5m, $1k risk, partial 206/264): current bot 200 trades +$3.3k; defaults 42 trades -$0.9k; best alternatives D4 full-candle OB midpoint +$4.8k and D2 Silver Bullet windows +$4.0k; worst D3 wick MSS -$7.6k, drop D12 lower-half rule -$11.3k. Use $ not avg R. Mase's daily-bias rule: bias comes from higher-timeframe draws on liquidity, FVGs, order blocks, daily gaps (5pm ET close to 6pm ET open) and weekly gaps (Fri 5pm ET close to Sun 6pm ET open).

Mase (2026-10-17): conviction comes from multiple PD arrays aligning; higher timeframe alignment = higher conviction; PD arrays are fractal across timeframes. Plan: score each setup by aligned PD arrays per timeframe (1m to MONTHLY per Mase, weighted up), label not filter, then test score vs results and sizing by score. Bot finds too few trades (42 with defaults vs ~400 at ICT's 1/week), Cause found (step counts 2023-24): 5m hides ICT's swings (1m: 3/4 sweeps -> MSS, ~0.7 trades/day, matches ICT ~1/day; 5m: 1/3). Lower-half rule bug (measured before the move finished) fixed. 1m is now the main timeframe. 10%-of-days timestamp bug fixed. Data gaps: 131/1954 days unusable (109 Feb-Jul 2023). CFD feed stops 16:14 ET, so daily/weekly/monthly gaps and daily-up candles are only approximate (Mase flagged 2026-10-17); daily-bias result untrusted until re-run on Databento ES/NQ 1m (Mase set DATABENTO_API_KEY on laptop 2026-10-17). Yahoo check: HistData tracks cash index (4pm close ~1pt off SPX), moves match ES/NQ 0.98-0.99; Dukascopy = same feed, fills Feb-Jul 2023 hole.

**Why:** later sessions should extend this, not rebuild. See [[silver-bullet-bot]], [[claude-hf-bot]], [[day-type-aware-strategies]].

## claude-hf-bot — Claude HF, Mase's second bot (high-frequency stock bot built by self-improving backtest loop), started 2026-10-15
(source: claude-hf-bot.md, modified 2026-10-15T19:04:49.835Z)

On 2026-10-15 Mase asked for a new bot named "Claude HF": high frequency, stocks only, profitable, built through recursive self improvement. It runs as a laptop Remote Control thread "Claude HF trading bot" in C:\Users\mason\bottrading, as its own package claude_hf next to silver_bullet (reusing its Schwab auth).

Defaults chosen in the brief: fastest the retail Schwab API allows (intraday, short holds, not true microsecond HFT); self-improvement = automated loop keeping only changes that also beat held-out data after costs; paper trading only, no real orders without Mase's explicit ask.

First result (2026-10-15): built on a local `claude-hf` branch in bottrading with 13 tagged event day types (FOMC, CPI, jobs, PCE, PPI, retail sales, GDP, quad witching, ISM mfg/services, JOLTS, Michigan sentiment, opex). Loop ran 5 times on 9 months of 5-min bars for 40 large caps (train Jan-Jun, select Jul-Aug, untouched test Aug 25-Oct 14). Best pick +3 bps/day, Sharpe 0.8, indistinguishable from zero and negative at 2x costs; the average of all 5 lost ~4 bps/day. No edge found; looks like fitting noise. `python -m claude_hf paper` paper-trades the pick (no live mode), `evolve` reruns the loop. Thread's suggestion: better inputs (order book, earnings) rather than more search over minute bars.

**Why:** later sessions should extend this, not restart it.
**How to apply:** see [[silver-bullet-bot]] for the Schwab setup; never use the X folder ([[no-x-folder]]).
hack
Append to Active Rules Digest / decisions:
- (Mase 2026-11-02 04:46 UTC) Stop all backtesting until all four ict_fetch playlists (Trade Executions 71, Charter Content 34, Core Content 58, 2024 Mentorship 51) are downloaded and transcribed; engine is built from all of them. Download work gets its own thread and is the single laptop writer.
- (Mase 2026-11-02) Browser cookies for yt-dlp: ONLY from a spare Google account in a fresh Chrome profile, never the main profile; use as fallback if slow pacing + backoff does not clear the bot check.
- (Mase 2026-11-02) Keep the 2026 SMC playlist (143 videos) in the download set.
- (Mase 2026-11-02 04:5x UTC) Set each thread's model/effort to fit its work; idle laptop-ops threads use Sonnet 5.5 low.
Facts for data.md/laptop_ops.md: ict_fetch pipeline = fetch_win.py -> prep_win.py -> manifest.json -> cloud box /workspace/yt_fetch acks -> sync_tool.py deletes all but DONE and writes SYNCED; fetcher pauses at >8 GB un-acked or low disk; supervisor run_all.py, scheduled task "ICT Fetch" (start.ps1); state in data/ict_fetch_handoff.md. C: 107 GB, ~13 GB free; ict_fetch/out 8.1 GB; stash@{0} is only a little in .git (18 MB).
