# Have the engine's switches been tested enough? (2026-11-17)

Mase (04:01 UTC): analyse whether the engine has been tested enough with the switches available.
Analysis of existing results plus one cheap spot-check. No engine code or default was changed.

Standard used for "tested": fixed-roll ES + NQ + YM, true $1k risk with no sizing cap, 2019-26, chosen on 2019-22 and
checked on 2023-26, on 5m and/or 1m bars.

Files here: `coverage.csv` (one row per switch with its coverage level), `replay.py` (independent 1-minute replay of
engine trades), `spot_check.txt` (the runs below), `spot_check.py`.

## Answer

**Switch by switch, almost nothing is tested to the standard. For the question that matters (is there an edge in this
engine), testing is sufficient, with a short list of exceptions below.**

- The engine has 2,616 switches (`Params`, mentorship @ e68ef84). 30 have been run to the standard (11 of them in this
  PR), 9 more on fixed-roll data but with the old sizing cap or on ES only, 24 only in the ICT replication runs.
- 1,896 were last run in the old one-year screen (2021, ES only, old late rolls, $400k cap, engine before the
  2026-11-09 rebuild). 646 have never been run at all (404 have a variant defined, 242 do not; the 242 are mostly
  numeric thresholds).
- That thin coverage matters much less than it looks, because of what the switches do (section 2), and because the
  best-looking untested switches turn out to be nothing when run properly (section 3).

## 1. Coverage

| level | switches | what it means |
|---|---|---|
| 1. Standard | 30 | week rule (on/off, which levels), OB stop at the sweep extreme, OB wick stop, 3-point minimum stop, FVG counts as the shift, 3 trades a session, narrow morning engine and its 11 pieces, plus the 11 switches spot-checked here |
| 2. Fixed-roll data, but capped sizing or ES only | 9 | weekly rule "nearest", MT-break stop (PR #67); the DXY and bond switches (PR #72) |
| 3. ICT replication runs only | 24 | day and session gates opened together on 1m, ES 2023 and NQ 2023-24 (PRs #69, #77) |
| 4. Old 2021 screen only | 1,896 | one year, ES, old rolls, capped, pre-rebuild engine; 2,008 variants |
| 5. Variant defined, never run | 404 | mostly added after the old screen (rule cards, caption-gap rules) |
| 6. No variant, never run | 242 | mostly numeric thresholds |
| Runner settings, not rules | 11 | costs, sizing, symbols |

Also tested to the standard without being engine switches: setups dropped runner-side (AM, PM Silver Bullet), 512
on/off combinations of 9 day and session filters, 276 + 467 feature splits of the saved trades, 30 bias rules scored
for direction (PR #83), 85 single-idea variants (PR #85).

Combinations tested: week rule x setups dropped; the 512 filter combinations; DXY x bonds; the two PR #77 switches
together; "everything opened" in the replication runs. No entry-type switch has been combined with another
entry-type switch to the standard.

## 2. Why the gaps mostly do not matter

Nearly every switch acts on the same stream of entries. What the standard runs already show about that stream limits
what any switch of each kind can do:

| kind of switch | what bounds it | open risk |
|---|---|---|
| Filters and gates that remove trades (days, news, sessions, bias agreement) | 512 filter combinations: none beats a random day filter. 743 feature splits: 5 confirmed against about 3 expected by luck, none profitable | low |
| Gates that are on by default (turning them off adds trades) | week rule off: -0.13 R a trade on 2,897 (5m) and 4,908 (1m) trades. Everything opened: -0.2 R a trade | low |
| Exits, partials, trailing, targets | After the fill, price shows no move in the trade's direction at 5, 15, 30, 60 minutes or the close, and stop-versus-target is a coin flip at 1R, 2R and 3R. No exit rule makes money from entries with no drift | very low |
| Stop placement | Five stop switches run; a stop 3x wider gives 0.00 R. Loss shrinks, never turns positive | very low |
| Which side to trade (bias, draw, premium / discount) | 30 bias rules: none calls direction (PR #83). A model on 57 coded columns cannot find ICT's side (PR #93) | low; only the default settings of each bias rule were scored |
| New entry types (setups and entry models that are off) | Sweep, FVG, order block, time window and gap each alone: no edge in 85 variants (PR #85). Narrow morning engine: within luck (PR #89). Old screen: of 100 variants that added many trades in 2021, 94 lost | the one place a surprise could sit; see section 3 |

## 3. Spot-check: the old screen's best movers, run to the standard

The old 2021 screen is the only evidence for most switches, so its best results are the natural place to look for a
missed edge. Its top mover by far was "arm the order-block order on touch" (`ob_arm='touch'`): +$50.6k in 2021 on 98
trades with 64% winners, against -$2.6k for the defaults. Nobody followed it up, because the engine was rebuilt a week
later. I ran it on the current engine to the standard (5m, week rule off as the base, like the PR #80 switch runs).

**It is a fill artefact, not an edge.** On the current engine ES 2021 again looks spectacular (161 trades, +$108.5k),
but 55 of those trades have their stop on the profit side of the entry (for example short at 3832.50 with the "stop"
at 3831.125). Each one "stops out" in its entry bar at a profit: 98% winners, +49 R of the +39 R total. With `touch`
the order is armed before price has left the order block, the limit ends up through the market, and the stop at the
order block's midpoint lands on the wrong side. The other arming modes move such an entry to just under the close;
`touch` does not (`_ob_pre` in `strategy.py`).

| 5m, ES + NQ + YM, 2019-26, week rule off | trades | wrong-side-stop trades | their R | rest: R a trade (t) | 2019-22 | 2023-26 | rest: total |
|---|---|---|---|---|---|---|---|
| base | 2,897 | 1 | -0.2 | -0.13 (-4.5) | -0.14 | -0.11 | -$306k |
| `ob_arm='touch'` | 3,765 | 1,168 | +861 | -0.11 (-1.9) | -0.14 | -0.07 | -$159k |

- Without the impossible trades, touch arming loses in both halves and on all three markets, like everything else.
- The published standard runs are clean: I scanned every saved trade file from PRs #76 and #80 (13 variants, about
  41,500 trade rows) and found one such trade (-0.2 R) per variant at most. No earlier result changes.
- `replay.py` confirms the check is sound: it re-fills the base trades from raw 1-minute bars and finds all 104 of
  104 ES 2021 base trades; the 55 cannot be replayed at all, because a stop on the profit side is not a trade.
- **Consequence for the old screen:** its ranking cannot be trusted as a list of leads. A switch that breaks the
  order logic shows up as the best "winner". Any future broad screen needs a guard that rejects orders whose stop is
  not on the loss side.

**The next seven movers of the old screen, same runs** (trades with a wrong-side stop removed; R a trade, t in
brackets; last column is the paired weekly difference to the base):

| switch | old screen 2021 | trades | total | R a trade (t) | 2019-22 | 2023-26 | vs base, weekly t |
|---|---|---|---|---|---|---|---|
| base (week rule off) | | 2,896 | -$306k | -0.13 (-4.5) | -0.14 | -0.11 | |
| arm on touch (`ob_arm='touch'`) | +$50.6k | 2,597 | -$159k | -0.11 (-1.9) | -0.14 | -0.07 | +0.6 |
| HTF resistance cap off (`htf_resist_cap=False`) | +$21.9k | 2,998 | -$278k | -0.11 (-3.2) | -0.14 | -0.09 | +0.5 |
| draw re-lock (`draw_relock`) | +$20.6k | 3,770 | -$480k | -0.15 (-5.8) | -0.15 | -0.15 | -2.9 |
| full market-maker plan (`mm_plan='full'`, `mmxm_ctx`) | +$16.4k | 3,049 | -$200k | -0.08 (-1.8) | -0.13 | -0.03 | +1.2 |
| volume-imbalance draw lock (`vi_arrays`, `vi_htf_draw`) | +$14.2k | 3,092 | -$312k | -0.12 (-4.0) | -0.13 | -0.10 | +0.1 |
| three drives required (`three_drives='require'`) | +$13.5k | 426 | -$44k | -0.14 (-1.7) | -0.13 | -0.15 | +3.9 |
| SMT needs an array (`smt_min=1`, `smt_need_array`) | +$12.0k | 347 | -$37k | -0.13 (-1.3) | -0.17 | -0.09 | +4.2 |
| PM lunch order flow (`pm_lunch_org`) | +$11.7k | 2,315 | -$186k | -0.09 (-3.0) | -0.10 | -0.09 | +3.4 |

- All eight of the old screen's best results lose in both halves, at about the same -0.08 to -0.15 R a trade as the
  base. None has a positive half. Only the touch switch produced wrong-side stops; the other seven are clean.
- The three that "beat the base" (three drives, SMT array, PM lunch order flow) do it by taking fewer of the same
  losing trades, the pattern seen with the week rule and the DXY switches.
- So one good year on ES in the old screen predicted nothing. That is the strongest evidence here that the 1,896
  switches seen only in that screen are not hiding an edge.
- Runs: engine e68ef84, 5m, 192 jobs, 0 failed, about 55 minutes in the cloud. The base is the saved PR #76 run
  (engine 2101d04); a rerun of ES 2021 on e68ef84 gave 104 trades against 103 saved (one extra AM trade).

## 4. Under-tested areas, and whether an edge is plausible there

| area | status | is an edge plausible? |
|---|---|---|
| The ~1,900 switches seen only in the old 2021 screen | Half (1,029 of 2,008 variants) changed nothing at all in 2021. Of the rest, the big trade-adders all lost and the best mover is the artefact above | Unlikely. They act on entries that are coin flips |
| The 404 newer switches never run (rule cards, caption-gap rules) | 72 single card switches were run on 2021 only: 43 identical to defaults, the rest noise | Unlikely, same reason |
| Settings of the bias rules (PR #83 scored each rule at its default setting only) | under-tested | Low. 60 tests of 30 rules found nothing; tuning the settings of rules with no signal mostly finds luck |
| Entry-type switches combined with each other | untested | Low. Each piece alone is a coin flip or worse (PR #85), and the narrow engine, which is the cleanest combination, is within luck |
| Overnight-gap scalp settings | 76 trades, +0.45 R, weak in 2023-26 (PR #79) | The only positive setup, but about 7 trades a year. More data, not more switches, would settle it |
| Narrow morning engine with a direction input (`nar_bias`) | shell built and tested, direction filter not | This is where the one real lead points: ICT's own morning calls are right about 80% of the time, and the shell is not clearly losing. But no coded rule supplies that direction (PRs #83, #93) |
| 1m runs of anything except the week rule and the six PR #80 switches | untested | Low. 1m and 5m agree wherever both were run (-0.13 R a trade on both) |
| Sessions the engine has no setup for (08:30 release, FOMC afternoon, pre-market, Asia) | not switches; 10 of ICT's 21 missed trades are here | Unknown, would be new building, not testing |

Nothing in the untested switch space is a better bet than the one lead already found: short-term direction on the
morning window. That is not a switch-testing problem.

## 5. Recommended remaining tests

1. **Stop testing switches as a search for an edge.** The entry stream is settled: no direction, coin-flip paths,
   on 5m and 1m, three markets, both halves. More switch runs will mostly produce lucky or broken "winners".
2. **Add the stop-side guard** (small engine fix plus one test): reject, or count and report, any order whose stop is
   not on the loss side, and make `report.py` print the count. Fix the `ob_arm='touch'` path. Cheap, and it protects
   every later run. Needs Mase's OK because it changes engine code.
3. ~~Finish this spot-check~~ Done: all eight lose in both halves (section 3).
4. **Only if Mase wants the switch space formally closed:** rerun the roughly 980 old-screen variants that changed
   something, plus the 404 never run, on the current engine with the guard, 5m, three markets, 2019-22 only, and check
   survivors on 2023-26. About 50 to 70 hours of cloud time on 4 cores. With about 1,400 variants, roughly 70 will
   pass 2019-22 by luck and 3 or 4 will pass both halves by luck, so anything it finds needs a third check (2016-18).
   I do not recommend it: expected finds are close to zero.
5. **If there is one more test worth building,** it is the narrow morning engine fed with a hand-made direction: use
   ICT's 114 dated calls (PRs #87-#92) as `nar_bias` on those days. That tests whether a correct morning call can be
   turned into money by this entry at all. If not, even a perfect bias model would not rescue the engine.
