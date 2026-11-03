# 2024 Mentorship Lecture 06 (woAQ1XJeD7Y): Monday before CPI/PPI, live short from a bearish OB, deferred TGIF
Live 2024-08-12 (Mon), ~09:15-10:30 ET, NQ, 1m. ~2h39m (first minutes silent). Captions only.
Source tier: 2024 Mentorship. Live trade (stopped out in profit, trailed stop).

## Summary
Monday with no AM news and PPI (Tue) + CPI (Wed) ahead = skittish, seek-and-destroy-like; take one early chance, pay yourself partials, don't re-enter after being stopped. Bias: at 07:00 price was ABOVE this week's NWOG and Friday's NDOG cluster, and Friday had NOT delivered its TGIF retracement → expect the 20-30% retracement Monday. Waited for post-07:00 relative equal highs to be pierced, sold the bearish OB open, added at a SIBI low, partial taken, stopped on trailed stop, price then fell to the NDOG CE.

## Rules
- CPI/PPI/NFP/FOMC days are "extremely manipulated"; ICT does not try to trade the release direction; waits until after it; streams start 09:15 on those days ~7:00, ~13:30, ~2:14:00
- NO-NEWS MONDAY BEFORE BIG NEWS (CPI/PPI Tue/Wed): big players won't position; expect up-down skittish "seek and destroy"-like delivery; pick shots carefully, take partials, move quickly to protect, no home runs; give yourself ONE chance early; if stopped, don't re-enter ~11:30-19:00, ~26:00, ~39:30
  - With big news the next day, take trades EARLY (07:00-09:30 window) rather than at 09:30/10:00 ~48:00
- Mondays in general: ICT usually not interested, EXCEPT Mondays of NFP week (trades every one of those) ~24:00
- SEEK AND DESTROY: price goes just above a short-term high, then below an old short-term low, then back above the new high, back and forth, running both sides ~26:30
- PARTIALS ALWAYS PAY: once the first partial is taken and stop covers costs, the outcome no longer matters ~18:30, ~44:30
- 07:00 start detail: if a high forms right on the 07:00 candle with highs to its left, wait for the initial run above them; only label initial buy-side/sell-side after a short-term high is made and then a low is taken ~9:00-10:30
  - Post-08:00 start: use relative equal highs formed after 07:00 that are unbreached; if already taken, wait for new ones after 08:00 ~36:00
- Layered sell-side liquidity: several close lows (London 05:00 low etc.) marked as one pool ~10:30, ~22:00
- Orange-shaded FVG = watching for inversion (trade below, return, hold as barrier) ~21:00
- BIAS (sell program): at 07:00 price above this week's NWOG AND a cluster of NDOGs below → algorithm seeks fair value in a discount; wait for relative equal highs to form, then be pierced; then every premium array is a short ~47:30-1:40:00, ~2:16:00
  - Don't take a strong rally as "I'm wrong"; wait for it to fizzle above post-07:00 old highs ~1:39:00
- TGIF DEFERRED: if Friday did NOT retrace 20-30% of a one-sided week's range, expect that retracement on Monday (even with CPI/PPI later in the week) ~1:06:30-1:09:00
- Session bias ≠ daily close bias; first determine the session run ~1:09:30
- BEARISH ORDER BLOCK: an up-close candle; validated when a later candle CLOSES below its OPEN (change in state of delivery). "My order block does not require the trade below the wick" ~1:11:00, ~1:39:00-1:42:00
  - Entry: at the OB open, or between open and low, on an uptick (next candle opened below the OB open, then traded up into it) ~1:11:00, ~1:40:30
  - Stop: at the MEAN THRESHOLD (midpoint) of the OB candle / rejection block (its close) ~1:12:00, ~1:40:30
- Mean threshold = midpoint of an OB candle; CE = midpoint of a gap ~1:20:30
- FVG with a volume imbalance: measure from the BODY close (not the wick) → "true" CE ~1:12:30
- ENTRY THRESHOLD (shorts): use the "lowest threshold" level — the LOW of the SIBI — so the order fills, rather than demanding CE ~51:00, ~1:42:00
- Adding: a new FVG → add; do NOT move the stop aggressively because you added; wait for price to roll out after proving the idea ~1:42:30
- Signature: bodies respect only the LOWER half of a SIBI (upper half left open) → measurable displacement coming ~1:14:00, ~1:17:00
  - Dislikes trades where the FVG is fully closed before continuing ~1:15:00
  - If price trades to the top of the FVG: need immediate rejection; then use a lower-TF FVG to enter (price delivery continuum) ~1:18:30
- Stop placement logic: price may poke just outside the FVG but returns to the OB that started the run ~1:22:00
- Never move a stop back once reduced; accept being stopped in profit; no re-entry today (big news next) ~2:02:00
- Done after the draw (CE of Friday's NDOG) is reached; not interested in more ~32:30, ~1:23:00
- SMT/other: none this lecture
- Use live-stream chat sentiment as contrarian gauge ~1:28:00

## Risk and process ([beginner] / "for Caleb")
- Demo minimum 6 months before real money ~58:30
- Never > 1% risk per trade; not every session; max one trade a day; if you take a loss you're done for the day ~2:34:00-2:36:30
- Mistake fill (accidental click): beginner should close it and manage as if ~1:16:00

## Trade examples
- 2024-08-12 NQ: short at bearish OB open after post-07:00 relative equal highs (and London highs) pierced; add at SIBI low; partial taken; stop trailed and hit in profit; price then dropped to Friday NDOG CE / NWOG levels. Also one accidental fill (ignored).

## Definitions
- Seek and destroy; layered sell-side; mean threshold vs CE; TGIF deferred

## Open questions / conflict checks
- [conflict] 1% max risk, one trade/day, stop after a loss ("for Caleb") vs owner directive #12 risk 1.2%/1.3% and experienced default "reversing after a loss allowed" → 2023/owner stays; beginner switch only
- [conflict check] Mondays generally avoided except NFP-week Mondays vs experienced default "Mondays traded"
- [conflict check] OB entry at open on uptick, stop at mean threshold vs rulebook OB entry (#11 OB entry before the break; Ep 07 OB-body entry)
- Switches: `pre_news_day_one_chance` (Mon before CPI/PPI), `early_entries_if_big_news_tomorrow`, `tgif_deferred_monday`, `ob_stop_mean_threshold`, `short_entry_at_sibi_low`, `skip_monday_unless_nfp_week`
