# 2024 Mentorship Lecture 37 (l7eu9yvUUtg): "Premarket concepts": weekly prep from a blank slate, Fed chair speech = manual intervention (no trading during and 15 min after; a 09:00-10:00 speech = trade before 08:00), wait 15 min after 09:45 news, Powell-afternoon day = setup must come 09:30-10:30, decoupled indices, bearish inversion FVG vs reclaimed bullish FVG
Live Mon Sep 30 2024, ~08:00-10:35 ET, NQ (Dec), ES, YM, 1m, 5m, 15m, daily, weekly. ~2h35m (Turtle soup / Larry Williams history, fear of shorting, level 2 rant; skipped). Captions only.
Source tier: 2024 Mentorship. No live trade; framed short (FPFVG used as a bearish inversion at its CE with the NWOG overlap, target relative equal lows) gave the first target, the second failed.

## Summary
Monday of NFP week; Chicago PMI (medium) at 09:45; Fed chair Powell speaking in the afternoon. ICT does his Sunday-style weekly prep live without having looked at levels: weekly imbalance traded to, daily OB change-in-state-of-delivery retraced, so he wants the heaviest-leverage "one shot one kill" short of the week down into a weekly BISI and daily relative equal lows. Day rules: wait until 10:00 because of the 09:45 news (minimum 15 minutes after any high/medium release); with Powell in the afternoon, the setup must form in the first hour (09:30-10:30) or no trade, and don't trade the PM (manual intervention). The market decoupled (NQ, ES, YM doing different things), which reduces confidence and targets. The FPFVG (09:31, an up-close gap) was used as a bearish inversion: price returned to its CE to the tick and sold off to relative equal lows; then it came back to the FPFVG, so the second target failed.

## Rules
- FED CHAIR SPEECH / FOMC = manual intervention: don't trade while he talks and for 15 minutes after; resume only when PD arrays book "to the tick" again (algorithmic delivery back) ~1:12, ~1:16, ~2:10 (NEWS-WAIT, FOMC-DAY)
  - Speech any time in the 09:00-10:00 hour: trade premarket, before 08:00 (premarket = before 09:00; starts 07:00) ~5:00-8:00 [new]
  - Speech in the afternoon: find the setup in the first hour (09:30-10:30); if none, no trade; don't trade the PM session ~1:13, ~1:27-1:30
  - Lead-up to a Fed speech is fickle; on Powell/FOMC days ICT prefers trading early (cleaner, pros take something early) ~4:00-5:00
- NEWS WAIT: a 09:45 medium-impact release = wait until 10:00; minimum 15 minutes after any high or medium impact news ~6:00-7:00
- MONDAY (adds to MONDAY card): ICT always trades the Monday of NFP week; new students sit still on other Mondays (they set the weekly range parameters) ~1:12-1:13
- LUNCH: 11:30-13:30 (two hours) ~1:13 (LUNCH-WINDOW)
- WEEKLY PREP: blank slate on Sunday: NWOG, weekly/daily PD arrays; pick the week's heaviest-leverage "one shot one kill" idea; other trades that week are scalps ~8:00-12:00, ~1:02-1:03
  - Premium/discount: every profitable short was entered in a premium, every long in a discount ~20:00
  - Every price run will have an FVG (not always a breaker, OB or propulsion block); being late is fine if the FVG is in a premium relative to the range to the target ~1:03
- STOP (adds to conflict 39): above candle 2 if it can be afforded; if ranges are small, above candle 3's body, or one tick past candle 3's wick CE; err toward the smallest logical risk ~46:00
- 15m is enough for a day trader (old 1h/4h lows visible); SMT on a 15m bellwether ~37:00, ~40:00
- DECOUPLING: NQ, ES and YM doing different things (common around Fed speeches/FOMC) = don't use high risk; targets may not be reached; want all three indices to agree when in a trade; Dow can be the "canary" ~1:32-1:37, ~2:10-2:13
- RE-ENTRY INTO A PREMIUM ARRAY must be on a new candle; never the same candle that left the PD array and came back ~2:06
- INVERSION NAMING: an up-close FVG (BISI) used bearishly = bearish inversion FVG; if price later trades back above and returns into it, it's a reclaimed bullish FVG, not an inversion ~2:17-2:20
  - Inversion entry at the CE of the FPFVG when bearish; lower half for entries; upper half stays untouched ~2:18, ~2:21
- DECOUPLED TARGETS: take the large portion off at the first target (relative equal lows); runner likely stopped ~2:27-2:28
- Market condition rules: high resistance = tradable with a wider stop held near entry; seek & destroy = don't trade; decoupled = tradable but expect missed targets ~2:32

## Risk / Process [beginner]
- Volatility pinball drill introduced (buy and sell in the same session to desensitize; detailed in L38) ~37:00
- ICT writes each hour's high and low in a notepad (30-year habit; not required) ~52:00

## Trade examples
- 2024-09-30 AM (framed, no live trade): premium ORG; 09:31 FPFVG (up-close gap) as a bearish inversion; return to its CE "to the tick", overlap with the NWOG; short to relative equal lows (first partial / majority off); second target failed as price returned to the FPFVG; ES and YM decoupled from NQ.

## Definitions
- Decoupling: the three index futures move independently (symmetry broken).
- Reclaimed bullish FVG: a bullish FVG traded through and then back above, used again as support.

## Open questions / conflict checks
- [conflict check] Fed speech in 09:00-10:00 = trade before 08:00: PREMARKET-ENTRY card.
- [conflict check] Powell afternoon = setup only 09:30-10:30, no PM: NEWS-WAIT and FOMC-DAY cards.
- [conflict check] Trade Monday of NFP week: MONDAY card.
- [conflict check] Lunch 11:30-13:30: LUNCH-WINDOW card.
- [conflict check] Decoupled indices = low risk / first-target exit: SMT-USE card.
- [new] `fed_speech_window_block`; `decoupled_index_filter`; `reentry_new_candle_only`; default off.
