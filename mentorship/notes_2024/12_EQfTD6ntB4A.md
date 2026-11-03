# 2024 Mentorship Lecture 12 (EQfTD6ntB4A): After-close review of Aug 19, lunch macro target rule, last-hour macros, size with daily bias
Recorded 2024-08-19 (Mon) after the close (~17:00 ET), NQ, 1m/15s + daily. ~52m. Captions only.
Source tier: 2024 Mentorship. Review of the morning's IOFED long (lecture 11); no new trade.

## Summary
ICT reviews Monday: the IOFED long was the low-risk buy; the NWOG acted as support (swept, then the OB opening price held). He defines the lunch macro target precisely (at 11:30, look back to the first low formed after 10:00), says to hold runners to at least 15:15 (start of the last-hour macros), and explains that the 15:45-16:00 "market on close" window is 15 minutes. Size should be heaviest in the direction of the daily bias.

## Rules
- SESSION BIAS: mark both buy-side and sell-side for the session; whichever is taken first, price usually then goes for the opposite ~4:00
- Entry = IOFED in the direction of the session/daily draw; a "low-risk buy" should not come back below the entry ~24:01, ~28:00
- OB with two consecutive down-close candles: use the opening price (change in state of delivery); wicks may "color outside the lines" of the NWOG ~28:00
- Don't strangle a position by trailing the stop up repeatedly ~28:00
- LUNCH MACRO (precise): at 11:30, look backward for the FIRST low (bullish morning) that formed AFTER 10:00 (e.g., 11:17); the lunch macro seeks the stops under it; it can last until 13:30; after 13:30 price is free to resume the morning direction ~28:00-34:00
  - The after-10:00 condition factors in the 10:00 run and gives the obvious trailed-stop level ~32:00
  - It may also not retrace at all (keeps going higher) ~32:00
- HOLDING: for longer trades, hold to at least 15:15 (start of the last hour's macros); four macros in the last hour ~34:00
  - 15:15-15:45 macro; 15:45-16:00 = market on close (15 min, not 10) ~42:00
  - If you haven't taken anything off by 15:00, pay yourself ~14:01
- Daily power of three: the day's high/low form, then price cycles timeframes down to seconds and back up, incorporating all inefficiencies and liquidity ~38:02
- Jackson Hole (Wed-Fri): treat like an NFP week; trade Monday (setups early in the week), expect the HTF targets from Aug 13 ~26:01
- SIZE WITH THE DAILY BIAS: heaviest positions on the side of daily order flow while HTF targets remain; counter-trend or after most of the daily move is done: 1-4 contracts instead of 10-20 ~46:02-48:00
- HTF targets from Aug 13 (daily SIBI/VI, mean threshold of an up-close candle, rejection block, buy-side) were reached ~40:00, ~44:02

## Risk / Process [beginner]
- Use the setup over weeks/months of drills before expecting to hold trades ~24:01
- ICT streams with ~3s latency; don't copy stops he says aloud ~24:01

## Trade examples
- 2024-08-19 review: IOFED long → through NWOG high → lunch macro took the 11:17 low (also NWOG) → rally after 13:30 → last-hour run.

## Open questions / conflict checks
- [new] `lunch_macro_first_low_after_1000` (precise target rule for the lunch retrace); default off.
- [new] `hold_runner_to_1515`; default off. Conflicts with rulebook exits? Check rulebook session close/flat rules.
- [new] `size_by_daily_bias` (full size with daily bias, reduced counter-trend); default off; check against owner risk #12 (1.2%/1.3%).
- [conflict check] Jackson Hole / NFP-week framing: trade Monday vs rulebook "Mondays traded" (consistent) and lecture 06 "skip Mondays except NFP week".
