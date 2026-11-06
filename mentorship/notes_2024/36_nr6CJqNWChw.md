# 2024 Mentorship Lecture 36 (nr6CJqNWChw): "How to identify high resistance liquidity conditions": price camping inside FVGs = high resistance; ORG under 75 handles invites it (under 40 = definitely); stop = 2x the FVG range on high resistance days, one tick past CE on low resistance days; TGIF 20%/30% of the weekly range as partial and target
Live Fri Sep 27 2024, ~09:28-12:00 ET, NQ (Dec), 15s + 1m, 15m, weekly. ~2h32m (Caleb present; live-streamer rants, 1099-B aside; skipped). Captions only.
Source tier: 2024 Mentorship. No live trade; the framed short (first presented FVG retest after the ORG upper portion was left open) delivered.

## Summary
Friday after an up week. Small premium ORG (well under 75 handles), so ICT expected a lackluster morning. The 1m first presented FVG formed at 09:34-09:35 (the 09:30 candle gap is noted but not used by Caleb's model). Price traded down through the FPFVG, then chopped: it marked time inside the FVG (the hallmark of a high resistance liquidity run), ran stops into the upper portion of the ORG (bodies stopped at the ORG upper quadrant, a small portion left open = signature the low target will be hit), then came back down and kissed the low of the FPFVG: that's the short. On high resistance days the stop must be at least two times the FVG's range beyond it (use a micro); on low resistance days one tick past CE. Targets: the ORG mid-gap (70%) and TGIF's 20% then 30% retracement of the weekly range, which price hit inside an FVG.

## Rules
- HIGH vs LOW RESISTANCE LIQUIDITY RUN (definition): if price spends a lot of time inside FVGs or revisits them several times before moving = high resistance; if not = low resistance; "that's all I ever use to determine it"; journal the classification every day ~2:09, ~2:16, ~2:30
  - ORG under 75 handles invites a lethargic morning; under 40 = definitely lackluster; the first 30 minutes tells you which condition you're in ~1:32-1:33 (adds to ORG-SIZE)
  - Preferred ORG: more than 40 handles; ICT likes closer to 75 ~8:00
- HIGH RESISTANCE STOP (adds to conflict 39 / stop placement): the stop has to factor the FVG's range: entry gap width added again beyond the gap (2x the range); likely means a micro; if you won't take that stop, don't trade today ~1:47-1:49
  - LOW RESISTANCE STOP: one tick past the CE of the gap ~1:49
- HIGH RESISTANCE MANAGEMENT: dial back leverage, slow down, after a stop-out think twice about re-entering (paper or tape read instead) ~51:00
  - Max leverage (not over-leverage) only on low resistance days; few trades on high resistance days ~1:50
  - If you realize mid-trade that it's high resistance, cut to one contract ~2:09
  - Take partials every time; when bearish, a partial each time price trades below a low ~1:50, ~1:56
  - Don't rush the stop into the range on high resistance days; on some trades just cover costs ~1:30
- ORG AS AN INEFFICIENCY: after the ORG's gap closure, treat the whole ORG like an FVG; bearish = turning points should stop in the lower half; bodies stop at the upper quadrant, wick leaves a small portion open = algorithmic signature the target gets hit; if fully closed and traded outside, less likely ~14:00, ~43:00-46:00
- SHORT ENTRY (Caleb model): after price leaves the ORG upper portion and trades back down, it kisses the low of the 1m FPFVG = short; stop above the FPFVG (2x range rule today) ~1:47
  - Don't short just because price is inside the FPFVG; wait for displacement below it with a body close away, then the first 15s FVG retrace as the catalyst ~26:00-27:00, ~1:40
- ORG BIAS (restated): 09:30 above yesterday's 16:14 settlement = bearish opening range bias; 70% mid-gap in 30 minutes = "built-in advantage, short from the opening bell" ~1:19, ~1:23-1:27
- TGIF: up week = Friday retraces 20-30% of the weekly range; 20% level = first partial, 30% = target; if not Friday, usually Monday ~11:00, ~1:27-1:28 (TGIF-DEPTH)
- Exhaustion gap at the open: gap filled, rally fails, folds lower; then use the low of the gap like an FVG for a short-term turtle soup ~10:00
- SEEK & DESTROY vs HIGH RESISTANCE: never two seek & destroy days in the same week; most "seek & destroy" labels are just high resistance ~2:15-2:16
- Reclaimed bullish FVG is not an inversion FVG (he mislabeled one; correction video to come) ~24:00
- Same gap logic worked on currency futures (GBP, DEM, JPY, CAD) ~1:25

## Risk / Process [beginner]
- On high resistance days demo with one micro and count how many entries it takes before one works; commissions can make a "right" day net negative ~59:00
- Say "I don't know what to do right now" ~1:03

## Trade examples
- 2024-09-27 AM (no live trade): small premium ORG; 1m FPFVG at 09:34/09:35; first drop through it, chop inside it (high resistance), stop run into the ORG upper portion (bodies at the upper quadrant), then kiss of the FPFVG low = short; stop 2x the FVG range; delivery to the ORG mid-gap and TGIF 20%/30% weekly levels.

## Definitions
- High resistance liquidity run: price marks time in FVGs, deep retracements, trailing stops get hit. Low resistance: fast runs to targets with immediate feedback.

## Open questions / conflict checks
- [conflict check] Stop = 2x FVG range on high resistance days vs one tick past CE on low resistance days: m2024 conflict 39 (stop placement) gets a condition-based answer.
- [conflict check] ORG under 75/40 handles: ORG-SIZE card.
- [conflict check] Partial every time a low is taken (high resistance) vs partials at fixed levels: PARTIAL-TRIGGER card.
- [conflict check] TGIF 20%/30%: TGIF-DEPTH card.
- [conflict check] Re-entry after stop-out on high resistance days: REENTRY card.
- [new] `hrlr_classifier` (time spent inside FVGs before moving); default off.
- [new] `hrlr_stop_2x_fvg` and `lrlr_stop_ce_plus1`; default off.
